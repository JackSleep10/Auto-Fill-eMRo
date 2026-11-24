"""Background scheduler (every 30 min during 06:00–22:00) + manual sync runner."""
import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from inventory import db
from inventory.config import Config
from inventory.emro_session import EmroSession
from inventory.fetcher import InventoryFetcher

logger = logging.getLogger("SyncWorker")

_sync_lock = threading.Lock()

SYNC_STATE: Dict[str, Optional[object]] = {
    "running": False,
    "progress": "พร้อมทำงาน",
    "last_error": None,
    "last_started": None,
    "last_finished": None,
    "last_result": None,
}


def set_progress(msg: str):
    SYNC_STATE["progress"] = msg


def get_sync_state() -> Dict:
    return dict(SYNC_STATE)


def seed_from_existing_export_if_empty() -> bool:
    """If the DB has 0 items and an export xlsx exists on disk, import it immediately."""
    summary = db.status_summary()
    if (summary.get("counts") or {}).get("all_pns", 0):
        return False

    candidates = sorted(
        list(Config.DOWNLOAD_DIR.glob("*.xlsx")) + list((Config.DATA_DIR / "explore").glob("*.xlsx")),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    for xlsx in candidates:
        try:
            rows = InventoryFetcher.parse_export(xlsx)
            if rows:
                loc = (rows[0].get("location") or Config.LOCATIONS[0]).upper()
                started = datetime.fromtimestamp(xlsx.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                res = db.apply_snapshot(loc, rows, "export", (len(rows), len(rows)), started, triggered_by="initial-seed")
                logger.info(f"Seeded DB from {xlsx.name}: {res}")
                return True
        except Exception as e:
            logger.warning(f"Failed seeding from {xlsx}: {e}")
    return False


async def _sync_all_async(triggered_by: str) -> Dict:
    session = EmroSession(user=Config.INVENTORY_USER, headless=Config.HEADLESS)
    results = {}
    try:
        fetcher = InventoryFetcher(session)
        for loc in Config.LOCATIONS:
            started = db.now()
            set_progress(f"[{loc}] กำลังเชื่อมต่อ eMRO...")
            try:
                res = await fetcher.fetch(loc, on_progress=lambda m, l=loc: set_progress(f"[{l}] {m}"))
                if not res.complete:
                    msg = f"ดึงข้อมูลไม่ครบ ({len(res.rows)} แถว จากที่คาดไว้ {res.expected_range}) — ยกเลิกเพื่อความปลอดภัย"
                    db.record_failed_run(loc, started, res.method, len(res.rows), res.expected_range, msg, triggered_by)
                    results[loc] = {"status": "FAILED", "message": msg}
                    SYNC_STATE["last_error"] = msg
                    continue

                set_progress(f"[{loc}] กำลังบันทึก {len(res.rows)} แถวลงฐานข้อมูล SQLite...")
                applied = db.apply_snapshot(loc, res.rows, res.method, res.expected_range, started, triggered_by=triggered_by)

                # Step 2: Fetch Inventory Transaction History Query in the same browser session
                try:
                    min_dt = db.get_tx_start_date()
                    known_nos = db.get_known_tx_nos(loc)
                    tx_rows = await fetcher.fetch_transaction_history(
                        loc,
                        min_date_iso=min_dt,
                        known_tx_nos=known_nos,
                        on_progress=lambda m, l=loc: set_progress(f"[{l}] {m}"),
                    )
                    tx_saved = db.save_transactions(tx_rows, location=loc, min_date_iso="")
                    applied["tx_history"] = tx_saved
                    logger.info(f"[{loc}] Saved transaction history: {tx_saved}")
                except Exception as tx_err:
                    logger.warning(f"[{loc}] Transaction history fetch warning: {tx_err}")
                    applied["tx_history_error"] = str(tx_err)

                results[loc] = applied
                if applied.get("status") != "OK":
                    SYNC_STATE["last_error"] = applied.get("message")
                else:
                    SYNC_STATE["last_error"] = None
            except Exception as e:
                logger.exception(f"Sync failed for {loc}")
                err_msg = str(e)
                db.record_failed_run(loc, started, "export", 0, None, err_msg, triggered_by)
                results[loc] = {"status": "FAILED", "message": err_msg}
                SYNC_STATE["last_error"] = err_msg
    finally:
        await session.close()
    return results


def run_sync_blocking(triggered_by: str = "manual") -> Dict:
    if not _sync_lock.acquire(blocking=False):
        return {"status": "BUSY", "message": "กำลังดึงข้อมูลอยู่ กรุณารอสักครู่"}

    SYNC_STATE["running"] = True
    SYNC_STATE["last_started"] = db.now()
    SYNC_STATE["progress"] = "เริ่มต้นการดึงข้อมูล..."
    try:
        res = asyncio.run(_sync_all_async(triggered_by))
        SYNC_STATE["last_result"] = res
        SYNC_STATE["last_finished"] = db.now()
        if not SYNC_STATE["last_error"]:
            SYNC_STATE["progress"] = "อัปเดตข้อมูลสำเร็จเรียบร้อย"
        else:
            SYNC_STATE["progress"] = f"เสร็จสิ้นพร้อมข้อผิดพลาด: {SYNC_STATE['last_error']}"
        return {"status": "OK", "results": res}
    except Exception as e:
        SYNC_STATE["last_error"] = str(e)
        SYNC_STATE["progress"] = f"เกิดข้อผิดพลาด: {e}"
        return {"status": "FAILED", "message": str(e)}
    finally:
        SYNC_STATE["running"] = False
        _sync_lock.release()


def trigger_sync_async(triggered_by: str = "manual") -> bool:
    if SYNC_STATE["running"]:
        return False
    t = threading.Thread(target=run_sync_blocking, args=(triggered_by,), daemon=True)
    t.start()
    return True


def _is_within_work_hours(dt: datetime) -> bool:
    return Config.SYNC_START_HOUR <= dt.hour < Config.SYNC_END_HOUR


def _should_run_scheduled() -> bool:
    now_dt = datetime.now()
    if not _is_within_work_hours(now_dt):
        return False
    summary = db.status_summary()
    last_ok = summary.get("last_ok")
    if not last_ok or not last_ok.get("finished_at"):
        return True
    try:
        last_dt = datetime.strptime(last_ok["finished_at"], "%Y-%m-%d %H:%M:%S")
        return (now_dt - last_dt) >= timedelta(minutes=Config.SYNC_INTERVAL_MINUTES)
    except Exception:
        return True


def start_scheduler():
    def _loop():
        logger.info(
            f"Scheduler active: every {Config.SYNC_INTERVAL_MINUTES} min between "
            f"{Config.SYNC_START_HOUR:02d}:00–{Config.SYNC_END_HOUR:02d}:00 for locations {Config.LOCATIONS}"
        )
        while True:
            try:
                if not SYNC_STATE["running"] and _should_run_scheduled():
                    logger.info("Scheduled sync triggered.")
                    run_sync_blocking(triggered_by="schedule")
            except Exception as e:
                logger.warning(f"Scheduler check error: {e}")
            time.sleep(30)

    t = threading.Thread(target=_loop, daemon=True, name="InventoryScheduler")
    t.start()
