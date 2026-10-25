import asyncio
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Callable
import pyotp
import requests
from playwright.async_api import async_playwright, BrowserContext, Page

from scraper.config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GSEWorkOrderCreator")

class GSEWorkOrderCreator:
    def __init__(self, user: str = "TL248005", headless: bool = False, slow_mo: int = 50):
        self.user = (user or "TL248005").strip().upper()
        self.headless = headless
        self.slow_mo = slow_mo
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.current_user: Optional[str] = None

    def is_alive(self) -> bool:
        """Checks if browser context and page are active and responsive."""
        try:
            return bool(self.context and self.page and not self.page.is_closed())
        except Exception:
            return False

    async def start(self):
        """Initializes the Playwright persistent browser session for this specific user."""
        user_session_dir = Config.SESSION_DIR / self.user
        user_session_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[GSE Creator] Launching browser session for {self.user} (headless={self.headless}, slow_mo={self.slow_mo}ms, dir={user_session_dir})...")
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_session_dir),
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=["--start-maximized"] if not self.headless else [],
            no_viewport=True if not self.headless else False,
            viewport=None if not self.headless else {"width": 1440, "height": 900}
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        if not self.headless:
            try:
                await self.page.bring_to_front()
            except Exception:
                pass

    async def capture_live_screen(self, label: str = ""):
        """Captures current screen and saves to live_screen.jpg for UI streaming."""
        try:
            if self.page:
                path = Path("data/screenshots/live_screen.jpg")
                path.parent.mkdir(parents=True, exist_ok=True)
                await self.page.screenshot(path=str(path), type="jpeg", quality=75)
        except Exception:
            pass

    async def close(self):
        """Closes browser session."""
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("[GSE Creator] Browser closed.")

    async def ensure_logged_in(self, user: Optional[str] = None) -> bool:
        """Navigates to eMRO and handles login and 2FA if required."""
        user_upper = (user or self.user or Config.EMRO_USERNAME or "").strip().upper()
        if not user_upper:
            raise ValueError("No user specified for eMRO login.")
        if not Config.has_emro_account(user_upper):
            raise ValueError(f"บัญชี '{user_upper}' ยังไม่ได้เชื่อมต่อกับระบบ eMRO (ไม่มีรหัสผ่าน/2FA) กรุณาติดต่อผู้ดูแลระบบเพื่อลงทะเบียนก่อนเปิดใบงาน")

        cred = Config.EMRO_USERS[user_upper]

        # Fast-path check: if already logged in as THIS EXACT USER on eMRO, skip reload!
        if self.current_user == user_upper and self.page and not self.page.is_closed():
            try:
                curr_url = self.page.url
                if "emro.lionair.com" in curr_url and ("Home.trax" in curr_url or "Dashboard" in curr_url):
                    submit_btn = self.page.locator('#mainForm\\:j_idt169, button:has-text("Submit")').first
                    if not await submit_btn.is_visible():
                        logger.info(f"[GSE Creator] Session already active and logged in as {user_upper}.")
                        return True
            except Exception:
                pass

        # If switching user from another logged-in user, clear cookies/session
        if self.current_user and self.current_user != user_upper and self.context:
            logger.info(f"[GSE Creator] Switching eMRO user from {self.current_user} to {user_upper}. Resetting session...")
            try:
                await self.context.clear_cookies()
            except Exception:
                pass
            self.current_user = None

        logger.info(f"[GSE Creator] Navigating to {Config.EMRO_URL} (Target User: {user_upper})...")
        goto_resp = await self.page.goto(Config.EMRO_URL, wait_until="load", timeout=30000)
        await asyncio.sleep(2)

        # 1. Detect if eMRO server is down or returning HTTP 502/503/504 Bad Gateway
        page_title = (await self.page.title()) or ""
        status_code = goto_resp.status if goto_resp else 200

        # Check by HTTP status code or Cloudflare error page content
        is_server_error = status_code >= 500
        if not is_server_error:
            try:
                body_text = (await self.page.inner_text("body", timeout=1500)) or ""
                if "Bad gateway" in body_text or "Error code 502" in body_text or "Host Error" in body_text or "502 Bad Gateway" in page_title:
                    is_server_error = True
            except Exception:
                pass

        if is_server_error:
            shot_file = Config.SCREENSHOTS_DIR / f"login_failure_{user_upper}.png"
            try:
                await self.page.screenshot(path=str(shot_file))
            except Exception:
                pass
            raise RuntimeError(
                f"เซิร์ฟเวอร์ระบบ eMRO ของ Thai Lion Air (emro.lionair.com) ขัดข้องชั่วคราว "
                f"(HTTP {status_code} Bad Gateway / Host Error) ไม่สามารถเปิดหน้าเว็บ eMRO ได้ในขณะนี้ "
                f"กรุณารอสักครู่ให้ทางระบบ eMRO กลับมาทำงาน แล้วลองใหม่อีกครั้ง"
            )

        fav_locator = self.page.locator(':text("Favorites")').first
        mfa_dlg = self.page.locator('#mainForm\\:MFADlg')
        submit_btn = self.page.locator('#mainForm\\:j_idt169, button:has-text("Submit")').first

        # Check if already logged in after navigation
        if not await submit_btn.is_visible() and not await mfa_dlg.is_visible():
            if await fav_locator.is_visible():
                logger.info(f"[GSE Creator] Already logged in and on dashboard as {user_upper}.")
                self.current_user = user_upper
                return True

        # Check for login submit button
        if await submit_btn.is_visible():
            logger.info(f"[GSE Creator] Login page detected. Authenticating as {user_upper}...")
            user_input = self.page.locator("input[name*='user' i], input[id*='user' i], input[type='text']:visible").first
            if await user_input.is_visible():
                await user_input.fill("")
                await user_input.fill(user_upper)
                logger.info(f"[GSE Creator] Filled username: {user_upper}")

            pass_input = self.page.locator('input[type="password"]').first
            if await pass_input.is_visible():
                p_val = cred.get("password") or Config.EMRO_PASSWORD
                if p_val:
                    await pass_input.fill("")
                    await pass_input.fill(p_val)
                    logger.info("[GSE Creator] Filled password from configuration.")
                else:
                    for _ in range(10):
                        cur_p = await pass_input.input_value()
                        if cur_p:
                            break
                        await asyncio.sleep(0.5)

            await submit_btn.click()
            logger.info("[GSE Creator] Clicked Submit. Waiting for 2FA dialog or dashboard...")

            # Wait up to 15 seconds dynamically for 2FA dialog, dashboard, or error
            for _ in range(30):
                await asyncio.sleep(0.5)
                # Check error message
                err_loc = self.page.locator('.ui-messages-error, .ui-growl-message, .ui-message-error, .ui-messages-error-detail').first
                if await err_loc.is_visible():
                    err_txt = await err_loc.inner_text()
                    if err_txt and err_txt.strip():
                        raise RuntimeError(f"eMRO login rejected for {user_upper}: {err_txt.strip()}")

                if await mfa_dlg.is_visible():
                    logger.info(f"[GSE Creator] 2FA dialog detected for {user_upper}.")
                    break

                if await fav_locator.is_visible():
                    logger.info(f"[GSE Creator] Dashboard visible directly for {user_upper}.")
                    break

        # Check for 2FA dialog
        if await mfa_dlg.is_visible():
            secret = cred.get("totp_secret") or Config.EMRO_TOTP_SECRET
            if not secret:
                raise ValueError(f"User {user_upper} has no TOTP 2FA secret configured.")
            logger.info(f"[GSE Creator] 2FA required for user {user_upper}. Generating TOTP code...")
            totp = pyotp.TOTP(secret)
            code = totp.now()
            logger.info(f"[GSE Creator] Generated TOTP code: {code}")
            c1 = self.page.locator('#mainForm\\:code1_input')
            await c1.wait_for(state="visible", timeout=10000)
            await c1.click()
            for digit in code:
                await self.page.keyboard.press(digit)
                await asyncio.sleep(0.12)
            for i in range(1, 7):
                await self.page.evaluate(
                    f'() => {{ const h = document.getElementById("mainForm:code{i}_hinput"); if (h) h.value = "{code[i-1]}"; }}'
                )
            verify_btn = self.page.locator('#mainForm\\:j_idt163, button:has-text("Verify"), button:has-text("Submit")').first
            await verify_btn.click()
            logger.info("[GSE Creator] Submitted 2FA TOTP code. Waiting for dashboard to load...")

            # Wait dynamically up to 20s for dashboard / Favorites
            for _ in range(40):
                await asyncio.sleep(0.5)
                err_loc = self.page.locator('.ui-messages-error, .ui-growl-message, .ui-message-error, .ui-messages-error-detail').first
                if await err_loc.is_visible():
                    err_txt = await err_loc.inner_text()
                    if err_txt and err_txt.strip():
                        raise RuntimeError(f"eMRO 2FA verification rejected for {user_upper}: {err_txt.strip()}")
                if await fav_locator.is_visible():
                    break

        # Confirm user is actually logged in and on the dashboard
        is_logged_in = False
        for _ in range(12):
            if await fav_locator.is_visible():
                is_logged_in = True
                break
            await asyncio.sleep(0.5)

        if not is_logged_in:
            await self.dismiss_any_popups()
            if await fav_locator.is_visible():
                is_logged_in = True

        if not is_logged_in:
            shot_file = Config.SCREENSHOTS_DIR / f"login_failure_{user_upper}.png"
            try:
                await self.page.screenshot(path=str(shot_file))
            except Exception:
                pass

            err_detail = ""
            try:
                err_loc = self.page.locator('.ui-messages-error, .ui-growl-message, .ui-message-error, .ui-messages-error-detail').first
                if await err_loc.is_visible():
                    err_detail = (await err_loc.inner_text()).strip()
            except Exception:
                pass

            if err_detail:
                raise RuntimeError(f"เข้าสู่ระบบ eMRO ในชื่อ {user_upper} ไม่สำเร็จ: {err_detail}")
            raise RuntimeError(f"เข้าสู่ระบบ eMRO ในชื่อ {user_upper} ไม่สำเร็จ: ไม่พบหน้า Dashboard (Favorites) หลังเข้าสู่ระบบ กรุณาตรวจสอบสถานะระบบ eMRO")

        logger.info(f"[GSE Creator] Successfully logged in and verified to eMRO as {user_upper}.")
        self.current_user = user_upper
        return True

    async def dismiss_any_popups(self) -> bool:
        """
        Checks for and dismisses any eMRO dialogs, confirmation alerts, or blocking modals.
        Handling hierarchy per user instruction:
        1. If close 'X' (ปุ่มกากบาท) exists on popup, click it first!
        2. If no 'X' and popup has checkbox/radio options, tick 'NO' then click 'Submit'!
        3. Fallback to OK, Yes, Close, Confirm, etc.
        4. If modal overlay blocks pointer events, click any visible close or remove overlay.
        """
        dismissed = False
        try:
            # 1. Check for visible dialogs / modal windows
            dialogs = self.page.locator("div.ui-dialog:visible, div[role='dialog']:visible, div[role='alertdialog']:visible")
            count = await dialogs.count()
            if count > 0:
                for i in range(count):
                    dlg = dialogs.nth(i)
                    if not await dlg.is_visible():
                        continue
                    dlg_text = ""
                    try:
                        dlg_text = (await dlg.inner_text()).strip().replace("\n", " ")
                    except Exception:
                        pass
                    logger.warning(f"[GSE Creator] Detected popup dialog: '{dlg_text[:120]}'")

                    # Rule 1: First check for Close 'X' button (ปุ่มกากบาท)
                    close_x = dlg.locator(
                        "a.ui-dialog-titlebar-close, .ui-dialog-titlebar-close, .ui-icon-closethick, "
                        "[class*='titlebar-close'], [class*='dialog-close'], [aria-label*='Close' i], "
                        "button.ui-dialog-titlebar-close, .ui-dialog-titlebar-icon, span.ui-icon-close"
                    ).first
                    if await close_x.is_visible():
                        logger.info("[GSE Creator] Found close 'X' button on popup. Clicking to dismiss...")
                        await close_x.click()
                        await asyncio.sleep(1)
                        dismissed = True
                        continue

                    # Rule 2: If no 'X', check if there is a checkbox/radio option -> select 'NO' and click 'Submit'
                    no_opts = dlg.locator(
                        "div.ui-radiobutton:has-text('NO'), div.ui-radiobutton:has-text('No'), "
                        "div.ui-selectbooleancheckbox:has-text('NO'), div.ui-selectbooleancheckbox:has-text('No'), "
                        "label:text-is('NO'), label:text-is('No'), label:has-text('NO'), label:has-text('No'), "
                        "td:has-text('NO') input, td:has-text('No') input, "
                        "input[type='radio'][value*='N' i], input[type='checkbox'][value*='N' i], "
                        ":text-matches('^\\s*NO\\s*$', 'i'), :text-matches('\\bNO\\b', 'i')"
                    )
                    if await no_opts.count() > 0:
                        no_opt = no_opts.first
                        if await no_opt.is_visible():
                            logger.info("[GSE Creator] Found 'NO' checkbox/radio option. Ticking 'NO'...")
                            await no_opt.click()
                            await asyncio.sleep(0.5)

                    submit_btn = dlg.locator(
                        "button:has-text('Submit'), a:has-text('Submit'), "
                        "button:has-text('SUBMIT'), a:has-text('SUBMIT'), "
                        "input[type='submit'][value*='Submit' i], "
                        "button:has-text('Confirm'), a:has-text('Confirm')"
                    ).first
                    if await submit_btn.is_visible():
                        logger.info(f"[GSE Creator] Clicking 'Submit' button on popup: {submit_btn}")
                        await submit_btn.click()
                        await asyncio.sleep(1)
                        dismissed = True
                        continue

                    # Rule 3: Fallback action buttons (OK, Yes, Close, ตกลง, ปิด)
                    btn = dlg.locator("button:has-text('OK'), button:has-text('Yes'), button:has-text('Close'), button:has-text('ตกลง'), button:has-text('ปิด'), a:has-text('Close')").first
                    if await btn.is_visible():
                        logger.info(f"[GSE Creator] Dismissing dialog via button click: {btn}")
                        await btn.click()
                        await asyncio.sleep(1)
                        dismissed = True
                    else:
                        await self.page.keyboard.press("Escape")
                        await asyncio.sleep(0.5)
                        dismissed = True

            # 2. Check if a blocking overlay exists
            overlay = self.page.locator("div.ui-widget-overlay:visible").first
            if await overlay.is_visible():
                logger.warning("[GSE Creator] Modal overlay still visible. Attempting to click any visible close button or clearing overlay...")
                any_close = self.page.locator(
                    "a.ui-dialog-titlebar-close:visible, .ui-dialog-titlebar-close:visible, .ui-icon-closethick:visible, "
                    "button.ui-dialog-titlebar-close:visible"
                ).first
                if await any_close.is_visible():
                    await any_close.click()
                    await asyncio.sleep(1)
                else:
                    await self.page.keyboard.press("Escape")
                    await asyncio.sleep(0.5)

                # Clear overlay element via JS if still lingering so it doesn't freeze pointer events
                try:
                    await self.page.evaluate("() => { document.querySelectorAll('.ui-widget-overlay').forEach(el => el.remove()); }")
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"[GSE Creator] Exception while checking popups: {e}")

        return dismissed

    async def open_new_detail_tab(self) -> Page:
        """Navigates to Favorites -> GSE W/O -> Clicks '+ New Detail'."""
        await self.dismiss_any_popups()

        new_detail_btn = self.page.locator('button:has-text("New Detail"), a:has-text("New Detail"), [id*="newDetail" i]').first
        # Only navigate if + New Detail is not already visible on the current page
        if not await new_detail_btn.is_visible():
            logger.info("[GSE Creator] Navigating to GSE W/O module...")
            fav = self.page.locator(':text("Favorites")').first
            try:
                await fav.wait_for(state="visible", timeout=8000)
            except Exception:
                await self.dismiss_any_popups()
                await fav.wait_for(state="visible", timeout=5000)

            await fav.click()
            await asyncio.sleep(0.5)

            gse_btn = self.page.locator('span:text-is("GSE W/O"), a:text-is("GSE W/O")').first
            if not await gse_btn.is_visible():
                await fav.click()
                await asyncio.sleep(0.5)

            await gse_btn.wait_for(state="visible", timeout=6000)
            await gse_btn.click()
            await asyncio.sleep(1.5)
            await self.dismiss_any_popups()
        else:
            logger.info("[GSE Creator] Already on GSE W/O module, clicking + New Detail directly...")

        # Check and close older tabs to ensure we never hit eMRO's max tab limit
        try:
            close_buttons = self.page.locator("ul.ui-tabs-nav li .ui-icon-close, ul.ui-tabview-nav li .ui-icon-close")
            tab_cnt = await close_buttons.count()
            if tab_cnt > 2:
                for idx in range(tab_cnt - 1):
                    btn = close_buttons.nth(idx)
                    if await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(0.3)
        except Exception:
            pass

        # Click + New Detail
        if not await new_detail_btn.is_visible():
            new_detail_btn = self.page.locator('button:has-text("New Detail"), a:has-text("New Detail"), [id*="newDetail" i]').first
            if not await new_detail_btn.is_visible():
                await asyncio.sleep(1)

        await new_detail_btn.click()
        # Fast Smart Wait: wait for Category input in the new tab to be visible
        try:
            cat_inp = self.page.locator("div.ui-tabs-panel:visible div[id$='_wo_category'] input, div.ui-tabview-panel:visible div[id$='_wo_category'] input, input[id*='category' i]").last
            await cat_inp.wait_for(state="visible", timeout=3500)
        except Exception:
            await asyncio.sleep(1)

        await self.dismiss_any_popups()
        await self.capture_live_screen("opened_new_detail")
        return self.page

    async def create_single_wo(
        self,
        gse: str,
        description: str,
        priority: str = "SCHED",
        category: str = "GSE MAIN",
        company: str = "TLM",
        location: str = "DMK",
        site: str = "APRON",
        expenditure: str = "GSE WO",
        user: Optional[str] = None
    ) -> Dict:
        """
        Creates a single GSE Work Order in eMRO.
        Returns a dict with generated details: { success, wo_number, gse, sn, description, priority, error }
        """
        now = datetime.now()
        actual_user = (user or self.user or self.current_user or Config.EMRO_USERNAME or "").strip().upper()
        result = {
            "success": False,
            "wo_number": "",
            "gse": gse.strip().upper(),
            "sn": "",
            "priority": priority.strip().upper(),
            "description": description.strip(),
            "user": actual_user,
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "date": f"{now.month}/{now.day}/{now.year}",
            "error": ""
        }

        try:
            # 1. Open new detail tab
            await self.open_new_detail_tab()

            # 2. Scope to the newest active tab panel
            active_panel = self.page.locator("div.ui-tabs-panel:visible, div.ui-tabview-panel:visible").last

            # 3. Select Company (TLM)
            comp_box = active_panel.locator("div[id$='_gl_company']").first
            company_dropdown = comp_box.locator("div.ui-selectonemenu").first
            if not await company_dropdown.is_visible():
                company_dropdown = active_panel.locator("div.ui-selectonemenu:not(.ui-state-disabled)").first

            if await company_dropdown.is_visible():
                lbl_elem = company_dropdown.locator("label.ui-selectonemenu-label").first
                curr_label = (await lbl_elem.inner_text()).strip() if await lbl_elem.is_visible() else ""
                logger.info(f"[GSE Creator] Current Company is '{curr_label}' (target: '{company}')")

                if curr_label != company:
                    logger.info(f"[GSE Creator] Opening Company dropdown to switch to '{company}'...")
                    trigger = company_dropdown.locator("div.ui-selectonemenu-trigger, label.ui-selectonemenu-label").first
                    await trigger.click()
                    await asyncio.sleep(0.8)

                    option = self.page.locator(f"li.ui-selectonemenu-item:visible").filter(has_text=company).first
                    if not await option.is_visible():
                        option = self.page.locator(f"li[data-label='{company}']").first

                    if await option.is_visible():
                        await option.click()
                        logger.info(f"[GSE Creator] Selected Company: '{company}'")
                        await asyncio.sleep(0.8)
                    else:
                        logger.warning(f"[GSE Creator] Option '{company}' not found in dropdown list!")

            # 4. Fill Category
            cat_inp = active_panel.locator("div[id$='_wo_category'] input").first
            if await cat_inp.is_visible():
                await cat_inp.fill(category)
                await self.page.keyboard.press("Tab")

            # 5. Fill Description (English only)
            desc_inp = active_panel.locator("div[id$='_wo_description'] textarea, textarea:visible").first
            if await desc_inp.is_visible():
                await desc_inp.fill(description)

            # 6. Fill Location
            loc_inp = active_panel.locator("div[id$='_location'] input").first
            if await loc_inp.is_visible():
                await loc_inp.fill(location)
                await self.page.keyboard.press("Tab")

            # 7. Fill Site
            site_inp = active_panel.locator("div[id$='_site'] input").first
            if await site_inp.is_visible():
                await site_inp.fill(site)
                await self.page.keyboard.press("Tab")

            # 8. Fill Priority
            prio_inp = active_panel.locator("div[id$='_priority'] input").first
            if await prio_inp.is_visible():
                await prio_inp.fill(priority)
                await self.page.keyboard.press("Tab")

            # 9. Fill Expenditure
            exp_inp = active_panel.locator("div[id$='_expenditure'] input").first
            if await exp_inp.is_visible():
                await exp_inp.fill(expenditure)
                await self.page.keyboard.press("Tab")

            # 10. Fill GSE (Equipment Code)
            gse_inp = active_panel.locator("div[id$='_ac'] input").first
            await gse_inp.click()
            await gse_inp.fill(gse.strip().upper())
            await self.page.keyboard.press("Tab")
            await asyncio.sleep(0.6)

            # Check if entering GSE triggered a validation popup
            await self.dismiss_any_popups()

            # 11. Locate Save button
            save_btn = self.page.locator("a[role='menuitem']:has-text('Save'):visible, a:has-text('Save'):visible, button:has-text('Save'):visible").first

            # Click Save
            logger.info(f"[GSE Creator] Saving GSE W/O for {gse}...")
            try:
                await save_btn.click(timeout=6000)
            except Exception as save_err:
                logger.warning(f"[GSE Creator] Save click blocked or timed out: {save_err}. Checking for popups...")
                if await self.dismiss_any_popups():
                    await asyncio.sleep(0.5)
                    if await save_btn.is_visible():
                        await save_btn.click(timeout=6000)
                else:
                    raise save_err

            # Smart polling for generated W/O number (breaks immediately when value appears!)
            wo_inp = active_panel.locator("div[id$='_wo'] input[id$='_input']").first
            wo_val = ""
            for _ in range(15):
                await asyncio.sleep(0.2)
                await self.dismiss_any_popups()
                if await wo_inp.is_visible():
                    wo_val = (await wo_inp.input_value()).strip()
                    if wo_val:
                        break

            # Retry loop if W/O number empty (per user rule)
            retry_count = 0
            while not wo_val and retry_count < 3:
                retry_count += 1
                logger.warning(f"[GSE Creator] W/O number empty for {gse}, retrying #{retry_count}...")
                await self.dismiss_any_popups()
                await gse_inp.click()
                await gse_inp.fill(gse.strip().upper())
                await self.page.keyboard.press("Tab")
                await asyncio.sleep(1.5)
                await self.dismiss_any_popups()
                try:
                    await save_btn.click(timeout=8000)
                except Exception:
                    await self.dismiss_any_popups()
                    if await save_btn.is_visible():
                        await save_btn.click(timeout=8000)
                await asyncio.sleep(3)
                await self.dismiss_any_popups()
                wo_val = (await wo_inp.input_value() if await wo_inp.is_visible() else "").strip()

            # Extract GSE S/N
            sn_inp = active_panel.locator("div[id$='_ac_sn'] input").first
            sn_val = (await sn_inp.input_value() if await sn_inp.is_visible() else "").strip()

            if wo_val:
                result["success"] = True
                result["wo_number"] = wo_val
                result["sn"] = sn_val
                logger.info(f"[GSE Creator] SUCCESS! W/O: {wo_val} | GSE: {gse} | S/N: {sn_val}")
                await self.capture_live_screen(f"success_{gse}")

                # CLEANUP: Close the completed detail tab so we never accumulate tabs or hit the 9-tab limit!
                try:
                    close_tab_btn = self.page.locator("ul.ui-tabs-nav li.ui-tabs-selected .ui-icon-close, ul.ui-tabview-nav li.ui-tabs-selected .ui-icon-close, li[aria-selected='true'] .ui-icon-close").first
                    if await close_tab_btn.is_visible():
                        logger.info("[GSE Creator] Closing completed tab to keep workspace clean...")
                        await close_tab_btn.click()
                        await asyncio.sleep(1)
                except Exception as tab_err:
                    logger.warning(f"[GSE Creator] Notice closing tab: {tab_err}")
            else:
                result["error"] = "Failed to generate W/O number after retries."
                logger.error(f"[GSE Creator] FAILED to generate W/O for {gse}")
                await self.capture_live_screen(f"fail_{gse}")

        except Exception as e:
            result["error"] = str(e)
            logger.exception(f"[GSE Creator] Exception while creating W/O for {gse}: {e}")
            # CLEANUP: Dismiss popups and close the failed tab so next item isn't blocked!
            try:
                await self.dismiss_any_popups()
                # Close the active tab in eMRO tabview if close icon exists
                close_tab_btn = self.page.locator("ul.ui-tabs-nav li.ui-tabs-selected .ui-icon-close, ul.ui-tabview-nav li.ui-tabs-selected .ui-icon-close, li[aria-selected='true'] .ui-icon-close").first
                if await close_tab_btn.is_visible():
                    logger.info("[GSE Creator] Closing failed tab to reset workspace...")
                    await close_tab_btn.click()
                    await asyncio.sleep(1.5)
                    await self.dismiss_any_popups()
            except Exception as clean_err:
                logger.warning(f"[GSE Creator] Cleanup error: {clean_err}")

        return result

    async def create_batch_wo(
        self,
        items: List[Dict],
        on_progress: Optional[Callable[[int, int, Dict], None]] = None
    ) -> List[Dict]:
        """
        Creates multiple GSE Work Orders in batch.
        items: list of dicts with keys: {'gse': str, 'description': str, 'priority': 'SCHED' (optional)}
        """
        results = []
        total = len(items)
        logger.info(f"[GSE Creator] Starting batch creation for {total} items...")

        await self.ensure_logged_in()

        for idx, item in enumerate(items):
            gse = item.get("gse", "")
            desc = item.get("description", "PM")
            prio = item.get("priority", "SCHED")

            logger.info(f"[GSE Creator] Processing ({idx+1}/{total}): GSE={gse} | DESC={desc} | PRIO={prio}")
            res = await self.create_single_wo(gse=gse, description=desc, priority=prio)
            results.append(res)

            if on_progress:
                try:
                    on_progress(idx + 1, total, res)
                except Exception as cb_err:
                    logger.warning(f"[GSE Creator] Progress callback error: {cb_err}")

            # Small pause between creations to let eMRO session settle
            await asyncio.sleep(2)

        return results

    @staticmethod
    def sync_to_google_sheet(results: List[Dict]) -> bool:
        """Sends created PM W/O records strictly to Monthly PM Tracking Sheet."""
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)
        url = os.getenv("APPS_SCRIPT_URL", Config.APPS_SCRIPT_URL)
        if not url:
            logger.warning("[GSE Creator] APPS_SCRIPT_URL not configured.")
            return False

        # Rule: Only PM / Scheduled work orders go to the monthly PM tracking sheet
        pm_items = [r for r in results if (r.get("priority") or "").upper() in ("SCHED", "PM")]
        if not pm_items:
            logger.info("[GSE Creator] No PM items to sync to Monthly PM Tracking Sheet. (CM is logged separately)")
            return True

        try:
            target_id = os.getenv("SPREADSHEET_ID", Config.SPREADSHEET_ID)
            payload = {
                "action": "append_gse_wo",
                "target_spreadsheet_id": target_id,
                "items": pm_items
            }
            logger.info(f"[GSE Creator] Syncing {len(pm_items)} PM items to Monthly Tracking Sheet ({target_id})...")
            resp = requests.post(url, json=payload, timeout=35)
            if resp.status_code == 200:
                logger.info("[GSE Creator] Monthly PM Tracking Sheet sync completed successfully!")
                return True
            else:
                logger.error(f"[GSE Creator] PM Sheet sync returned status {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            logger.exception(f"[GSE Creator] Error syncing PM items to Google Sheets: {e}")
            return False

    @staticmethod
    def log_to_google_sheet(results: List[Dict]) -> bool:
        """Sends created W/O records (excluding PM) to Master Audit Log Sheet."""
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)
        url = os.getenv("LOG_APPS_SCRIPT_URL", Config.LOG_APPS_SCRIPT_URL) or os.getenv("APPS_SCRIPT_URL", Config.APPS_SCRIPT_URL)
        if not url:
            logger.warning("[GSE Creator] LOG_APPS_SCRIPT_URL not configured.")
            return False

        # Also persist to local history file (dedup, locked, atomic)
        try:
            from scraper.history_store import append_history
            append_history(results)
        except Exception as e:
            logger.exception(f"[GSE Creator] Failed to save local W/O history: {e}")

        # Rule: Exclude PM / Scheduled work orders from sheet บันทึกข้อมูล W/O (Master Log Sheet is strictly for CM/Unscheduled)
        cm_items = [r for r in results if (r.get("priority") or "").upper() not in ("SCHED", "PM")]
        if not cm_items:
            logger.info("[GSE Creator] No CM items to send to Master Log Sheet (PM items excluded from บันทึกข้อมูล W/O).")
            return True

        try:
            log_id = os.getenv("LOG_SPREADSHEET_ID", Config.LOG_SPREADSHEET_ID)
            payload = {
                "action": "append_wo_log",
                "target_spreadsheet_id": log_id,
                "items": cm_items
            }
            logger.info(f"[GSE Creator] Logging {len(cm_items)} W/O records to Master Log Sheet ({log_id})...")
            resp = requests.post(url, json=payload, timeout=35)
            if resp.status_code == 200:
                logger.info("[GSE Creator] Master W/O Log Sheet sync completed successfully!")
                return True
            else:
                logger.error(f"[GSE Creator] Master Log sync returned status {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            logger.exception(f"[GSE Creator] Error logging to Master Log Sheet: {e}")
            return False

    @staticmethod
    def init_log_sheet_headers() -> bool:
        """Initializes header columns and styling in Master Log Sheet."""
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)
        url = os.getenv("LOG_APPS_SCRIPT_URL", Config.LOG_APPS_SCRIPT_URL) or os.getenv("APPS_SCRIPT_URL", Config.APPS_SCRIPT_URL)
        if not url:
            return False
        try:
            log_id = os.getenv("LOG_SPREADSHEET_ID", Config.LOG_SPREADSHEET_ID)
            payload = {
                "action": "init_wo_log_headers",
                "target_spreadsheet_id": log_id
            }
            logger.info(f"[GSE Creator] Initializing headers on Master Log Sheet ({log_id})...")
            resp = requests.post(url, json=payload, timeout=35)
            return resp.status_code == 200
        except Exception as e:
            logger.exception(f"[GSE Creator] Error initializing log sheet headers: {e}")
            return False
