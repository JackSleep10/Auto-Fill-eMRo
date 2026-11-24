"""Fetch the full inventory snapshot of a Location from eMRO 'Inventory Transaction'.

Primary:  Find -> click Excel export icon -> parse .xlsx  (all rows, incl. DESCRIPTION)
Fallback: Find -> rows-per-page 50 -> read every page of the grid (no DESCRIPTION)
"""
import asyncio
import logging
import math
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import openpyxl

from inventory.config import Config
from inventory.emro_session import EmroSession
from inventory.tx_parser import TransactionParser

logger = logging.getLogger("Fetcher")

WINDOW_NAME = "Inventory Transaction"
WINDOW_HISTORY_NAME = "Inventory Transaction History Query"

# Excel header -> our field name
EXPORT_COLUMNS = {
    "LOCATION": "location", "BIN": "bin", "BATCH": "batch", "P/N": "pn", "S/N": "sn",
    "DESCRIPTION": "description", "AVBL": "avbl", "RSVD": "rsvd", "TRANSF": "transf",
    "R/I": "ri", "R/O": "ro", "U/S": "us", "MISSING": "missing", "ONHOLD": "onhold",
    "UOM": "uom", "CONDITION": "condition", "MAIN P/N": "main_pn", "MFG": "mfg",
    "COMPANY": "company", "PHYSICAL COUNT DATE": "physical_count_date",
}
HISTORY_EXPORT_COLUMNS = {
    "TRANSACTION NO": "transaction_no",
    "TRANSACTION TYPE": "transaction_type",
    "CREATED DATE": "created_date",
    "LOCATION": "location",
    "BIN": "bin",
    "BATCH": "batch",
    "GRB": "grb",
    "P/N": "pn",
    "S/N": "sn",
    "CONDITION": "condition",
    "QTY": "qty",
    "A/C": "ac",
    "W/O - S/O": "wo_so",
    "ISSUED TO": "issued_to",
    "ISSUED TO NAME": "issued_to_name",
    "CREATED BY": "created_by",
    "NAME": "created_name",
    "ORDE TYPE": "order_type",
    "ORDER NO": "order_no",
    "LINE": "order_line",
    "VENDOR/CUSTOMER": "vendor_customer",
    "VENDOR NAME": "vendor_name",
    "REFERENCE": "reference",
    "STATUS": "status",
    "DEFECT DESCRIPTION": "defect_description",
}
# Grid header -> field (fallback)
GRID_COLUMNS = {
    "Location": "location", "Bin": "bin", "Batch": "batch", "P/N": "pn", "S/N": "sn",
    "Avbl": "avbl", "Rsvd": "rsvd", "Transf": "transf", "R/I": "ri", "R/O": "ro",
    "U/S": "us", "Missing": "missing", "OnHold": "onhold",
}
NUMERIC = {"avbl", "rsvd", "transf", "ri", "ro", "us", "missing", "onhold"}


class FetchResult:
    def __init__(self, location: str, rows: List[Dict], method: str, expected_range: Optional[Tuple[int, int]]):
        self.location = location
        self.rows = rows
        self.method = method
        self.expected_range = expected_range  # (min,max) rows implied by eMRO paginator

    @property
    def complete(self) -> bool:
        if self.expected_range is None:
            return False
        lo, hi = self.expected_range
        return lo <= len(self.rows) <= hi


def _num(v) -> float:
    try:
        s = str(v).replace(",", "").strip()
        return float(s) if s else 0.0
    except Exception:
        return 0.0


def _clean(row: Dict) -> Dict:
    out = {}
    for k, v in row.items():
        if k in NUMERIC:
            out[k] = _num(v)
        else:
            out[k] = (str(v).strip() if v is not None else "").replace("\\n", "\n")
    return out


