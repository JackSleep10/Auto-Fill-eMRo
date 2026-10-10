import asyncio
from playwright.async_api import async_playwright

async def inspect():
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()

    # 1. Master sheet tabs
    print("[1] Opening Master sheet...")
    url2 = "https://docs.google.com/spreadsheets/d/1i0hjTtfuJZX5EVIDxKNGcj4zr4qy3xuZHar1NAeYsQ0/edit"
    await page.goto(url2, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(5)

    master_tabs = await page.locator("div.docs-sheet-tab, span.docs-sheet-tab-name").all_inner_texts()
    print("Master Sheet Tabs:", [t.strip() for t in master_tabs if t.strip()])

    # Get tab elements to see their IDs / data-id
    tab_elems = await page.locator(".docs-sheet-tab").all()
    for te in tab_elems:
        text = await te.inner_text()
        id_ = await te.get_attribute("id")
        aria_id = await te.get_attribute("aria-labelledby")
        print(f"  Tab: '{text.strip()}' | ID: {id_}")

    # 2. Tracking sheet tabs
    print("\n[2] Opening tracking sheet...")
    url1 = "https://docs.google.com/spreadsheets/d/1luje0x1QXrhhucSvmO6h_k5Es91X8rCcJeP2Fet7uYs/edit?gid=2018892674"
    await page.goto(url1, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(5)

    track_tabs = await page.locator("div.docs-sheet-tab, span.docs-sheet-tab-name").all_inner_texts()
    print("Tracking Sheet Tabs:", [t.strip() for t in track_tabs if t.strip()])

    tab_elems1 = await page.locator(".docs-sheet-tab").all()
    for te in tab_elems1:
        text = await te.inner_text()
        id_ = await te.get_attribute("id")
        print(f"  Track Tab: '{text.strip()}' | ID: {id_}")

    await browser.close()
    await p.stop()

if __name__ == "__main__":
    asyncio.run(inspect())
