import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright
from scraper.config import Config

async def check():
    p = await async_playwright().start()
    ctx = await p.chromium.launch_persistent_context(
        user_data_dir=str(Config.SESSION_DIR),
        headless=False,
        viewport={"width": 1440, "height": 900}
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.goto(Config.EMRO_URL)
    await asyncio.sleep(3)

    # Check tabs or open GSE W/O
    active_panel = page.locator("div.ui-tabs-panel:visible, div.ui-tabview-panel:visible").last
    gse_input = active_panel.locator("xpath=.//label[text()='GSE']/following::input[1]").first
    if not await gse_input.is_visible():
        # Open GSE W/O
        fav = page.locator(':text("Favorites")').first
        if await fav.is_visible():
            await fav.click()
            await asyncio.sleep(1)
        gse_btn = page.locator('span:text-is("GSE W/O"), a:text-is("GSE W/O")').first
        await gse_btn.click()
        await asyncio.sleep(4)
        new_detail = page.locator('button:has-text("New Detail"), a:has-text("New Detail")').first
        await new_detail.click()
        await asyncio.sleep(3)
        active_panel = page.locator("div.ui-tabs-panel:visible, div.ui-tabview-panel:visible").last
        gse_input = active_panel.locator("xpath=.//label[text()='GSE']/following::input[1]").first

    print("Found GSE Input! Extracting details...")
    html = await gse_input.evaluate("e => e.outerHTML")
    print("GSE INPUT HTML:\n", html)

    # Check onchange, onblur attributes and bound PrimeFaces events
    info = await gse_input.evaluate("""e => {
        return {
            id: e.id,
            name: e.name,
            className: e.className,
            onchange: e.getAttribute('onchange'),
            onblur: e.getAttribute('onblur'),
            onkeydown: e.getAttribute('onkeydown'),
            events: Object.keys(e).filter(k => k.startsWith('on'))
        }
    }""")
    print("Input attributes/events:", info)

    # Let's test typing into GSE
    print("\nFocusing and typing 'TLM-TB-048' sequentially...")
    await gse_input.click()
    await gse_input.fill("")
    await gse_input.press_sequentially("TLM-TB-048", delay=50)
    print("Pressing Tab...")
    await page.keyboard.press("Tab")
    
    print("Waiting 3 seconds...")
    await asyncio.sleep(3)

    sn_input = active_panel.locator("xpath=.//label[contains(text(), 'GSE S/N')]/following::input[1]").first
    sn_val = await sn_input.input_value()
    print(f"--> GSE S/N after Tab: '{sn_val}'")

    if not sn_val:
        print("S/N still empty. Let's try pressing Enter on GSE input...")
        await gse_input.click()
        await page.keyboard.press("Enter")
        await asyncio.sleep(3)
        sn_val = await sn_input.input_value()
        print(f"--> GSE S/N after Enter: '{sn_val}'")

    if not sn_val:
        print("Let's check if the label 'GSE' itself is clickable (lookup button)...")
        gse_label = active_panel.locator("xpath=.//label[text()='GSE']").first
        label_html = await gse_label.evaluate("e => e.outerHTML")
        print("GSE LABEL HTML:", label_html)

    # Check Save button selector
    save_btn = page.locator("a:has-text('Save'), button:has-text('Save'), [id*='save' i]").first
    print("Save button visible:", await save_btn.is_visible())
    if await save_btn.is_visible():
        save_html = await save_btn.evaluate("e => e.outerHTML")
        print("Save button HTML:", save_html)

    await ctx.close()
    await p.stop()

if __name__ == "__main__":
    asyncio.run(check())
