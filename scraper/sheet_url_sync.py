import datetime
import logging
import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import requests
from scraper.config import Config

logger = logging.getLogger("SheetUrlSync")

def sync_online_url_to_sheet(cf_url: str, lan_ip: str = "172.21.1.111") -> bool:
    """
    Automatically pushes the latest Cloudflare online URL and LAN IP
    to the shared Google Sheet so users outside the network can always find the active link.
    """
    if not cf_url or "trycloudflare.com" not in cf_url:
        logger.warning(f"[SheetUrlSync] Invalid Cloudflare URL: {cf_url}")
        return False

    url = Config.APPS_SCRIPT_URL
    if not url:
        logger.warning("[SheetUrlSync] APPS_SCRIPT_URL not configured.")
        return False

    now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    headers = [
        "ลำดับ",
        "ประเภทการเชื่อมต่อ",
        "ลิงก์เข้าใช้งานล่าสุด (Click to Open)",
        "สถานะ (Status)",
        "อัปเดตล่าสุด (Last Updated)"
    ]
    rows = [
        [
            "1",
            "📱 คอมนอกเครือข่าย / เน็ตบ้าน / มือถือ 4G/5G",
            cf_url.strip(),
            "ONLINE",
            now_str
        ],
        [
            "2",
            "💻 คอมในออฟฟิศ / Wi-Fi เดียวกัน (LAN)",
            f"http://{lan_ip.strip()}:8000",
            "ONLINE",
            now_str
        ],
        [
            "3",
            "🖥️ เครื่องคอมหลักตัวนี้ (Localhost)",
            "http://localhost:8000",
            "ONLINE",
            now_str
        ]
    ]

    payload = {
        "action": "update_live",
        "headers": headers,
        "rows": rows
    }

    try:
        resp = requests.post(url, json=payload, timeout=25)
        if resp.status_code == 200:
            logger.info(f"[SheetUrlSync] Successfully synced latest Online URL ({cf_url}) to Google Sheet!")
            return True
        else:
            logger.error(f"[SheetUrlSync] Google Sheet returned status {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        logger.exception(f"[SheetUrlSync] Error syncing Online URL to Google Sheet: {e}")
        return False

if __name__ == "__main__":
    import sys
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://executives-configure-sailing-trusted.trycloudflare.com"
    ok = sync_online_url_to_sheet(test_url)
    print("Sync result:", ok)
