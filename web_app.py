import os
import sys

# Ensure stdout/stderr and logging are fully safe under pythonw.exe
_devnull = open(os.devnull, "w", encoding="utf-8")
if sys.stdout is None:
    sys.stdout = _devnull
if sys.stderr is None:
    sys.stderr = _devnull
if sys.__stdout__ is None:
    sys.__stdout__ = _devnull
if sys.__stderr__ is None:
    sys.__stderr__ = _devnull

import logging
logging.lastResort = None

import asyncio
import csv
import io
import json
import logging
import re
import socket
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import requests
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, send_file

from scraper.config import Config
from scraper.emro_scraper import eMROScraper
from scraper.change_detector import ChangeDetector
from scraper.gse_wo_creator import GSEWorkOrderCreator
from scraper.history_store import append_history, load_history
from sheets.google_sheets import GoogleSheetsClient

_INV_PKG_DIR = str(Config.BASE_DIR / "project_inventory")
if _INV_PKG_DIR not in sys.path:
    sys.path.insert(0, _INV_PKG_DIR)
from inventory import db as inv_db, sync_worker as inv_sync_worker  # noqa: E402
from inventory.config import Config as InvConfig  # noqa: E402

InvConfig.DATA_DIR.mkdir(parents=True, exist_ok=True)
inv_db.init_db()
inv_sync_worker.seed_from_existing_export_if_empty()

from logging.handlers import RotatingFileHandler

