import asyncio
import pyotp
from playwright.async_api import async_playwright
from scraper.config import Config

async def inspect():
    p = await async_playwright().start()
    ctx = await p.chromium.launch_persistent_context(
        user_data_dir=str(Config.SESSION_DIR),
        headless=False,
        viewport={"width": 1440, "height": 900}
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()

    print("[Inspect] Navigating to eMRO...")
    await page.goto(Config.EMRO_URL)
    await asyncio.sleep(3)

    # If login page, wait for password autofill then submit
    submit_btn = page.locator('#mainForm\\:j_idt169, button:has-text("Submit")').first
    if await submit_btn.is_visible():
        print("[Inspect] Waiting for password autofill...")
        for _ in range(10):
            p_val = await page.locator('input[type="password"]').first.input_value()
            if p_val:
                print(f"[Inspect] Password autofilled (len={len(p_val)})!")
                break
            await asyncio.sleep(0.5)
        print("[Inspect] Clicking Submit...")
        await submit_btn.click()
        await asyncio.sleep(2)

    # 2FA if visible
    mfa_dlg = page.locator('#mainForm\\:MFADlg')
    if await mfa_dlg.is_visible():
        totp = pyotp.TOTP(Config.EMRO_TOTP_SECRET)
        code = totp.now()
        print(f"[Inspect] 2FA Code: {code}")
        c1 = page.locator('#mainForm\\:code1_input')
        await c1.click()
        for idx, digit in enumerate(code):
            await page.keyboard.press(digit)
            await asyncio.sleep(0.2)
        for i in range(1, 7):
            await page.evaluate(f'() => {{ const h = document.getElementById("mainForm:code{i}_hinput"); if (h) h.value = "{code[i-1]}"; }}')
        await page.locator('#mainForm\\:j_idt163').click()
        await asyncio.sleep(5)

    print("[Inspect] Logged in! Navigating to GSE W/O...")
    fav = page.locator(':text("Favorites")').first
    if await fav.is_visible():
        await fav.click()
        await asyncio.sleep(1)

    gse_btn = page.locator('span:text-is("GSE W/O"), a:text-is("GSE W/O")').first
    print("[Inspect] GSE W/O link visible:", await gse_btn.is_visible())
    await gse_btn.click()
    await asyncio.sleep(4)

    # Click + New Detail
    new_detail = page.locator('button:has-text("New Detail"), a:has-text("New Detail"), [id*="newDetail" i]').first
    print("[Inspect] + New Detail visible:", await new_detail.is_visible())
    await new_detail.click()
    await asyncio.sleep(4)

    await page.screenshot(path="data/screenshots/gse_detail_form.png")
    print("[Inspect] Saved screenshot to data/screenshots/gse_detail_form.png")

    # Dump all input IDs
    inputs = await page.locator("input:visible, textarea:visible, select:visible").all()
    print(f"\n--- TOTAL VISIBLE INPUTS: {len(inputs)} ---")
    for inp in inputs:
        id_ = await inp.get_attribute("id")
        name = await inp.get_attribute("name")
        val = await inp.input_value()
        tag = await inp.evaluate("e => e.tagName")
        print(f"  [{tag:8s}] ID: {id_} | Name: {name} | Val: '{val}'")

    # Dump action toolbar buttons
    buttons = await page.locator("button:visible, a.ui-button:visible, [role='button']:visible").all()
    print(f"\n--- TOTAL VISIBLE BUTTONS: {len(buttons)} ---")
    for b in buttons:
        id_ = await b.get_attribute("id")
        text = await b.inner_text()
        if text.strip():
            print(f"  Button: ID: {id_} | Text: '{text.strip()}'")

    await ctx.close()
    await p.stop()

if __name__ == "__main__":
    asyncio.run(inspect())
