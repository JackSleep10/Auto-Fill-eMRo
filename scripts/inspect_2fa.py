import asyncio
from scraper.config import Config
from playwright.async_api import async_playwright
import re

async def main():
    playwright = await async_playwright().start()
    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=str(Config.SESSION_DIR),
        headless=False,
        viewport={"width": 1280, "height": 800}
    )
    page = context.pages[0] if context.pages else await context.new_page()

    print("[Inspect] Navigating to", Config.EMRO_URL)
    await page.goto(Config.EMRO_URL, wait_until="domcontentloaded")
    await asyncio.sleep(2)

    # Click Submit if visible
    submit_btn = page.locator("button:has-text('Submit'), input[value='Submit'], [id*='submit' i]").first
    if await submit_btn.is_visible():
        print("[Inspect] Found Submit button, clicking...")
        await submit_btn.click()
        await asyncio.sleep(3)

    print("\n--- FRAMES ---")
    for f in page.frames:
        print("Frame:", f.name, f.url)

    print("\n--- ALL INPUTS ON PAGE ---")
    inputs = await page.locator("input").all()
    for idx, inp in enumerate(inputs):
        try:
            visible = await inp.is_visible()
            attrs = await inp.evaluate("el => ({id: el.id, name: el.name, type: el.type, class: el.className, maxlength: el.maxLength, placeholder: el.placeholder, value: el.value})")
            print(f"Input #{idx}: visible={visible} | {attrs}")
        except Exception as e:
            print(f"Input #{idx}: error {e}")

    print("\n--- HTML SNIPPET AROUND 'One-Time' or 'Multi-Factor' ---")
    content = await page.content()
    with open("data/2fa_screen.html", "w", encoding="utf-8") as f:
        f.write(content)
    print("[Inspect] Full HTML saved to data/2fa_screen.html")

    for match in re.finditer(r"(Multi-Factor|One-Time|Authenticator|Verify)", content, re.IGNORECASE):
        start = max(0, match.start() - 200)
        end = min(len(content), match.end() + 300)
        print("MATCH SNIPPET:\n", content[start:end])
        print("="*60)
        break

    await asyncio.sleep(2)
    await context.close()
    await playwright.stop()

if __name__ == "__main__":
    asyncio.run(main())
