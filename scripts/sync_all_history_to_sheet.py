import json
import logging
import os
from pathlib import Path
import requests
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SyncHistory")

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

APPS_SCRIPT_URL = os.getenv("APPS_SCRIPT_URL", "").strip()
LOG_SPREADSHEET_ID = os.getenv("LOG_SPREADSHEET_ID", "1BdMWDX9anf2wD1_yLTH3S1LRBSuWCIKPAjKUOpPIrhA").strip()

def collect_all_history():
    all_items = []
    
    # 1. Load from last_batch_results.json
    batch_file = BASE_DIR / "data" / "last_batch_results.json"
    if batch_file.exists():
        with open(batch_file, "r", encoding="utf-8") as f:
            batch_items = json.load(f)
            for itm in batch_items:
                if itm.get("wo_number") and itm.get("success"):
                    all_items.append(itm)
    logger.info(f"Loaded {len(all_items)} valid items from last_batch_results.json")

    # 2. Add single CM Work Order TLM-TR-031 created by TL248006
    cm_item = {
        "success": True,
        "wo_number": "2346873",
        "gse": "TLM-TR-031",
        "sn": "132110",
        "priority": "UNSCHED",
        "description": "OIL LEAKED TEST 2FA",
        "user": "TL248006",
        "created_at": "2026-10-04 19:13:07",
        "date": "10/4/2026",
        "error": ""
    }
    
    # Avoid duplicate
    if not any(it.get("wo_number") == cm_item["wo_number"] for it in all_items):
        all_items.append(cm_item)
        logger.info(f"Added CM W/O #{cm_item['wo_number']} ({cm_item['gse']}) to history.")

    # Save to local work_order_history.json
    hist_file = BASE_DIR / "data" / "work_order_history.json"
    with open(hist_file, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved total {len(all_items)} work order records to {hist_file}")

    return all_items

def sync_to_google_sheet(items):
    if not APPS_SCRIPT_URL:
        logger.error("APPS_SCRIPT_URL is not set!")
        return False

    logger.info(f"Syncing {len(items)} items to Google Sheet {LOG_SPREADSHEET_ID}...")

    # Step 1: Initialize Headers if needed
    init_payload = {
        "action": "init_wo_log_headers",
        "target_spreadsheet_id": LOG_SPREADSHEET_ID
    }
    try:
        r_init = requests.post(APPS_SCRIPT_URL, json=init_payload, timeout=35)
        logger.info(f"Init headers status: {r_init.status_code}")
    except Exception as e:
        logger.warning(f"Init headers request failed: {e}")

    # Step 2: Send items in chunks of 50 to avoid timeout
    chunk_size = 50
    total_chunks = (len(items) + chunk_size - 1) // chunk_size

    for i in range(0, len(items), chunk_size):
        chunk = items[i:i + chunk_size]
        chunk_idx = (i // chunk_size) + 1
        logger.info(f"Sending chunk {chunk_idx}/{total_chunks} ({len(chunk)} items)...")
        payload = {
            "action": "append_wo_log",
            "target_spreadsheet_id": LOG_SPREADSHEET_ID,
            "items": chunk
        }
        try:
            resp = requests.post(APPS_SCRIPT_URL, json=payload, timeout=35)
            logger.info(f"Chunk {chunk_idx} response status: {resp.status_code}")
        except Exception as e:
            logger.error(f"Chunk {chunk_idx} failed: {e}")

    logger.info("Sync to Master Log Sheet completed!")
    return True

if __name__ == "__main__":
    records = collect_all_history()
    sync_to_google_sheet(records)
