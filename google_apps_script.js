/**
 * eMRO Inventory Monitor — Google Apps Script Webhook & Responsive Dashboard
 * วางโค้ดนี้ทั้งหมดลงใน Extensions -> Apps Script ใน Google Sheets ของคุณ
 * แล้วกด Deploy -> Manage deployments -> Edit -> New version -> Deploy
 */

function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(30000);

    var contents = e.postData.contents;
    var data = JSON.parse(contents);
    var ss = SpreadsheetApp.getActiveSpreadsheet();

    // 1. อัปเดตข้อมูลตาราง Live Transactions
    if (data.action === "update_live") {
      var sheetName = "Live Transactions";
      var sheet = ss.getSheetByName(sheetName);
      if (!sheet) {
        sheet = ss.insertSheet(sheetName);
      }

      var headers = data.headers;
      var rows = data.rows;

      sheet.clearContents();

      if (headers && headers.length > 0) {
        sheet.appendRow(headers);
        var headerRange = sheet.getRange(1, 1, 1, headers.length);
        headerRange.setFontWeight("bold");
        headerRange.setBackground("#334155"); // สี Slate เข้มสบายตา
        headerRange.setFontColor("#FFFFFF");
        sheet.setFrozenRows(1);
      }

      if (rows && rows.length > 0) {
        var numRows = rows.length;
        var numCols = rows[0].length;
        sheet.getRange(2, 1, numRows, numCols).setValues(rows);

        var typeColIndex = headers.indexOf("Transaction Type") + 1;
        if (typeColIndex > 0) {
          for (var i = 0; i < numRows; i++) {
            var transType = (rows[i][typeColIndex - 1] || "").toUpperCase();
            if (transType === "ISSUED") {
              sheet.getRange(i + 2, 1, 1, numCols).setBackground("#FEF3C7"); // สี Amber นวลตา
            } else if (transType.indexOf("RECEIVING") !== -1) {
              sheet.getRange(i + 2, 1, 1, numCols).setBackground("#D1FAE5"); // สี Emerald นวลตา
            } else if (transType.indexOf("TRANSFER") !== -1) {
              sheet.getRange(i + 2, 1, 1, numCols).setBackground("#E0E7FF"); // สี Indigo นวลตา
            }
          }
        }
      }
    }

    // 2. บันทึกประวัติลง Activity Log เมื่อมีรายการใหม่
    if (data.action === "append_log" && data.events && data.events.length > 0) {
      var logSheetName = "Activity Log";
      var logSheet = ss.getSheetByName(logSheetName);
      if (!logSheet) {
        logSheet = ss.insertSheet(logSheetName);
        var logHeaders = ["Timestamp", "Action", "Transaction NO", "Type", "Details"];
        logSheet.appendRow(logHeaders);
        logSheet.getRange(1, 1, 1, logHeaders.length).setFontWeight("bold");
        logSheet.getRange(1, 1, 1, logHeaders.length).setBackground("#1E293B");
        logSheet.getRange(1, 1, 1, logHeaders.length).setFontColor("#FFFFFF");
        logSheet.setFrozenRows(1);
      }

      data.events.forEach(function(ev) {
        logSheet.appendRow(ev);
      });
    }

    // 3. บันทึก GSE Work Order ที่สร้างขึ้นใหม่ลงใน Sheet ติดตามงานรายเดือน
    if (data.action === "append_gse_wo" && data.items && data.items.length > 0) {
      var targetSsId = data.target_spreadsheet_id || "1luje0x1QXrhhucSvmO6h_k5Es91X8rCcJeP2Fet7uYs";
      var targetSs;
      try {
        targetSs = SpreadsheetApp.openById(targetSsId);
      } catch (errOpen) {
        targetSs = ss; // fallback to active sheet if openById fails
      }

      var now = new Date();
      var monthNames = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
      var defaultMonth = monthNames[now.getMonth()];
      var defaultYear = now.getFullYear();

      data.items.forEach(function(item) {
        if (!item.success && !item.wo_number) return;
        var prioUpper = (item.priority || "").toUpperCase();
        if (prioUpper === "UNSCHED" || prioUpper === "CM") return; // PM Sheet strictly only!

        // Detect month from description (e.g. PM OCT, PM NOV) or current date
        var targetMonth = defaultMonth;
        var descUpper = (item.description || "").toUpperCase();
        for (var m = 0; m < monthNames.length; m++) {
          if (descUpper.indexOf(monthNames[m]) !== -1) {
            targetMonth = monthNames[m];
            break;
          }
        }

        // Find sheet matching "หน้าเก็บข้อมูล {MONTH}"
        var targetTab = null;
        var sheets = targetSs.getSheets();
        for (var i = 0; i < sheets.length; i++) {
          var sName = sheets[i].getName();
          if (sName.indexOf("หน้าเก็บข้อมูล " + targetMonth) === 0 || sName.indexOf(targetMonth) !== -1) {
            targetTab = sheets[i];
            break;
          }
        }

        if (!targetTab) {
          targetTab = targetSs.getActiveSheet();
        }

        // Priority display: SCHED -> PM, UNSCHED -> CM
        var prioDisplay = (item.priority === "SCHED" || item.priority === "PM") ? "PM" : "CM";
        var dateDisplay = item.date || Utilities.formatDate(now, "Asia/Bangkok", "M/d/yyyy");

        // Format row matching user's table:
        // A: EQ NO. | B: อาการ | C: Priority | D: W/O | E: สถานะ W/O | F: สแกนเอกสาร | G: สถานะปริ้นท์ | H: คนเปิดใบงาน | I: วันที่เปิด
        var row = [
          item.gse || "-",                       // A: EQ NO.
          item.description || "-",               // B: อาการ
          prioDisplay,                           // C: Priority (PM / CM)
          item.wo_number || "-",                 // D: W/O
          "OPEN",                                // E: สถานะ W/O
          "NO",                                  // F: สแกนเอกสาร
          "Not Print",                           // G: สถานะปริ้นท์
          item.user || "TL248006",               // H: คนเปิดใบงาน
          dateDisplay                            // I: วันที่เปิด
        ];
        // Find first empty row in Column A (starting from row 2) to prevent jumping past empty template rows
        var colA = targetTab.getRange("A1:A").getValues();
        var writeRow = -1;
        for (var r = 1; r < colA.length; r++) {
          var val = colA[r][0];
          if (val === "" || val === null || val === undefined) {
            writeRow = r + 1;
            break;
          }
        }
        if (writeRow === -1) {
          writeRow = colA.length + 1;
        }

        // Check duplicate by W/O number
        var isDuplicate = false;
        if (item.wo_number && item.wo_number !== "-") {
          var checkRows = Math.min(Math.max(writeRow + 10, 100), colA.length);
          var colD = targetTab.getRange("D1:D" + checkRows).getValues();
          for (var d = 1; d < colD.length; d++) {
            if (String(colD[d][0]).trim() === String(item.wo_number).trim()) {
              isDuplicate = true;
              break;
            }
          }
        }

        if (!isDuplicate) {
          targetTab.getRange(writeRow, 1, 1, row.length).setValues([row]);
        }
      });
    }

    // 4. ทำความสะอาดและจัดเรียงแถวในหน้าเก็บข้อมูล NOV (Cleanup & Deduplicate)
    if (data.action === "cleanup_nov") {
      cleanupAndConsolidateNovSheet();
    }

    // 5. บันทึกประวัติและสร้างหัวตาราง W/O Audit Log ลง Master Log Sheet (1BdMWDX9anf2wD1_yLTH3S1LRBSuWCIKPAjKUOpPIrhA)
    if (data.action === "init_wo_log_headers" || (data.action === "append_wo_log" && data.items && data.items.length > 0)) {
      var logSsId = data.target_spreadsheet_id || "1BdMWDX9anf2wD1_yLTH3S1LRBSuWCIKPAjKUOpPIrhA";
      var logSs;
      try {
        logSs = SpreadsheetApp.openById(logSsId);
      } catch (errOpen) {
        logSs = ss;
      }

      var sheet = logSs.getSheets()[0];
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

      // สร้างหัวตารางถ้าชีตว่างเปล่า หรือเรียกคำสั่ง init_wo_log_headers
      if (sheet.getLastRow() === 0 || data.action === "init_wo_log_headers") {
        if (data.action === "init_wo_log_headers") {
          sheet.clearContents();
        }
        sheet.appendRow(headers);
        var headerRange = sheet.getRange(1, 1, 1, headers.length);
        headerRange.setFontWeight("bold");
        headerRange.setBackground("#0F172A"); // Slate 900
        headerRange.setFontColor("#F8FAFC"); // White
        headerRange.setHorizontalAlignment("center");
        headerRange.setVerticalAlignment("middle");
        sheet.setRowHeight(1, 38);
        sheet.setFrozenRows(1);
      }

      // บันทึกแถวข้อมูล W/O Log (Bulk Insert รวดเร็วและแม่นยำ)
      if (data.action === "append_wo_log" && data.items && data.items.length > 0) {
        var now = new Date();
        var nowStr = Utilities.formatDate(now, "Asia/Bangkok", "dd/MM/yyyy HH:mm:ss");
        var rowsToAdd = [];

        data.items.forEach(function(item) {
          if (!item.success && !item.wo_number) return;
          var prioDisplay = (item.priority === "SCHED" || item.priority === "PM") ? "PM" : "CM";
          var timeDisplay = item.created_at || nowStr;
          var statusDisplay = item.success ? "SUCCESS" : ("FAILED: " + (item.error || ""));
          rowsToAdd.push([
            timeDisplay,
            item.user || "TL248006",
            item.gse || "-",
            item.sn || "-",
            item.wo_number || "-",
            prioDisplay,
            item.description || "-",
            statusDisplay
          ]);
        });

        if (rowsToAdd.length > 0) {
          var startRow = sheet.getLastRow() + 1;
          sheet.getRange(startRow, 1, rowsToAdd.length, headers.length).setValues(rowsToAdd);
          // จัดกึ่งกลางคอลัมน์สำคัญ
          sheet.getRange(startRow, 1, rowsToAdd.length, 1).setHorizontalAlignment("center");
          sheet.getRange(startRow, 2, rowsToAdd.length, 1).setHorizontalAlignment("center");
          sheet.getRange(startRow, 3, rowsToAdd.length, 1).setHorizontalAlignment("center");
          sheet.getRange(startRow, 4, rowsToAdd.length, 1).setHorizontalAlignment("center");
          sheet.getRange(startRow, 5, rowsToAdd.length, 1).setHorizontalAlignment("center").setFontWeight("bold");
          sheet.getRange(startRow, 6, rowsToAdd.length, 1).setHorizontalAlignment("center").setFontWeight("bold");
          sheet.getRange(startRow, 8, rowsToAdd.length, 1).setHorizontalAlignment("center");
        }
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

/**
 * Handle GET Requests:
 * - ?api=data : Return JSON data for live auto-refresh
 * - default   : Return full Responsive HTML Dashboard (Mobile & Desktop)
 */
function doGet(e) {
  if (e && e.parameter && e.parameter.api === "data") {
    var data = getDashboardData();
    return ContentService.createTextOutput(JSON.stringify(data))
      .setMimeType(ContentService.MimeType.JSON);
  }

  var initialData = getDashboardData();
  var html = renderDashboardHtml(initialData);
  return HtmlService.createHtmlOutput(html)
    .setTitle("eMRO Inventory Monitor (DM01)")
    .addMetaTag("viewport", "width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no")
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/**
 * Return JSON String for client-side google.script.run
 * (Prevents serialization drops of Date objects or 2D arrays in Apps Script RPC)
 */
function getDashboardDataJson() {
  return JSON.stringify(getDashboardData());
}

function getDashboardData() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Live Transactions");
  var logSheet = ss.getSheetByName("Activity Log");

  var headers = [];
  var rows = [];
  var stats = { total: 0, issued: 0, receiving: 0, transfer: 0, lastSync: "-" };

  if (sheet && sheet.getLastRow() > 0) {
    var data = sheet.getDataRange().getValues();
    if (data.length > 0) {
      headers = data[0].map(function(h) { return String(h || ""); });
      var typeIdx = headers.indexOf("Transaction Type");
      var syncIdx = headers.indexOf("Last Synced");

      for (var i = 1; i < data.length; i++) {
        var rawRow = data[i];
        var cleanRow = [];
        for (var c = 0; c < rawRow.length; c++) {
          var val = rawRow[c];
          if (val instanceof Date) {
            val = Utilities.formatDate(val, "GMT+7", "yyyy-MM-dd HH:mm:ss");
          } else if (val === null || val === undefined) {
            val = "";
          } else {
            val = String(val);
          }
          cleanRow.push(val);
        }
        rows.push(cleanRow);

        var tType = typeIdx >= 0 ? cleanRow[typeIdx].toUpperCase() : "";
        if (tType.indexOf("ISSUED") !== -1) stats.issued++;
        else if (tType.indexOf("RECEIVING") !== -1) stats.receiving++;
        else if (tType.indexOf("TRANSFER") !== -1 || tType.indexOf("RTS") !== -1) stats.transfer++;

        if (syncIdx >= 0 && cleanRow[syncIdx]) {
          stats.lastSync = cleanRow[syncIdx];
        }
      }
      stats.total = rows.length;
    }
  }

  var logs = [];
  if (logSheet && logSheet.getLastRow() > 1) {
    var logData = logSheet.getDataRange().getValues();
    for (var j = Math.max(1, logData.length - 30); j < logData.length; j++) {
      var logRow = [];
      for (var k = 0; k < logData[j].length; k++) {
        var lval = logData[j][k];
        if (lval instanceof Date) {
          lval = Utilities.formatDate(lval, "GMT+7", "yyyy-MM-dd HH:mm:ss");
        } else {
          lval = String(lval || "");
        }
        logRow.push(lval);
      }
      logs.unshift(logRow);
    }
  }

  return {
    status: "success",
    headers: headers,
    rows: rows,
    stats: stats,
    logs: logs
  };
}

function renderDashboardHtml(initialData) {
  var payloadJson = JSON.stringify(initialData || { status: "empty", headers: [], rows: [], stats: { total: 0, issued: 0, receiving: 0, transfer: 0, lastSync: "-" } });

  return '<!DOCTYPE html>\n' +
'<html lang="th">\n' +
'<head>\n' +
'  <meta charset="UTF-8">\n' +
'  <title>eMRO Inventory Monitor (DM01)</title>\n' +
'  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n' +
'  <script src="https://cdn.tailwindcss.com"></script>\n' +
'  <link rel="preconnect" href="https://fonts.googleapis.com">\n' +
'  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n' +
'  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Prompt:wght@300;400;500;600&display=swap" rel="stylesheet">\n' +
'  <style>\n' +
'    body { font-family: "Plus Jakarta Sans", "Prompt", sans-serif; background-color: #F8FAFC; color: #1E293B; }\n' +
'    .badge-issued { background-color: #FEF3C7; color: #92400E; border: 1px solid #FDE68A; }\n' +
'    .badge-receiving { background-color: #D1FAE5; color: #065F46; border: 1px solid #A7F3D0; }\n' +
'    .badge-transfer { background-color: #E0E7FF; color: #3730A3; border: 1px solid #C7D2FE; }\n' +
'    .badge-other { background-color: #F1F5F9; color: #475569; border: 1px solid #E2E8F0; }\n' +
'    .card-shadow { box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px 0 rgba(0, 0, 0, 0.03); }\n' +
'    ::-webkit-scrollbar { width: 6px; height: 6px; }\n' +
'    ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 4px; }\n' +
'  </style>\n' +
'</head>\n' +
'<body class="min-h-screen pb-12 antialiased">\n' +
'\n' +
'  <!-- Top Navigation Header -->\n' +
'  <header class="sticky top-0 z-30 bg-white/85 backdrop-blur border-b border-slate-200">\n' +
'    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">\n' +
'      <div class="flex items-center space-x-3">\n' +
'        <div class="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white font-bold shadow-sm shadow-indigo-200">\n' +
'          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>\n' +
'        </div>\n' +
'        <div>\n' +
'          <div class="flex items-center space-x-2">\n' +
'            <h1 class="text-base sm:text-lg font-bold text-slate-800">eMRO Inventory Monitor</h1>\n' +
'            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">\n' +
'              <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5 animate-pulse"></span>DM01\n' +
'            </span>\n' +
'          </div>\n' +
'          <p class="text-xs text-slate-400" id="syncStatus">กำลังเชื่อมต่อข้อมูล...</p>\n' +
'        </div>\n' +
'      </div>\n' +
'\n' +
'      <div class="flex items-center space-x-2">\n' +
'        <button onclick="fetchData()" id="refreshBtn" class="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 active:scale-95 transition rounded-lg border border-slate-200">\n' +
'          <svg id="refreshIcon" class="w-3.5 h-3.5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>\n' +
'          <span class="hidden sm:inline">รีเฟรช</span>\n' +
'        </button>\n' +
'      </div>\n' +
'    </div>\n' +
'  </header>\n' +
'\n' +
'  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 space-y-6">\n' +
'\n' +
'    <!-- KPI Summary Cards -->\n' +
'    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">\n' +
'      <div class="bg-white p-4 rounded-2xl border border-slate-200 card-shadow">\n' +
'        <div class="flex items-center justify-between text-slate-400 mb-1">\n' +
'          <span class="text-xs font-medium">รายการทั้งหมด</span>\n' +
'          <div class="p-1.5 rounded-lg bg-slate-100 text-slate-600"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg></div>\n' +
'        </div>\n' +
'        <div class="text-2xl font-bold text-slate-800" id="kpiTotal">0</div>\n' +
'        <div class="text-[11px] text-slate-400 mt-0.5">ในรอบ Polling ปัจจุบัน</div>\n' +
'      </div>\n' +
'\n' +
'      <div class="bg-white p-4 rounded-2xl border border-amber-200/70 card-shadow">\n' +
'        <div class="flex items-center justify-between text-amber-600 mb-1">\n' +
'          <span class="text-xs font-medium">เบิกจ่าย (ISSUED)</span>\n' +
'          <div class="p-1.5 rounded-lg bg-amber-50 text-amber-600"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg></div>\n' +
'        </div>\n' +
'        <div class="text-2xl font-bold text-amber-700" id="kpiIssued">0</div>\n' +
'        <div class="text-[11px] text-amber-600/70 mt-0.5">ตัดยอดจากสต็อก</div>\n' +
'      </div>\n' +
'\n' +
'      <div class="bg-white p-4 rounded-2xl border border-emerald-200/70 card-shadow">\n' +
'        <div class="flex items-center justify-between text-emerald-600 mb-1">\n' +
'          <span class="text-xs font-medium">รับเข้า (RECEIVING)</span>\n' +
'          <div class="p-1.5 rounded-lg bg-emerald-50 text-emerald-600"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16l-4-4m0 0l4-4m-4 4h14m-6 4v1a3 3 0 003 3h4a3 3 0 003-3V7a3 3 0 00-3-3h-4a3 3 0 00-3 3v1"/></svg></div>\n' +
'        </div>\n' +
'        <div class="text-2xl font-bold text-emerald-700" id="kpiReceiving">0</div>\n' +
'        <div class="text-[11px] text-emerald-600/70 mt-0.5">รับเข้าจาก PO / Initial</div>\n' +
'      </div>\n' +
'\n' +
'      <div class="bg-white p-4 rounded-2xl border border-indigo-200/70 card-shadow">\n' +
'        <div class="flex items-center justify-between text-indigo-600 mb-1">\n' +
'          <span class="text-xs font-medium">ย้าย/คืน (TRANSFER/RTS)</span>\n' +
'          <div class="p-1.5 rounded-lg bg-indigo-50 text-indigo-600"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"/></svg></div>\n' +
'        </div>\n' +
'        <div class="text-2xl font-bold text-indigo-700" id="kpiTransfer">0</div>\n' +
'        <div class="text-[11px] text-indigo-600/70 mt-0.5">เปลี่ยน Bin / คืน W/O</div>\n' +
'      </div>\n' +
'    </div>\n' +
'\n' +
'    <!-- Search & Filter Controls -->\n' +
'    <div class="bg-white p-3.5 sm:p-4 rounded-2xl border border-slate-200 card-shadow space-y-3">\n' +
'      <div class="flex flex-col sm:flex-row gap-2 sm:items-center justify-between">\n' +
'        <div class="relative flex-1">\n' +
'          <svg class="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>\n' +
'          <input type="text" id="searchInput" oninput="applyFilters()" placeholder="ค้นหา P/N, W/O, Batch, Bin, ผู้เบิก..." class="w-full pl-10 pr-4 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition">\n' +
'        </div>\n' +
'\n' +
'        <!-- View Mode Buttons -->\n' +
'        <div class="flex items-center space-x-1.5 overflow-x-auto pb-1 sm:pb-0">\n' +
'          <button onclick="setFilterType(\'ALL\')" id="btnFilterALL" class="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 text-white transition whitespace-nowrap">ทั้งหมด</button>\n' +
'          <button onclick="setFilterType(\'ISSUED\')" id="btnFilterISSUED" class="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 text-slate-600 hover:bg-slate-200 transition whitespace-nowrap">ISSUED</button>\n' +
'          <button onclick="setFilterType(\'RECEIVING\')" id="btnFilterRECEIVING" class="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 text-slate-600 hover:bg-slate-200 transition whitespace-nowrap">RECEIVING</button>\n' +
'          <button onclick="setFilterType(\'TRANSFER\')" id="btnFilterTRANSFER" class="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 text-slate-600 hover:bg-slate-200 transition whitespace-nowrap">TRANSFER</button>\n' +
'          <button onclick="setFilterType(\'RTS\')" id="btnFilterRTS" class="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 text-slate-600 hover:bg-slate-200 transition whitespace-nowrap">RTS/WO</button>\n' +
'        </div>\n' +
'      </div>\n' +
'    </div>\n' +
'\n' +
'    <!-- Mobile Card View (List) -->\n' +
'    <div class="block md:hidden space-y-3" id="mobileCardContainer">\n' +
'      <div class="text-center py-12 text-slate-400 text-sm">กำลังโหลดข้อมูล...</div>\n' +
'    </div>\n' +
'\n' +
'    <!-- Desktop Interactive Table -->\n' +
'    <div class="hidden md:block bg-white rounded-2xl border border-slate-200 card-shadow overflow-hidden">\n' +
'      <div class="overflow-x-auto max-h-[700px]">\n' +
'        <table class="w-full text-left text-xs">\n' +
'          <thead class="sticky top-0 z-10 bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider">\n' +
'            <tr>\n' +
'              <th class="px-3.5 py-3">Type</th>\n' +
'              <th class="px-3.5 py-3">P/N</th>\n' +
'              <th class="px-3.5 py-3">QTY</th>\n' +
'              <th class="px-3.5 py-3">Bin</th>\n' +
'              <th class="px-3.5 py-3">Batch</th>\n' +
'              <th class="px-3.5 py-3">W/O - S/O</th>\n' +
'              <th class="px-3.5 py-3">Issued To</th>\n' +
'              <th class="px-3.5 py-3">Date / By</th>\n' +
'              <th class="px-3.5 py-3 text-right">Action</th>\n' +
'            </tr>\n' +
'          </thead>\n' +
'          <tbody id="desktopTableBody" class="divide-y divide-slate-100">\n' +
'            <tr><td colspan="9" class="text-center py-12 text-slate-400">กำลังโหลดข้อมูล...</td></tr>\n' +
'          </tbody>\n' +
'        </table>\n' +
'      </div>\n' +
'    </div>\n' +
'\n' +
'  </main>\n' +
'\n' +
'  <!-- 27-Field Detail Modal -->\n' +
'  <div id="detailModal" class="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm hidden items-center justify-center p-4 overflow-y-auto">\n' +
'    <div class="bg-white rounded-2xl border border-slate-200 max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col shadow-2xl">\n' +
'      <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">\n' +
'        <div>\n' +
'          <h3 class="text-base font-bold text-slate-800" id="modalTitle">รายละเอียด Transaction</h3>\n' +
'          <p class="text-xs text-slate-400" id="modalSubtitle">-</p>\n' +
'        </div>\n' +
'        <button onclick="closeModal()" class="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition">\n' +
'          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>\n' +
'        </button>\n' +
'      </div>\n' +
'      <div class="p-6 overflow-y-auto space-y-4 text-xs" id="modalBody">\n' +
'        <!-- Injected dynamically -->\n' +
'      </div>\n' +
'      <div class="px-6 py-3 bg-slate-50 border-t border-slate-100 text-right">\n' +
'        <button onclick="closeModal()" class="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 rounded-xl transition">ปิดหน้าต่าง</button>\n' +
'      </div>\n' +
'    </div>\n' +
'  </div>\n' +
'\n' +
'  <script>\n' +
'    var initialPayload = ' + payloadJson + ';\n' +
'    var rawData = [];\n' +
'    var headers = [];\n' +
'    var currentFilterType = "ALL";\n' +
'    var isFetching = false;\n' +
'\n' +
'    function getBadgeClass(type) {\n' +
'      var t = (type || "").toUpperCase();\n' +
'      if (t.indexOf("ISSUED") !== -1) return "badge-issued";\n' +
'      if (t.indexOf("RECEIVING") !== -1) return "badge-receiving";\n' +
'      if (t.indexOf("TRANSFER") !== -1) return "badge-transfer";\n' +
'      return "badge-other";\n' +
'    }\n' +
'\n' +
'    function fetchData() {\n' +
'      if (isFetching) return;\n' +
'      isFetching = true;\n' +
'      var icon = document.getElementById("refreshIcon");\n' +
'      if (icon) icon.classList.add("animate-spin");\n' +
'      document.getElementById("syncStatus").innerText = "กำลังรีเฟรชข้อมูล...";\n' +
'\n' +
'      // 1. Try google.script.run with JSON String (RPC safe)\n' +
'      if (typeof google !== "undefined" && google.script && google.script.run) {\n' +
'        google.script.run\n' +
'          .withSuccessHandler(function(jsonStr) {\n' +
'            try {\n' +
'              var res = typeof jsonStr === "string" ? JSON.parse(jsonStr) : jsonStr;\n' +
'              onDataLoaded(res);\n' +
'            } catch(e) {\n' +
'              onDataError(e);\n' +
'            }\n' +
'          })\n' +
'          .withFailureHandler(onDataError)\n' +
'          .getDashboardDataJson();\n' +
'      } else {\n' +
'        // 2. Fallback for standalone / external preview via fetch API\n' +
'        fetch(window.location.href.split("?")[0] + "?api=data")\n' +
'          .then(function(r) { return r.json(); })\n' +
'          .then(onDataLoaded)\n' +
'          .catch(onDataError);\n' +
'      }\n' +
'    }\n' +
'\n' +
'    function onDataLoaded(res) {\n' +
'      isFetching = false;\n' +
'      var icon = document.getElementById("refreshIcon");\n' +
'      if (icon) icon.classList.remove("animate-spin");\n' +
'\n' +
'      if (!res || res.status !== "success" || !res.rows) {\n' +
'        document.getElementById("syncStatus").innerText = "ไม่พบข้อมูล";\n' +
'        return;\n' +
'      }\n' +
'\n' +
'      headers = res.headers || [];\n' +
'      rawData = res.rows || [];\n' +
'\n' +
'      // Update KPIs\n' +
'      var s = res.stats || {};\n' +
'      document.getElementById("kpiTotal").innerText = s.total !== undefined ? s.total : rawData.length;\n' +
'      document.getElementById("kpiIssued").innerText = s.issued || 0;\n' +
'      document.getElementById("kpiReceiving").innerText = s.receiving || 0;\n' +
'      document.getElementById("kpiTransfer").innerText = s.transfer || 0;\n' +
'      document.getElementById("syncStatus").innerText = "อัปเดตล่าสุด: " + (s.lastSync || "เพิ่งซิงค์");\n' +
'\n' +
'      applyFilters();\n' +
'    }\n' +
'\n' +
'    function onDataError(err) {\n' +
'      isFetching = false;\n' +
'      var icon = document.getElementById("refreshIcon");\n' +
'      if (icon) icon.classList.remove("animate-spin");\n' +
'      document.getElementById("syncStatus").innerText = "การเชื่อมต่อขัดข้อง ชั่วคราว";\n' +
'    }\n' +
'\n' +
'    function setFilterType(type) {\n' +
'      currentFilterType = type;\n' +
'      ["ALL", "ISSUED", "RECEIVING", "TRANSFER", "RTS"].forEach(function(t) {\n' +
'        var btn = document.getElementById("btnFilter" + t);\n' +
'        if (btn) {\n' +
'          if (t === type) {\n' +
'            btn.className = "px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 text-white transition whitespace-nowrap";\n' +
'          } else {\n' +
'            btn.className = "px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 text-slate-600 hover:bg-slate-200 transition whitespace-nowrap";\n' +
'          }\n' +
'        }\n' +
'      });\n' +
'      applyFilters();\n' +
'    }\n' +
'\n' +
'    function applyFilters() {\n' +
'      var q = (document.getElementById("searchInput").value || "").toLowerCase().trim();\n' +
'      var typeIdx = headers.indexOf("Transaction Type");\n' +
'\n' +
'      var filtered = rawData.filter(function(row) {\n' +
'        var tType = typeIdx >= 0 ? String(row[typeIdx] || "").toUpperCase() : "";\n' +
'        if (currentFilterType !== "ALL" && tType.indexOf(currentFilterType) === -1) {\n' +
'          return false;\n' +
'        }\n' +
'        if (q) {\n' +
'          var match = row.some(function(cell) { return String(cell || "").toLowerCase().indexOf(q) !== -1; });\n' +
'          if (!match) return false;\n' +
'        }\n' +
'        return true;\n' +
'      });\n' +
'\n' +
'      renderMobileCards(filtered);\n' +
'      renderDesktopTable(filtered);\n' +
'    }\n' +
'\n' +
'    function renderMobileCards(items) {\n' +
'      var container = document.getElementById("mobileCardContainer");\n' +
'      if (!items || items.length === 0) {\n' +
'        container.innerHTML = \'<div class="text-center py-12 text-slate-400 text-xs">ไม่พบรายการข้อมูลที่ค้นหา</div>\';\n' +
'        return;\n' +
'      }\n' +
'\n' +
'      var h = {\n' +
'        tNo: headers.indexOf("Transaction NO"),\n' +
'        type: headers.indexOf("Transaction Type"),\n' +
'        pn: headers.indexOf("P/N"),\n' +
'        qty: headers.indexOf("QTY"),\n' +
'        loc: headers.indexOf("Location"),\n' +
'        bin: headers.indexOf("Bin"),\n' +
'        wo: headers.indexOf("W/O - S/O"),\n' +
'        issued: headers.indexOf("Issued To"),\n' +
'        date: headers.indexOf("Created Date"),\n' +
'        name: headers.indexOf("Name")\n' +
'      };\n' +
'\n' +
'      var html = items.map(function(r, idx) {\n' +
'        var type = r[h.type] || "TRANSACTION";\n' +
'        var badgeClass = getBadgeClass(type);\n' +
'        var pn = r[h.pn] || "-";\n' +
'        var qty = r[h.qty] || "-";\n' +
'        var bin = r[h.bin] || "-";\n' +
'        var loc = r[h.loc] || "DM01";\n' +
'        var tNo = r[h.tNo] || "-";\n' +
'        var wo = r[h.wo] || "";\n' +
'        var issued = r[h.issued] || "";\n' +
'        var date = r[h.date] || "";\n' +
'\n' +
'        return \'<div class="bg-white p-4 rounded-2xl border border-slate-200 card-shadow space-y-2.5">\' +\n' +
'          \'<div class="flex items-center justify-between">\' +\n' +
'            \'<span class="px-2.5 py-0.5 rounded-full text-[11px] font-semibold \' + badgeClass + \'">\' + type + \'</span>\' +\n' +
'            \'<span class="text-[11px] text-slate-400 font-mono">#\' + tNo + \'</span>\' +\n' +
'          \'</div>\' +\n' +
'          \'<div>\' +\n' +
'            \'<div class="text-base font-bold text-slate-800">\' + pn + \'</div>\' +\n' +
'            \'<div class="flex items-center space-x-2 text-xs text-slate-500 mt-1">\' +\n' +
'              \'<span class="inline-flex items-center px-2 py-0.5 rounded-md bg-slate-100 font-mono text-[11px]">\' + loc + \' / \' + bin + \'</span>\' +\n' +
'              \'<span class="inline-flex items-center px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-700 font-bold text-[11px]">QTY: \' + qty + \'</span>\' +\n' +
'            \'</div>\' +\n' +
'          \'</div>\' +\n' +
'          (wo || issued ? \'<div class="pt-2 border-t border-slate-100 text-xs text-slate-600 flex flex-wrap gap-x-3">\' +\n' +
'            (wo ? \'<span>W/O: <strong class="text-slate-800">\' + wo + \'</strong></span>\' : \'\') +\n' +
'            (issued ? \'<span>To: <strong class="text-slate-800">\' + issued + \'</strong></span>\' : \'\') +\n' +
'          \'</div>\' : \'\') +\n' +
'          \'<div class="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">\' +\n' +
'            \'<span>\' + date + \'</span>\' +\n' +
'            \'<button onclick="openModalByIdx(\' + idx + \')" class="text-indigo-600 font-semibold hover:underline">ดูข้อมูลทั้งหมด →</button>\' +\n' +
'          \'</div>\' +\n' +
'        \'</div>\';\n' +
'      }).join("");\n' +
'\n' +
'      container.innerHTML = html;\n' +
'    }\n' +
'\n' +
'    function renderDesktopTable(items) {\n' +
'      var tbody = document.getElementById("desktopTableBody");\n' +
'      if (!items || items.length === 0) {\n' +
'        tbody.innerHTML = \'<tr><td colspan="9" class="text-center py-12 text-slate-400">ไม่พบข้อมูลที่ค้นหา</td></tr>\';\n' +
'        return;\n' +
'      }\n' +
'\n' +
'      var h = {\n' +
'        tNo: headers.indexOf("Transaction NO"),\n' +
'        type: headers.indexOf("Transaction Type"),\n' +
'        pn: headers.indexOf("P/N"),\n' +
'        qty: headers.indexOf("QTY"),\n' +
'        bin: headers.indexOf("Bin"),\n' +
'        batch: headers.indexOf("Batch"),\n' +
'        wo: headers.indexOf("W/O - S/O"),\n' +
'        issued: headers.indexOf("Issued To"),\n' +
'        date: headers.indexOf("Created Date"),\n' +
'        name: headers.indexOf("Name")\n' +
'      };\n' +
'\n' +
'      var html = items.map(function(r, idx) {\n' +
'        var type = r[h.type] || "-";\n' +
'        var badgeClass = getBadgeClass(type);\n' +
'        return \'<tr class="hover:bg-slate-50/80 transition group">\' +\n' +
'          \'<td class="px-3.5 py-3 whitespace-nowrap"><span class="px-2 py-0.5 rounded-full text-[11px] font-semibold \' + badgeClass + \'">\' + type + \'</span></td>\' +\n' +
'          \'<td class="px-3.5 py-3 font-semibold text-slate-800 whitespace-nowrap">\' + (r[h.pn] || "-") + \'</td>\' +\n' +
'          \'<td class="px-3.5 py-3 whitespace-nowrap font-mono font-medium">\' + (r[h.qty] || "-") + \'</td>\' +\n' +
'          \'<td class="px-3.5 py-3 whitespace-nowrap text-slate-600 font-mono">\' + (r[h.bin] || "-") + \'</td>\' +\n' +
'          \'<td class="px-3.5 py-3 whitespace-nowrap text-slate-500 font-mono text-[11px]">\' + (r[h.batch] || "-") + \'</td>\' +\n' +
'          \'<td class="px-3.5 py-3 whitespace-nowrap font-medium text-slate-700">\' + (r[h.wo] || "-") + \'</td>\' +\n' +
'          \'<td class="px-3.5 py-3 whitespace-nowrap text-slate-600">\' + (r[h.issued] || "-") + \'</td>\' +\n' +
'          \'<td class="px-3.5 py-3 whitespace-nowrap text-slate-400 text-[11px]">\' + (r[h.date] || "-") + \'<br>\' + (r[h.name] || "") + \'</td>\' +\n' +
'          \'<td class="px-3.5 py-3 text-right whitespace-nowrap">\' +\n' +
'            \'<button onclick="openModalByIdx(\' + idx + \')" class="px-2.5 py-1 text-[11px] font-medium text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition">ดูครบ 27 ฟิลด์</button>\' +\n' +
'          \'</td>\' +\n' +
'        \'</tr>\';\n' +
'      }).join("");\n' +
'\n' +
'      tbody.innerHTML = html;\n' +
'    }\n' +
'\n' +
'    function openModalByIdx(idx) {\n' +
'      var r = rawData[idx];\n' +
'      if (!r) return;\n' +
'      var modal = document.getElementById("detailModal");\n' +
'      var body = document.getElementById("modalBody");\n' +
'      var title = document.getElementById("modalTitle");\n' +
'      var subtitle = document.getElementById("modalSubtitle");\n' +
'\n' +
'      var typeIdx = headers.indexOf("Transaction Type");\n' +
'      var pnIdx = headers.indexOf("P/N");\n' +
'      var tNoIdx = headers.indexOf("Transaction NO");\n' +
'\n' +
'      title.innerText = (r[pnIdx] || "Part Number") + " (" + (r[typeIdx] || "Record") + ")";\n' +
'      subtitle.innerText = "Transaction NO: " + (r[tNoIdx] || "-");\n' +
'\n' +
'      var fieldsHtml = \'<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">\';\n' +
'      for (var i = 0; i < headers.length; i++) {\n' +
'        var h = headers[i];\n' +
'        if (h === "Last Synced") continue;\n' +
'        var val = r[i] !== undefined && r[i] !== null && String(r[i]).trim() !== "" ? String(r[i]) : "-";\n' +
'        fieldsHtml += \'<div class="p-2.5 bg-slate-50 rounded-xl border border-slate-100">\' +\n' +
'          \'<div class="text-[10px] uppercase tracking-wider text-slate-400 font-semibold mb-0.5">\' + h + \'</div>\' +\n' +
'          \'<div class="text-xs font-semibold text-slate-800 break-words font-mono">\' + val + \'</div>\' +\n' +
'        \'</div>\';\n' +
'      }\n' +
'      fieldsHtml += \'</div>\';\n' +
'      body.innerHTML = fieldsHtml;\n' +
'      modal.classList.remove("hidden");\n' +
'      modal.classList.add("flex");\n' +
'    }\n' +
'\n' +
'    function closeModal() {\n' +
'      var modal = document.getElementById("detailModal");\n' +
'      modal.classList.add("hidden");\n' +
'      modal.classList.remove("flex");\n' +
'    }\n' +
'\n' +
'    // Initial load: render immediately if initialPayload is available\n' +
'    try {\n' +
'      if (typeof initialPayload !== "undefined" && initialPayload && initialPayload.rows && initialPayload.rows.length > 0) {\n' +
'        onDataLoaded(initialPayload);\n' +
'      } else {\n' +
'        fetchData();\n' +
'      }\n' +
'    } catch(e) {\n' +
'      fetchData();\n' +
'    }\n' +
'\n' +
'    // Auto-refresh every 30 seconds\n' +
'    setInterval(fetchData, 30000);\n' +
'  </script>\n' +
'</body>\n' +
'</html>';
}

/**
 * ฟังก์ชันสำหรับรวบรวมข้อมูลในหน้าเก็บข้อมูล NOV 2026 ให้กระชับขึ้นมาอยู่แถวบนสุด (Row 2)
 * สามารถกด Run จากใน Apps Script Editor ได้โดยตรง
 */
function cleanupAndConsolidateNovSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("หน้าเก็บข้อมูล NOV 2026");
  if (!sheet) {
    Logger.log("ไม่พบชีต หน้าเก็บข้อมูล NOV 2026");
    return;
  }

  var data = sheet.getDataRange().getValues();
  if (data.length <= 1) return;

  var header = data[0];
  var validRows = [];
  var seen = {};

  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    var eq = String(row[0] || "").trim();
    var wo = String(row[3] || "").trim();
    if (eq !== "" || wo !== "") {
      var key = (wo && wo !== "-") ? wo : (eq + "_" + String(row[1] || "").trim());
      if (!seen[key]) {
        seen[key] = true;
        validRows.push(row);
      }
    }
  }

  // เคลียร์ชีตและใส่ Header ใหม่
  sheet.clearContents();
  sheet.appendRow(header);

  // วางข้อมูลทั้งหมดเริ่มจากแถวที่ 2
  if (validRows.length > 0) {
    sheet.getRange(2, 1, validRows.length, validRows[0].length).setValues(validRows);
  }

  // ลบแถวว่างด้านล่างที่เกิน 2,000 แถว เพื่อให้ชีตโหลดเร็วและไม่กินพื้นที่
  var maxRows = sheet.getMaxRows();
  var keepRows = Math.max(validRows.length + 100, 200);
  if (maxRows > keepRows) {
    sheet.deleteRows(keepRows + 1, maxRows - keepRows);
  }

  Logger.log("สำเร็จ! จัดเรียงข้อมูล " + validRows.length + " แถว เรียบร้อยแล้ว");
}
