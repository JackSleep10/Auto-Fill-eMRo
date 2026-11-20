import os
import sys
import io
import time
import socket
import subprocess
import webbrowser
import re
import atexit
from pathlib import Path

# Force UTF-8 encoding on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent

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

def kill_existing():
    try:
        subprocess.run(["taskkill", "/f", "/im", "cloudflared.exe"], capture_output=True)
    except Exception:
        pass
    # Free port 8000 if occupied by another process
    try:
        res = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
        for line in res.stdout.splitlines():
            if ":8000" in line and "LISTENING" in line:
                parts = line.strip().split()
                pid = parts[-1]
                if pid and pid != "0" and pid != str(os.getpid()):
                    subprocess.run(["taskkill", "/f", "/pid", pid], capture_output=True)
    except Exception:
        pass

def main():
    os.chdir(str(BASE_DIR))
    kill_existing()

    lan_ip = get_lan_ip()
    log_file = BASE_DIR / "data" / "cloudflare.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    if log_file.exists():
        try:
            log_file.unlink()
        except Exception:
            pass

    print("=" * 66)
    print("  THAI LION AIR - GSE WORK ORDER CREATOR")
    print("=" * 66)
    print("\n  [+] กำลังเริ่มการทำงานระบบเซิร์ฟเวอร์...")

    # Start Flask Web App in background
    web_proc = subprocess.Popen(
        [sys.executable, "web_app.py"],
        cwd=str(BASE_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Start Cloudflare Tunnel
    cf_proc = None
    cf_exe = BASE_DIR / "cloudflared.exe"
    if cf_exe.exists():
        cf_proc = subprocess.Popen(
            [str(cf_exe), "tunnel", "--url", "http://127.0.0.1:8000", "--logfile", str(log_file)],
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    def cleanup():
        print("\n  [-] กำลังปิดระบบ...")
        try:
            if web_proc and web_proc.poll() is None:
                web_proc.terminate()
        except Exception:
            pass
        try:
            if cf_proc and cf_proc.poll() is None:
                cf_proc.terminate()
        except Exception:
            pass
        kill_existing()

    atexit.register(cleanup)

    # Wait until web server is listening on port 8000
    server_ready = False
    for _ in range(30):
        try:
            with socket.create_connection(("127.0.0.1", 8000), timeout=0.5):
                server_ready = True
                break
        except Exception:
            time.sleep(0.3)

    # Extract Cloudflare URL from log only when cloudflared is running
    cf_url = ""
    if cf_exe.exists() and cf_proc is not None:
        cf_url = "Checking..."
        for _ in range(6):
            if log_file.exists():
                try:
                    content = log_file.read_text(encoding="utf-8", errors="ignore")
                    m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", content)
                    if m:
                        cf_url = m.group(0)
                        break
                except Exception:
                    pass
            time.sleep(1)

    # Auto sync latest Online URL to Google Sheet for outside users
    if cf_url.startswith("https://"):
        try:
            import threading
            from scraper.sheet_url_sync import sync_online_url_to_sheet
            threading.Thread(target=sync_online_url_to_sheet, args=(cf_url, lan_ip), daemon=True).start()
        except Exception:
            pass

    # Open local browser once server is confirmed ready
    if server_ready:
        try:
            webbrowser.open("http://localhost:8000")
        except Exception:
            pass

    os.system("cls" if os.name == "nt" else "clear")
    print("=" * 66)
    print("  THAI LION AIR - GSE WORK ORDER CREATOR")
    print("=" * 66)
    print(f"\n  [1] ลิงก์ภายในวงเน็ต (LAN / Wi-Fi) : http://{lan_ip}:8000")
    print("      (ลิงก์คงที่ ไม่เปลี่ยน เข้าได้ทุกเครื่องในออฟฟิศ/วงเน็ตเดียวกัน)\n")
    print(f"  [2] ลิงก์เครื่องนี้ (Localhost)      : http://localhost:8000\n")
    if cf_url.startswith("https://"):
        print(f"  [3] ลิงก์ออนไลน์ภายนอก (Cloudflare) : {cf_url}")
        print("      (สำหรับเข้านอกสถานที่ / เชื่อมต่อผ่านเน็ตมือถือ 4G/5G)")
        print("      * อัปเดตลิงก์ไปยัง Google Sheet (แท็บ Live Transactions) เรียบร้อยแล้ว\n")
    print("-" * 66)
    print("  สถานะ: ระบบออนไลน์พร้อมใช้งานแล้ว! (Online and Ready)")
    print("\n  * เปิดหน้าต่างนี้ค้างไว้ตลอดการใช้งาน")
    print("  * หากต้องการปิดระบบ: กด Ctrl+C หรือปิดหน้าต่างนี้")
    print("=" * 66)

    try:
        while True:
            time.sleep(1)
            if web_proc.poll() is not None:
                print("\n[!] Web server process exited unexpectedly!")
                break
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()

if __name__ == "__main__":
    main()
