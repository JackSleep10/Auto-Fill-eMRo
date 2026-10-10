"""Single, thread-safe store for the local work order history file.

All reads/writes of data/work_order_history.json must go through this module so that:
- concurrent writers never corrupt the file (process-wide lock),
- a W/O number is never stored twice,
- an unreadable file is never overwritten (data loss protection),
- writes are atomic (temp file + os.replace) with a .bak copy kept.
"""
import json
import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Dict, Iterable, List

from scraper.config import Config

logger = logging.getLogger("HistoryStore")

HISTORY_FILE: Path = Config.BASE_DIR / "data" / "work_order_history.json"
_LOCK = threading.RLock()


class HistoryReadError(Exception):
    """Raised when the history file exists but cannot be parsed."""


def _read_unlocked() -> List[Dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise HistoryReadError(f"Cannot read {HISTORY_FILE}: {e}") from e
    if not isinstance(data, list):
        raise HistoryReadError(f"{HISTORY_FILE} does not contain a JSON list")
    return data


def load_history() -> List[Dict]:
    """Return all history records (oldest first). Returns [] if unreadable."""
    with _LOCK:
        try:
            return _read_unlocked()
        except HistoryReadError as e:
            logger.error(str(e))
            return []


def append_history(items: Iterable[Dict]) -> int:
    """Append successful W/O records, skipping duplicates. Returns number added.

    If the existing file is unreadable, nothing is written (to avoid wiping history).
    """
    items = list(items)
    with _LOCK:
        try:
            hist = _read_unlocked()
        except HistoryReadError as e:
            logger.error(f"{e} -- refusing to overwrite history. New items NOT saved: "
                         f"{[i.get('wo_number') for i in items]}")
            return 0

        existing = {str(h.get("wo_number")) for h in hist if h.get("wo_number")}
        added = 0
        for item in items:
            wo = str(item.get("wo_number") or "").strip()
            if not item.get("success") or not wo or wo in existing:
                continue
            hist.append(item)
            existing.add(wo)
            added += 1

        if added == 0:
            return 0

        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        if HISTORY_FILE.exists():
            shutil.copy2(HISTORY_FILE, HISTORY_FILE.with_suffix(".json.bak"))
        tmp = HISTORY_FILE.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, HISTORY_FILE)
        logger.info(f"Saved {added} new W/O record(s) to history (total {len(hist)}).")
        return added
