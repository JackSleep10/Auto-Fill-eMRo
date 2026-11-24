import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import web_app  # noqa: E402
from scraper.config import Config  # noqa: E402
from sheets.google_sheets import GoogleSheetsClient  # noqa: E402


class TestInventoryAPI(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.orig_snapshot = web_app.INVENTORY_SNAPSHOT_FILE
        self.orig_cache_file = Config.CACHE_FILE
        web_app.INVENTORY_SNAPSHOT_FILE = Path(self.tmp_dir.name) / "inventory_snapshot.json"
        Config.CACHE_FILE = Path(self.tmp_dir.name) / "cache.json"

        self.orig_inv_state = dict(web_app.INVENTORY_STATE)
        web_app.INVENTORY_STATE["is_syncing"] = False
        web_app.INVENTORY_STATE["last_error"] = ""
        web_app.INVENTORY_STATE["cache"] = None
        web_app.INVENTORY_STATE["cache_ts"] = 0.0

        self.orig_batch_running = web_app.BATCH_STATE["is_running"]
        web_app.BATCH_STATE["is_running"] = False

        self.client = web_app.app.test_client()

    def tearDown(self):
        web_app.INVENTORY_SNAPSHOT_FILE = self.orig_snapshot
        Config.CACHE_FILE = self.orig_cache_file
        web_app.INVENTORY_STATE.clear()
        web_app.INVENTORY_STATE.update(self.orig_inv_state)
        web_app.BATCH_STATE["is_running"] = self.orig_batch_running
        self.tmp_dir.cleanup()

    def _login(self, user="TL248006"):
        with self.client.session_transaction() as sess:
            sess["logged_in"] = True
            sess["user"] = user

    def test_rows_to_inventory_items_valid_31_cols(self):
        headers = list(GoogleSheetsClient.HEADERS)
        self.assertEqual(len(headers), 31)
        row = [f"VAL_{i}" for i in range(31)]
        row[0] = "41409704"
        row[1] = "ISSUED"
        row[2] = "4.10/3.50-6 TR87"
        row[7] = "DM01"
        row[8] = "TYRE02"
        row[10] = "1"
        row[30] = "2026-10-26 23:00:25"

        items = web_app.rows_to_inventory_items(headers, [row])
        self.assertIsNotNone(items)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["transaction_no"], "41409704")
        self.assertEqual(item["transaction_type"], "ISSUED")
        self.assertEqual(item["pn"], "4.10/3.50-6 TR87")
        self.assertEqual(item["location"], "DM01")
        self.assertEqual(item["bin"], "TYRE02")
        self.assertEqual(item["qty"], "1")
        self.assertEqual(item["last_synced"], "2026-10-26 23:00:25")
        self.assertEqual(len(item), 31)

    def test_rows_to_inventory_items_rejects_sheet_url_sync_headers(self):
        url_sync_headers = [
            "ลำดับ",
            "ประเภทการเชื่อมต่อ",
            "ลิงก์เข้าใช้งานล่าสุด (Click to Open)",
            "สถานะ (Status)",
            "อัปเดตล่าสุด (Last Updated)",
        ]
        url_sync_rows = [["1", "LAN", "http://127.0.0.1:8000", "ONLINE", "20/11/2026 08:00:00"]]
        self.assertIsNone(web_app.rows_to_inventory_items(url_sync_headers, url_sync_rows))

    def test_compute_inventory_stats(self):
        items = [
            {"transaction_type": "ISSUED", "last_synced": "2026-10-26 23:00:25"},
            {"transaction_type": "ISSUED"},
            {"transaction_type": "PO/RECEIVING"},
            {"transaction_type": "BIN/TRANSFER"},
            {"transaction_type": "RTS/WO"},
        ]
        stats = web_app.compute_inventory_stats(items)
        self.assertEqual(stats["total"], 5)
        self.assertEqual(stats["issued"], 2)
        self.assertEqual(stats["receiving"], 1)
        self.assertEqual(stats["transfer"], 2)
        self.assertEqual(stats["rts"], 1)
        self.assertEqual(stats["last_sync"], "2026-10-26 23:00:25")

    def test_get_inventory_requires_login(self):
        resp = self.client.get("/api/inventory")
        self.assertEqual(resp.status_code, 401)

    def test_get_inventory_mocked_sheets_and_fallback(self):
        self._login("TL248006")
        sample_row = [""] * 31
        sample_row[0] = "41409704"
        sample_row[1] = "ISSUED"
        sample_row[2] = "BOSNY-RED"
        sample_row[7] = "DM01"
        sample_row[8] = "RS-3"
        sample_row[10] = "2.00"
        sample_row[30] = "2026-10-26 23:00:25"

        mock_resp_ok = MagicMock()
        mock_resp_ok.status_code = 200
        mock_resp_ok.json.return_value = {
            "status": "success",
            "headers": list(GoogleSheetsClient.HEADERS),
            "rows": [sample_row],
            "stats": {"total": 1, "issued": 1, "receiving": 0, "transfer": 0, "lastSync": "2026-10-26 23:00:25"},
            "logs": [["2026-10-26 23:00:25", "NEW", "41409704", "ISSUED", "P/N: BOSNY-RED"]],
        }

        with patch.object(web_app, "_get_inventory_webhook_url", return_value="https://example.invalid/exec"):
            with patch("web_app.requests.get", return_value=mock_resp_ok):
                resp = self.client.get("/api/inventory")
                self.assertEqual(resp.status_code, 200)
                data = resp.get_json()
                self.assertTrue(data["success"])
                self.assertEqual(data["source"], "google_sheets")
                self.assertEqual(len(data["items"]), 1)
                self.assertEqual(data["items"][0]["pn"], "BOSNY-RED")
                self.assertEqual(data["stats"]["issued"], 1)
                self.assertTrue(web_app.INVENTORY_SNAPSHOT_FILE.exists())

            # Simulate sheet_url_sync overwriting Live Transactions headers
            mock_resp_url_sync = MagicMock()
            mock_resp_url_sync.status_code = 200
            mock_resp_url_sync.json.return_value = {
                "status": "success",
                "headers": ["ลำดับ", "ประเภทการเชื่อมต่อ", "ลิงก์เข้าใช้งานล่าสุด (Click to Open)"],
                "rows": [["1", "LAN", "http://127.0.0.1:8000"]],
            }
            with patch("web_app.requests.get", return_value=mock_resp_url_sync):
                resp2 = self.client.get("/api/inventory?refresh=1")
                self.assertEqual(resp2.status_code, 200)
                data2 = resp2.get_json()
                self.assertTrue(data2["success"])
                self.assertEqual(data2["source"], "snapshot")
                self.assertEqual(len(data2["items"]), 1)
                self.assertEqual(data2["items"][0]["pn"], "BOSNY-RED")

    def test_sync_emro_unlinked_user_403(self):
        self._login("TL186205")
        resp = self.client.post("/api/inventory/sync-emro", json={"location": "DM01"})
        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertFalse(data["success"])

    def test_sync_emro_batch_running_409(self):
        self._login("TL248006")
        web_app.BATCH_STATE["is_running"] = True
        resp = self.client.post("/api/inventory/sync-emro", json={"location": "DM01"})
        self.assertEqual(resp.status_code, 409)
        data = resp.get_json()
        self.assertFalse(data["success"])

    def test_export_inventory_excel_returns_xlsx(self):
        self._login("TL248006")
        items = [
            {
                "transaction_no": "41409704",
                "transaction_type": "ISSUED",
                "pn": "4.10/3.50-6 TR87",
                "sn": "",
                "batch": "4897241",
                "grb": "4897241",
                "location": "DM01",
                "bin": "TYRE02",
                "condition": "FN",
                "qty": "1",
                "unit_cost": "0",
                "ac": "TLM-GE-004",
                "wo_so": "2356161",
                "issued_to": "TL258728",
                "issued_to_name": "KHANTHON CHANTHAKHOT",
                "order_type": "",
                "order_no": "",
                "vendor_name": "",
                "status": "OPEN",
                "created_date": "2026-10-26 22:17:20",
                "created_by": "TL248006",
                "created_name": "BANNATHAT TATA",
                "defect_description": "",
            }
        ]
        resp = self.client.post("/api/inventory/export-excel", json={"items": items})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            resp.content_type,
        )
        self.assertTrue(resp.data.startswith(b"PK"))

        wb = openpyxl.load_workbook(io.BytesIO(resp.data))
        ws = wb.active
        self.assertEqual(ws.cell(1, 1).value, "Transaction NO")
        self.assertEqual(ws.cell(2, 1).value, "41409704")
        self.assertEqual(ws.cell(2, 3).value, "4.10/3.50-6 TR87")


