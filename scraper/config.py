import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory is D:\Project dashboard
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
load_dotenv(BASE_DIR / ".env", override=True)

class Config:
    BASE_DIR = BASE_DIR
    EMRO_URL = os.getenv("EMRO_URL", "https://emro.lionair.com/emro/Home.trax")
    EMRO_USERNAME = os.getenv("EMRO_USERNAME", "")
    EMRO_PASSWORD = os.getenv("EMRO_PASSWORD", "")
    EMRO_TOTP_SECRET = os.getenv("EMRO_TOTP_SECRET", "").strip()

    # Credentials are read ONLY from .env (never hardcode passwords / TOTP secrets here)
    EMRO_USERS = {
        "TL248005": {
            "password": os.getenv("EMRO_USER_TL248005_PASS") or os.getenv("EMRO_PASSWORD", ""),
            "totp_secret": (os.getenv("EMRO_USER_TL248005_SECRET") or os.getenv("EMRO_TOTP_SECRET", "")).strip()
        },
        "TL248006": {
            "password": os.getenv("EMRO_USER_TL248006_PASS", ""),
            "totp_secret": os.getenv("EMRO_USER_TL248006_SECRET", "").strip()
        }
    }

    @classmethod
    def has_emro_account(cls, user: str) -> bool:
        if not user:
            return False
        u = user.strip().upper()
        cred = cls.EMRO_USERS.get(u)
        if not cred:
            return False
        return bool(cred.get("totp_secret"))
    
    POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
    MONITOR_LOCATION = os.getenv("MONITOR_LOCATION", "DM01")
    
    HEADLESS = os.getenv("HEADLESS", "false").lower() in ("true", "1", "yes")
    
    # Google Sheets Apps Script Webhook URL
    APPS_SCRIPT_URL = os.getenv("APPS_SCRIPT_URL", "")
    SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1luje0x1QXrhhucSvmO6h_k5Es91X8rCcJeP2Fet7uYs")
    LOG_SPREADSHEET_ID = os.getenv("LOG_SPREADSHEET_ID", "1BdMWDX9anf2wD1_yLTH3S1LRBSuWCIKPAjKUOpPIrhA")
    LOG_APPS_SCRIPT_URL = os.getenv("LOG_APPS_SCRIPT_URL", "https://script.google.com/macros/s/AKfycbyL9vjvTJn2nI84kGKYTTfMsmCTXB6JJbvLTkl-VhB-uBNtkMEKXHz7S-ulckCdg0z9/exec")
    
    # Path configurations
    SESSION_DIR = BASE_DIR / "data" / "browser_session"
    SCREENSHOTS_DIR = BASE_DIR / "data" / "screenshots"
    CACHE_FILE = BASE_DIR / "data" / "cache.json"
