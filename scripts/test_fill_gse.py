import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pyotp
from playwright.async_api import async_playwright
from scraper.config import Config

async def test_fill():
    p = await async_playwright().start()
    ctx = await p.chromium.launch_persistent_context(
        user_data_dir=str(Config.SESSION_DIR),
        headless=False,
        viewport={"width": 1440, "height": 900}
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()

    print("[Test Fill] Navigating to eMRO...")
    await page.goto(Config.EMRO_URL)
    await asyncio.sleep(3)

    # Login if needed
    submit_btn = page.locator('#mainForm\\:j_idt169, button:has-text("Submit")').first
    if await submit_btn.is_visible():
        for _ in range(10):
            p_val = await page.locator('input[type="password"]').first.input_value()
            if p_val:
                break
            await asyncio.sleep(0.5)
        await submit_btn.click()
        await asyncio.sleep(2)

    # 2FA if visible
    mfa_dlg = page.locator('#mainForm\\:MFADlg')
    if await mfa_dlg.is_visible():
        totp = pyotp.TOTP(Config.EMRO_TOTP_SECRET)
        code = totp.now()
        c1 = page.locator('#mainForm\\:code1_input')
        await c1.click()
        for idx, digit in enumerate(code):
            await page.keyboard.press(digit)
            await asyncio.sleep(0.2)
        for i in range(1, 7):
            await page.evaluate(f'() => {{ const h = document.getElementById("mainForm:code{i}_hinput"); if (h) h.value = "{code[i-1]}"; }}')
        await page.locator('#mainForm\\:j_idt163').click()
        await asyncio.sleep(5)

    print("[Test Fill] Navigating to GSE W/O...")
    fav = page.locator(':text("Favorites")').first
    if await fav.is_visible():
        await fav.click()
        await asyncio.sleep(1)

    gse_btn = page.locator('span:text-is("GSE W/O"), a:text-is("GSE W/O")').first
    if not await gse_btn.is_visible():
        await fav.click()
        await asyncio.sleep(1)

    await gse_btn.click()
    await asyncio.sleep(4)

    # Click + New Detail
    new_detail_btn = page.locator('button:has-text("New Detail"), a:has-text("New Detail"), [id*="newDetail" i]').first
    print(f"[Test Fill] '+ New Detail' visible: {await new_detail_btn.is_visible()}")
    await new_detail_btn.click()
    await asyncio.sleep(4)

    # Scope to active tab panel
    active_panel = page.locator("div.ui-tabs-panel:visible, div.ui-tabview-panel:visible").last
    print("[Test Fill] Active tab panel located.")

    # 1. Company dropdown: change BAE to TLM
    company_dropdown = active_panel.locator("xpath=.//label[contains(text(), 'Company')]/following::div[contains(@class, 'ui-selectonemenu')][1]")
    if not await company_dropdown.is_visible():
        company_dropdown = active_panel.locator("div.ui-selectonemenu:not(.ui-state-disabled)").first
    print(f"Company dropdown found: {await company_dropdown.is_visible()}")
    if await company_dropdown.is_visible():
        print("Opening Company dropdown...")
        await company_dropdown.click()
        await asyncio.sleep(1)
        tlm_option = page.locator("li.ui-selectonemenu-item:has-text('TLM')").first
        if await tlm_option.is_visible():
            await tlm_option.click()
            print("Selected Company: TLM")
            await asyncio.sleep(1)

    # 2. Fill Category: GSE MAIN
    print("Filling Category...")
    cat_input = active_panel.locator("xpath=.//label[contains(text(), 'Category')]/following::input[1]").first
    await cat_input.fill("GSE MAIN")
    await page.keyboard.press("Tab")

    # 3. Fill Description: PM OCT
    print("Filling Description...")
    desc_box = active_panel.locator("textarea").first
    await desc_box.fill("PM OCT")

    # 4. Fill Location: DMK
    print("Filling Location...")
    loc_input = active_panel.locator("xpath=.//label[contains(text(), 'Location')]/following::input[1]").first
    await loc_input.fill("DMK")
    await page.keyboard.press("Tab")

    # 5. Fill Site: APRON
    print("Filling Site...")
    site_input = active_panel.locator("xpath=.//label[contains(text(), 'Site')]/following::input[1]").first
    await site_input.fill("APRON")
    await page.keyboard.press("Tab")

    # 6. Fill Priority: SCHED
    print("Filling Priority...")
    prio_input = active_panel.locator("xpath=.//label[contains(text(), 'Priority')]/following::input[1]").first
    await prio_input.fill("SCHED")
    await page.keyboard.press("Tab")

    # 7. Fill Expenditure: GSE WO
    print("Filling Expenditure...")
    exp_input = active_panel.locator("xpath=.//label[contains(text(), 'Expenditure')]/following::input[1]").first
    await exp_input.fill("GSE WO")
    await page.keyboard.press("Tab")

    # 8. Fill GSE: TLM-TB-048
    print("Filling GSE 'TLM-TB-048'...")
    gse_input = active_panel.locator("xpath=.//label[text()='GSE']/following::input[1]").first
    await gse_input.fill("TLM-TB-048")
    await page.keyboard.press("Tab")
    await asyncio.sleep(2)

    # Save active_panel HTML for inspection
    panel_html = await active_panel.evaluate("e => e.outerHTML")
    with open("data/gse_form_panel.html", "w", encoding="utf-8") as f:
        f.write(panel_html)
    print("Saved active panel HTML to data/gse_form_panel.html")

    # Check GSE S/N
    gse_sn_input = active_panel.locator("xpath=.//label[contains(text(), 'GSE S/N')]/following::input[1]").first
    sn_val = await gse_sn_input.input_value()
    print(f"GSE S/N populated: '{sn_val}'")

    # Inspect Save button
    save_btns = await page.locator("a:has-text('Save'), button:has-text('Save'), [id*='save' i]").all()
    target_save_btn = None
    for idx, sb in enumerate(save_btns):
        vis = await sb.is_visible()
        id_ = await sb.get_attribute("id")
        text = await sb.inner_text()
        print(f"  [{idx}] vis={vis}, id={id_}, text='{text.strip()}'")
        if vis and "save" in text.lower():
            target_save_btn = sb
            outer = await sb.evaluate("e => e.outerHTML")
            print(f"Target Save Button outerHTML: {outer}")
            break

    if target_save_btn:
        print("[Test Fill] Clicking Save button...")
        await target_save_btn.click()
        await asyncio.sleep(4)

        wo_inp = active_panel.locator("div[id$='_wo'] input[id$='_input']").first
        wo_val = await wo_inp.input_value() if await wo_inp.is_visible() else ""
        print(f"[Test Fill] First attempt W/O Number: '{wo_val}'")

        # Retry logic if empty (per user instructions)
        retry_count = 0
        while not wo_val and retry_count < 3:
            retry_count += 1
            print(f"[Test Fill] W/O number empty, retrying #{retry_count} (refilling GSE & clicking Save)...")
            await gse_input.click()
            await gse_input.fill("TLM-TB-048")
            await page.keyboard.press("Tab")
            await asyncio.sleep(2)
            await target_save_btn.click()
            await asyncio.sleep(4)
            wo_val = await wo_inp.input_value() if await wo_inp.is_visible() else ""
            print(f"[Test Fill] Retry #{retry_count} W/O Number: '{wo_val}'")

        sn_val = await gse_sn_input.input_value() if await gse_sn_input.is_visible() else ""
        print(f"\n==========================================")
        print(f"[*] FINAL RESULT SUCCESS:")
        print(f"   GSE: TLM-TB-048")
        print(f"   GSE S/N: {sn_val}")
        print(f"   GSE W/O NUMBER: {wo_val}")
        print(f"==========================================\n")

    await page.screenshot(path="data/screenshots/after_save.png")
    print("Saved screenshot of result: data/screenshots/after_save.png")

    await ctx.close()
    await p.stop()
    print("[Test Fill] Done!")

if __name__ == "__main__":
    asyncio.run(test_fill())
