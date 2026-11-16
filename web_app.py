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
from datetime import datetime
from pathlib import Path
from typing import Optional
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, send_file

from scraper.config import Config
from scraper.gse_wo_creator import GSEWorkOrderCreator
from scraper.history_store import append_history, load_history

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
MASTER_CSV_PATH = Path("data/gse_master_list.csv")

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

load_master_list()

def sync_master_from_google_sheet():
    global GSE_MASTER
    url = "https://docs.google.com/spreadsheets/d/1i0hjTtfuJZX5EVIDxKNGcj4zr4qy3xuZHar1NAeYsQ0/export?format=csv&gid=982490752"
    try:
        import requests
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200 and "GSE NO." in resp.text:
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

if __name__ == "__main__":
    import sys
    if sys.stdout is None or sys.stderr is None:
        log_out = open(_LOG_DIR / "stdout.log", "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = log_out
        if sys.stderr is None:
            sys.stderr = log_out

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
