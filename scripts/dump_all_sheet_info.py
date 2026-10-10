import asyncio
from playwright.async_api import async_playwright

async def dump():
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()

    out = []

    # 1. Master sheet
    url_master = "https://docs.google.com/spreadsheets/d/1i0hjTtfuJZX5EVIDxKNGcj4zr4qy3xuZHar1NAeYsQ0/edit"
    await page.goto(url_master, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(5)

    master_tabs = await page.locator("div.docs-sheet-tab").all()
    out.append("=== MASTER SHEET TABS ===")
    for t in master_tabs:
        name = (await t.inner_text()).strip()
        # Click each tab and get its URL with gid
        await t.click()
        await asyncio.sleep(1)
        curr_url = page.url
        out.append(f"Tab: {name} | URL: {curr_url}")

    # 2. Tracking sheet
    url_track = "https://docs.google.com/spreadsheets/d/1luje0x1QXrhhucSvmO6h_k5Es91X8rCcJeP2Fet7uYs/edit?gid=2018892674"
    await page.goto(url_track, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(5)

    track_tabs = await page.locator("div.docs-sheet-tab").all()
    out.append("\n=== TRACKING SHEET TABS ===")
    for t in track_tabs:
        name = (await t.inner_text()).strip()
        await t.click()
        await asyncio.sleep(1)
        curr_url = page.url
        out.append(f"Tab: {name} | URL: {curr_url}")

    with open("data/all_sheets_info.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(out))

    await browser.close()
    await p.stop()
    print("Saved to data/all_sheets_info.txt successfully!")

if __name__ == "__main__":
    asyncio.run(dump())
