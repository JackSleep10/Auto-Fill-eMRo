"""Flask web server for Inventory Search & Transaction Tracking (Port 8001)."""
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

import io
import logging
import socket
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, render_template, request, send_file

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from inventory import db, sync_worker
from inventory.config import Config

_LOG_DIR = Config.DATA_DIR / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_file_handler = RotatingFileHandler(_LOG_DIR / "web_app.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _console_handler])
logger = logging.getLogger("InventoryWeb")

app = Flask(__name__)
app.secret_key = Config.FLASK_SECRET_KEY
app.config["TEMPLATES_AUTO_RELOAD"] = True


def get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


@app.route("/")
def index():
    return render_template(
        "index.html",
        locations=Config.LOCATIONS,
        lan_ip=get_lan_ip(),
        port=Config.WEB_PORT,
        pin_required=bool(Config.REFRESH_PIN),
        sync_interval=Config.SYNC_INTERVAL_MINUTES,
        sync_hours=f"{Config.SYNC_START_HOUR:02d}:00–{Config.SYNC_END_HOUR:02d}:00",
    )


@app.route("/api/status")
def api_status():
    summary = db.status_summary()
    summary["sync"] = sync_worker.get_sync_state()
    summary["locations"] = Config.LOCATIONS
    summary["lan_ip"] = get_lan_ip()
    summary["port"] = Config.WEB_PORT
    return jsonify(summary)


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "all").strip().lower()
    location = request.args.get("location", "").strip().upper() or None
    limit = min(int(request.args.get("limit", "2000")), 5000)
    sort_by = request.args.get("sort_by", "pn").strip().lower()
    sort_dir = request.args.get("sort_dir", "asc").strip().lower()
    data = db.search(q=q, status=status, location=location, limit=limit, sort_by=sort_by, sort_dir=sort_dir)
    return jsonify(data)


@app.route("/api/item-history")
def api_item_history():
    location = request.args.get("location", Config.LOCATIONS[0]).strip().upper()
    pn = request.args.get("pn", "").strip()
    if not pn:
        return jsonify({"items": [], "transactions": []})
    return jsonify({
        "items": db.item_history(location, pn),
        "transactions": db.item_transactions(location, pn),
    })


@app.route("/api/transactions")
def api_transactions():
    q = request.args.get("q", "").strip()
    tx_type = request.args.get("tx_type", "all").strip()
    days = int(request.args.get("days", "0"))
    location = request.args.get("location", "").strip().upper() or None
    sort_by = request.args.get("sort_by", "tx_datetime").strip()
    sort_dir = request.args.get("sort_dir", "desc").strip()
    since = None
    if days == 1:
        since = datetime.now().strftime("%Y-%m-%d 00:00:00")
    elif days > 1:
        since = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d 00:00:00")
    data = db.search_transactions(
        q=q, tx_type=tx_type, since=since, location=location, sort_by=sort_by, sort_dir=sort_dir, limit=2000
    )
    return jsonify(data)


@app.route("/api/export-transactions.xlsx")
def api_export_transactions_xlsx():
    q = request.args.get("q", "").strip()
    tx_type = request.args.get("tx_type", "all").strip()
    days = int(request.args.get("days", "0"))
    sort_by = request.args.get("sort_by", "tx_datetime").strip()
    sort_dir = request.args.get("sort_dir", "desc").strip()
    since = None
    if days == 1:
        since = datetime.now().strftime("%Y-%m-%d 00:00:00")
    elif days > 1:
        since = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d 00:00:00")
    rows = db.search_transactions(
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

    header_fill = PatternFill("solid", fgColor="0F172A")
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


@app.route("/api/changes")
def api_changes():
    days = int(request.args.get("days", "1"))
    location = request.args.get("location", "").strip().upper() or None
    if days <= 1:
        since = datetime.now().strftime("%Y-%m-%d 00:00:00")
    else:
        since = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d 00:00:00")
    items = db.changes_since(since, location=location)
    return jsonify({"since": since, "total": len(items), "items": items})


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    body = request.get_json(silent=True) or {}
    pin = str(body.get("pin", "")).strip()
    if Config.REFRESH_PIN and pin != Config.REFRESH_PIN:
        return jsonify({"ok": False, "error": "รหัส PIN ไม่ถูกต้อง"}), 403

    started = sync_worker.trigger_sync_async(triggered_by="manual-web")
    if not started:
        return jsonify({"ok": False, "error": "ระบบกำลังดึงข้อมูลอยู่แล้ว กรุณารอสักครู่"}), 409
    return jsonify({"ok": True, "message": "เริ่มดึงข้อมูลจาก eMRO แล้ว"})


@app.route("/api/export.xlsx")
def api_export_xlsx():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "all").strip().lower()
    sort_by = request.args.get("sort_by", "pn").strip().lower()
    sort_dir = request.args.get("sort_dir", "asc").strip().lower()
    rows = db.export_rows(q=q, status=status, sort_by=sort_by, sort_dir=sort_dir)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventory"

    headers = ["Location", "P/N", "Description", "Bin", "Batch", "S/N", "Avbl", "Rsvd", "UOM", "Status", "Last Seen", "Out Since"]
    ws.append(headers)

    header_fill = PatternFill("solid", fgColor="0F172A")
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


def initialize():
    # If running under pythonw.exe, redirect stdout/stderr to avoid NoneType write crashes
    import sys
    if sys.stdout is None or sys.stderr is None:
        log_out = open(_LOG_DIR / "stdout.log", "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = log_out
        if sys.stderr is None:
            sys.stderr = log_out

    pid_file = Config.DATA_DIR / "inventory_web.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    db.init_db()
    sync_worker.seed_from_existing_export_if_empty()
    sync_worker.start_scheduler()


if __name__ == "__main__":
    initialize()
    logger.info(f"Starting Inventory Search Web App on http://0.0.0.0:{Config.WEB_PORT} (LAN: http://{get_lan_ip()}:{Config.WEB_PORT})")
    print(f"[INFO] Serving Inventory Search on http://0.0.0.0:{Config.WEB_PORT} (LAN: http://{get_lan_ip()}:{Config.WEB_PORT})", flush=True)
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=Config.WEB_PORT, threads=16)
    except ImportError:
        logger.warning("waitress not installed -- falling back to Flask dev server.")
        app.run(host="0.0.0.0", port=Config.WEB_PORT, debug=False, threaded=True)
