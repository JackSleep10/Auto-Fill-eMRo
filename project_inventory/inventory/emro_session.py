"""eMRO browser session: login (password + TOTP 2FA), domain failover, popup handling.

Adapted from D:\\Project dashboard\\scraper\\gse_wo_creator.py (ensure_logged_in / dismiss_any_popups).
"""
import asyncio
import logging
from typing import Optional

import pyotp
from playwright.async_api import async_playwright, BrowserContext, Page

from inventory.config import Config

logger = logging.getLogger("EmroSession")

ERROR_SEL = ".ui-messages-error, .ui-growl-message, .ui-message-error, .ui-messages-error-detail"


class EmroSession:
    def __init__(self, user: Optional[str] = None, headless: Optional[bool] = None):
        self.user = (user or Config.INVENTORY_USER).strip().upper()
        self.headless = Config.HEADLESS if headless is None else headless
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.logged_in = False

    def is_alive(self) -> bool:
        try:
            return bool(self.context and self.page and not self.page.is_closed())
        except Exception:
            return False

    async def start(self):
        session_dir = Config.SESSION_DIR / self.user
        session_dir.mkdir(parents=True, exist_ok=True)
        Config.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        Config.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(session_dir),
            headless=self.headless,
            accept_downloads=True,
            downloads_path=str(Config.DOWNLOAD_DIR),
            viewport={"width": 1440, "height": 900},
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        self.page.set_default_timeout(30000)

    async def close(self):
        try:
            if self.context:
                await self.context.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.warning(f"close: {e}")
        self.context = self.page = self.playwright = None
        self.logged_in = False

    async def screenshot(self, name: str):
        try:
            path = Config.SCREENSHOTS_DIR / f"{name}.png"
            await self.page.screenshot(path=str(path), full_page=False)
            return path
        except Exception:
            return None

    async def _fav_visible(self) -> bool:
        try:
            return await self.page.locator(':text("Favorites")').first.is_visible()
        except Exception:
            return False

    async def _raise_if_error(self, stage: str):
        err = self.page.locator(ERROR_SEL).first
        if await err.is_visible():
            txt = (await err.inner_text()).strip()
            if txt:
                raise RuntimeError(f"eMRO {stage} rejected for {self.user}: {txt}")

    async def ensure_logged_in(self) -> bool:
        if not self.is_alive():
            await self.start()

        cred = Config.credentials(self.user)
        if not cred["totp_secret"]:
            raise ValueError(f"บัญชี {self.user} ไม่มี TOTP secret ใน .env")

        # Fast path: already on dashboard
        if self.logged_in and await self._fav_visible():
            return True

        urls = [Config.EMRO_URL]
        if Config.EMRO_FALLBACK_URL and Config.EMRO_FALLBACK_URL not in urls:
            urls.append(Config.EMRO_FALLBACK_URL)

        opened, last_error = False, ""
        for url in urls:
            try:
                resp = await self.page.goto(url, wait_until="load", timeout=30000)
                await asyncio.sleep(2)
                status = resp.status if resp else 200
                body = ""
                try:
                    body = await self.page.inner_text("body", timeout=1500)
                except Exception:
                    pass
                if status >= 500 or "Bad gateway" in body or "Host Error" in body:
                    last_error = f"HTTP {status}"
                    logger.warning(f"{url} server error {status}, trying fallback")
                    continue
                opened = True
                break
            except Exception as e:
                last_error = str(e)
                logger.warning(f"goto {url} failed: {e}")
        if not opened:
            raise RuntimeError(f"เซิร์ฟเวอร์ eMRO ขัดข้อง ({last_error})")

        mfa_dlg = self.page.locator("#mainForm\\:MFADlg")
        submit_btn = self.page.locator('#mainForm\\:j_idt169, button:has-text("Submit")').first

        if not await submit_btn.is_visible() and not await mfa_dlg.is_visible() and await self._fav_visible():
            self.logged_in = True
            return True

        if await submit_btn.is_visible():
            logger.info(f"Logging in as {self.user}...")
            user_input = self.page.locator("input[name*='user' i], input[id*='user' i], input[type='text']:visible").first
            if await user_input.is_visible():
                await user_input.fill(self.user)
            pass_input = self.page.locator('input[type="password"]').first
            if await pass_input.is_visible() and cred["password"]:
                await pass_input.fill(cred["password"])
            await submit_btn.click()
            for _ in range(30):
                await asyncio.sleep(0.5)
                await self._raise_if_error("login")
                if await mfa_dlg.is_visible() or await self._fav_visible():
                    break

        if await mfa_dlg.is_visible():
            code = pyotp.TOTP(cred["totp_secret"]).now()
            c1 = self.page.locator("#mainForm\\:code1_input")
            await c1.wait_for(state="visible", timeout=10000)
            await c1.click()
            for d in code:
                await self.page.keyboard.press(d)
                await asyncio.sleep(0.12)
            for i in range(1, 7):
                await self.page.evaluate(
                    f'() => {{ const h = document.getElementById("mainForm:code{i}_hinput"); if (h) h.value = "{code[i-1]}"; }}'
                )
            await self.page.locator('#mainForm\\:j_idt163, button:has-text("Verify"), button:has-text("Submit")').first.click()
            for _ in range(40):
                await asyncio.sleep(0.5)
                await self._raise_if_error("2FA")
                if await self._fav_visible():
                    break

        for _ in range(12):
            if await self._fav_visible():
                break
            await asyncio.sleep(0.5)
        if not await self._fav_visible():
            await self.dismiss_popups()
        if not await self._fav_visible():
            await self.screenshot(f"login_failure_{self.user}")
            raise RuntimeError(f"เข้าสู่ระบบ eMRO ในชื่อ {self.user} ไม่สำเร็จ (ไม่พบหน้า Dashboard)")

        await self.dismiss_popups()
        self.logged_in = True
        logger.info(f"Logged in to eMRO as {self.user}")
        return True

    async def dismiss_popups(self) -> bool:
        """1) click X  2) tick NO + Submit  3) OK/Yes/Close  4) clear overlay."""
        dismissed = False
        try:
            dialogs = self.page.locator("div.ui-dialog:visible, div[role='dialog']:visible")
            for i in range(await dialogs.count()):
                dlg = dialogs.nth(i)
                if not await dlg.is_visible():
                    continue
                close_x = dlg.locator(".ui-dialog-titlebar-close, .ui-icon-closethick, [aria-label*='Close' i]").first
                if await close_x.is_visible():
                    await close_x.click()
                    await asyncio.sleep(0.8)
                    dismissed = True
                    continue
                no_opt = dlg.locator("div.ui-radiobutton:has-text('NO'), label:text-is('NO'), label:text-is('No')").first
                if await no_opt.is_visible():
                    await no_opt.click()
                    await asyncio.sleep(0.3)
                btn = dlg.locator("button:has-text('Submit'), button:has-text('OK'), button:has-text('Yes'), button:has-text('Close')").first
                if await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(0.8)
                    dismissed = True
                else:
                    await self.page.keyboard.press("Escape")
                    dismissed = True
            if await self.page.locator("div.ui-widget-overlay:visible").first.is_visible():
                await self.page.keyboard.press("Escape")
                await self.page.evaluate("() => document.querySelectorAll('.ui-widget-overlay').forEach(e => e.remove())")
        except Exception as e:
            logger.warning(f"dismiss_popups: {e}")
        return dismissed
