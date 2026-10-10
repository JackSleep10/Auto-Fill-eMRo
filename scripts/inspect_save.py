import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright
from scraper.config import Config

async def test_save():
    p = await async_playwright().start()
    ctx = await p.chromium.launch_persistent_context(
        user_data_dir=str(Config.SESSION_DIR),
        headless=False,
        viewport={"width": 1440, "height": 900}
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.goto(Config.EMRO_URL)
    await asyncio.sleep(3)

    active_panel = page.locator("div.ui-tabs-panel:visible, div.ui-tabview-panel:visible").last

    # Save button locator
    save_btn = active_panel.locator("xpath=preceding::a[.//span[text()='Save']] | preceding::button[.//span[text()='Save']]").last
    if not await save_btn.is_visible():
        save_btn = page.locator("a:has-text('Save'):visible, button:has-text('Save'):visible").first

    print("Save button visible:", await save_btn.is_visible())
    if await save_btn.is_visible():
        html = await save_btn.evaluate("e => e.outerHTML")
        print("Save button HTML:", html)

    # Let's inspect GSE S/N and GSE value right now
    gse_inp = active_panel.locator("div[id$='_ac'] input").first
    sn_inp = active_panel.locator("div[id$='_ac_sn'] input").first
    wo_inp = active_panel.locator("div[id$='_wo'] input[id$='_input']").first

    print("Current GSE value:", await gse_inp.input_value())
    print("Current GSE S/N value:", await sn_inp.input_value())
    print("Current GSE W/O value:", await wo_inp.input_value())

    await ctx.close()
    await p.stop()

if __name__ == "__main__":
    asyncio.run(test_save())
