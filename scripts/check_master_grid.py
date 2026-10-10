import asyncio
from playwright.async_api import async_playwright

async def check():
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()

    url = "https://docs.google.com/spreadsheets/d/1i0hjTtfuJZX5EVIDxKNGcj4zr4qy3xuZHar1NAeYsQ0/edit?gid=982490752"
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(5)

    # Let's inspect the sheet name displayed
    doc_title = await page.title()
    print("Document Title:", doc_title)

    # Check if there are filters applied
    # Let's press Ctrl+Down or check cell values
    # Or inspect the grid
    # Let's check how many rows are in the sheet
    info = await page.evaluate("""() => {
        // Find row headers or canvas or table
        const rowHeaders = Array.from(document.querySelectorAll('.row-header-wrapper, .goog-inline-block')).map(e => e.innerText);
        return {
            title: document.title,
            tabNames: Array.from(document.querySelectorAll('.docs-sheet-tab-name')).map(e => e.innerText)
        };
    }""")
    print("Page info:", info)

    # Let's check if there is another tab or where TB is!
    # Where is TLM-TB-048 in this sheet?
    # Let's check if TLM-TB-048 is in ALL GSE IN EMRO
    await browser.close()
    await p.stop()

if __name__ == "__main__":
    asyncio.run(check())
