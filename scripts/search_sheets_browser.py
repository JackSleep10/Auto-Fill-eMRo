import asyncio
from playwright.async_api import async_playwright

async def inspect_full_sheet():
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()

    url = "https://docs.google.com/spreadsheets/d/1i0hjTtfuJZX5EVIDxKNGcj4zr4qy3xuZHar1NAeYsQ0/edit?gid=982490752"
    print("Navigating to sheet...")
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(6)

    # Let's search inside the sheet for TB-048 or Towbar
    # Using Google Sheets find: press Ctrl+F
    await page.keyboard.press("Control+f")
    await asyncio.sleep(1)
    await page.keyboard.type("TLM-TB-048")
    await page.keyboard.press("Enter")
    await asyncio.sleep(2)

    # Check search result bubble or status
    search_bubble = await page.locator(".docs-findinput-bubble, .docs-sheet-find-bubble").inner_text() if await page.locator(".docs-findinput-bubble, .docs-sheet-find-bubble").is_visible() else "No bubble"
    print("Search 'TLM-TB-048' bubble:", search_bubble)

    # Search 'TB-'
    await page.keyboard.press("Control+a")
    await page.keyboard.type("TLM-TB")
    await page.keyboard.press("Enter")
    await asyncio.sleep(2)
    search_bubble2 = await page.locator(".docs-findinput-bubble, .docs-sheet-find-bubble").inner_text() if await page.locator(".docs-findinput-bubble, .docs-sheet-find-bubble").is_visible() else "No bubble"
    print("Search 'TLM-TB' bubble:", search_bubble2)

    # Let's check the other sheet! (https://docs.google.com/spreadsheets/d/1luje0x1QXrhhucSvmO6h_k5Es91X8rCcJeP2Fet7uYs)
    # Does the tracking sheet or another sheet have the full GSE list?
    print("\nChecking tracking sheet for GSE master...")
    url_track = "https://docs.google.com/spreadsheets/d/1luje0x1QXrhhucSvmO6h_k5Es91X8rCcJeP2Fet7uYs/edit?gid=2018892674"
    await page.goto(url_track, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(6)

    await page.keyboard.press("Control+f")
    await asyncio.sleep(1)
    await page.keyboard.type("TLM-TB-048")
    await page.keyboard.press("Enter")
    await asyncio.sleep(2)
    search_bubble3 = await page.locator(".docs-findinput-bubble, .docs-sheet-find-bubble").inner_text() if await page.locator(".docs-findinput-bubble, .docs-sheet-find-bubble").is_visible() else "No bubble"
    print("Tracking sheet search 'TLM-TB-048' bubble:", search_bubble3)

    await browser.close()
    await p.stop()

if __name__ == "__main__":
    asyncio.run(inspect_full_sheet())
