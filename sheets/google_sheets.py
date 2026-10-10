import datetime
from typing import List, Dict
import requests
from scraper.config import Config

class GoogleSheetsClient:
    HEADERS = [
        "Transaction NO", "Transaction Type", "P/N", "S/N", "Batch", "GRB", "Vendor Lot",
        "Location", "Bin", "Condition", "QTY", "Unit Cost", "Secondary Cost", "CUR EXC Rate",
        "A/C", "W/O - S/O", "Issued To", "Issued To Name", "Order Type", "Order NO", "Line",
        "Vendor/Customer", "Vendor Name", "Reference", "Status", "Created By", "Created Date",
        "Name", "G/L", "Defect Description", "Last Synced"
    ]

    def __init__(self):
        raw_url = Config.APPS_SCRIPT_URL.strip()
        if raw_url:
            if raw_url.startswith("http://") or raw_url.startswith("https://"):
                self.webhook_url = raw_url
            else:
                # User provided just the Script/Deployment ID
                self.webhook_url = f"https://script.google.com/macros/s/{raw_url}/exec"
        else:
            self.webhook_url = ""

        if self.webhook_url:
            print(f"[GoogleSheets] Using Apps Script Webhook: {self.webhook_url}")
        else:
            print("[GoogleSheets] APPS_SCRIPT_URL is not set in .env. Skipping Google Sheets sync.")

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    def update_live_sheet(self, transactions: List[Dict]):
        if not self.is_configured:
            return

        try:
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rows_data = []

            for item in transactions:
                row = [
                    item.get("transaction_no", ""),
                    item.get("transaction_type", ""),
                    item.get("pn", ""),
                    item.get("sn", ""),
                    item.get("batch", ""),
                    item.get("grb", ""),
                    item.get("vendor_lot", ""),
                    item.get("location", ""),
                    item.get("bin", ""),
                    item.get("condition", ""),
                    item.get("qty", ""),
                    item.get("unit_cost", ""),
                    item.get("secondary_cost", ""),
                    item.get("cur_exc_rate", ""),
                    item.get("ac", ""),
                    item.get("wo_so", ""),
                    item.get("issued_to", ""),
                    item.get("issued_to_name", ""),
                    item.get("order_type", ""),
                    item.get("order_no", ""),
                    item.get("order_line", ""),
                    item.get("vendor_customer", ""),
                    item.get("vendor_name", ""),
                    item.get("reference", ""),
                    item.get("status", ""),
                    item.get("created_by", ""),
                    item.get("created_date", ""),
                    item.get("created_name", ""),
                    item.get("gl", ""),
                    item.get("defect_description", ""),
                    now_str
                ]
                rows_data.append(row)

            payload = {
                "action": "update_live",
                "headers": self.HEADERS,
                "rows": rows_data
            }

            resp = requests.post(self.webhook_url, json=payload, timeout=30, allow_redirects=True)
            if resp.status_code == 200:
                print(f"[GoogleSheets] Successfully synced {len(rows_data)} rows to Google Sheets at {now_str}")
            else:
                print(f"[GoogleSheets] Sync response: {resp.status_code} - {resp.text[:200]}")

        except Exception as e:
            print(f"[GoogleSheets] Error syncing to Google Sheets: {e}")

    def append_activity_log(self, new_items: List[Dict], updated_items: List[Dict]):
        if not self.is_configured:
            return

        try:
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            events = []

            for item in new_items:
                details = f"P/N: {item.get('pn', '')} | QTY: {item.get('qty', '')} | Bin: {item.get('bin', '')} | By: {item.get('created_name', '')}"
                events.append([now_str, "NEW", item.get("transaction_no", ""), item.get("transaction_type", ""), details])

            for item in updated_items:
                details = f"Status: {item.get('status', '')} | P/N: {item.get('pn', '')} | QTY: {item.get('qty', '')}"
                events.append([now_str, "UPDATED", item.get("transaction_no", ""), item.get("transaction_type", ""), details])

            if not events:
                return

            payload = {
                "action": "append_log",
                "events": events
            }

            resp = requests.post(self.webhook_url, json=payload, timeout=30, allow_redirects=True)
            if resp.status_code == 200:
                print(f"[GoogleSheets] Appended {len(events)} events to Activity Log")
            else:
                print(f"[GoogleSheets] Activity log response: {resp.status_code} - {resp.text[:200]}")

        except Exception as e:
            print(f"[GoogleSheets] Error appending to Activity Log: {e}")
