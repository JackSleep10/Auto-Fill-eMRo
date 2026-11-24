"""One-off exploration: log in, open Inventory Transaction, Find DM01, dump DOM info, try Export."""
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from inventory.config import Config
from inventory.emro_session import EmroSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
OUT = Config.DATA_DIR / "explore"
OUT.mkdir(parents=True, exist_ok=True)


async def main():
    s = EmroSession(headless=True)
    await s.ensure_logged_in()
    p = s.page
    await p.screenshot(path=str(OUT / "01_dashboard.png"))

    # Sidebar / favorites text
    sidebar = await p.evaluate("""() => Array.from(document.querySelectorAll('a, span, li'))
        .filter(e => e.offsetParent && /inventory/i.test(e.innerText||'') && (e.innerText||'').length < 60)
        .map(e => e.tagName + '|' + e.innerText.trim() + '|' + (e.id||'')).slice(0, 60)""")
    (OUT / "sidebar_inventory_items.json").write_text(json.dumps(sidebar, indent=1, ensure_ascii=False), encoding="utf-8")
    inputs = await p.evaluate("""() => Array.from(document.querySelectorAll('input')).filter(e=>e.offsetParent)
        .map(e => (e.id||'') + '|' + (e.placeholder||'') + '|' + e.type).slice(0, 40)""")
    (OUT / "dashboard_inputs.json").write_text(json.dumps(inputs, indent=1), encoding="utf-8")
    print("SIDEBAR:", sidebar[:30])
    print("INPUTS:", inputs[:20])

    # Try opening the window via search box
    search = p.locator("input[placeholder*='search a window' i], input[placeholder*='Typing here' i]").first
    if await search.is_visible():
        await search.fill("Inventory Transaction")
        await asyncio.sleep(1.5)
        await p.screenshot(path=str(OUT / "02_search_suggest.png"))
        sugg = await p.evaluate("""() => Array.from(document.querySelectorAll('li, a, span'))
            .filter(e => e.offsetParent && /^\\s*Inventory Transaction\\s*$/i.test(e.innerText||''))
            .map(e => e.tagName + '|' + e.className + '|' + (e.id||''))""")
        print("EXACT SUGGESTIONS:", sugg)
        clicked = False
        try:
            await search.press("Enter")
            await p.get_by_text("Search results").first.wait_for(state="visible", timeout=15000)
            item = p.get_by_text("Inventory Transaction", exact=True).first
            await item.wait_for(state="visible", timeout=10000)
            await item.click()
            clicked = True
            try:
                await p.locator("text=Inventory Transaction >> nth=1").wait_for(timeout=3000)
            except Exception:
                pass
        except Exception as e:
            print("click result failed:", e)
        print("clicked exact suggestion:", clicked)
        if not clicked:
            await search.press("Enter")
        await asyncio.sleep(4)
    else:
        print("search box not visible")
    await s.dismiss_popups()
    await p.screenshot(path=str(OUT / "03_module.png"))

    # Location input
    await asyncio.sleep(3)
    labels = await p.evaluate("""() => Array.from(document.querySelectorAll('*'))
        .filter(e => e.offsetParent && e.children.length === 0 && /^(Location|P\\/N|S\\/N|Batch)$/.test((e.textContent||'').trim()))
        .map(e => e.tagName + '|' + e.textContent.trim() + '|' + (e.getAttribute('for')||'') + '|' + (e.id||'') + '|' + e.className)""")
    print("LABELS:", labels)
    vis_inputs = await p.evaluate("""() => Array.from(document.querySelectorAll('input[type=text], input:not([type])'))
        .filter(e=>e.offsetParent).map(e => e.id).slice(0, 60)""")
    (OUT / "module_inputs.json").write_text(json.dumps({"labels": labels, "inputs": vis_inputs}, indent=1), encoding="utf-8")

    print("VISIBLE INPUT IDS:", vis_inputs)
    loc = p.get_by_text("Location", exact=True).first
    loc_input = loc.locator("xpath=following::input[not(@type='hidden')][1]").first
    await loc_input.fill("DM01")
    print("filled location, id=", await loc_input.get_attribute("id"))

    find = p.locator("a:has-text('Find'), button:has-text('Find'), span:text-is('Find')").first
    await find.click()
    await asyncio.sleep(5)
    await p.screenshot(path=str(OUT / "04_after_find.png"))

    paginator = await p.evaluate("""() => Array.from(document.querySelectorAll('.ui-paginator-current'))
        .filter(e=>e.offsetParent).map(e=>e.innerText)""")
    headers = await p.evaluate("""() => Array.from(document.querySelectorAll('thead th'))
        .filter(e=>e.offsetParent).map(e=>e.innerText.trim())""")
    first_rows = await p.evaluate("""() => Array.from(document.querySelectorAll('tbody.ui-datatable-data > tr'))
        .filter(e=>e.offsetParent).slice(0,3).map(tr => Array.from(tr.querySelectorAll(':scope > td')).map(td=>td.innerText.trim()))""")
    tbody_ids = await p.evaluate("""() => Array.from(document.querySelectorAll('tbody.ui-datatable-data')).map(e=>e.id)""")
    rpp = await p.evaluate("""() => Array.from(document.querySelectorAll('select.ui-paginator-rpp-options')).map(e=>e.id + '|' + Array.from(e.options).map(o=>o.value).join(','))""")
    export_els = await p.evaluate("""() => Array.from(document.querySelectorAll('a, button, img, span'))
        .filter(e => e.offsetParent && (/export|excel|xls/i.test((e.id||'') + (e.className||'') + (e.title||'') + (e.getAttribute('src')||'') + (e.getAttribute('onclick')||''))))
        .map(e => e.tagName + '|' + (e.id||'') + '|' + (e.className||'') + '|' + (e.title||'') + '|' + (e.getAttribute('src')||'')).slice(0,20)""")
    info = {"paginator": paginator, "headers": headers, "first_rows": first_rows, "tbody_ids": tbody_ids,
            "rpp": rpp, "export_elements": export_els}
    (OUT / "grid_info.json").write_text(json.dumps(info, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(info, indent=1, ensure_ascii=False))

    # Expand first row to see detail content (description?)
    try:
        tog = p.locator("tbody.ui-datatable-data > tr .ui-row-toggler").first
        if await tog.is_visible():
            await tog.click()
            await asyncio.sleep(2)
            exp = await p.evaluate("""() => { const e = document.querySelector('tr.ui-expanded-row-content'); return e ? e.innerText : ''; }""")
            (OUT / "expanded_row.txt").write_text(exp, encoding="utf-8")
            print("EXPANDED ROW:\n", exp[:1500])
            await p.screenshot(path=str(OUT / "05_expanded.png"))
            await tog.click()
            await asyncio.sleep(1)
    except Exception as e:
        print("expand failed:", e)

    # Try export
    try:
        cand = p.locator("a:has(img[src*='xls' i]), a:has(img[src*='excel' i]), [id*='export' i] a, a[id*='xls' i], a[id*='excel' i], img[src*='xls' i], img[src*='excel' i]").first
        async with p.expect_download(timeout=90000) as dl_info:
            await cand.click()
        dl = await dl_info.value
        target = OUT / ("export_sample_" + dl.suggested_filename)
        await dl.save_as(str(target))
        print("EXPORT SAVED:", target)
    except Exception as e:
        print("export failed:", e)
        await p.screenshot(path=str(OUT / "06_export_fail.png"))

    await s.close()


if __name__ == "__main__":
    asyncio.run(main())
