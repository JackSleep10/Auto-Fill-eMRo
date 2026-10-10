import asyncio
import pyotp
from playwright.async_api import async_playwright
from scraper.config import Config

async def test_2fa():
    playwright = await async_playwright().start()
    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=str(Config.SESSION_DIR),
        headless=False,
        viewport={"width": 1280, "height": 800}
    )
    page = context.pages[0] if context.pages else await context.new_page()

    print(f"[Test 2FA] Navigating to {Config.EMRO_URL}...")
    await page.goto(Config.EMRO_URL, wait_until="domcontentloaded")
    await asyncio.sleep(2)

    submit_btn = page.locator("button:has-text('Submit'), input[value='Submit'], #mainForm\\:j_idt169").first
    if await submit_btn.is_visible():
        print("[Test 2FA] Login Submit button is visible. Clicking Submit...")
        await submit_btn.click()
        await asyncio.sleep(2)

    mfa_dlg = page.locator("#mainForm\\:MFADlg")
    is_mfa_visible = await mfa_dlg.is_visible()
    print(f"[Test 2FA] MFA Dialog visible: {is_mfa_visible}")

    if is_mfa_visible:
        totp = pyotp.TOTP(Config.EMRO_TOTP_SECRET)
        code = totp.now()
        print(f"[Test 2FA] Fresh TOTP Code: {code}")

        # Let's test typing sequentially starting from code1_input
        print("[Test 2FA] Clicking code1_input...")
        c1 = page.locator("#mainForm\\:code1_input")
        await c1.click()
        await asyncio.sleep(0.2)

        # Clear any existing text in all 6 inputs first
        for i in range(1, 7):
            await page.evaluate(f"""() => {{
                const inp = document.getElementById('mainForm:code{i}_input');
                const hinp = document.getElementById('mainForm:code{i}_hinput');
                if (inp) inp.value = '';
                if (hinp) hinp.value = '';
            }}""")

        await c1.click()
        await asyncio.sleep(0.1)

        # Type each digit into the currently focused element
        for idx, digit in enumerate(code):
            active_id = await page.evaluate("() => document.activeElement ? document.activeElement.id : null")
            print(f"  Typing digit {idx+1} ('{digit}'), active element is: {active_id}")
            # If active element is not code{idx+1}_input, focus it explicitly
            target_id = f"mainForm:code{idx+1}_input"
            if active_id != target_id:
                print(f"  Focusing {target_id} explicitly")
                await page.locator(f"#{target_id.replace(':', r'\:')}").focus()
                await asyncio.sleep(0.1)

            # Type the character
            await page.keyboard.press(digit)
            await asyncio.sleep(0.25)

        # Let's inspect the values of input and hinput for all 6
        print("[Test 2FA] Checking values after typing:")
        for i in range(1, 7):
            inp_val = await page.evaluate(f"() => document.getElementById('mainForm:code{i}_input')?.value")
            hinp_val = await page.evaluate(f"() => document.getElementById('mainForm:code{i}_hinput')?.value")
            print(f"  Box {i}: input='{inp_val}', hinput='{hinp_val}'")

        # Ensure both input and hinput have the right digits
        print("[Test 2FA] Ensuring both input and hinput have correct digits...")
        for i in range(1, 7):
            expected = code[i-1]
            await page.evaluate(f"""() => {{
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

        # Check values again
        for i in range(1, 7):
            inp_val = await page.evaluate(f"() => document.getElementById('mainForm:code{i}_input')?.value")
            hinp_val = await page.evaluate(f"() => document.getElementById('mainForm:code{i}_hinput')?.value")
            print(f"  Confirmed Box {i}: input='{inp_val}', hinput='{hinp_val}'")

        # Listen to network requests/responses on verify click
        async def on_response(response):
            if "Home.trax" in response.url or "emro" in response.url:
                try:
                    text = await response.text()
                    print(f"[Network Response] {response.status} {response.url}: length={len(text)}")
                    if "error" in text.lower() or "invalid" in text.lower() or "fail" in text.lower():
                        print(f"  Response snippet: {text[:300]}")
                    elif "xml" in response.headers.get("content-type", ""):
                        print(f"  XML response snippet: {text[:400]}")
                except Exception:
                    pass

        page.on("response", on_response)

        # Click the Verify button
        print("[Test 2FA] Clicking Verify button #mainForm:j_idt163...")
        verify_btn = page.locator("#mainForm\\:j_idt163")
        await verify_btn.click()

        print("[Test 2FA] Waiting 8s for AJAX and page update...")
        await asyncio.sleep(8)

        print(f"[Test 2FA] Current URL: {page.url}")
        print(f"[Test 2FA] Page Title: {await page.title()}")
        is_mfa_still = await page.locator("#mainForm\\:MFADlg").is_visible()
        print(f"[Test 2FA] MFA Dialog still visible: {is_mfa_still}")

        # Check if tabs or favorites or main navigation are visible
        tabview = await page.locator(".ui-tabview, #mainTabView").count()
        favorites = await page.locator(":text('Favorites'), :text('Inventory')").count()
        print(f"[Test 2FA] TabView count={tabview}, Favorites/Inventory count={favorites}")

        await page.screenshot(path="data/screenshots/after_2fa.png")
        print("[Test 2FA] Screenshot saved to data/screenshots/after_2fa.png")

    await asyncio.sleep(2)
    await context.close()
    await playwright.stop()

if __name__ == "__main__":
    asyncio.run(test_2fa())