class TestUnifiedInventorySearchAPI(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.orig_db_file = web_app.InvConfig.DB_FILE
        self.orig_pin = web_app.InvConfig.REFRESH_PIN
        web_app.InvConfig.DB_FILE = Path(self.tmp_dir.name) / "inventory.db"
        web_app.inv_db.init_db()
        self.client = web_app.app.test_client()

    def tearDown(self):
        web_app.InvConfig.DB_FILE = self.orig_db_file
        web_app.InvConfig.REFRESH_PIN = self.orig_pin
        self.tmp_dir.cleanup()

    def _login(self, user="TL248006"):
        with self.client.session_transaction() as sess:
            sess["logged_in"] = True
            sess["user"] = user

    def _seed_sample_data(self):
        snapshot_rows = [
            {
                "location": "DM01",
                "bin": "TYRE02",
                "batch": "4897241",
                "pn": "4.10/3.50-6 TR87",
                "sn": "",
                "description": "TUBE TYPE TYRE",
                "uom": "EA",
                "condition": "FN",
                "avbl": 4.0,
                "rsvd": 0.0,
            },
            {
                "location": "DM01",
                "bin": "RS-3",
                "batch": "4766094",
                "pn": "BOSNY-RED",
                "sn": "",
                "description": "SPRAY PAINT RED",
                "uom": "EA",
                "condition": "SV",
                "avbl": 2.0,
                "rsvd": 1.0,
            },
        ]
        web_app.inv_db.apply_snapshot("DM01", snapshot_rows, "export", (2, 2), "2026-11-24 09:00:00", triggered_by="test")
        # Second snapshot removes BOSNY-RED so it becomes OUT_OF_STOCK
        web_app.inv_db.apply_snapshot("DM01", [snapshot_rows[0]], "export", (1, 1), "2026-11-24 09:30:00", triggered_by="test")

        web_app.inv_db.save_transactions(
            [
                {
                    "transaction_no": "41409704",
                    "transaction_type": "ISSUED",
                    "created_date": "11/24/2026 09:15:00",
                    "tx_datetime": "2026-11-24 09:15:00",
                    "location": "DM01",
                    "bin": "RS-3",
                    "batch": "4766094",
                    "grb": "4766094",
                    "pn": "BOSNY-RED",
                    "sn": "",
                    "condition": "SV",
                    "qty": "2.00",
                    "ac": "TLM-GE-004",
                    "wo_so": "2356161",
                    "issued_to": "TL258728",
                    "issued_to_name": "KHANTHON CHANTHAKHOT",
                    "created_by": "TL248006",
                    "created_name": "BANNATHAT TATA",
                    "status": "OPEN",
                }
            ],
            location="DM01",
            min_date_iso="",
        )

    def test_inv_status_requires_login_and_returns_summary(self):
        resp_unauth = self.client.get("/api/inv/status")
        self.assertEqual(resp_unauth.status_code, 401)

        self._login("TL248006")
        self._seed_sample_data()
        resp = self.client.get("/api/inv/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["counts"]["in_pns"], 1)
        self.assertEqual(data["counts"]["out_pns"], 1)
        self.assertEqual(data["counts"]["tx_total"], 1)
        self.assertIn("sync", data)
        self.assertIn("locations", data)

    def test_inv_search_filter_and_sort(self):
        self._login("TL248006")
        self._seed_sample_data()

        r_all = self.client.get("/api/inv/search?status=all")
        self.assertEqual(r_all.status_code, 200)
        self.assertEqual(r_all.get_json()["total"], 2)

        r_in = self.client.get("/api/inv/search?status=in&q=TYRE")
        d_in = r_in.get_json()
        self.assertEqual(d_in["total"], 1)
        self.assertEqual(d_in["items"][0]["pn"], "4.10/3.50-6 TR87")

        r_out = self.client.get("/api/inv/search?status=out&q=BOSNY")
        d_out = r_out.get_json()
        self.assertEqual(d_out["total"], 1)
        self.assertEqual(d_out["items"][0]["pn"], "BOSNY-RED")
        self.assertEqual(d_out["items"][0]["status"], "OUT")

    def test_inv_transactions_item_history_and_changes(self):
        self._login("TL248006")
        self._seed_sample_data()

        r_tx = self.client.get("/api/inv/transactions?q=TLM-GE-004&tx_type=ISSUED")
        self.assertEqual(r_tx.status_code, 200)
        d_tx = r_tx.get_json()
        self.assertEqual(d_tx["total"], 1)
        self.assertEqual(d_tx["items"][0]["wo_so"], "2356161")

        r_hist = self.client.get("/api/inv/item-history?location=DM01&pn=BOSNY-RED")
        self.assertEqual(r_hist.status_code, 200)
        d_hist = r_hist.get_json()
        self.assertGreaterEqual(len(d_hist["items"]), 1)
        self.assertEqual(len(d_hist["transactions"]), 1)

        r_chg = self.client.get("/api/inv/changes?days=7")
        self.assertEqual(r_chg.status_code, 200)
        self.assertGreaterEqual(r_chg.get_json()["total"], 1)

    def test_inv_refresh_pin_check_403(self):
        self._login("TL248006")
        web_app.InvConfig.REFRESH_PIN = "654321"
        resp = self.client.post("/api/inv/refresh", json={"pin": "000000"})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(resp.get_json()["ok"])

    def test_inv_export_xlsx_endpoints(self):
        self._login("TL248006")
        self._seed_sample_data()

        r_stock = self.client.get("/api/inv/export.xlsx?status=all")
        self.assertEqual(r_stock.status_code, 200)
        self.assertTrue(r_stock.data.startswith(b"PK"))
        wb_stock = openpyxl.load_workbook(io.BytesIO(r_stock.data))
        self.assertEqual(wb_stock.active.cell(1, 2).value, "P/N")

        r_tx = self.client.get("/api/inv/export-transactions.xlsx")
        self.assertEqual(r_tx.status_code, 200)
        self.assertTrue(r_tx.data.startswith(b"PK"))
        wb_tx = openpyxl.load_workbook(io.BytesIO(r_tx.data))
        self.assertEqual(wb_tx.active.cell(1, 3).value, "P/N")
        self.assertEqual(wb_tx.active.cell(2, 3).value, "BOSNY-RED")


if __name__ == "__main__":
    unittest.main()
