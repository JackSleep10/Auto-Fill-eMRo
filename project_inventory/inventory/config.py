import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
if (ROOT_DIR / ".env").exists():
    load_dotenv(ROOT_DIR / ".env", override=False)
if (BASE_DIR / ".env").exists():
    load_dotenv(BASE_DIR / ".env", override=True)


class Config:
    BASE_DIR = BASE_DIR

    EMRO_URL = os.getenv("EMRO_URL", "https://emro.lionairthai.com/emro/Home.trax")
    EMRO_FALLBACK_URL = os.getenv("EMRO_FALLBACK_URL", "https://emro.lionair.com/emro/Home.trax")

    # Dedicated read-only account used for syncing inventory
    INVENTORY_USER = os.getenv("INVENTORY_USER", "TL248005").strip().upper()

    @classmethod
    def credentials(cls, user: str) -> dict:
        u = user.strip().upper()
        return {
            "password": os.getenv(f"EMRO_USER_{u}_PASS") or os.getenv("EMRO_PASSWORD", ""),
            "totp_secret": (os.getenv(f"EMRO_USER_{u}_SECRET") or os.getenv("EMRO_TOTP_SECRET", "")).strip(),
        }

    LOCATIONS = [x.strip().upper() for x in os.getenv("INVENTORY_LOCATIONS", "DM01").split(",") if x.strip()]

    SYNC_INTERVAL_MINUTES = int(os.getenv("SYNC_INTERVAL_MINUTES", "30"))
    SYNC_START_HOUR = int(os.getenv("SYNC_START_HOUR", "6"))
    SYNC_END_HOUR = int(os.getenv("SYNC_END_HOUR", "22"))

    # Safety guard: abort marking items OUT if row count drops more than this ratio vs previous run
    MAX_DROP_RATIO = float(os.getenv("MAX_DROP_RATIO", "0.2"))

    REFRESH_PIN = os.getenv("REFRESH_PIN", "")
    WEB_PORT = int(os.getenv("WEB_PORT", "8001"))
    HEADLESS = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "inventory-search-secret")

    DATA_DIR = BASE_DIR / "data"
    DB_FILE = DATA_DIR / "inventory.db"
    SESSION_DIR = DATA_DIR / "browser_session"
    DOWNLOAD_DIR = DATA_DIR / "exports"
    SCREENSHOTS_DIR = DATA_DIR / "screenshots"
    KEEP_EXPORT_FILES = 3
