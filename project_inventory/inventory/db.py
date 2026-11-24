"""SQLite store: current snapshot (items), change log (changes), sync audit (sync_runs)."""
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional

from inventory.config import Config

_lock = threading.Lock()

KEY_FIELDS = ("location", "bin", "batch", "pn", "sn")
QTY_FIELDS = ("avbl", "rsvd", "transf", "ri", "ro", "us", "missing", "onhold")
INFO_FIELDS = ("description", "uom", "condition", "main_pn", "mfg", "company", "physical_count_date")
TRACKED = ("avbl", "rsvd", "us", "onhold")  # fields whose changes are logged

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location TEXT NOT NULL, bin TEXT NOT NULL DEFAULT '', batch TEXT NOT NULL DEFAULT '',
    pn TEXT NOT NULL, sn TEXT NOT NULL DEFAULT '',
    description TEXT DEFAULT '', uom TEXT DEFAULT '', condition TEXT DEFAULT '', main_pn TEXT DEFAULT '',
    mfg TEXT DEFAULT '', company TEXT DEFAULT '', physical_count_date TEXT DEFAULT '',
    avbl REAL DEFAULT 0, rsvd REAL DEFAULT 0, transf REAL DEFAULT 0, ri REAL DEFAULT 0, ro REAL DEFAULT 0,
    us REAL DEFAULT 0, missing REAL DEFAULT 0, onhold REAL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'IN_STOCK',
    first_seen TEXT, last_seen TEXT, out_since TEXT,
    UNIQUE(location, bin, batch, pn, sn)
);
CREATE INDEX IF NOT EXISTS ix_items_pn ON items(pn);
CREATE INDEX IF NOT EXISTS ix_items_status ON items(location, status);

-- Description per P/N (kept even when the paging fallback has no description column)
CREATE TABLE IF NOT EXISTS parts (
    pn TEXT PRIMARY KEY, description TEXT DEFAULT '', uom TEXT DEFAULT '', updated_at TEXT
);

CREATE TABLE IF NOT EXISTS changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL, sync_id INTEGER,
    event TEXT NOT NULL,            -- NEW | CHANGE | OUT | BACK
    field TEXT, old_value TEXT, new_value TEXT,
    changed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_changes_item ON changes(item_id);
CREATE INDEX IF NOT EXISTS ix_changes_time ON changes(changed_at);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location TEXT, started_at TEXT, finished_at TEXT, method TEXT,
    row_count INTEGER, expected TEXT, status TEXT, message TEXT,
    added INTEGER DEFAULT 0, changed INTEGER DEFAULT 0, removed INTEGER DEFAULT 0, triggered_by TEXT
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY, value TEXT
);

