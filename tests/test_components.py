import unittest
from bs4 import BeautifulSoup
from scraper.parser import eMROParser
from scraper.change_detector import ChangeDetector
from pathlib import Path
import tempfile

class TestEMROComponents(unittest.TestCase):
    def test_parse_transaction_row(self):
        # Sample table cells:
        # Col 0: Select, Col 1: Toggler, Col 2: Type, Col 3: P/N, Col 4: S/N, Col 5: Batch, Col 6: GRB, Col 7: Lot
        cells = ["Select", "", "ISSUED", "BOSNY-RED", "", "4766094", "4766094", ""]

        # Expanded detail HTML with standard table layout
        detail_html = """
        <div class="ui-expanded-row-content">
          <table>
            <tr>
              <td><label>Location</label></td>
              <td><label>Bin</label></td>
              <td><label>QTY</label></td>
              <td><label>Transaction NO</label></td>
              <td><label>Status</label></td>
            </tr>
            <tr>
              <td><input value="DM01" /></td>
              <td><input value="RS-3" /></td>
              <td><input value="2.00" /></td>
              <td><input value="40817106" /></td>
              <td><input value="OPEN" /></td>
            </tr>
          </table>
        </div>
        """

        result = eMROParser.parse_transaction_row(cells, detail_html)
        self.assertEqual(result["transaction_type"], "ISSUED")
        self.assertEqual(result["pn"], "BOSNY-RED")
        self.assertEqual(result["batch"], "4766094")
        self.assertEqual(result["grb"], "4766094")
        self.assertEqual(result["location"], "DM01")
        self.assertEqual(result["bin"], "RS-3")
        self.assertEqual(result["qty"], "2.00")
        self.assertEqual(result["transaction_no"], "40817106")
        self.assertEqual(result["status"], "OPEN")
        print("\n[OK] Parser test passed successfully!")

    def test_change_detector(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            detector = ChangeDetector(cache_file=tmp_path)
            
            sample_data = [
                {"transaction_no": "40817106", "pn": "BOSNY-RED", "qty": "2.00", "status": "OPEN"},
                {"transaction_no": "40811121", "pn": "81570-0K100", "qty": "1.00", "status": ""}
            ]
            new_items, updated = detector.compare(sample_data)
            self.assertEqual(len(new_items), 2)
            self.assertEqual(len(updated), 0)

            # Second run with no changes
            new_items, updated = detector.compare(sample_data)
            self.assertEqual(len(new_items), 0)
            self.assertEqual(len(updated), 0)

            # Third run with one new item and one updated status
            modified_data = [
                {"transaction_no": "40817106", "pn": "BOSNY-RED", "qty": "2.00", "status": "CLOSED"},
                {"transaction_no": "40811121", "pn": "81570-0K100", "qty": "1.00", "status": ""},
                {"transaction_no": "40810315", "pn": "7.00-14", "qty": "10.00", "status": ""}
            ]
            new_items, updated = detector.compare(modified_data)
            self.assertEqual(len(new_items), 1)
            self.assertEqual(new_items[0]["transaction_no"], "40810315")
            self.assertEqual(len(updated), 1)
            self.assertEqual(updated[0]["transaction_no"], "40817106")
            print("[OK] ChangeDetector test passed successfully!")

        finally:
            if tmp_path.exists():
                tmp_path.unlink()

if __name__ == "__main__":
    unittest.main()
