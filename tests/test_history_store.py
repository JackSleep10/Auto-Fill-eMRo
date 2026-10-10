"""Tests for scraper.history_store (dedup, concurrency, corrupt-file protection)."""
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scraper import history_store as hs  # noqa: E402


def _use_tmp(tmp_path: Path):
    hs.HISTORY_FILE = tmp_path / "work_order_history.json"


def _rec(n):
    return {"success": True, "wo_number": str(n), "gse": "TLM-X", "priority": "UNSCHED"}


def test_dedup(tmp_path):
    _use_tmp(tmp_path)
    assert hs.append_history([_rec(1)]) == 1
    assert hs.append_history([_rec(1)]) == 0  # duplicate ignored
    assert len(hs.load_history()) == 1


def test_skip_failed(tmp_path):
    _use_tmp(tmp_path)
    assert hs.append_history([{"success": False, "wo_number": "", "error": "x"}]) == 0


def test_concurrent_writers(tmp_path):
    _use_tmp(tmp_path)
    threads = [threading.Thread(target=hs.append_history, args=([_rec(i)],)) for i in range(50)]
    threads += [threading.Thread(target=hs.append_history, args=([_rec(i)],)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    data = json.loads(hs.HISTORY_FILE.read_text(encoding="utf-8"))
    assert len(data) == 50
    assert len({d["wo_number"] for d in data}) == 50


def test_corrupt_file_not_overwritten(tmp_path):
    _use_tmp(tmp_path)
    hs.HISTORY_FILE.write_text("{ broken json", encoding="utf-8")
    assert hs.append_history([_rec(9)]) == 0
    assert hs.HISTORY_FILE.read_text(encoding="utf-8") == "{ broken json"
