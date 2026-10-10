import asyncio
import datetime
from pathlib import Path
from typing import List, Dict, Optional
import pyotp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, BrowserContext, Page

from scraper.config import Config
from scraper.parser import eMROParser

class eMROScraper:
    def __init__(self):
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def initialize(self):
        """Initializes Playwright browser with persistent context to preserve 2FA session."""
        if not self.playwright:
            self.playwright = await async_playwright().start()

        Config.SESSION_DIR.mkdir(parents=True, exist_ok=True)
        Config.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

        print(f"[eMROScraper] Launching browser (Headless: {Config.HEADLESS}, SessionDir: {Config.SESSION_DIR})...")
        
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox"
        ]

        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(Config.SESSION_DIR),
            headless=Config.HEADLESS,
            args=args,
            viewport={"width": 1440, "height": 900}
        )

        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        self.page.set_default_timeout(45000)

    async def ensure_authenticated(self):
        """Checks if session is valid; auto-authenticates with credentials and TOTP if configured, or prompts user."""
        if not self.page:
            await self.initialize()

        print(f"[eMROScraper] Checking authentication status at {Config.EMRO_URL}...")
        try:
            await self.page.goto(Config.EMRO_URL, wait_until="domcontentloaded")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"[eMROScraper] Note loading page: {e}")

        # Check if already authenticated
        if await self._is_dashboard_page():
            print("[eMROScraper] Active session found. Authentication verified!")
            return

        is_login = await self._is_login_page()
        is_2fa = await self._is_2fa_page()

        if is_login or is_2fa:
            print("[eMROScraper] Authentication required. Attempting automated login...")

            # 1. Fill Username & Password on standard login form
            if is_login and not is_2fa:
                try:
                    # A. Username
                    user_input = self.page.locator("input[name*='user' i], input[id*='user' i], input[type='text']:visible, input[placeholder*='user' i]").first
                    if await user_input.is_visible():
                        cur_user = await user_input.input_value()
                        if Config.EMRO_USERNAME and cur_user.strip() != Config.EMRO_USERNAME:
                            await user_input.fill(Config.EMRO_USERNAME)
                            print(f"[eMROScraper] Auto-filled username: {Config.EMRO_USERNAME}")
                        elif cur_user:
                            print(f"[eMROScraper] Using existing username in field: {cur_user}")

                    # B. Password
                    pass_input = self.page.locator("input[type='password']").first
                    if await pass_input.is_visible():
                        if Config.EMRO_PASSWORD:
                            await pass_input.fill(Config.EMRO_PASSWORD)
                            print("[eMROScraper] Filled password from config.")
                        else:
                            # Wait up to 5 seconds for browser saved password to autofill
                            for _ in range(10):
                                cur_pass = await pass_input.input_value()
                                if cur_pass:
                                    print(f"[eMROScraper] Password populated by browser saved credentials (len={len(cur_pass)}).")
                                    break
                                await asyncio.sleep(0.5)

                        await asyncio.sleep(0.5)

                        # C. Click Submit button
                        submit_btn = self.page.locator(
                            "#mainForm\\:j_idt169, button:has-text('Submit'), input[value='Submit'], input[type='submit'], "
                            "button[type='submit'], button:has-text('Sign in'), button:has-text('Login')"
                        ).first

                        if await submit_btn.is_visible():
                            print("[eMROScraper] Clicking 'Submit' button on Sign in page...")
                            await submit_btn.click()
                        else:
                            print("[eMROScraper] Pressing Enter on password field...")
                            await pass_input.press("Enter")

                        # Wait for transition to 2FA screen or main dashboard
                        for _ in range(12):
                            await asyncio.sleep(0.5)
                            if await self._is_2fa_page() or await self._is_dashboard_page():
                                break

                except Exception as e:
                    print(f"[eMROScraper] Note on login form submit: {e}")

            # 2. Handle 2FA / Authenticator code (TOTP)
            if await self._is_2fa_page():
                print("[eMROScraper] 2FA / Authenticator verification screen detected!")
                if Config.EMRO_TOTP_SECRET:
                    try:
                        await asyncio.sleep(1)
                        totp = pyotp.TOTP(Config.EMRO_TOTP_SECRET)
                        otp_code = totp.now()
                        print(f"[eMROScraper] Generated TOTP 2FA code: {otp_code}")

                        c1 = self.page.locator("#mainForm\\:code1_input")
                        if await c1.is_visible():
                            # Clear old values
                            for i in range(1, 7):
                                await self.page.evaluate(f"""() => {{
                                    const inp = document.getElementById('mainForm:code{i}_input');
                                    const hinp = document.getElementById('mainForm:code{i}_hinput');
                                    if (inp) inp.value = '';
                                    if (hinp) hinp.value = '';
                                }}""")

                            await c1.click()
                            await asyncio.sleep(0.1)

                            # Type each digit sequentially with 250ms spacing
                            for idx, digit in enumerate(otp_code):
                                target_id = f"mainForm:code{idx+1}_input"
                                active_id = await self.page.evaluate("() => document.activeElement ? document.activeElement.id : null")
                                if active_id != target_id:
                                    await self.page.locator(f"#{target_id.replace(':', r'\\:')}").focus()
                                    await asyncio.sleep(0.1)
                                await self.page.keyboard.press(digit)
                                await asyncio.sleep(0.25)

                            # Synchronize input and hidden input fields
                            for i in range(1, 7):
                                expected = otp_code[i-1]
                                await self.page.evaluate(f"""() => {{
                                    const inp = document.getElementById('mainForm:code{i}_input');
                                    const hinp = document.getElementById('mainForm:code{i}_hinput');
                                    if (inp && inp.value !== '{expected}') {{
                                        inp.value = '{expected}';
                                        inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                                        inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                                    }}
                                    if (hinp && hinp.value !== '{expected}') {{
                                        hinp.value = '{expected}';
                                        hinp.dispatchEvent(new Event('input', {{bubbles: true}}));
                                        hinp.dispatchEvent(new Event('change', {{bubbles: true}}));
                                    }}
                                }}""")

                            await asyncio.sleep(0.5)

                            # Click Verify button
                            verify_btn = self.page.locator("#mainForm\\:j_idt163, button:has-text('Verify')").first
                            if await verify_btn.is_visible():
                                print("[eMROScraper] Clicking 'Verify' button on 2FA screen...")
                                await verify_btn.click()
                            else:
                                print("[eMROScraper] Executing verifyClick remoteCommand...")
                                await self.page.evaluate("() => { if (typeof command_mainForm_verifyClick === 'function') command_mainForm_verifyClick(); }")
                        else:
                            # Fallback for single OTP input box if ever used
                            single_box = self.page.locator("input[autocomplete='one-time-code'], input[name*='otp' i]").first
                            if await single_box.is_visible():
                                await single_box.click()
                                await single_box.fill("")
                                await single_box.press_sequentially(otp_code, delay=200)
                                verify_btn = self.page.locator("button:has-text('Verify'), button[type='submit']").first
                                if await verify_btn.is_visible():
                                    await verify_btn.click()

                        await asyncio.sleep(2)
                    except Exception as e:
                        print(f"[eMROScraper] Error auto-filling TOTP code: {e}")
                else:
                    print("[eMROScraper] EMRO_TOTP_SECRET not set in .env. Please enter OTP manually.")

            # 3. Wait for the main eMRO dashboard to load
            try:
                await self.page.wait_for_selector(
                    ":text('Favorites'), :text('Log out'), :text('Modules'), #mainTabView",
                    timeout=30_000
                )
                print("[eMROScraper] Successfully authenticated and logged into eMRO! Session active.")
            except Exception as e:
                print(f"[eMROScraper] Waiting for manual completion if needed: {e}")
                await self.page.wait_for_selector(
                    ":text('Favorites'), :text('Log out'), :text('Modules'), #mainTabView",
                    timeout=180_000
                )
                print("[eMROScraper] Authenticated successfully!")
        else:
            print("[eMROScraper] Active session found. Authentication verified!")

    async def _is_dashboard_page(self) -> bool:
        """Determines if the main authenticated eMRO dashboard is loaded."""
        indicators = [
            ":text('Favorites')",
            ":text('Log out')",
            ":text('Modules')",
            "#mainTabView"
        ]
        for sel in indicators:
            try:
                el = self.page.locator(sel).first
                if await el.is_visible():
                    return True
            except Exception:
                pass
        return False

    async def _is_login_page(self) -> bool:
        """Determines if current page is a login/password screen."""
        login_indicators = [
            'input[type="password"]',
            '#mainForm\\:j_idt75',
            'button:has-text("Submit")',
            'button:has-text("Login")',
            'a:has-text("Login with External Provider")'
        ]
        for sel in login_indicators:
            try:
                el = self.page.locator(sel).first
                if await el.is_visible():
                    return True
            except Exception:
                pass
        return False

    async def _is_2fa_page(self) -> bool:
        """Determines if current page is waiting for 2FA / Authenticator code."""
        otp_indicators = [
            '#mainForm\\:MFADlg',
            '#mainForm\\:code1_input',
            ':text("Multi-Factor")',
            ':text("One-Time password")',
            ':text("Authenticator")'
        ]
        for sel in otp_indicators:
            try:
                el = self.page.locator(sel).first
                if await el.is_visible():
                    return True
            except Exception:
                pass
        return False

    async def navigate_to_module(self):
        """
        Step 1:
        Checks if module is open. If not, clicks 'Favorites' in the left sidebar,
        then clicks 'Inventory Transaction History Query'.
        Fallback: Uses the sidebar search box 'Typing here to search a window...'.
        """
        print("[eMROScraper] Checking if 'Inventory Transaction History Query' module is open...")
        try:
            # 1. Check if FIND button or module is already visible
            find_btn = self.page.locator("button:has-text('Find'), a:has-text('Find'), span:has-text('Find'), [title='Find']").first
            if await find_btn.is_visible():
                print("[eMROScraper] Module is already open and active.")
                return

            # Check if there is an inactive tab header for Inventory that we can click
            tab_header = self.page.locator(".ui-tabview-title:has-text('Inventory')").first
            if await tab_header.is_visible():
                await tab_header.click()
                await asyncio.sleep(1)
                if await find_btn.is_visible():
                    print("[eMROScraper] Switched to open Inventory tab.")
                    return

            # 2. Locate exact 'Favorites' menu header
            fav_el = self.page.get_by_text("Favorites", exact=True).first
            if await fav_el.is_visible():
                item = self.page.get_by_text("Inventory Transaction History Query", exact=False).first
                if not await item.is_visible():
                    print("[eMROScraper] Clicking 'Favorites' header to expand sidebar menu...")
                    await fav_el.click()
                    await asyncio.sleep(1.5)

                if await item.is_visible():
                    print("[eMROScraper] Clicking 'Inventory Transaction History Query'...")
                    await item.click()
                    await asyncio.sleep(3)
                    try:
                        await self.page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    return

            # 3. Fallback: Use the sidebar search box 'Typing here to search a window...'
            search_box = self.page.locator("input[placeholder*='search a window'], input[placeholder*='Typing here']").first
            if await search_box.is_visible():
                print("[eMROScraper] Using sidebar search box to open module...")
                await search_box.fill("Inventory Transaction History Query")
                await asyncio.sleep(1)
                suggestion = self.page.get_by_text("Inventory Transaction History Query", exact=False).first
                if await suggestion.is_visible():
                    await suggestion.click()
                else:
                    await search_box.press("Enter")
                await asyncio.sleep(3)
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass

        except Exception as e:
            print(f"[eMROScraper] Note on navigation: {e}")

    async def set_rows_per_page(self, count: int = 50):
        """
        Step 3:
        Changes the pagination rows-per-page dropdown from 10 to 50.
        """
        print(f"[eMROScraper] Checking rows per page setting ({count})...")
        try:
            # Check native select
            select_el = self.page.locator("select[id*='rppDD'], select.ui-paginator-rpp-options").first
            if await select_el.is_visible():
                current_val = await select_el.input_value()
                if current_val != str(count):
                    await select_el.select_option(str(count))
                    print(f"[eMROScraper] Selected {count} in native dropdown.")
                    await asyncio.sleep(2)
                    try:
                        await self.page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        pass
                return

            # Check PrimeFaces custom dropdown
            custom_dropdown = self.page.locator("div[id*='rppDD'], .ui-paginator-rpp-options").first
            if await custom_dropdown.is_visible():
                text = await custom_dropdown.inner_text()
                if str(count) not in text:
                    await custom_dropdown.click()
                    await asyncio.sleep(0.5)
                    opt = self.page.locator(f".ui-selectonemenu-item:has-text('{count}')").first
                    if await opt.is_visible():
                        await opt.click()
                        print(f"[eMROScraper] Selected '{count}' in custom dropdown.")
                        await asyncio.sleep(2)
                        try:
                            await self.page.wait_for_load_state("networkidle", timeout=10000)
                        except Exception:
                            pass
        except Exception as e:
            print(f"[eMROScraper] Note on setting rows per page: {e}")

    async def query_inventory_transactions(self, location: str = Config.MONITOR_LOCATION) -> List[Dict]:
        """
        1. Open module via Favorites (if needed)
        2. Enter Location DM01 & Click FIND
        3. Set page size to 50
        4. Extract rows with details
        """
        try:
            # 0. Ensure session is still active
            if await self._is_login_page() or await self._is_2fa_page():
                print("[eMROScraper] Session expired or on login page. Auto-authenticating...")
                await self.ensure_authenticated()

            # 1. Ensure module is opened via Favorites
            await self.navigate_to_module()

            # 2. Enter Location DM01 & Click FIND
            print(f"[eMROScraper] Step 2: Entering Location '{location}' and clicking FIND...")
            
            loc_input = None
            
            # Method A: By known ID pattern
            by_id = self.page.locator("input[id*='22918'], input[id*='location' i]").first
            if await by_id.is_visible():
                loc_input = by_id

            # Method B: By Location label proximity
            if not loc_input:
                loc_label = self.page.get_by_text("Location", exact=True).first
                if await loc_label.is_visible():
                    cand = loc_label.locator("xpath=following::input[1]").first
                    if await cand.is_visible():
                        loc_input = cand

            # Method C: Search all visible inputs in the General panel
            if not loc_input:
                inputs = await self.page.locator("input[type='text'], input:not([type])").all()
                for inp in inputs:
                    try:
                        if await inp.is_visible():
                            val = await inp.input_value()
                            if val.strip().upper() == location.upper():
                                loc_input = inp
                                break
                    except Exception:
                        pass

            if loc_input:
                await loc_input.fill("")
                await loc_input.fill(location)
                print(f"[eMROScraper] Filled Location: {location}")
            else:
                print(f"[eMROScraper] Warning: Location input field not found directly.")

            # Click FIND button (binoculars icon or text Find)
            find_btn = self.page.locator("button:has-text('Find'), a:has-text('Find'), span:has-text('Find'), [title='Find']").first
            if await find_btn.is_visible():
                await find_btn.click()
                print("[eMROScraper] Clicked FIND button.")
            elif loc_input:
                await loc_input.press("Enter")

            # Wait for data table to load
            await asyncio.sleep(3)
            try:
                await self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            # 3. Change rows per page to 50
            await self.set_rows_per_page(50)

            # 4. Extract records
            transactions = await self._extract_datatable_rows()
            print(f"[eMROScraper] Extracted {len(transactions)} transaction records.")
            return transactions

        except Exception as e:
            print(f"[eMROScraper] Error during scraping: {e}")
            await self.take_screenshot("scrape_error")
            return []

    async def _extract_datatable_rows(self) -> List[Dict]:
        """
        Finds the PrimeFaces DataTable, clicks row togglers to expand detail panels,
        and extracts all 27 fields cleanly 1-to-1.
        """
        results = []

        # Target only main data rows (exclude expansion containers)
        rows = await self.page.query_selector_all(
            "tbody[id*='dw_inventory'] tr:not(.ui-expanded-row-content), .ui-datatable-data tr:not(.ui-expanded-row-content)"
        )
        if not rows:
            rows = await self.page.query_selector_all("table tbody tr:not(.ui-expanded-row-content)")

        print(f"[eMROScraper] Found {len(rows)} data rows to process.")

        for idx, row in enumerate(rows):
            try:
                # 1. Extract cell text for this row
                cells_text = await row.evaluate("el => Array.from(el.querySelectorAll('td')).map(td => td.innerText.trim())")
                if not any(cells_text):
                    continue

                joined = " ".join(cells_text).upper()
                if not any(kw in joined for kw in ["ISSUED", "RECEIVING", "TRANSFER", "RTS", "PO", "BIN"]):
                    continue

                # 2. Check if already expanded, or click toggler to expand
                expanded_html = await row.evaluate("""el => {
                    const next = el.nextElementSibling;
                    if (next && (next.classList.contains('ui-expanded-row-content') || 
                                 next.classList.contains('ui-expanded-row-expansion') || 
                                 next.querySelector('.ui-expanded-row-content'))) {
                        return next.innerHTML;
                    }
                    return '';
                }""")

                if not expanded_html:
                    # Look for toggler button in the row (column 2 or class toggler)
                    toggler = await row.query_selector(
                        ".ui-row-toggler, [class*='toggler'], td:nth-child(2) button, td:nth-child(2) a, td:nth-child(2)"
                    )
                    if toggler:
                        try:
                            await toggler.click()
                            for _ in range(10):
                                await asyncio.sleep(0.15)
                                expanded_html = await row.evaluate("""el => {
                                    const next = el.nextElementSibling;
                                    if (next && (next.classList.contains('ui-expanded-row-content') || 
                                                 next.classList.contains('ui-expanded-row-expansion') || 
                                                 next.querySelector('.ui-expanded-row-content'))) {
                                        return next.innerHTML;
                                    }
                                    return '';
                                }""")
                                if expanded_html:
                                    break
                        except Exception:
                            pass

                # 3. Parse row with its expanded details
                parsed = eMROParser.parse_transaction_row(cells_text, expanded_html if expanded_html else None)
                results.append(parsed)

            except Exception as e:
                print(f"[eMROScraper] Note on extracting row #{idx}: {e}")

        return results

    async def take_screenshot(self, name: str = "capture"):
        """Saves a screenshot with timestamp for debugging."""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = Config.SCREENSHOTS_DIR / f"{name}_{timestamp}.png"
            if self.page:
                await self.page.screenshot(path=str(filename), full_page=True)
                print(f"[eMROScraper] Screenshot saved: {filename}")
        except Exception as e:
            print(f"[eMROScraper] Failed to take screenshot: {e}")

    async def close(self):
        """Closes browser context and Playwright instance."""
        try:
            if self.context:
                await self.context.close()
            if self.playwright:
                await self.playwright.stop()
            print("[eMROScraper] Browser closed successfully.")
        except Exception as e:
            print(f"[eMROScraper] Error closing browser: {e}")