CREATE TABLE IF NOT EXISTS tx_history (
    transaction_no TEXT PRIMARY KEY,
    transaction_type TEXT DEFAULT '',
    created_date TEXT DEFAULT '',
    tx_datetime TEXT DEFAULT '',
    location TEXT DEFAULT '',
    bin TEXT DEFAULT '',
    batch TEXT DEFAULT '',
    grb TEXT DEFAULT '',
    pn TEXT NOT NULL DEFAULT '',
    sn TEXT DEFAULT '',
    condition TEXT DEFAULT '',
    qty REAL DEFAULT 0,
    ac TEXT DEFAULT '',
    wo_so TEXT DEFAULT '',
    issued_to TEXT DEFAULT '',
    issued_to_name TEXT DEFAULT '',
    created_by TEXT DEFAULT '',
    created_name TEXT DEFAULT '',
    order_type TEXT DEFAULT '',
    order_no TEXT DEFAULT '',
    order_line TEXT DEFAULT '',
    vendor_customer TEXT DEFAULT '',
    vendor_name TEXT DEFAULT '',
    reference TEXT DEFAULT '',
    status TEXT DEFAULT '',
    gl TEXT DEFAULT '',
    defect_description TEXT DEFAULT '',
    synced_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_tx_pn ON tx_history(location, pn);
CREATE INDEX IF NOT EXISTS ix_tx_dt ON tx_history(tx_datetime DESC);
CREATE INDEX IF NOT EXISTS ix_tx_ac ON tx_history(ac);
CREATE INDEX IF NOT EXISTS ix_tx_wo ON tx_history(wo_so);
"""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def connect():
    Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(Config.DB_FILE, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    today_start = datetime.now().strftime("%Y-%m-%d 00:00:00")
    with connect() as con:
        con.executescript(SCHEMA)
        con.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('tx_start_date', ?)", (today_start,))


def get_tx_start_date() -> str:
    with connect() as con:
        row = con.execute("SELECT value FROM meta WHERE key='tx_start_date'").fetchone()
        return row["value"] if row and row["value"] else datetime.now().strftime("%Y-%m-%d 00:00:00")


def get_known_tx_nos(location: Optional[str] = None) -> set:
    with connect() as con:
        if location:
            rows = con.execute("SELECT transaction_no FROM tx_history WHERE location=?", (location.upper(),)).fetchall()
        else:
            rows = con.execute("SELECT transaction_no FROM tx_history").fetchall()
        return {r["transaction_no"] for r in rows if r["transaction_no"]}


def _fmt(v) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def record_failed_run(location: str, started: str, method: str, row_count: int, expected, message: str, triggered_by: str):
    with _lock, connect() as con:
        con.execute(
            "INSERT INTO sync_runs(location, started_at, finished_at, method, row_count, expected, status, message, triggered_by)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (location, started, now(), method, row_count, str(expected), "FAILED", message, triggered_by))


def apply_snapshot(location: str, rows: List[Dict], method: str, expected, started: str, triggered_by: str = "schedule") -> Dict:
    """Upsert a COMPLETE snapshot. Items not present are marked OUT (never deleted)."""
    ts = now()
    with _lock, connect() as con:
        prev_in = con.execute("SELECT COUNT(*) FROM items WHERE location=? AND status='IN_STOCK'", (location,)).fetchone()[0]
        if prev_in > 50 and len(rows) < prev_in * (1 - Config.MAX_DROP_RATIO):
            msg = f"จำนวนแถวลดลงผิดปกติ ({prev_in} → {len(rows)}) ยกเลิกรอบนี้เพื่อป้องกันการตั้งค่าหมดผิดพลาด"
            con.execute(
                "INSERT INTO sync_runs(location, started_at, finished_at, method, row_count, expected, status, message, triggered_by)"
                " VALUES (?,?,?,?,?,?,?,?,?)", (location, started, ts, method, len(rows), str(expected), "ABORTED", msg, triggered_by))
            return {"status": "ABORTED", "message": msg}

        cur = con.execute(
            "INSERT INTO sync_runs(location, started_at, method, row_count, expected, status, triggered_by) VALUES (?,?,?,?,?,?,?)",
            (location, started, method, len(rows), str(expected), "RUNNING", triggered_by))
        sync_id = cur.lastrowid

        existing = {}
        for r in con.execute("SELECT * FROM items WHERE location=?", (location,)):
            existing[tuple(r[k] for k in KEY_FIELDS)] = dict(r)

        # Merge duplicate keys inside one snapshot (sum quantities)
        merged: Dict[tuple, Dict] = {}
        for row in rows:
            row = dict(row)
            row["location"] = (row.get("location") or location).upper()
            for k in KEY_FIELDS:
                row[k] = (row.get(k) or "").strip()
            key = tuple(row[k] for k in KEY_FIELDS)
            if key in merged:
                for q in QTY_FIELDS:
                    merged[key][q] = merged[key].get(q, 0) + row.get(q, 0)
            else:
                merged[key] = row

        added = changed = removed = 0
        changes = []
        for key, row in merged.items():
            # parts table (description per P/N)
            if row.get("description"):
                con.execute(
                    "INSERT INTO parts(pn, description, uom, updated_at) VALUES (?,?,?,?) "
                    "ON CONFLICT(pn) DO UPDATE SET description=excluded.description, uom=excluded.uom, updated_at=excluded.updated_at",
                    (row["pn"], row["description"], row.get("uom", ""), ts))

            old = existing.pop(key, None)
            if old is None:
                cols = list(KEY_FIELDS) + [f for f in INFO_FIELDS if row.get(f)] + list(QTY_FIELDS)
                vals = [row.get(c, 0 if c in QTY_FIELDS else "") for c in cols]
                cols += ["status", "first_seen", "last_seen"]
                vals += ["IN_STOCK", ts, ts]
                c = con.execute(f"INSERT INTO items({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)
                changes.append((c.lastrowid, sync_id, "NEW", "avbl", "", _fmt(row.get("avbl", 0)), ts))
                added += 1
                continue

            sets, params = [], []
            if old["status"] == "OUT":
                sets += ["status='IN_STOCK'", "out_since=NULL"]
                changes.append((old["id"], sync_id, "BACK", "avbl", "0", _fmt(row.get("avbl", 0)), ts))
                changed += 1
            for q in QTY_FIELDS:
                nv = row.get(q, 0)
                if float(old[q] or 0) != float(nv):
                    sets.append(f"{q}=?")
                    params.append(nv)
                    if q in TRACKED and old["status"] != "OUT":
                        changes.append((old["id"], sync_id, "CHANGE", q, _fmt(old[q] or 0), _fmt(nv), ts))
            if any(c[0] == old["id"] and c[2] == "CHANGE" for c in changes[-len(TRACKED):]):
                changed += 1
            for f in INFO_FIELDS:
                if row.get(f) and row[f] != old[f]:
                    sets.append(f"{f}=?")
                    params.append(row[f])
            sets.append("last_seen=?")
            params.append(ts)
            con.execute(f"UPDATE items SET {', '.join(sets)} WHERE id=?", params + [old["id"]])

        # Rows that disappeared from eMRO -> OUT (eMRO hides zero-stock records)
        for old in existing.values():
            if old["status"] == "IN_STOCK":
                con.execute("UPDATE items SET status='OUT', out_since=?, avbl=0, rsvd=0 WHERE id=?", (ts, old["id"]))
                changes.append((old["id"], sync_id, "OUT", "avbl", _fmt(old["avbl"] or 0), "0", ts))
                removed += 1

        con.executemany(
            "INSERT INTO changes(item_id, sync_id, event, field, old_value, new_value, changed_at) VALUES (?,?,?,?,?,?,?)", changes)
        con.execute("UPDATE sync_runs SET finished_at=?, status='OK', added=?, changed=?, removed=? WHERE id=?",
                    (now(), added, changed, removed, sync_id))
        return {"status": "OK", "added": added, "changed": changed, "removed": removed, "rows": len(merged)}


# ---------------- queries ----------------

def _nat_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s or ""))]


def search(
    q: str = "",
    status: str = "all",
    location: Optional[str] = None,
    limit: int = 2000,
    sort_by: str = "pn",
    sort_dir: str = "asc",
) -> Dict:
    """Return P/N groups. status: all | in | out (out = P/N with no stock left)."""
    where, params = [], []
    if location:
        where.append("i.location=?")
        params.append(location)
    terms = [t for t in (q or "").strip().split() if t]
    for t in terms:
        like = f"%{t}%"
        where.append("(i.pn LIKE ? OR i.sn LIKE ? OR i.bin LIKE ? OR i.batch LIKE ? OR COALESCE(NULLIF(i.description,''), p.description, '') LIKE ? OR i.main_pn LIKE ?)")
        params += [like] * 6
    sql = ("SELECT i.*, COALESCE(NULLIF(i.description,''), p.description, '') AS desc_full FROM items i "
           "LEFT JOIN parts p ON p.pn=i.pn" + (" WHERE " + " AND ".join(where) if where else "") +
           " ORDER BY i.pn, i.status, i.bin")
    with connect() as con:
        rows = [dict(r) for r in con.execute(sql, params)]

    groups: Dict[tuple, Dict] = {}
    for r in rows:
        k = (r["location"], r["pn"])
        g = groups.setdefault(k, {"location": r["location"], "pn": r["pn"], "description": r["desc_full"],
                                  "uom": r["uom"], "total_avbl": 0, "total_rsvd": 0, "rows": [], "out_rows": [],
                                  "last_seen": r["last_seen"], "out_since": None})
        if not g["description"] and r["desc_full"]:
            g["description"] = r["desc_full"]
        if r["status"] == "IN_STOCK":
            g["total_avbl"] += r["avbl"] or 0
            g["total_rsvd"] += r["rsvd"] or 0
            g["rows"].append(r)
        else:
            g["out_rows"].append(r)
            if r["out_since"] and (g["out_since"] is None or r["out_since"] > g["out_since"]):
                g["out_since"] = r["out_since"]
        if r["last_seen"] and r["last_seen"] > (g["last_seen"] or ""):
            g["last_seen"] = r["last_seen"]

    result = []
    for g in groups.values():
        g["status"] = "IN_STOCK" if g["rows"] else "OUT"
        if g["status"] == "IN_STOCK":
            g["out_since"] = None
            g["primary_bin"] = g["rows"][0]["bin"] if g["rows"] else ""
        if status == "in" and g["status"] != "IN_STOCK":
            continue
        if status == "out" and g["status"] != "OUT":
            continue
        if g["status"] == "OUT":
            last = max(g["out_rows"], key=lambda x: x["out_since"] or "")
            g["last_bin"] = last["bin"]
            g["primary_bin"] = last["bin"] or ""
        result.append(g)

    reverse = (sort_dir or "asc").lower() == "desc"
    sb = (sort_by or "pn").lower()
    if sb == "avbl":
        result.sort(key=lambda g: (float(g["total_avbl"] or 0), _nat_key(g["pn"])), reverse=reverse)
    elif sb == "description":
        result.sort(key=lambda g: (_nat_key(g.get("description") or ""), _nat_key(g["pn"])), reverse=reverse)
    elif sb == "bin":
        result.sort(key=lambda g: (_nat_key(g.get("primary_bin") or ""), _nat_key(g["pn"])), reverse=reverse)
    elif sb == "status":
        result.sort(key=lambda g: (0 if g["status"] == "IN_STOCK" else 1, _nat_key(g["pn"])), reverse=reverse)
    else:
        result.sort(key=lambda g: _nat_key(g["pn"]), reverse=reverse)

    return {"total": len(result), "items": result[:limit]}


def item_history(location: str, pn: str) -> List[Dict]:
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT c.*, i.bin, i.batch, i.sn FROM changes c JOIN items i ON i.id=c.item_id "
            "WHERE i.location=? AND i.pn=? ORDER BY c.changed_at DESC, c.id DESC LIMIT 200", (location, pn))]


def item_transactions(location: str, pn: str) -> List[Dict]:
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT t.*, COALESCE(p.description, '') AS description, COALESCE(p.uom, '') AS uom "
            "FROM tx_history t LEFT JOIN parts p ON p.pn=t.pn "
            "WHERE t.location=? AND t.pn=? ORDER BY t.tx_datetime DESC, t.transaction_no DESC LIMIT 200",
            (location.upper(), pn),
        )]


def save_transactions(rows: List[Dict], location: str = "DM01", min_date_iso: Optional[str] = None) -> Dict:
    """Upsert transactions from 'Inventory Transaction History Query' on or after min_date_iso."""
    cutoff = min_date_iso if min_date_iso is not None else get_tx_start_date()
    ts = now()
    added = updated = skipped_old = 0
    with _lock, connect() as con:
        for r in rows:
            tno = str(r.get("transaction_no") or "").strip()
            pn = str(r.get("pn") or "").strip()
            if not tno or not pn:
                continue
            tx_dt = str(r.get("tx_datetime") or "").strip()
            if cutoff and tx_dt and tx_dt < cutoff:
                skipped_old += 1
                continue
            try:
                qty_val = float(str(r.get("qty") or "0").replace(",", "").strip() or 0)
            except Exception:
                qty_val = 0.0
            loc = (str(r.get("location") or location).strip() or location).upper()
            ex = con.execute("SELECT transaction_no FROM tx_history WHERE transaction_no=?", (tno,)).fetchone()
            con.execute(
                """INSERT INTO tx_history(
                    transaction_no, transaction_type, created_date, tx_datetime, location, bin, batch, grb,
                    pn, sn, condition, qty, ac, wo_so, issued_to, issued_to_name, created_by, created_name,
                    order_type, order_no, order_line, vendor_customer, vendor_name, reference, status, gl,
                    defect_description, synced_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(transaction_no) DO UPDATE SET
                    status=excluded.status, qty=excluded.qty, ac=excluded.ac, wo_so=excluded.wo_so,
                    issued_to=excluded.issued_to, issued_to_name=excluded.issued_to_name,
                    created_by=excluded.created_by, created_name=excluded.created_name,
                    synced_at=excluded.synced_at""",
                (
                    tno,
                    str(r.get("transaction_type") or "").strip(),
                    str(r.get("created_date") or "").strip(),
                    tx_dt,
                    loc,
                    str(r.get("bin") or "").strip(),
                    str(r.get("batch") or "").strip(),
                    str(r.get("grb") or "").strip(),
                    pn,
                    str(r.get("sn") or "").strip(),
                    str(r.get("condition") or "").strip(),
                    qty_val,
                    str(r.get("ac") or "").strip(),
                    str(r.get("wo_so") or "").strip(),
                    str(r.get("issued_to") or "").strip(),
                    str(r.get("issued_to_name") or "").strip(),
                    str(r.get("created_by") or "").strip(),
                    str(r.get("created_name") or "").strip(),
                    str(r.get("order_type") or "").strip(),
                    str(r.get("order_no") or "").strip(),
                    str(r.get("order_line") or "").strip(),
                    str(r.get("vendor_customer") or "").strip(),
                    str(r.get("vendor_name") or "").strip(),
                    str(r.get("reference") or "").strip(),
                    str(r.get("status") or "").strip(),
                    str(r.get("gl") or "").strip(),
                    str(r.get("defect_description") or "").strip(),
                    ts,
                ),
            )
            if ex:
                updated += 1
            else:
                added += 1
        _backfill_out_items_from_tx_history(con, location.upper(), ts)
    return {"added": added, "updated": updated, "skipped_old": skipped_old}


def _backfill_out_items_from_tx_history(con: sqlite3.Connection, location: str, ts: str):
    """Ensure any P/N present in tx_history but missing from items is registered as OUT (avbl=0)."""
    existing_pns = {
        r["pn"] for r in con.execute("SELECT DISTINCT pn FROM items WHERE location=?", (location,)).fetchall()
    }
    rows = con.execute(
        """SELECT pn, bin, batch, sn, condition, MAX(tx_datetime) AS last_dt, MIN(tx_datetime) AS first_dt
           FROM tx_history
           WHERE location=? AND pn != ''
           GROUP BY pn""",
        (location,),
    ).fetchall()
    for r in rows:
        pn = r["pn"]
        if pn in existing_pns:
            continue
        con.execute(
            """INSERT OR IGNORE INTO items(
                location, bin, batch, pn, sn, condition, avbl, status, first_seen, last_seen, out_since
            ) VALUES (?,?,?,?,?,?,0,'OUT',?,?,?)""",
            (
                location,
                r["bin"] or "",
                r["batch"] or "",
                pn,
                r["sn"] or "",
                r["condition"] or "",
                r["first_dt"] or ts,
                r["last_dt"] or ts,
                r["last_dt"] or ts,
            ),
        )


def search_transactions(
    q: str = "",
    tx_type: str = "all",
    since: Optional[str] = None,
    location: Optional[str] = None,
    sort_by: str = "tx_datetime",
    sort_dir: str = "desc",
    limit: int = 1000,
) -> Dict:
    where, params = [], []
    if location:
        where.append("t.location=?")
        params.append(location.upper())
    if since:
        where.append("t.tx_datetime>=?")
        params.append(since)
    tt = (tx_type or "all").strip().upper()
    if tt == "ISSUED":
        where.append("UPPER(t.transaction_type) LIKE '%ISSUED%'")
    elif tt == "RECEIVING":
        where.append("(UPPER(t.transaction_type) LIKE '%RECEIV%' OR UPPER(t.transaction_type) LIKE '%INITIAL%')")
    elif tt == "OTHER":
        where.append("UPPER(t.transaction_type) NOT LIKE '%ISSUED%' AND UPPER(t.transaction_type) NOT LIKE '%RECEIV%'")

    for term in [x for x in (q or "").strip().split() if x]:
        like = f"%{term}%"
        where.append(
            "(t.pn LIKE ? OR COALESCE(p.description,'') LIKE ? OR t.ac LIKE ? OR t.wo_so LIKE ? "
            "OR t.issued_to LIKE ? OR t.issued_to_name LIKE ? OR t.created_by LIKE ? OR t.created_name LIKE ? "
            "OR t.bin LIKE ? OR t.batch LIKE ? OR t.transaction_no LIKE ?)"
        )
        params += [like] * 11

    sql = (
        "SELECT t.*, COALESCE(p.description, '') AS description, COALESCE(p.uom, '') AS uom "
        "FROM tx_history t LEFT JOIN parts p ON p.pn=t.pn"
        + (" WHERE " + " AND ".join(where) if where else "")
        + " ORDER BY t.tx_datetime DESC, t.transaction_no DESC"
    )
    with connect() as con:
        rows = [dict(r) for r in con.execute(sql, params)]

    reverse = (sort_dir or "desc").lower() == "desc"
    sb = (sort_by or "tx_datetime").lower()
    if sb == "qty":
        rows.sort(key=lambda r: (float(r.get("qty") or 0), r.get("tx_datetime") or ""), reverse=reverse)
    elif sb == "pn":
        rows.sort(key=lambda r: (_nat_key(r.get("pn") or ""), r.get("tx_datetime") or ""), reverse=reverse)
    elif sb == "ac":
        rows.sort(key=lambda r: (_nat_key(r.get("ac") or ""), r.get("tx_datetime") or ""), reverse=reverse)
    elif sb == "wo_so":
        rows.sort(key=lambda r: (_nat_key(r.get("wo_so") or ""), r.get("tx_datetime") or ""), reverse=reverse)
    elif sb == "issued_to":
        rows.sort(key=lambda r: (_nat_key(r.get("issued_to_name") or r.get("issued_to") or ""), r.get("tx_datetime") or ""), reverse=reverse)
    elif sb == "transaction_type":
        rows.sort(key=lambda r: (r.get("transaction_type") or "", r.get("tx_datetime") or ""), reverse=reverse)
    else:
        rows.sort(key=lambda r: (r.get("tx_datetime") or "", r.get("transaction_no") or ""), reverse=reverse)

    return {"total": len(rows), "items": rows[:limit], "tx_start_date": get_tx_start_date()}


def changes_since(since: str, location: Optional[str] = None) -> List[Dict]:
    sql = ("SELECT c.*, i.location, i.bin, i.batch, i.pn, i.sn, COALESCE(NULLIF(i.description,''), p.description, '') AS description "
           "FROM changes c JOIN items i ON i.id=c.item_id LEFT JOIN parts p ON p.pn=i.pn "
           "WHERE c.changed_at>=? AND NOT (c.event='NEW' AND c.sync_id=(SELECT MIN(id) FROM sync_runs WHERE status='OK' AND location=i.location))")
    params = [since]
    if location:
        sql += " AND i.location=?"
        params.append(location)
    sql += " ORDER BY c.changed_at DESC, c.id DESC LIMIT 1000"
    with connect() as con:
        return [dict(r) for r in con.execute(sql, params)]


def status_summary() -> Dict:
    today_start = datetime.now().strftime("%Y-%m-%d 00:00:00")
    with connect() as con:
        last_ok = con.execute("SELECT * FROM sync_runs WHERE status='OK' ORDER BY id DESC LIMIT 1").fetchone()
        last_any = con.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
        counts_row = con.execute(
            "SELECT COALESCE(SUM(status='IN_STOCK'), 0) AS in_rows,"
            " COUNT(DISTINCT CASE WHEN status='IN_STOCK' THEN pn END) AS in_pns,"
            " COUNT(DISTINCT pn) AS all_pns FROM items").fetchone()
        counts = dict(counts_row) if counts_row else {"in_rows": 0, "in_pns": 0, "all_pns": 0}
        counts["out_pns"] = max(0, (counts.get("all_pns") or 0) - (counts.get("in_pns") or 0))
        today_chg = con.execute(
            "SELECT COUNT(*) FROM changes c JOIN items i ON i.id=c.item_id "
            "WHERE c.changed_at>=? AND NOT (c.event='NEW' AND c.sync_id=(SELECT MIN(id) FROM sync_runs WHERE status='OK' AND location=i.location))",
            (today_start,),
        ).fetchone()[0]
        counts["today_changes"] = today_chg
        tx_today = con.execute("SELECT COUNT(*) FROM tx_history WHERE tx_datetime>=?", (today_start,)).fetchone()[0]
        tx_total = con.execute("SELECT COUNT(*) FROM tx_history").fetchone()[0]
        counts["tx_today"] = tx_today
        counts["tx_total"] = tx_total
        runs = [dict(r) for r in con.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 10")]
    return {"last_ok": dict(last_ok) if last_ok else None, "last_run": dict(last_any) if last_any else None,
            "counts": counts, "recent_runs": runs, "tx_start_date": get_tx_start_date()}


def export_rows(q: str = "", status: str = "all", sort_by: str = "pn", sort_dir: str = "asc") -> List[Dict]:
    data = search(q, status, limit=100000, sort_by=sort_by, sort_dir=sort_dir)["items"]
    out = []
    for g in data:
        if g["rows"]:
            for r in g["rows"]:
                out.append({"Location": r["location"], "P/N": r["pn"], "Description": g["description"], "Bin": r["bin"],
                            "Batch": r["batch"], "S/N": r["sn"], "Avbl": r["avbl"], "Rsvd": r["rsvd"], "UOM": r["uom"],
                            "Status": "มีของ", "Last Seen": r["last_seen"], "Out Since": ""})
        else:
            out.append({"Location": g["location"], "P/N": g["pn"], "Description": g["description"], "Bin": g.get("last_bin", ""),
                        "Batch": "", "S/N": "", "Avbl": 0, "Rsvd": 0, "UOM": g["uom"], "Status": "หมด",
                        "Last Seen": g["last_seen"], "Out Since": g["out_since"] or ""})
    return out
