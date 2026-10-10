import json
from pathlib import Path

BASE_DIR = Path(r"D:\Project dashboard")
hist_file = BASE_DIR / "data" / "work_order_history.json"

with open(hist_file, "r", encoding="utf-8") as f:
    items = json.load(f)

js_rows = []
for it in items:
    prio = "PM" if (it.get("priority") or "").upper() in ("SCHED", "PM") else "CM"
    js_rows.append([
        it.get("created_at") or it.get("date") or "-",
        it.get("user") or "TL248006",
        it.get("gse") or "-",
        it.get("sn") or "-",
        it.get("wo_number") or "-",
        prio,
        it.get("description") or "-",
        "SUCCESS" if it.get("success") else ("FAILED: " + (it.get("error") or ""))
    ])

template = """/**
 * LOG eMRO W/O — Google Apps Script
 * สำหรับใส่ใน Google Sheets "LOG eMRO W/O"
 * 
 * วิธีใช้:
 * 1. กดปุ่ม 'เรียกใช้' (Run ▶️) ที่ฟังก์ชัน initAndImportAllLogs ด้านบน
 *    ข้อมูลประวัติ 192 รายการพร้อมหัวตารางจะปรากฏบนชีตทันที!
 * 2. หากต้องการให้ระบบส่งใบงานใหม่เข้าชีตนี้อัตโนมัติ:
 *    กดปุ่ม 'ทำให้ใช้งานได้' (Deploy) -> 'การทำให้ใช้งานได้ใหม่' (New deployment)
 *    เลือกประเภท: เว็บแอป (Web app) -> ให้สิทธิ์: ทุกคน (Anyone) -> Deploy
 */

var INITIAL_LOGS = """ + json.dumps(js_rows, ensure_ascii=False, indent=2) + """;

function initAndImportAllLogs() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheets()[0];
  
  var headers = [
    "วันที่-เวลา (Timestamp)",
    "ผู้เปิดใบงาน (User)",
    "รหัสรถ (GSE NO.)",
    "หมายเลขตัวถัง (S/N)",
    "เลขที่ W/O",
    "ประเภท (Type)",
    "อาการ / รายละเอียด (Description)",
    "สถานะ (Status)"
  ];

  sheet.clearContents();
  sheet.appendRow(headers);

  // สไตล์หัวตาราง Dark Slate
  var headerRange = sheet.getRange(1, 1, 1, headers.length);
  headerRange.setFontWeight("bold");
  headerRange.setBackground("#0F172A");
  headerRange.setFontColor("#F8FAFC");
  headerRange.setHorizontalAlignment("center");
  headerRange.setVerticalAlignment("middle");
  sheet.setRowHeight(1, 38);
  sheet.setFrozenRows(1);

  // ใส่ข้อมูลทั้ง 192 รายการ
  if (INITIAL_LOGS.length > 0) {
    sheet.getRange(2, 1, INITIAL_LOGS.length, headers.length).setValues(INITIAL_LOGS);

    // จัด Alignment และสี
    sheet.getRange(2, 1, INITIAL_LOGS.length, 1).setHorizontalAlignment("center");
    sheet.getRange(2, 2, INITIAL_LOGS.length, 1).setHorizontalAlignment("center");
    sheet.getRange(2, 3, INITIAL_LOGS.length, 1).setHorizontalAlignment("center");
    sheet.getRange(2, 4, INITIAL_LOGS.length, 1).setHorizontalAlignment("center");
    sheet.getRange(2, 5, INITIAL_LOGS.length, 1).setHorizontalAlignment("center").setFontWeight("bold");
    sheet.getRange(2, 6, INITIAL_LOGS.length, 1).setHorizontalAlignment("center").setFontWeight("bold");
    sheet.getRange(2, 8, INITIAL_LOGS.length, 1).setHorizontalAlignment("center");

    // แบ่งสี CM / PM
    for (var i = 0; i < INITIAL_LOGS.length; i++) {
      var pType = INITIAL_LOGS[i][5];
      var cell = sheet.getRange(i + 2, 6);
      if (pType === "CM") {
        cell.setFontColor("#D97706");
      } else {
        cell.setFontColor("#059669");
      }
    }
  }

  // ปรับความกว้างคอลัมน์ให้อ่านง่าย
  for (var c = 1; c <= headers.length; c++) {
    sheet.autoResizeColumn(c);
  }
  SpreadsheetApp.flush();
}

// รับข้อมูลใบงานใหม่ในอนาคตแบบอัตโนมัติ
function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(30000);
    var contents = e.postData.contents;
    var data = JSON.parse(contents);
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheets()[0];

    if (data.items && data.items.length > 0) {
      var now = new Date();
      var nowStr = Utilities.formatDate(now, "Asia/Bangkok", "dd/MM/yyyy HH:mm:ss");
      var newRows = [];

      data.items.forEach(function(item) {
        if (!item.success && !item.wo_number) return;
        var prio = (item.priority === "SCHED" || item.priority === "PM") ? "PM" : "CM";
        newRows.push([
          item.created_at || nowStr,
          item.user || "TL248006",
          item.gse || "-",
          item.sn || "-",
          item.wo_number || "-",
          prio,
          item.description || "-",
          item.success ? "SUCCESS" : ("FAILED: " + (item.error || ""))
        ]);
      });

      if (newRows.length > 0) {
        var startRow = sheet.getLastRow() + 1;
        sheet.getRange(startRow, 1, newRows.length, 8).setValues(newRows);
        sheet.getRange(startRow, 1, newRows.length, 1).setHorizontalAlignment("center");
        sheet.getRange(startRow, 2, newRows.length, 1).setHorizontalAlignment("center");
        sheet.getRange(startRow, 3, newRows.length, 1).setHorizontalAlignment("center");
        sheet.getRange(startRow, 4, newRows.length, 1).setHorizontalAlignment("center");
        sheet.getRange(startRow, 5, newRows.length, 1).setHorizontalAlignment("center").setFontWeight("bold");
        sheet.getRange(startRow, 6, newRows.length, 1).setHorizontalAlignment("center").setFontWeight("bold");
        sheet.getRange(startRow, 8, newRows.length, 1).setHorizontalAlignment("center");
      }
    }

    return ContentService.createTextOutput(JSON.stringify({ status: "success" }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ status: "error", message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}
"""

out_file = BASE_DIR / "data" / "log_sheet_apps_script.js"
with open(out_file, "w", encoding="utf-8") as f:
    f.write(template)

print(f"Created {out_file} successfully! Total records embedded: {len(js_rows)}")
