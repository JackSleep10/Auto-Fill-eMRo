import asyncio
from scraper.config import Config
from scraper.emro_scraper import eMROScraper
from playwright.async_api import async_playwright

async def inspect_gse_screen():
    scraper = eMROScraper()
    print("[Inspect GSE] Initializing scraper...")
    await scraper.initialize()

    print("[Inspect GSE] Ensuring authenticated...")
    await scraper.ensure_authenticated()

    page = scraper.page
    print("[Inspect GSE] Navigating to Favorites -> GSE W/O...")

    # 1. Expand Favorites if needed
    fav_header = page.locator("h3:has-text('Favorites'), a:has-text('Favorites'), span:has-text('Favorites')").first
    if await fav_header.is_visible():
        await fav_header.click()
        await asyncio.sleep(1)

    # 2. Click GSE W/O in sidebar
    gse_wo_link = page.locator("a:has-text('GSE W/O'), span:has-text('GSE W/O')").first
    if await gse_wo_link.is_visible():
        print("[Inspect GSE] Clicking 'GSE W/O' menu...")
        await gse_wo_link.click()
        await asyncio.sleep(3)
    else:
        print("[Inspect GSE] Using search window input for 'GSE W/O'...")
        search_box = page.locator("input[placeholder*='search a window' i]").first
        if await search_box.is_visible():
            await search_box.fill("GSE W/O")
            await asyncio.sleep(1)
            await page.keyboard.press("Enter")
            await asyncio.sleep(3)

    # Take screenshot of the GSE W/O module page
    await page.screenshot(path="data/screenshots/gse_wo_main.png")
    print("[Inspect GSE] Screenshot saved: data/screenshots/gse_wo_main.png")

    # 3. Locate the '+ New Detail' button in the toolbar
    new_detail_btn = page.locator("button:has-text('New Detail'), a:has-text('New Detail'), [id*='newDetail' i], span:has-text('New Detail')").first
    print(f"[Inspect GSE] '+ New Detail' button visible: {await new_detail_btn.is_visible()}")

    if await new_detail_btn.is_visible():
        print("[Inspect GSE] Clicking '+ New Detail'...")
        await new_detail_btn.click()
        await asyncio.sleep(4)

        await page.screenshot(path="data/screenshots/gse_wo_new_detail.png")
        print("[Inspect GSE] Screenshot saved: data/screenshots/gse_wo_new_detail.png")

        # Dump HTML of the new detail view
        content = await page.content()
        with open("data/gse_wo_new_detail.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("[Inspect GSE] Saved HTML to data/gse_wo_new_detail.html")

        # Inspect all visible inputs, selects, textareas on page
        print("\n--- VISIBLE INPUTS & FIELDS ON NEW DETAIL SCREEN ---")
        inputs = await page.locator("input:visible, textarea:visible, select:visible, .ui-selectonemenu:visible").all()
        for i, el in enumerate(inputs):
            try:
                tag = await el.evaluate("e => e.tagName")
                id_ = await el.get_attribute("id") or ""
                name = await el.get_attribute("name") or ""
                val = await el.input_value() if tag in ["INPUT", "TEXTAREA"] else ""
                placeholder = await el.get_attribute("placeholder") or ""
                # Get nearby label or text
                parent_text = await el.evaluate("""e => {
                    const label = document.querySelector(`label[for='${e.id}']`);
                    if (label) return label.innerText;
                    let p = e.parentElement;
                    for (let k = 0; k < 3 && p; k++) {
                        if (p.innerText && p.innerText.trim().length < 50) return p.innerText.trim().replace(/\\n/g, ' ');
                        p = p.parentElement;
                    }
                    return '';
                }""")
                print(f"[{i:02d}] Tag={tag:8s} | ID={id_:35s} | Label={parent_text:25s} | Val='{val}'")
            except Exception as ex:
                pass

        # Inspect Save button
        save_btn = page.locator("button:has-text('Save'), a:has-text('Save'), [id*='save' i], span:has-text('Save')").all()
        print(f"\n--- SAVE BUTTONS FOUND: {len(save_btn)} ---")
        for b in save_btn:
            try:
                vis = await b.is_visible()
                id_ = await b.get_attribute("id") or ""
                text = await b.inner_text()
                print(f"Save button: vis={vis}, id={id_}, text='{text}'")
            except Exception:
                pass

    await scraper.close()
    print("[Inspect GSE] Done!")

if __name__ == "__main__":
    asyncio.run(inspect_gse_screen())
