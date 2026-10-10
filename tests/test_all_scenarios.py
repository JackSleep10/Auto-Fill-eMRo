import unittest
import re
from bs4 import BeautifulSoup
from scraper.parser import eMROParser

class TestAllScenarios(unittest.TestCase):
    def test_case_issued(self):
        html = '''
        <div class="ui-expanded-row-content">
          <div class="ui-g">
            <div class="ui-g-4"><label>Location</label><input value="DM01" /></div>
            <div class="ui-g-4"><label>Bin</label><input value="RS-3" /></div>
            <div class="ui-g-4"><label>Condition</label><input value="SV" /></div>
          </div>
          <div class="ui-g">
            <div class="ui-g-2"><label>QTY</label><input value="2.00" /></div>
            <div class="ui-g-2"><label>Unit Cost</label><input value="0.6672" /></div>
            <div class="ui-g-2"><label>Secondary Cost</label><input value="9,139.5897" /></div>
            <div class="ui-g-2"><label>CUR EXC Rate</label><input value="1.0000000" /></div>
            <div class="ui-g-4"><label>A/C</label><input value="TLM-BC-129" /></div>
          </div>
          <div class="ui-g">
            <div class="ui-g-12"><a class="ui-commandlink">W/O - S/O</a><input value="2329829" /></div>
          </div>
          <div class="ui-g">
            <div class="ui-g-4"><label>Issued To</label><input value="TL162939" /></div>
            <div class="ui-g-8"><label>Issued To Name</label><input value="MR.BOONKERD HEMKONG" /></div>
          </div>
          <div class="ui-g">
            <div class="ui-g-2"><label>Transaction NO</label><input value="40817106" /></div>
            <div class="ui-g-2"><label>Status</label><input value="OPEN" /></div>
            <div class="ui-g-2"><label>Created By</label><input value="TL248006" /></div>
            <div class="ui-g-3"><label>Created Date</label><input value="09/13/2026 10:48:42" /></div>
            <div class="ui-g-3"><label>Name</label><input value="BANNATHAT TATA" /></div>
          </div>
          <div class="ui-g">
            <div class="ui-g-12"><label>G/L</label><input value="TLM / JT11520 / 40 / 994" /></div>
          </div>
        </div>
        '''
        cells = ["Select", "", "ISSUED", "BOSNY-RED", "", "4766094", "4766094", ""]
        res = eMROParser.parse_transaction_row(cells, html)
        self.assertEqual(res["transaction_type"], "ISSUED")
        self.assertEqual(res["pn"], "BOSNY-RED")
        self.assertEqual(res["location"], "DM01")
        self.assertEqual(res["bin"], "RS-3")
        self.assertEqual(res["qty"], "2.00")
        self.assertEqual(res["wo_so"], "2329829")
        self.assertEqual(res["issued_to"], "TL162939")
        self.assertEqual(res["issued_to_name"], "MR.BOONKERD HEMKONG")
        self.assertEqual(res["transaction_no"], "40817106")
        self.assertEqual(res["status"], "OPEN")
        self.assertEqual(res["order_no"], "")
        self.assertEqual(res["vendor_customer"], "")

    def test_case_po_receiving(self):
        html = '''
        <div class="ui-expanded-row-content">
          <div class="ui-g">
            <div class="ui-g-4"><label>Location</label><input value="DM01" /></div>
            <div class="ui-g-4"><label>Bin</label><input value="TYRE01" /></div>
            <div class="ui-g-4"><label>Condition</label><input value="NEW" /></div>
          </div>
          <div class="ui-g">
            <div class="ui-g-2"><label>QTY</label><input value="10.00" /></div>
            <div class="ui-g-2"><label>Unit Cost</label><input value="88.7400" /></div>
            <div class="ui-g-2"><label>Secondary Cost</label><input value="1,215,616.4384" /></div>
            <div class="ui-g-2"><label>CUR EXC Rate</label><input value="0.0295800" /></div>
          </div>
          <div class="ui-g">
            <div class="ui-g-2"><a class="ui-commandlink">Orde Type</a><input value="PO" /></div>
            <div class="ui-g-2"><a class="ui-commandlink">Order NO</a><input value="2597253" /></div>
            <div class="ui-g-2"><label>Line</label><input value="2" /></div>
            <div class="ui-g-3"><a class="ui-commandlink">Vendor/Customer</a><input value="TYR-001" /></div>
            <div class="ui-g-3"><label>Vendor Name</label><input value="TYRE WORK SOLUTIO" /></div>
          </div>
          <div class="ui-g">
            <div class="ui-g-12"><label>Reference</label><input value="1 OF 1" /></div>
          </div>
          <div class="ui-g">
            <div class="ui-g-2"><label>Transaction NO</label><input value="40810315" /></div>
            <div class="ui-g-2"><label>Status</label><input value="" /></div>
            <div class="ui-g-2"><label>Created By</label><input value="TL248006" /></div>
            <div class="ui-g-3"><label>Created Date</label><input value="09/12/2026 00:00:00" /></div>
            <div class="ui-g-3"><label>Name</label><input value="BANNATHAT TATA" /></div>
          </div>
        </div>
        '''
        cells = ["Select", "", "PO/RECEIVING", "7.00-14", "", "4855588", "4855588", ""]
        res = eMROParser.parse_transaction_row(cells, html)
        self.assertEqual(res["transaction_type"], "PO/RECEIVING")
        self.assertEqual(res["pn"], "7.00-14")
        self.assertEqual(res["order_type"], "PO")
        self.assertEqual(res["order_no"], "2597253")
        self.assertEqual(res["order_line"], "2")
        self.assertEqual(res["vendor_customer"], "TYR-001")
        self.assertEqual(res["vendor_name"], "TYRE WORK SOLUTIO")
        self.assertEqual(res["reference"], "1 OF 1")
        self.assertEqual(res["transaction_no"], "40810315")
        self.assertEqual(res["status"], "")
        self.assertEqual(res["wo_so"], "")
        self.assertEqual(res["issued_to"], "")

    def test_case_bin_transfer(self):
        html = '''
        <div class="ui-expanded-row-content">
          <div class="ui-g">
            <div class="ui-g-4"><label>Location</label><input value="DM01" /></div>
            <div class="ui-g-4"><label>Bin</label><input value="BC-316" /></div>
            <div class="ui-g-4"><label>Condition</label><input value="SV" /></div>
          </div>
          <div class="ui-g">
            <div class="ui-g-2"><label>QTY</label><input value="12.00" /></div>
            <div class="ui-g-2"><label>Unit Cost</label><input value="" /></div>
            <div class="ui-g-2"><label>Secondary Cost</label><input value="" /></div>
            <div class="ui-g-2"><label>CUR EXC Rate</label><input value="" /></div>
          </div>
          <div class="ui-g">
            <div class="ui-g-2"><label>Transaction NO</label><input value="40808145" /></div>
            <div class="ui-g-2"><label>Status</label><input value="" /></div>
            <div class="ui-g-2"><label>Created By</label><input value="TL248006" /></div>
            <div class="ui-g-3"><label>Created Date</label><input value="09/12/2026 08:02:46" /></div>
            <div class="ui-g-3"><label>Name</label><input value="BANNATHAT TATA" /></div>
          </div>
          <div class="ui-g">
            <div class="ui-g-12"><label>G/L</label><input value="///" /></div>
          </div>
        </div>
        '''
        cells = ["Select", "", "BIN/TRANSFER", "DW-01", "", "4855424", "4783433", ""]
        res = eMROParser.parse_transaction_row(cells, html)
        self.assertEqual(res["transaction_type"], "BIN/TRANSFER")
        self.assertEqual(res["pn"], "DW-01")
        self.assertEqual(res["bin"], "BC-316")
        self.assertEqual(res["qty"], "12.00")
        self.assertEqual(res["unit_cost"], "")
        self.assertEqual(res["wo_so"], "")
        self.assertEqual(res["issued_to"], "")
        self.assertEqual(res["gl"], "///")

    def test_case_rts_wo(self):
        html = '''
        <div class="ui-expanded-row-content">
          <div class="ui-g">
            <div class="ui-g-4"><label>Location</label><input value="DM01" /></div>
            <div class="ui-g-4"><label>Bin</label><input value="GA301" /></div>
            <div class="ui-g-4"><label>Condition</label><input value="SV" /></div>
          </div>
          <div class="ui-g">
            <div class="ui-g-2"><label>QTY</label><input value="1.00" /></div>
            <div class="ui-g-2"><label>Unit Cost</label><input value="0.0000" /></div>
            <div class="ui-g-2"><label>Secondary Cost</label><input value="0.0000" /></div>
            <div class="ui-g-2"><label>CUR EXC Rate</label><input value="1.0000000" /></div>
            <div class="ui-g-4"><label>A/C</label><input value="TLM-CB-023" /></div>
          </div>
          <div class="ui-g">
            <div class="ui-g-12"><a class="ui-commandlink">W/O - S/O</a><input value="2324104" /></div>
          </div>
          <div class="ui-g">
            <div class="ui-g-2"><label>Transaction NO</label><input value="40808717" /></div>
            <div class="ui-g-2"><label>Status</label><input value="" /></div>
            <div class="ui-g-2"><label>Created By</label><input value="TL248006" /></div>
            <div class="ui-g-3"><label>Created Date</label><input value="09/12/2026 09:26:23" /></div>
            <div class="ui-g-3"><label>Name</label><input value="BANNATHAT TATA" /></div>
          </div>
          <div class="ui-g">
            <div class="ui-g-6"><label>G/L</label><input value="TLM / JT11520 / 40 / 994" /></div>
            <div class="ui-g-6"><label>Defect Description</label><textarea>RETURN</textarea></div>
          </div>
        </div>
        '''
        cells = ["Select", "", "RTS/WO", "P171527", "", "4855475", "4223464", ""]
        res = eMROParser.parse_transaction_row(cells, html)
        self.assertEqual(res["transaction_type"], "RTS/WO")
        self.assertEqual(res["pn"], "P171527")
        self.assertEqual(res["wo_so"], "2324104")
        self.assertEqual(res["defect_description"], "RETURN")
        self.assertEqual(res["ac"], "TLM-CB-023")
        self.assertEqual(res["issued_to"], "")

    def test_case_table_layout(self):
        html = '''
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
        '''
        cells = ["Select", "", "ISSUED", "BOSNY-RED", "", "4766094", "4766094", ""]
        res = eMROParser.parse_transaction_row(cells, html)
        self.assertEqual(res["location"], "DM01")
        self.assertEqual(res["bin"], "RS-3")
        self.assertEqual(res["qty"], "2.00")
        self.assertEqual(res["transaction_no"], "40817106")
        self.assertEqual(res["status"], "OPEN")

if __name__ == "__main__":
    unittest.main()
