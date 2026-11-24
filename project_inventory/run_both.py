"""THAI LION AIR - Run both eMRO Web Systems in a single console window.

- Port 8000: GSE Work Order Creator
- Port 8001: Inventory Search & Transaction History
"""
import atexit
import os
import socket
import subprocess
import sys
import time

# Reconfigure stdout/stderr to UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def free_port(port: int):
    """Release port if held by a previous stale process."""
    try:
        cmd = f'powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"'
        res = subprocess.check_output(cmd, shell=True, text=True).strip()
        for line in res.splitlines():
            line = line.strip()
            if line.isdigit():
                pid = int(line)
                if pid != os.getpid():
                    print(f"[INFO] Freeing Port {port} (Terminating stale PID {pid})...")
                    subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(0.5)
    except Exception:
        pass


def main():
    lan_ip = get_lan_ip()
    print("=" * 72)
    print("      THAI LION AIR - eMRO SYSTEMS RUNNER (SINGLE CONSOLE)")
    print("=" * 72)
    print(f" [1] GSE Work Order Creator  : http://localhost:8000  (LAN: http://{lan_ip}:8000)")
    print(f" [2] Inventory Search (DM01) : http://localhost:8001  (LAN: http://{lan_ip}:8001)")
    print("=" * 72)

    # Ensure ports are clean before starting
    free_port(8000)
    free_port(8001)

    print(" Starting both services in this single window...")
    print(" Press Ctrl+C or close this window to stop both services.\n")

    py_exe = sys.executable

    p_gse = subprocess.Popen(
        [py_exe, "web_app.py"],
        cwd=r"D:\Project dashboard",
    )
    p_inv = subprocess.Popen(
        [py_exe, "web_app.py"],
        cwd=r"D:\Project inventory",
    )

    def cleanup():
        print("\nStopping both services...")
        for p in (p_gse, p_inv):
            try:
                if p.poll() is None:
                    p.terminate()
            except Exception:
                pass
        time.sleep(1)
        for p in (p_gse, p_inv):
            try:
                if p.poll() is None:
                    p.kill()
            except Exception:
                pass
        print("All services stopped.")

    atexit.register(cleanup)

    try:
        while True:
            if p_gse.poll() is not None:
                print(f"[WARNING] GSE Work Order process exited with code {p_gse.returncode}")
                break
            if p_inv.poll() is not None:
                print(f"[WARNING] Inventory Search process exited with code {p_inv.returncode}")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