_LOG_DIR = Config.BASE_DIR / "data" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_file_handler = RotatingFileHandler(_LOG_DIR / "web_app.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_file_handler])
logger = logging.getLogger("GSEWebApp")

# Work from the project folder regardless of where the app was launched from
os.chdir(Config.BASE_DIR)

app = Flask(__name__)
_secret = os.environ.get("FLASK_SECRET_KEY", "").strip()
if not _secret:
    import secrets as _secrets
    _secret = _secrets.token_hex(32)
    logger.warning("FLASK_SECRET_KEY not set in .env -- using a random key (users must re-login after restart).")
app.secret_key = _secret
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

# Valid authorized users
VALID_USERS = {
    "TL186205": ["TL186205"],
    "TL206992": ["TL206992"],
    "TL248005": ["12345678", "TL248005"],
    "TL248006": ["TL248006"],
    "TL248007": ["TL248007"],
    "TL260005": ["TL260005"],
    "TL260006": ["TL260006"],
}

# Master list cache
GSE_MASTER = []
MASTER_CSV_PATH = Config.BASE_DIR / "data" / "gse_master_list.csv"
_MASTER_LOCK = threading.Lock()

def load_master_list():
    global GSE_MASTER
    if not MASTER_CSV_PATH.exists():
        logger.warning(f"Master CSV not found at {MASTER_CSV_PATH}")
        return
    items = []
    with open(MASTER_CSV_PATH, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gse_no = row.get("GSE NO.", "").strip()
            if gse_no:
                items.append({
                    "gse": gse_no,
                    "type": row.get("TYPE", "").strip(),
                    "brand": row.get("BRAND", "").strip(),
                    "sn": row.get("GSE S/N", "").strip(),
                    "model": row.get("MODEL or P/N", "").strip(),
                    "engine": row.get("ENGINE", "").strip(),
                    "description": row.get("DESCRIPTION", "").strip(),
                    "station": row.get("STATION", "").strip(),
                    "status": row.get("STATUS", "").strip(),
                    "emro_status": (row.get("EMRO STATUS", "ACTIVE") or "ACTIVE").strip().upper()
                })
    GSE_MASTER = items
    logger.info(f"Loaded {len(GSE_MASTER)} items from GSE Master List.")

def sync_master_from_google_sheet():
    global GSE_MASTER
    url = "https://docs.google.com/spreadsheets/d/1i0hjTtfuJZX5EVIDxKNGcj4zr4qy3xuZHar1NAeYsQ0/export?format=csv&gid=982490752"
    try:
        import requests
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200 and "GSE NO." in resp.text:
            MASTER_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(MASTER_CSV_PATH, "w", encoding="utf-8") as f:
                f.write(resp.text)
            load_master_list()
            logger.info(f"Successfully synced {len(GSE_MASTER)} items from Google Sheets!")
            return True, len(GSE_MASTER)
        else:
            logger.error(f"Failed to fetch master sheet: status {resp.status_code}")
            return False, f"HTTP Status {resp.status_code}"
    except Exception as e:
        logger.exception("Error syncing master sheet from Google")
        return False, str(e)

def ensure_master_list():
    """Ensure GSE_MASTER is populated; load from CSV or auto-sync from Google Sheets."""
    if GSE_MASTER:
        return
    with _MASTER_LOCK:
        if GSE_MASTER:
            return
        if MASTER_CSV_PATH.exists():
            load_master_list()
        if not GSE_MASTER:
            logger.info("GSE Master List is missing or empty; auto-syncing from Google Sheets...")
            sync_master_from_google_sheet()

ensure_master_list()

PM_MONTHS = {"JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"}

def format_pm_description(desc: str, default: str = "PM") -> str:
    d = (desc or "").strip().upper()
    if not d:
        return default
    if re.match(r"^[A-Z]$", d):
        return f"PM {d}"
    pmm = re.match(r"^PM[-_ ]?([A-Z])$", d)
    if pmm:
        return f"PM {pmm.group(1)}"
    if d in PM_MONTHS:
        return f"PM {d}"
    pm_m = re.match(r"^PM[-_ ]?([A-Z]{3,4})$", d)
    if pm_m and pm_m.group(1) in PM_MONTHS:
        return f"PM {pm_m.group(1)}"
    return d

# Helper to persist batch results across app restarts
RESULTS_FILE = Path("data/last_batch_results.json")

def load_saved_results():
    if RESULTS_FILE.exists():
        try:
            with open(RESULTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_batch_results(results):
    try:
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save batch results to disk: {e}")

# Global Batch Task State
BATCH_STATE = {
    "is_running": False,
    "total": 0,
    "current_index": 0,
    "current_gse": "",
    "results": load_saved_results(),
    "logs": [],
    "error": ""
}

def log_batch(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    logger.info(entry)
    BATCH_STATE["logs"].append(entry)
    if len(BATCH_STATE["logs"]) > 200:
        BATCH_STATE["logs"].pop(0)

class GSEWorker:
    def __init__(self):
        self.loop = None
        self.thread = None
        self.creator: Optional[GSEWorkOrderCreator] = None
        self.lock = threading.Lock()
        self._start_loop()

    def _start_loop(self):
        def _target():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()

        self.thread = threading.Thread(target=_target, daemon=True, name="GSEWorkerThread")
        self.thread.start()

    def run_coro(self, coro, timeout=120):
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=timeout)

    async def get_creator(self, user: str, slow_mo=40) -> GSEWorkOrderCreator:
        user_clean = (user or "").strip().upper()
        if not user_clean:
            raise ValueError("User must be specified to acquire eMRO session.")

        if self.creator is not None:
            if not self.creator.is_alive():
                logger.warning("[GSEWorker] Creator page or context was closed. Recreating session...")
                try:
                    await self.creator.close()
                except Exception:
                    pass
                self.creator = None
            elif getattr(self.creator, "user", None) != user_clean:
                # Active session belongs to a different user (e.g. TL248005 vs TL248006). Close cleanly to switch!
                logger.info(f"[GSEWorker] Active eMRO session is for '{getattr(self.creator, 'user', None)}', but requested by '{user_clean}'. Switching session cleanly...")
                try:
                    await self.creator.close()
                except Exception:
                    pass
                self.creator = None

        if self.creator is None:
            logger.info(f"[GSEWorker] Launching browser session for {user_clean} (headless={Config.HEADLESS}, slow_mo={slow_mo}ms)...")
            self.creator = GSEWorkOrderCreator(user=user_clean, headless=Config.HEADLESS, slow_mo=slow_mo)
            await self.creator.start()
            await self.creator.ensure_logged_in(user=user_clean)
        else:
            self.creator.slow_mo = slow_mo
            await self.creator.ensure_logged_in(user=user_clean)

        return self.creator

    async def close(self):
        if self.creator:
            try:
                await self.creator.close()
            except Exception:
                pass
            self.creator = None

WORKER = GSEWorker()

def run_batch_thread(items, user: str):
    global BATCH_STATE
    BATCH_STATE["is_running"] = True
    BATCH_STATE["total"] = len(items)
    BATCH_STATE["current_index"] = 0
    BATCH_STATE["results"] = []
    BATCH_STATE["logs"] = []
    BATCH_STATE["error"] = ""

    log_batch(f"Starting batch task for {len(items)} work orders (User: {user})...")

    async def _runner():
        creator = await WORKER.get_creator(user=user, slow_mo=100)
        try:
            for idx, itm in enumerate(items):
                BATCH_STATE["current_index"] = idx + 1
                gse_val = str(itm.get("gse", "")).strip().upper()
                desc_val = str(itm.get("description", "")).strip().upper()

                # Defensive parsing: if gse contains space e.g. "TLM-AC-003 PM A" or "TLM-AC-003 A"
                if " " in gse_val:
                    parts = gse_val.split(None, 1)
                    gse_val = parts[0].strip().upper()
                    if not desc_val or desc_val == "PM":
                        desc_val = parts[1].strip().upper()

                # Format single-letter or PM descriptions (e.g. 'A' -> 'PM A')
                desc_val = format_pm_description(desc_val, "PM")

                # Auto-resolve TLM- prefix
                if not gse_val.startswith("TLM-"):
                    if any(isinstance(m, dict) and m.get("gse") == f"TLM-{gse_val}" for m in GSE_MASTER):
                        gse_val = f"TLM-{gse_val}"

                BATCH_STATE["current_gse"] = gse_val
                log_batch(f"Creating W/O ({idx+1}/{len(items)}): GSE {gse_val} | {desc_val} ({itm.get('priority', 'SCHED')})...")

                res = await creator.create_single_wo(
                    gse=gse_val,
                    description=desc_val,
                    priority=itm.get("priority", "SCHED"),
                    user=user
                )
                BATCH_STATE["results"].append(res)
                save_batch_results(BATCH_STATE["results"])

                if res.get("success"):
                    log_batch(f"SUCCESS: GSE {itm['gse']} -> W/O #{res['wo_number']} (S/N: {res['sn']})")
                else:
                    log_batch(f"FAILED: GSE {itm['gse']} -> {res.get('error')}")

                await asyncio.sleep(0.5)

            save_batch_results(BATCH_STATE["results"])
            log_batch(f"Batch task completed! Finished {len(items)} items.")

            # Save to local history
            try:
                append_history(BATCH_STATE["results"])
            except Exception as he:
                logger.exception(f"Failed to save local history: {he}")

            # Auto sync to Monthly PM Tracking Sheet (PM items only; Master Log Sheet / บันทึกข้อมูล W/O is excluded)
            log_batch("Syncing results to Monthly PM Tracking Sheet...")
            GSEWorkOrderCreator.sync_to_google_sheet(BATCH_STATE["results"])
            log_batch("Google Sheets sync completed!")

        except Exception as e:
            logger.exception("Error in batch runner")
            BATCH_STATE["error"] = str(e)
            log_batch(f"ERROR: {e}")
        finally:
            BATCH_STATE["is_running"] = False

    def _exec():
        with WORKER.lock:
            timeout_sec = max(300, len(items) * 120)
            WORKER.run_coro(_runner(), timeout=timeout_sec)

    threading.Thread(target=_exec, daemon=True).start()

@app.before_request
def require_login():
    if request.path in ["/login", "/static"] or request.path.startswith("/static/"):
        return
    if not session.get("logged_in"):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Unauthorized. Please log in."}), 401
        return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("index"))

    error = None
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip().upper()
        password = request.form.get("password", "").strip()

        allowed_pw = VALID_USERS.get(username, [])
        if isinstance(allowed_pw, str):
            allowed_pw = [allowed_pw]

        if password in allowed_pw:
            session["logged_in"] = True
            session["user"] = username
            logger.info(f"User '{username}' logged in successfully.")
            return redirect(url_for("index"))
        else:
            error = "รหัสพนักงานหรือรหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง"
            logger.warning(f"Failed login attempt for user '{username}'.")

    with open("data/login.html", "r", encoding="utf-8") as f:
        html = f.read()
    return render_template_string(html, error=error, username=username)

@app.route("/logout")
def logout():
    user = session.get("user")
    session.clear()
    logger.info(f"User '{user}' logged out.")
    return redirect(url_for("login"))

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

@app.route("/api/me")
def get_current_user():
    user = session.get("user", "")
    return jsonify({
        "logged_in": bool(session.get("logged_in")),
        "user": user,
        "emro_connected": Config.has_emro_account(user),
        "lan_ip": get_lan_ip()
    })

@app.route("/")
def index():
    with open("data/gse_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()
    return render_template_string(html)

@app.route("/api/gse-master")
def get_gse_master():
    ensure_master_list()
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify(GSE_MASTER)
    filtered = [
        item for item in GSE_MASTER
        if q in item["gse"].lower() or q in item["type"].lower() or q in item["description"].lower() or q in item["sn"].lower()
    ]
    return jsonify(filtered)

@app.route("/api/sync-master-sheet", methods=["POST", "GET"])
def api_sync_master_sheet():
    ok, result = sync_master_from_google_sheet()
    if ok:
        return jsonify({"success": True, "count": result, "items": GSE_MASTER})
    else:
        return jsonify({"success": False, "error": str(result)}), 500

@app.route("/api/start-batch", methods=["POST"])
def start_batch():
    global BATCH_STATE
    if BATCH_STATE["is_running"]:
        return jsonify({"success": False, "message": "A batch task is already in progress!"}), 400

    data = request.get_json() or {}
    items = data.get("items", [])
    if not items:
        return jsonify({"success": False, "message": "No items provided."}), 400

    current_user = session.get("user", "")
    if not Config.has_emro_account(current_user):
        return jsonify({
            "success": False,
            "message": f"บัญชีของคุณ ({current_user}) ยังไม่ได้เชื่อมต่อกับระบบ eMRO (ไม่มีรหัสผ่าน/2FA) จึงไม่สามารถเปิดใบงานในนามของคุณได้ กรุณาติดต่อผู้ดูแลระบบ"
        }), 403

    thread = threading.Thread(target=run_batch_thread, args=(items, current_user), daemon=True)
    thread.start()
    return jsonify({"success": True, "message": f"Started batch for {len(items)} items."})

@app.route("/api/batch-status")
def batch_status():
    if not BATCH_STATE["is_running"]:
        BATCH_STATE["results"] = load_saved_results()
    return jsonify(BATCH_STATE)

@app.route("/api/export-results-excel", methods=["GET", "POST"])
def export_results_excel():
    try:
        items = None
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            items = data.get("items")
        if not items:
            items = load_saved_results()

        valid_items = [it for it in items if it.get("wo_number")] or items
        if not valid_items:
            return jsonify({"error": "No items to export"}), 400

        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "GSE WO Results"
        ws.views.sheetView[0].showGridLines = True

        header_fill = PatternFill(start_color="D71920", end_color="D71920", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        data_font = Font(name="Calibri", size=10)
        center_align = Alignment(horizontal="center", vertical="center")

        thin_border = Border(
            left=Side(style="thin", color="D1D5DB"),
            right=Side(style="thin", color="D1D5DB"),
            top=Side(style="thin", color="D1D5DB"),
            bottom=Side(style="thin", color="D1D5DB"),
        )

        headers = ["GSE NO.", "DESCRIPTION", "GSE W/O NO.", "GSE S/N", "PRIORITY"]
        ws.append(headers)

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align
            cell.border = thin_border
        ws.row_dimensions[1].height = 24

        for r_idx, itm in enumerate(valid_items, start=2):
            row_data = [
                str(itm.get("gse", "")).strip(),
                str(itm.get("description", "")).strip(),
                str(itm.get("wo_number", "")).strip(),
                str(itm.get("sn", "")).strip(),
                str(itm.get("priority", "SCHED")).strip()
            ]
            ws.append(row_data)
            ws.row_dimensions[r_idx].height = 20
            for c_idx in range(1, len(row_data) + 1):
                cell = ws.cell(row=r_idx, column=c_idx)
                cell.font = data_font
                cell.border = thin_border
                cell.alignment = center_align

        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = col[0].column_letter
            ws.column_dimensions[col_letter].width = max(max_len + 5, 14)

        bio = io.BytesIO()
        wb.save(bio)
        bio.seek(0)

        filename = f"GSE_WO_Results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(
            bio,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        logger.exception("Error exporting results to Excel")
        return jsonify({"error": str(e)}), 500

@app.route("/api/live-screenshot")
def live_screenshot():
    shot_path = Path("data/screenshots/live_screen.jpg")
    if shot_path.exists():
        return send_file(str(shot_path), mimetype="image/jpeg", max_age=0)
    return ("", 204)

@app.route("/api/create-single", methods=["POST"])
def create_single():
    data = request.get_json() or {}
    gse = data.get("gse", "").strip().upper()
    desc = data.get("description", "").strip().upper()
    prio = data.get("priority", "UNSCHED").strip()
    current_user = session.get("user", "")

    # Defensive parsing: if gse contains space e.g. "TLM-AC-003 PM A" or "TLM-AC-003 A"
    if " " in gse:
        parts = gse.split(None, 1)
        gse = parts[0].strip().upper()
        if not desc or desc == "PM":
            desc = parts[1].strip().upper()

    # Format single-letter or PM descriptions (e.g. 'A' -> 'PM A')
    desc = format_pm_description(desc, "PM")

    # Auto-resolve TLM- prefix
    if not gse.startswith("TLM-"):
        if any(isinstance(m, dict) and m.get("gse") == f"TLM-{gse}" for m in GSE_MASTER):
            gse = f"TLM-{gse}"

    if not Config.has_emro_account(current_user):
        return jsonify({
            "success": False,
            "error": f"บัญชีของคุณ ({current_user}) ยังไม่ได้เชื่อมต่อกับระบบ eMRO (ไม่มีรหัสผ่าน/2FA) จึงไม่สามารถเปิดใบงานในนามของคุณได้ กรุณาติดต่อผู้ดูแลระบบเพื่อลงทะเบียน"
        }), 403

    if not gse or not desc:
        return jsonify({"success": False, "error": "GSE and Description are required."}), 400

    if BATCH_STATE["is_running"]:
        return jsonify({"success": False, "error": "ระบบกำลังประมวลผลงานชุด (Batch) อยู่ กรุณารอสักครู่"}), 409

    async def _single_run():
        creator = await WORKER.get_creator(user=current_user, slow_mo=40)
        res = await creator.create_single_wo(gse=gse, description=desc, priority=prio, user=current_user)
        return res

    try:
        with WORKER.lock:
            res = WORKER.run_coro(_single_run(), timeout=90)
    except Exception as e:
        logger.exception("Error executing single W/O creation")
        return jsonify({"success": False, "error": f"Worker error: {e}"}), 500

    if res.get("success"):
        # Immediately save to local history file (dedup, locked, atomic)
        try:
            append_history([res])
        except Exception as he:
            logger.exception(f"Failed to save local history: {he}")

        # Send strictly to Master Audit Log Sheet (Never to PM monthly sheet)
        threading.Thread(target=GSEWorkOrderCreator.log_to_google_sheet, args=([res],), daemon=True).start()

    return jsonify(res)

@app.route("/api/reset-worker", methods=["POST"])
def reset_worker():
    with WORKER.lock:
        WORKER.run_coro(WORKER.close(), timeout=15)
    return jsonify({"success": True, "message": "Worker browser reset successfully."})

@app.route("/api/init-log-sheet", methods=["POST"])
def init_log_sheet():
    success = GSEWorkOrderCreator.init_log_sheet_headers()
    return jsonify({"success": success, "message": "Headers initialized on Master Log Sheet" if success else "Failed to initialize headers"})

# No eager browser prewarm with a hardcoded user on startup.
# Each user acquires their own clean eMRO browser session on-demand when creating work orders.

@app.route("/api/sync-online-url", methods=["POST", "GET"])
def api_sync_online_url():
    from scraper.sheet_url_sync import sync_online_url_to_sheet
    import re
    cf_url = ""
    log_file = Config.BASE_DIR / "data" / "cloudflare.log"
    if log_file.exists():
        try:
            content = log_file.read_text(encoding="utf-8", errors="ignore")
            m = re.findall(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", content)
            if m:
                cf_url = m[-1]
        except Exception:
            pass

    if not cf_url:
        return jsonify({"success": False, "error": "No active Cloudflare online URL found in log."}), 404

    lan_ip = get_lan_ip()
    ok = sync_online_url_to_sheet(cf_url, lan_ip=lan_ip)
    return jsonify({
        "success": ok,
        "cf_url": cf_url,
        "lan_ip": lan_ip,
        "message": "Online URL synced to Google Sheet successfully!" if ok else "Failed to sync to Google Sheet"
    })

@app.route("/api/sync-sheets", methods=["POST"])
def sync_sheets():
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    if not items:
        items = BATCH_STATE.get("results", [])
    if not items:
        return jsonify({"success": False, "message": "No items to sync."}), 400

    ok = GSEWorkOrderCreator.sync_to_google_sheet(items)
    return jsonify({"success": ok})

def load_work_order_history():
    return load_history()

@app.route("/api/history")
def get_work_order_history():
    items = load_work_order_history()
    items_reversed = list(reversed(items))

    q = request.args.get("q", "").strip().lower()
    type_filter = request.args.get("type", "").strip().upper()

    filtered = []
    pm_count = 0
    cm_count = 0

    for itm in items_reversed:
        prio = (itm.get("priority") or "SCHED").upper()
        is_pm = prio in ("SCHED", "PM")
        is_cm = not is_pm

        if is_pm:
            pm_count += 1
        else:
            cm_count += 1

        if type_filter == "PM" and not is_pm:
            continue
        if type_filter == "CM" and not is_cm:
            continue

        if q:
            match_fields = [
                itm.get("wo_number", ""),
                itm.get("gse", ""),
                itm.get("sn", ""),
                itm.get("description", ""),
                itm.get("user", ""),
                itm.get("created_at", "")
            ]
            if not any(q in str(f).lower() for f in match_fields):
                continue

        filtered.append(itm)

    return jsonify({
        "total": len(items),
        "pm_count": pm_count,
        "cm_count": cm_count,
        "filtered_count": len(filtered),
        "items": filtered
    })

# ==================== INVENTORY MONITOR API ====================
INVENTORY_SNAPSHOT_FILE = Config.BASE_DIR / "data" / "inventory_snapshot.json"
INVENTORY_CACHE_TTL_SECONDS = 30
_INVENTORY_LOCK = threading.Lock()
INVENTORY_STATE = {
    "is_syncing": False,
    "last_error": "",
    "cache": None,
    "cache_ts": 0.0,
}

INVENTORY_HEADER_TO_KEY = {
    "Transaction NO": "transaction_no",
    "Transaction Type": "transaction_type",
    "P/N": "pn",
    "S/N": "sn",
    "Batch": "batch",
    "GRB": "grb",
    "Vendor Lot": "vendor_lot",
    "Location": "location",
    "Bin": "bin",
    "Condition": "condition",
    "QTY": "qty",
    "Unit Cost": "unit_cost",
    "Secondary Cost": "secondary_cost",
    "CUR EXC Rate": "cur_exc_rate",
    "A/C": "ac",
    "W/O - S/O": "wo_so",
    "Issued To": "issued_to",
    "Issued To Name": "issued_to_name",
    "Order Type": "order_type",
    "Order NO": "order_no",
    "Line": "order_line",
    "Vendor/Customer": "vendor_customer",
    "Vendor Name": "vendor_name",
    "Reference": "reference",
    "Status": "status",
    "Created By": "created_by",
    "Created Date": "created_date",
    "Name": "created_name",
    "G/L": "gl",
    "Defect Description": "defect_description",
    "Last Synced": "last_synced",
}
INVENTORY_CANONICAL_KEYS = list(INVENTORY_HEADER_TO_KEY.values())


def _normalize_inventory_item(raw: dict, default_last_synced: str = "") -> dict:
    item = {}
    for key in INVENTORY_CANONICAL_KEYS:
        val = raw.get(key, "") if isinstance(raw, dict) else ""
        item[key] = "" if val is None else str(val)
    if default_last_synced and not item.get("last_synced"):
        item["last_synced"] = default_last_synced
    return item


def compute_inventory_stats(items: list, last_sync: str = "-") -> dict:
    issued = 0
    receiving = 0
    transfer = 0
    rts = 0
    resolved_sync = (last_sync or "").strip()

    for it in items or []:
        t_type = str(it.get("transaction_type", "")).upper()
        if "ISSUED" in t_type:
            issued += 1
        elif "RECEIVING" in t_type:
            receiving += 1
        elif "TRANSFER" in t_type or "RTS" in t_type:
            transfer += 1
        if "RTS" in t_type:
            rts += 1
        if (not resolved_sync or resolved_sync == "-") and it.get("last_synced"):
            resolved_sync = str(it.get("last_synced")).strip()

    return {
        "total": len(items or []),
        "issued": issued,
        "receiving": receiving,
        "transfer": transfer,
        "rts": rts,
        "last_sync": resolved_sync or "-",
    }


def rows_to_inventory_items(headers: list, rows: list) -> Optional[list]:
    if not isinstance(headers, list) or not isinstance(rows, list):
        return None
    clean_headers = [str(h).strip() for h in headers]
    if "Transaction Type" not in clean_headers or "P/N" not in clean_headers:
        return None

    col_keys = [INVENTORY_HEADER_TO_KEY.get(h) for h in clean_headers]
    items = []
    for row in rows:
        if not isinstance(row, (list, tuple)):
            continue
        item = {k: "" for k in INVENTORY_CANONICAL_KEYS}
        for idx, key in enumerate(col_keys):
            if key and idx < len(row):
                val = row[idx]
                item[key] = "" if val is None else str(val)
        items.append(item)
    return items


def save_inventory_snapshot(payload: dict):
    try:
        INVENTORY_SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = INVENTORY_SNAPSHOT_FILE.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp_path, INVENTORY_SNAPSHOT_FILE)
    except Exception as e:
        logger.warning(f"Failed to save inventory snapshot: {e}")


def load_inventory_fallback() -> dict:
    if INVENTORY_SNAPSHOT_FILE.exists():
        try:
            snap = json.loads(INVENTORY_SNAPSHOT_FILE.read_text(encoding="utf-8"))
            if isinstance(snap, dict) and isinstance(snap.get("items"), list):
                items = [_normalize_inventory_item(it) for it in snap["items"]]
                stats = compute_inventory_stats(items, last_sync=snap.get("last_sync", "-"))
                return {
                    "success": True,
                    "source": "snapshot",
                    "location": snap.get("location") or Config.MONITOR_LOCATION,
                    "last_sync": stats["last_sync"],
                    "stats": stats,
                    "items": items,
                    "logs": snap.get("logs", []) if isinstance(snap.get("logs"), list) else [],
                }
        except Exception as e:
            logger.warning(f"Failed to read inventory snapshot: {e}")

    if Config.CACHE_FILE.exists():
        try:
            raw_cache = json.loads(Config.CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(raw_cache, list):
                items = [_normalize_inventory_item(it) for it in raw_cache if isinstance(it, dict)]
                stats = compute_inventory_stats(items)
                return {
                    "success": True,
                    "source": "local_cache",
                    "location": Config.MONITOR_LOCATION,
                    "last_sync": stats["last_sync"],
                    "stats": stats,
                    "items": items,
                    "logs": [],
                }
        except Exception as e:
            logger.warning(f"Failed to read local inventory cache: {e}")

    return {
        "success": True,
        "source": "empty",
        "location": Config.MONITOR_LOCATION,
        "last_sync": "-",
        "stats": compute_inventory_stats([]),
        "items": [],
        "logs": [],
    }


def _get_inventory_webhook_url() -> str:
    raw_url = (Config.APPS_SCRIPT_URL or "").strip()
    if not raw_url:
        return ""
    if raw_url.startswith("http://") or raw_url.startswith("https://"):
        return raw_url
    return f"https://script.google.com/macros/s/{raw_url}/exec"


def fetch_inventory_from_google_sheets() -> Optional[dict]:
    webhook_url = _get_inventory_webhook_url()
    if not webhook_url:
        return None
    try:
        sep = "&" if "?" in webhook_url else "?"
        resp = requests.get(f"{webhook_url}{sep}api=data", timeout=20, allow_redirects=True)
        if resp.status_code != 200:
            logger.warning(f"Google Sheets inventory fetch returned status {resp.status_code}")
            return None
        data = resp.json()
        if not isinstance(data, dict):
            return None
        items = rows_to_inventory_items(data.get("headers", []), data.get("rows", []))
        if items is None:
            logger.info("Google Sheets response headers do not match inventory schema; using fallback.")
            return None

        raw_stats = data.get("stats") or {}
        last_sync = raw_stats.get("lastSync") or "-"
        stats = compute_inventory_stats(items, last_sync=last_sync)
        payload = {
            "success": True,
            "source": "google_sheets",
            "location": Config.MONITOR_LOCATION,
            "last_sync": stats["last_sync"],
            "stats": stats,
            "items": items,
            "logs": data.get("logs", []) if isinstance(data.get("logs"), list) else [],
        }
        save_inventory_snapshot(payload)
        return payload
    except Exception as e:
        logger.warning(f"Error fetching inventory from Google Sheets: {e}")
        return None


@app.route("/api/inventory")
def get_inventory():
    force_refresh = request.args.get("refresh", "").strip().lower() in ("1", "true", "yes")
    now = time.time()

    if not force_refresh:
        with _INVENTORY_LOCK:
            cached = INVENTORY_STATE.get("cache")
            if cached is not None and (now - INVENTORY_STATE.get("cache_ts", 0.0)) < INVENTORY_CACHE_TTL_SECONDS:
                res = dict(cached)
                res["is_syncing"] = INVENTORY_STATE["is_syncing"]
                res["default_location"] = Config.MONITOR_LOCATION
                res["last_error"] = INVENTORY_STATE["last_error"]
                return jsonify(res)

    payload = fetch_inventory_from_google_sheets()
    if payload is None:
        payload = load_inventory_fallback()
        with _INVENTORY_LOCK:
            res = dict(payload)
            res["is_syncing"] = INVENTORY_STATE["is_syncing"]
            res["default_location"] = Config.MONITOR_LOCATION
            res["last_error"] = INVENTORY_STATE["last_error"]
        return jsonify(res)

    with _INVENTORY_LOCK:
        INVENTORY_STATE["cache"] = payload
        INVENTORY_STATE["cache_ts"] = time.time()
        res = dict(payload)
        res["is_syncing"] = INVENTORY_STATE["is_syncing"]
        res["default_location"] = Config.MONITOR_LOCATION
        res["last_error"] = INVENTORY_STATE["last_error"]
    return jsonify(res)


@app.route("/api/inventory/sync-emro", methods=["POST"])
def sync_inventory_from_emro():
    data = request.get_json(silent=True) or {}
    raw_loc = str(data.get("location") or Config.MONITOR_LOCATION)
    location = re.sub(r"[^A-Z0-9_-]", "", raw_loc.strip().upper()) or Config.MONITOR_LOCATION
    sync_sheet = bool(data.get("sync_sheet", True))
    current_user = session.get("user", "")

    if not Config.has_emro_account(current_user):
        return jsonify({
            "success": False,
            "error": f"บัญชีของคุณ ({current_user}) ยังไม่ได้เชื่อมต่อกับระบบ eMRO (ไม่มีรหัสผ่าน/2FA) จึงไม่สามารถดึงข้อมูลจาก eMRO ได้"
        }), 403

    if BATCH_STATE["is_running"]:
        return jsonify({
            "success": False,
            "error": "ระบบกำลังเปิดใบงานชุด (Batch) อยู่ กรุณารอให้เสร็จสิ้นก่อนดึงข้อมูล Inventory"
        }), 409

    with _INVENTORY_LOCK:
        if INVENTORY_STATE["is_syncing"]:
            return jsonify({
                "success": False,
                "error": "กำลังซิงค์ข้อมูล Inventory จาก eMRO อยู่ กรุณารอสักครู่"
            }), 409
        INVENTORY_STATE["is_syncing"] = True
        INVENTORY_STATE["last_error"] = ""

    try:
        async def _scrape_inventory():
            creator = await WORKER.get_creator(user=current_user, slow_mo=40)
            try:
                await creator.dismiss_any_popups()
            except Exception:
                pass
            txns = await eMROScraper.scrape_inventory_from_page(
                creator.page,
                location=location,
                rows_per_page=50,
            )
            try:
                await creator.capture_live_screen("inventory_scraped")
            except Exception:
                pass
            return txns

        with WORKER.lock:
            transactions = WORKER.run_coro(_scrape_inventory(), timeout=180)

        detector = ChangeDetector()
        new_items, updated_items = detector.compare(transactions)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        normalized_items = [_normalize_inventory_item(it, default_last_synced=now_str) for it in (transactions or [])]

        sheet_synced = False
        if sync_sheet and transactions:
            try:
                sheets_client = GoogleSheetsClient()
                if sheets_client.is_configured:
                    sheets_client.update_live_sheet(transactions)
                    if new_items or updated_items:
                        sheets_client.append_activity_log(new_items, updated_items)
                    sheet_synced = True
            except Exception as se:
                logger.warning(f"Failed to sync live eMRO inventory to Google Sheets: {se}")

        existing_logs = []
        with _INVENTORY_LOCK:
            if INVENTORY_STATE.get("cache") and isinstance(INVENTORY_STATE["cache"].get("logs"), list):
                existing_logs = INVENTORY_STATE["cache"]["logs"]
        if not existing_logs and INVENTORY_SNAPSHOT_FILE.exists():
            try:
                prev_snap = json.loads(INVENTORY_SNAPSHOT_FILE.read_text(encoding="utf-8"))
                if isinstance(prev_snap.get("logs"), list):
                    existing_logs = prev_snap["logs"]
            except Exception:
                pass

        stats = compute_inventory_stats(normalized_items, last_sync=now_str)
        payload = {
            "success": True,
            "source": "emro_live",
            "location": location,
            "last_sync": now_str,
            "stats": stats,
            "items": normalized_items,
            "logs": existing_logs,
            "new_count": len(new_items),
            "updated_count": len(updated_items),
            "sheet_synced": sheet_synced,
            "is_syncing": False,
            "default_location": Config.MONITOR_LOCATION,
            "last_error": "",
        }
        save_inventory_snapshot(payload)
        with _INVENTORY_LOCK:
            INVENTORY_STATE["cache"] = payload
            INVENTORY_STATE["cache_ts"] = time.time()
        return jsonify(payload)

    except Exception as e:
        logger.exception("Error syncing inventory from eMRO")
        with _INVENTORY_LOCK:
            INVENTORY_STATE["last_error"] = str(e)
        return jsonify({"success": False, "error": f"ไม่สามารถดึงข้อมูลจาก eMRO ได้: {e}"}), 500
    finally:
        with _INVENTORY_LOCK:
            INVENTORY_STATE["is_syncing"] = False


@app.route("/api/inventory/export-excel", methods=["POST"])
def export_inventory_excel():
    try:
        data = request.get_json(silent=True) or {}
        items = data.get("items")
        if items is None:
            with _INVENTORY_LOCK:
                cached = INVENTORY_STATE.get("cache")
            if cached and isinstance(cached.get("items"), list):
                items = cached["items"]
            else:
                items = load_inventory_fallback().get("items", [])

        if not items:
            return jsonify({"error": "No inventory items to export"}), 400

        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Inventory Transactions"
        ws.views.sheetView[0].showGridLines = True

        header_fill = PatternFill(start_color="18181B", end_color="18181B", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        data_font = Font(name="Calibri", size=10)
        center_align = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")

        thin_border = Border(
            left=Side(style="thin", color="D1D5DB"),
            right=Side(style="thin", color="D1D5DB"),
            top=Side(style="thin", color="D1D5DB"),
            bottom=Side(style="thin", color="D1D5DB"),
        )

        columns = [
            ("Transaction NO", "transaction_no", True),
            ("Transaction Type", "transaction_type", True),
            ("P/N", "pn", False),
            ("S/N", "sn", False),
            ("Batch", "batch", True),
            ("GRB", "grb", True),
            ("Location", "location", True),
            ("Bin", "bin", True),
            ("Condition", "condition", True),
            ("QTY", "qty", True),
            ("Unit Cost", "unit_cost", True),
            ("A/C", "ac", True),
            ("W/O - S/O", "wo_so", True),
            ("Issued To", "issued_to", True),
            ("Issued To Name", "issued_to_name", False),
            ("Order Type", "order_type", True),
            ("Order NO", "order_no", True),
            ("Vendor Name", "vendor_name", False),
            ("Status", "status", True),
            ("Created Date", "created_date", True),
            ("Created By", "created_by", True),
            ("Name", "created_name", False),
            ("Defect Description", "defect_description", False),
        ]

        headers = [col[0] for col in columns]
        ws.append(headers)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align
            cell.border = thin_border
        ws.row_dimensions[1].height = 24

        for r_idx, itm in enumerate(items, start=2):
            row_data = [str(itm.get(key, "") or "").strip() for _, key, _ in columns]
            ws.append(row_data)
            ws.row_dimensions[r_idx].height = 20
            for c_idx, (_, _, is_center) in enumerate(columns, start=1):
                cell = ws.cell(row=r_idx, column=c_idx)
                cell.font = data_font
                cell.border = thin_border
                cell.alignment = center_align if is_center else left_align

        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = col[0].column_letter
            ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 48)

        bio = io.BytesIO()
        wb.save(bio)
        bio.seek(0)

        filename = f"Inventory_Transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(
            bio,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        logger.exception("Error exporting inventory transactions to Excel")
        return jsonify({"error": str(e)}), 500


# ==================== UNIFIED INVENTORY SEARCH & HISTORY (/api/inv/*) ====================
@app.route("/api/inv/status")
def api_inv_status():
    summary = inv_db.status_summary()
    summary["sync"] = inv_sync_worker.get_sync_state()
    summary["locations"] = InvConfig.LOCATIONS
    summary["sync_interval"] = InvConfig.SYNC_INTERVAL_MINUTES
    summary["sync_hours"] = f"{InvConfig.SYNC_START_HOUR:02d}:00–{InvConfig.SYNC_END_HOUR:02d}:00"
    summary["pin_required"] = bool(InvConfig.REFRESH_PIN)
    summary["lan_ip"] = get_lan_ip()
    summary["port"] = int(os.environ.get("PORT", 8000))
    return jsonify(summary)


@app.route("/api/inv/search")
def api_inv_search():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "all").strip().lower()
    location = request.args.get("location", "").strip().upper() or None
    try:
        limit = min(int(request.args.get("limit", "2000")), 5000)
    except ValueError:
        limit = 2000
    sort_by = request.args.get("sort_by", "pn").strip().lower()
    sort_dir = request.args.get("sort_dir", "asc").strip().lower()
    data = inv_db.search(q=q, status=status, location=location, limit=limit, sort_by=sort_by, sort_dir=sort_dir)
    return jsonify(data)


@app.route("/api/inv/item-history")
def api_inv_item_history():
    location = request.args.get("location", InvConfig.LOCATIONS[0]).strip().upper()
    pn = request.args.get("pn", "").strip()
    if not pn:
        return jsonify({"items": [], "transactions": []})
    return jsonify({
        "items": inv_db.item_history(location, pn),
        "transactions": inv_db.item_transactions(location, pn),
    })


@app.route("/api/inv/transactions")
def api_inv_transactions():
    q = request.args.get("q", "").strip()
    tx_type = request.args.get("tx_type", "all").strip()
    try:
        days = int(request.args.get("days", "0"))
    except ValueError:
        days = 0
    location = request.args.get("location", "").strip().upper() or None
    sort_by = request.args.get("sort_by", "tx_datetime").strip()
    sort_dir = request.args.get("sort_dir", "desc").strip()
    since = None
    if days == 1:
        since = datetime.now().strftime("%Y-%m-%d 00:00:00")
    elif days > 1:
        since = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d 00:00:00")
    data = inv_db.search_transactions(
        q=q, tx_type=tx_type, since=since, location=location, sort_by=sort_by, sort_dir=sort_dir, limit=2000
    )
    return jsonify(data)


@app.route("/api/inv/changes")
def api_inv_changes():
    try:
        days = int(request.args.get("days", "1"))
    except ValueError:
        days = 1
    location = request.args.get("location", "").strip().upper() or None
    if days <= 1:
        since = datetime.now().strftime("%Y-%m-%d 00:00:00")
    else:
        since = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d 00:00:00")
    items = inv_db.changes_since(since, location=location)
    return jsonify({"since": since, "total": len(items), "items": items})


@app.route("/api/inv/refresh", methods=["POST"])
def api_inv_refresh():
    body = request.get_json(silent=True) or {}
    pin = str(body.get("pin", "")).strip()
    if InvConfig.REFRESH_PIN and pin != InvConfig.REFRESH_PIN:
        return jsonify({"ok": False, "error": "รหัส PIN ไม่ถูกต้อง"}), 403

    user_label = session.get("user") or "user"
    started = inv_sync_worker.trigger_sync_async(triggered_by=f"manual-web:{user_label}")
    if not started:
        return jsonify({"ok": False, "error": "ระบบกำลังดึงข้อมูลอยู่แล้ว กรุณารอสักครู่"}), 409
    return jsonify({"ok": True, "message": "เริ่มดึงข้อมูลจาก eMRO แล้ว"})


@app.route("/api/inv/export.xlsx")
def api_inv_export_xlsx():
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    q = request.args.get("q", "").strip()
    status = request.args.get("status", "all").strip().lower()
    sort_by = request.args.get("sort_by", "pn").strip().lower()
    sort_dir = request.args.get("sort_dir", "asc").strip().lower()
    rows = inv_db.export_rows(q=q, status=status, sort_by=sort_by, sort_dir=sort_dir)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventory"

    headers = ["Location", "P/N", "Description", "Bin", "Batch", "S/N", "Avbl", "Rsvd", "UOM", "Status", "Last Seen", "Out Since"]
    ws.append(headers)

    header_fill = PatternFill("solid", fgColor="18181B")
    header_font = Font(bold=True, color="FFFFFF")
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for r in rows:
        ws.append([r.get(h, "") for h in headers])

    widths = [10, 20, 48, 12, 14, 18, 10, 10, 8, 10, 20, 20]
    for idx, w in enumerate(widths, start=1):
        col_letter = openpyxl.utils.get_column_letter(idx)
        ws.column_dimensions[col_letter].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return send_file(
        buf,
        as_attachment=True,
        download_name=f"Inventory_DM01_{stamp}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/api/inv/export-transactions.xlsx")
def api_inv_export_transactions_xlsx():
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    q = request.args.get("q", "").strip()
    tx_type = request.args.get("tx_type", "all").strip()
    try:
        days = int(request.args.get("days", "0"))
    except ValueError:
        days = 0
    sort_by = request.args.get("sort_by", "tx_datetime").strip()
    sort_dir = request.args.get("sort_dir", "desc").strip()
    since = None
    if days == 1:
        since = datetime.now().strftime("%Y-%m-%d 00:00:00")
    elif days > 1:
        since = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d 00:00:00")

    rows = inv_db.search_transactions(
        q=q, tx_type=tx_type, since=since, sort_by=sort_by, sort_dir=sort_dir, limit=50000
    )["items"]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Transaction History"

    headers = [
        "Created Date", "Type", "P/N", "Description", "Qty", "UOM", "GSE / A/C", "W/O - S/O",
        "Issued To", "Issued To Name", "Created By", "Created Name", "Location", "Bin", "Batch",
        "S/N", "Condition", "Transaction No", "Status",
    ]
    ws.append(headers)

    header_fill = PatternFill("solid", fgColor="18181B")
    header_font = Font(bold=True, color="FFFFFF")
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for r in rows:
        ws.append([
            r.get("created_date") or r.get("tx_datetime", ""),
            r.get("transaction_type", ""),
            r.get("pn", ""),
            r.get("description", ""),
            r.get("qty", 0),
            r.get("uom", ""),
            r.get("ac", ""),
            r.get("wo_so", ""),
            r.get("issued_to", ""),
            r.get("issued_to_name", ""),
            r.get("created_by", ""),
            r.get("created_name", ""),
            r.get("location", ""),
            r.get("bin", ""),
            r.get("batch", ""),
            r.get("sn", ""),
            r.get("condition", ""),
            r.get("transaction_no", ""),
            r.get("status", ""),
        ])

    widths = [20, 14, 18, 42, 10, 8, 16, 14, 14, 24, 14, 24, 10, 12, 14, 16, 10, 16, 10]
    for idx, w in enumerate(widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(idx)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return send_file(
        buf,
        as_attachment=True,
        download_name=f"Transaction_History_DM01_{stamp}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    import sys
    if sys.stdout is None or sys.stderr is None:
        log_out = open(_LOG_DIR / "stdout.log", "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = log_out
        if sys.stderr is None:
            sys.stderr = log_out

    inv_sync_worker.start_scheduler()

    port = int(os.environ.get("PORT", 8000))
    pid_file = Config.BASE_DIR / "data" / "web_app.pid"
    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    logger.info(f"Starting GSE Work Order Web App on http://0.0.0.0:{port} (PID {os.getpid()})...")
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=port, threads=16)
    except ImportError:
        logger.warning("waitress not installed -- falling back to Flask dev server (pip install waitress).")
        app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
