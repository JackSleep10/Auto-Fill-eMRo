import asyncio
import datetime
import os
import signal
import sys
import ctypes
from pathlib import Path

from scraper.config import Config
from scraper.emro_scraper import eMROScraper
from scraper.change_detector import ChangeDetector
from sheets.google_sheets import GoogleSheetsClient

def is_pid_running(pid: int) -> bool:
    """Check if process with given PID is still active on Windows."""
    if pid <= 0:
        return False
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    exit_code = ctypes.c_ulong()
    ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
    ctypes.windll.kernel32.CloseHandle(handle)
    return exit_code.value == STILL_ACTIVE

class DualWriter:
    """Redirects stdout/stderr to both console (if available) and data/monitor.log."""
    def __init__(self, log_path, original_stream):
        self.original_stream = original_stream
        self.log_file = open(log_path, "a", encoding="utf-8", buffering=1)

    def write(self, text):
        if self.original_stream:
            try:
                self.original_stream.write(text)
            except Exception:
                pass
        try:
            self.log_file.write(text)
        except Exception:
            pass

    def flush(self):
        if self.original_stream:
            try:
                self.original_stream.flush()
            except Exception:
                pass
        try:
            self.log_file.flush()
        except Exception:
            pass

BASE_DIR = Path(__file__).resolve().parent

def setup_logging():
    log_dir = BASE_DIR / "data"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "monitor.log"
    sys.stdout = DualWriter(log_file, sys.stdout)
    sys.stderr = DualWriter(log_file, sys.stderr)

PID_FILE = BASE_DIR / "data" / "monitor.pid"

def acquire_pid_lock() -> bool:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            if is_pid_running(old_pid):
                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [MonitorApplication] Another instance is already running with PID {old_pid}. Exiting.")
                return False
        except Exception:
            pass
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    return True

def release_pid_lock():
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except Exception:
        pass

class MonitorApplication:
    def __init__(self):
        self.scraper = eMROScraper()
        self.detector = ChangeDetector()
        self.sheets = GoogleSheetsClient()
        self.is_running = True

    async def run(self):
        print("\n" + "="*70)
        print("  eMRO Real-time Inventory Monitor & Dashboard Sync")
        print(f"  Process PID:      {os.getpid()}")
        print(f"  Target URL:       {Config.EMRO_URL}")
        print(f"  Target Location:  {Config.MONITOR_LOCATION}")
        print(f"  Polling Interval: {Config.POLL_INTERVAL_SECONDS} seconds")
        print(f"  Headless Mode:    {Config.HEADLESS}")
        print(f"  Session Storage:  {Config.SESSION_DIR}")
        print(f"  Google Sheets:    {'Configured' if self.sheets.is_configured else 'Not configured'}")
        print("="*70 + "\n")

        try:
            # 1. Initialize scraper and ensure session/2FA is active
            await self.scraper.initialize()
            await self.scraper.ensure_authenticated()

            cycle_count = 0
            while self.is_running:
                cycle_count += 1
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n[{now_str}] --- Cycle #{cycle_count}: Polling eMRO for Location {Config.MONITOR_LOCATION} ---")

                try:
                    # 2. Extract transactions from eMRO
                    transactions = await self.scraper.query_inventory_transactions(Config.MONITOR_LOCATION)

                    if transactions:
                        # 3. Detect changes (new transactions or status updates)
                        new_items, updated_items = self.detector.compare(transactions)

                        print(f"[{now_str}] Total Records: {len(transactions)} | New: {len(new_items)} | Updated: {len(updated_items)}")

                        # 4. Sync to Google Sheets
                        if self.sheets.is_configured:
                            self.sheets.update_live_sheet(transactions)
                            if new_items or updated_items:
                                self.sheets.append_activity_log(new_items, updated_items)
                        else:
                            # Log new transactions to console if Google Sheets is not configured yet
                            for item in new_items:
                                print(f"  [NEW] {item.get('transaction_type')} | P/N: {item.get('pn')} | QTY: {item.get('qty')} | Trans NO: {item.get('transaction_no')}")

                    else:
                        print(f"[{now_str}] No transactions returned in this cycle (or session refreshed).")

                except Exception as e:
                    print(f"[{now_str}] Error during poll cycle: {e}")
                    await self.scraper.take_screenshot("cycle_error")

                # 5. Wait for the next poll interval (keeps session active!)
                print(f"[{now_str}] Waiting {Config.POLL_INTERVAL_SECONDS} seconds until next check...")
                await asyncio.sleep(Config.POLL_INTERVAL_SECONDS)

        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n[MonitorApplication] Shutdown requested by user.")
        finally:
            await self.shutdown()

    async def shutdown(self):
        print("[MonitorApplication] Cleaning up resources...")
        self.is_running = False
        await self.scraper.close()
        release_pid_lock()
        print("[MonitorApplication] Shutdown complete. Goodbye!")

if __name__ == "__main__":
    setup_logging()
    if not acquire_pid_lock():
        sys.exit(0)

    app = MonitorApplication()
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        print("\nExited.")
    finally:
        release_pid_lock()