class InventoryFetcher:
    def __init__(self, session: EmroSession):
        self.s = session

    @property
    def p(self):
        return self.s.page

    async def open_window(self, window_name: str = WINDOW_NAME):
        """Open (or switch to) the given eMRO window tab."""
        p = self.p
        await self.s.dismiss_popups()
        tab = p.locator("ul.ui-tabs-nav li, ul.ui-tabview-nav li").filter(has_text=re.compile(rf"^\s*{re.escape(window_name)}\s*×?\s*$"))
        if await tab.count() > 0 and await tab.first.is_visible():
            await tab.first.click()
            await asyncio.sleep(1)
            return
        search = p.locator("input[placeholder*='search a window' i], input[placeholder*='Typing here' i]").first
        await search.wait_for(state="visible", timeout=15000)
        await search.fill("")
        await search.fill(window_name)
        await search.press("Enter")
        await p.get_by_text("Search results").first.wait_for(state="visible", timeout=15000)
        item = p.get_by_text(window_name, exact=True).first
        await item.wait_for(state="visible", timeout=10000)
        await item.click()
        await asyncio.sleep(2.5)
        await self.s.dismiss_popups()

    async def find_location(self, location: str):
        p = self.p
        # Find the visible Location label inside the active tab panel
        loc_id = await p.evaluate("""() => {
            const labels = Array.from(document.querySelectorAll('label, span')).filter(
                e => e.offsetParent && (e.innerText || '').trim() === 'Location'
            );
            for (const lbl of labels) {
                const forId = lbl.getAttribute('for');
                if (forId) {
                    const inp = document.getElementById(forId);
                    if (inp && inp.offsetParent) return inp.id;
                }
                const w = lbl.closest('div, td') || lbl.parentElement;
                if (w) {
                    const inp = w.querySelector('input:not([type=hidden])');
                    if (inp && inp.offsetParent) return inp.id;
                }
            }
            const fallback = Array.from(document.querySelectorAll("input[id*='location' i], input[id*='22918']")).find(e => e.offsetParent);
            return fallback ? fallback.id : '';
        }""")
        if loc_id:
            loc_input = p.locator(f"[id='{loc_id}']").first
        else:
            loc_input = p.get_by_text("Location", exact=True).first.locator("xpath=following::input[not(@type='hidden')][1]").first
        await loc_input.fill("")
        await loc_input.fill(location)
        find_btn = p.locator("a:has-text('Find'):visible, button:has-text('Find'):visible, span:text-is('Find'):visible").first
        await find_btn.click()
        for _ in range(60):
            await asyncio.sleep(0.5)
            txt = await self._paginator_text()
            if txt:
                break
        await asyncio.sleep(1.5)
        await self.s.dismiss_popups()

    async def _paginator_text(self) -> str:
        return await self.p.evaluate("""() => { const e = Array.from(document.querySelectorAll('.ui-paginator-current')).find(x => x.offsetParent); return e ? e.innerText : ''; }""")

    async def _rows_per_page(self) -> int:
        v = await self.p.evaluate("""() => { const e = Array.from(document.querySelectorAll('select.ui-paginator-rpp-options')).find(x => x.offsetParent); return e ? e.value : ''; }""")
        try:
            return int(v)
        except Exception:
            return 10

    async def expected_range(self) -> Optional[Tuple[int, int]]:
        """'(1 of 125)' with 10 rows/page -> rows in [1241, 1250]."""
        txt = await self._paginator_text()
        m = re.search(r"of\s+(\d+)", txt or "")
        if not m:
            no_rec = await self.p.get_by_text("No records found").first.is_visible()
            return (0, 0) if no_rec else None
        pages, rpp = int(m.group(1)), await self._rows_per_page()
        return ((pages - 1) * rpp + 1, pages * rpp)

    # ---------- primary: Excel export ----------
    async def export_excel(self, location: str) -> Path:
        p = self.p
        icon = p.locator("img[src*='excel' i]:visible").first
        await icon.wait_for(state="visible", timeout=15000)
        async with p.expect_download(timeout=180000) as dl_info:
            await icon.click()
        dl = await dl_info.value
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = Config.DOWNLOAD_DIR / f"{location}_{stamp}.xlsx"
        await dl.save_as(str(target))
        self._prune_exports()
        return target

    @staticmethod
    def _prune_exports():
        files = sorted(Config.DOWNLOAD_DIR.glob("*.xlsx"), key=lambda f: f.stat().st_mtime, reverse=True)
        for f in files[Config.KEEP_EXPORT_FILES:]:
            try:
                f.unlink()
            except Exception:
                pass

    @staticmethod
    def parse_export(path: Path) -> List[Dict]:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        header = [str(h).strip() if h is not None else "" for h in next(it)]
        idx = {}
        for i, h in enumerate(header):
            if h in EXPORT_COLUMNS and EXPORT_COLUMNS[h] not in idx:
                idx[EXPORT_COLUMNS[h]] = i
        missing = {"location", "pn", "bin", "avbl"} - set(idx)
        if missing:
            raise RuntimeError(f"ไฟล์ Export ไม่มีคอลัมน์ที่จำเป็น: {missing}")
        rows = []
        for r in it:
            if r is None or all(v in (None, "") for v in r):
                continue
            rec = {f: (r[i] if i < len(r) else None) for f, i in idx.items()}
            if not rec.get("pn"):
                continue
            rows.append(_clean(rec))
        wb.close()
        return rows

    @staticmethod
    def parse_history_export(path: Path) -> List[Dict]:
        """Parse an Excel file exported from 'Inventory Transaction History Query'."""
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        header = [str(h).strip() if h is not None else "" for h in next(it)]
        idx = {}
        gl_indices = []
        for i, h in enumerate(header):
            if h == "G/L":
                gl_indices.append(i)
            elif h in HISTORY_EXPORT_COLUMNS and HISTORY_EXPORT_COLUMNS[h] not in idx:
                idx[HISTORY_EXPORT_COLUMNS[h]] = i
        rows = []
        for r in it:
            if r is None or all(v in (None, "") for v in r):
                continue
            rec = {}
            for f, i in idx.items():
                val = r[i] if i < len(r) else None
                rec[f] = str(val).strip() if val is not None else ""
            # Pick longest G/L string (e.g. 'TLM / JT11520 / 40 / 994')
            gl_vals = [str(r[i]).strip() for i in gl_indices if i < len(r) and r[i] not in (None, "")]
            rec["gl"] = max(gl_vals, key=len) if gl_vals else ""
            rec["tx_datetime"] = TransactionParser.parse_created_date_iso(rec.get("created_date", ""))
            if rec.get("transaction_no") and rec.get("pn"):
                rows.append(rec)
        wb.close()
        return rows

    # ---------- fallback: page through grid ----------
    async def set_rows_per_page(self, n: int = 50):
        sel = self.p.locator("select.ui-paginator-rpp-options:visible").first
        if await sel.is_visible() and await sel.input_value() != str(n):
            await sel.select_option(str(n))
            await asyncio.sleep(3)

    async def _read_grid_page(self) -> List[Dict]:
        data = await self.p.evaluate("""() => {
            const heads = Array.from(document.querySelectorAll('thead th')).filter(e => e.offsetParent)
                .map(th => (th.querySelector('.ui-column-title') || th).innerText.trim());
            const tb = Array.from(document.querySelectorAll('tbody.ui-datatable-data')).find(e => e.offsetParent);
            if (!tb) return {heads, rows: []};
            const rows = Array.from(tb.querySelectorAll(':scope > tr'))
                .filter(tr => !tr.classList.contains('ui-expanded-row-content') && !tr.classList.contains('ui-datatable-empty-message'))
                .map(tr => Array.from(tr.querySelectorAll(':scope > td')).map(td => td.innerText.trim()));
            return {heads, rows};
        }""")
        heads = data["heads"]
        out = []
        for cells in data["rows"]:
            rec = {}
            for i, h in enumerate(heads):
                f = GRID_COLUMNS.get(h)
                if f and i < len(cells):
                    rec[f] = cells[i]
            if rec.get("pn"):
                out.append(_clean(rec))
        return out

    async def page_through(self) -> List[Dict]:
        await self.set_rows_per_page(50)
        rows: List[Dict] = []
        seen_first = set()
        for page_no in range(1, 1000):
            page_rows = await self._read_grid_page()
            sig = tuple(sorted((r.get("bin"), r.get("batch"), r.get("pn")) for r in page_rows[:3]))
            if sig in seen_first:
                break
            seen_first.add(sig)
            rows.extend(page_rows)
            nxt = self.p.locator(".ui-paginator-next:visible").first
            cls = (await nxt.get_attribute("class")) or ""
            if "ui-state-disabled" in cls:
                break
            await nxt.click()
            await asyncio.sleep(2)
        return rows

    # ---------- orchestrator ----------
    async def fetch(self, location: str, on_progress=None) -> FetchResult:
        def _prog(msg: str):
            logger.info(f"[{location}] {msg}")
            if on_progress:
                try:
                    on_progress(msg)
                except Exception:
                    pass

        _prog("กำลังเข้าสู่ระบบ eMRO...")
        await self.s.ensure_logged_in()
        _prog("กำลังเปิดหน้าต่าง Inventory Transaction...")
        await self.open_window()
        _prog(f"กำลังค้นหา Location {location}...")
        await self.find_location(location)
        exp = await self.expected_range()
        logger.info(f"[{location}] paginator expects rows in {exp}")
        if exp == (0, 0):
            return FetchResult(location, [], "export", exp)

        try:
            _prog(f"กำลังดาวน์โหลดไฟล์ Export Excel ({exp[0]}–{exp[1]} แถว)...")
            path = await self.export_excel(location)
            _prog("กำลังอ่านข้อมูลจากไฟล์ Excel...")
            rows = self.parse_export(path)
            res = FetchResult(location, rows, "export", exp)
            if res.complete:
                return res
            logger.warning(f"[{location}] export row count {len(rows)} outside {exp}; trying paging fallback")
        except Exception as e:
            logger.warning(f"[{location}] export failed: {e}; trying paging fallback")
            await self.s.screenshot(f"export_fail_{location}")

        _prog("สลับไปใช้วิธีอ่านตารางทีละหน้า (50 แถว/หน้า)...")
        rows = await self.page_through()
        exp50 = await self.expected_range()  # recompute with rpp=50
        return FetchResult(location, rows, "paging", exp50 or exp)

    # ---------- Inventory Transaction History Query ----------
    async def fetch_transaction_history(
        self,
        location: str,
        min_date_iso: str,
        known_tx_nos: Optional[set] = None,
        on_progress=None,
        max_pages: int = 10,
    ) -> List[Dict]:
        """Open 'Inventory Transaction History Query', search location, and extract recent transactions."""
        def _prog(msg: str):
            logger.info(f"[{location} History] {msg}")
            if on_progress:
                try:
                    on_progress(msg)
                except Exception:
                    pass

        known = known_tx_nos or set()
        await self.s.ensure_logged_in()
        _prog("กำลังเปิดหน้าต่าง Inventory Transaction History Query...")
        await self.open_window(WINDOW_HISTORY_NAME)

        # Primary: Date Range (last 14 days) + Excel Export (all 54 columns in 1 file)
        try:
            p = self.p
            loc_input = p.get_by_text("Location", exact=True).first.locator("xpath=following::input[not(@type='hidden')][1]").first
            await loc_input.fill("")
            await loc_input.fill(location)

            await p.get_by_text("Date Range", exact=True).first.click()
            await asyncio.sleep(1.0)
            from_str = (datetime.now() - timedelta(days=14)).strftime("%m/%d/%Y")
            to_str = datetime.now().strftime("%m/%d/%Y")
            from_inp = p.get_by_text("From Date", exact=True).first.locator("xpath=following::input[not(@type='hidden')][1]").first
            to_inp = p.get_by_text("To Date", exact=True).first.locator("xpath=following::input[not(@type='hidden')][1]").first
            await from_inp.fill("")
            await from_inp.fill(from_str)
            await from_inp.press("Tab")
            await to_inp.fill("")
            await to_inp.fill(to_str)
            await to_inp.press("Tab")
            await asyncio.sleep(0.3)

            _prog(f"กำลังค้นหาประวัติการตัดของ Location {location} ({from_str} – {to_str})...")
            find_btn = p.locator("a:has-text('Find'):visible, button:has-text('Find'):visible, span:text-is('Find'):visible").first
            await find_btn.click()
            for _ in range(40):
                await asyncio.sleep(0.5)
                txt = await self._paginator_text()
                if txt and txt != "(1 of 1)":
                    break
            await asyncio.sleep(1.2)
            _prog("กำลังดาวน์โหลดไฟล์ Export ประวัติการตัดของ (Excel)...")
            out_path = await self.export_excel(f"{location}_HIST")
            rows = self.parse_history_export(out_path)
            if rows:
                logger.info(f"[{location} History] Exported {len(rows)} transaction records via Excel.")
                return rows
        except Exception as e:
            logger.warning(f"[{location} History] Excel export failed ({e}), falling back to grid expansion")

        # Fallback: Grid row expansion
        _prog(f"กำลังค้นหาประวัติการตัดของ Location {location} (โหมดตาราง)...")
        await self.find_location(location)
        await self.set_rows_per_page(50)

        collected: List[Dict] = []
        stop_early = False

        for page_no in range(1, max_pages + 1):
            _prog(f"กำลังอ่านประวัติการตัดของ หน้าที่ {page_no}...")
            page_records, reached_cutoff = await self._extract_history_page_rows(min_date_iso, known)
            collected.extend(page_records)
            if reached_cutoff:
                stop_early = True
                break

            nxt = self.p.locator(".ui-paginator-next:visible").first
            if not await nxt.is_visible():
                break
            cls = (await nxt.get_attribute("class")) or ""
            if "ui-state-disabled" in cls:
                break
            await nxt.click()
            await asyncio.sleep(2.5)

        logger.info(f"[{location} History] Extracted {len(collected)} transaction records (stop_early={stop_early}).")
        return collected

    async def _extract_history_page_rows(self, min_date_iso: str, known_tx_nos: set) -> Tuple[List[Dict], bool]:
        """Expand visible rows in Inventory Transaction History Query and stop when hitting old/known records."""
        results: List[Dict] = []
        consecutive_old_or_known = 0

        rows = await self.p.query_selector_all(
            "div.ui-tabs-panel:not(.ui-helper-hidden) tbody[id*='dw_inventory'] tr:not(.ui-expanded-row-content), "
            "div.ui-tabview-panel:not(.ui-helper-hidden) tbody.ui-datatable-data tr:not(.ui-expanded-row-content)"
        )
        if not rows:
            rows = await self.p.query_selector_all("tbody.ui-datatable-data tr:not(.ui-expanded-row-content)")

        visible_rows = []
        for r in rows:
            try:
                if await r.is_visible():
                    visible_rows.append(r)
            except Exception:
                pass

        for row in visible_rows:
            try:
                cells_text = await row.evaluate("el => Array.from(el.querySelectorAll('td')).map(td => td.innerText.trim())")
                if not any(cells_text):
                    continue
                joined = " ".join(cells_text).upper()
                if not any(kw in joined for kw in ["ISSUED", "RECEIVING", "TRANSFER", "RTS", "PO", "BIN", "ADJUST", "RETURN"]):
                    continue

                expanded_html = await row.evaluate("""el => {
                    const next = el.nextElementSibling;
                    if (next && (next.classList.contains('ui-expanded-row-content') ||
                                 next.classList.contains('ui-expanded-row-expansion') ||
                                 next.querySelector('.ui-expanded-row-content'))) {
                        return next.innerHTML;
                    }
                    return '';
                }""")

                if not expanded_html:
                    toggler = await row.query_selector(
                        ".ui-row-toggler, [class*='toggler'], td:nth-child(2) button, td:nth-child(2) a, td:nth-child(2)"
                    )
                    if toggler:
                        try:
                            await toggler.click()
                            for _ in range(10):
                                await asyncio.sleep(0.15)
                                expanded_html = await row.evaluate("""el => {
                                    const next = el.nextElementSibling;
                                    if (next && (next.classList.contains('ui-expanded-row-content') ||
                                                 next.classList.contains('ui-expanded-row-expansion') ||
                                                 next.querySelector('.ui-expanded-row-content'))) {
                                        return next.innerHTML;
                                    }
                                    return '';
                                }""")
                                if expanded_html:
                                    break
                        except Exception:
                            pass

                parsed = TransactionParser.parse_transaction_row(cells_text, expanded_html if expanded_html else None)
                tno = parsed.get("transaction_no") or ""
                tx_dt = parsed.get("tx_datetime") or ""

                is_old = bool(min_date_iso and tx_dt and tx_dt < min_date_iso)
                is_known = bool(tno and tno in known_tx_nos)

                if not is_old and tno:
                    results.append(parsed)

                if is_old or is_known:
                    consecutive_old_or_known += 1
                    if consecutive_old_or_known >= 3:
                        return results, True
                else:
                    consecutive_old_or_known = 0
            except Exception as e:
                logger.warning(f"History row parse note: {e}")

        return results, False
