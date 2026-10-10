import json
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import csv

BASE_DIR = Path(r"D:\Project dashboard")
hist_file = BASE_DIR / "data" / "work_order_history.json"

with open(hist_file, "r", encoding="utf-8") as f:
    items = json.load(f)

print(f"Loaded {len(items)} items from history.")

headers = [
    "วันที่-เวลา (Timestamp)",
    "ผู้เปิดใบงาน (User)",
    "รหัสรถ (GSE NO.)",
    "หมายเลขตัวถัง (S/N)",
    "เลขที่ W/O",
    "ประเภท (Type)",
    "อาการ / รายละเอียด (Description)",
    "สถานะ (Status)"
]

# 1. Create CSV file (UTF-8 with BOM for Excel/Sheets compatibility)
csv_path = BASE_DIR / "data" / "log_emro_wo.csv"
with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(headers)
    for it in items:
        prio = "PM" if (it.get("priority") or "").upper() in ("SCHED", "PM") else "CM"
        writer.writerow([
            it.get("created_at") or it.get("date") or "-",
            it.get("user") or "TL248006",
            it.get("gse") or "-",
            it.get("sn") or "-",
            it.get("wo_number") or "-",
            prio,
            it.get("description") or "-",
            "SUCCESS" if it.get("success") else ("FAILED: " + (it.get("error") or ""))
        ])

print(f"Saved CSV to {csv_path}")

# 2. Create beautifully formatted Excel file
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "LOG eMRO WO"

# Header styles
header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid") # Dark Slate 900
header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
center_align = Alignment(horizontal="center", vertical="center")
left_align = Alignment(horizontal="left", vertical="center")

thin_border = Border(
    left=Side(style='thin', color='E2E8F0'),
    right=Side(style='thin', color='E2E8F0'),
    top=Side(style='thin', color='E2E8F0'),
    bottom=Side(style='thin', color='E2E8F0')
)

ws.append(headers)
ws.row_dimensions[1].height = 28

for col_idx in range(1, len(headers) + 1):
    cell = ws.cell(row=1, column=col_idx)
    cell.fill = header_fill
    cell.font = header_font
    cell.alignment = center_align

# Body rows
row_idx = 2
for it in items:
    prio = "PM" if (it.get("priority") or "").upper() in ("SCHED", "PM") else "CM"
    row_data = [
        it.get("created_at") or it.get("date") or "-",
        it.get("user") or "TL248006",
        it.get("gse") or "-",
        it.get("sn") or "-",
        it.get("wo_number") or "-",
        prio,
        it.get("description") or "-",
        "SUCCESS" if it.get("success") else ("FAILED: " + (it.get("error") or ""))
    ]
    ws.append(row_data)
    ws.row_dimensions[row_idx].height = 22
    
    for c_idx in range(1, len(row_data) + 1):
        cell = ws.cell(row=row_idx, column=c_idx)
        cell.font = Font(name="Segoe UI", size=10)
        cell.border = thin_border
        if c_idx in (1, 2, 3, 4, 5, 6, 8):
            cell.alignment = center_align
        else:
            cell.alignment = left_align
            
        if c_idx == 5: # W/O number
            cell.font = Font(name="Segoe UI", size=10, bold=True)
            
        if c_idx == 6: # Type
            if prio == "CM":
                cell.font = Font(name="Segoe UI", size=10, bold=True, color="D97706") # Amber
            else:
                cell.font = Font(name="Segoe UI", size=10, bold=True, color="059669") # Emerald
                
        if c_idx == 8: # Status
            cell.font = Font(name="Segoe UI", size=10, bold=True, color="16A34A")

    row_idx += 1

# Auto-adjust column widths
for col in ws.columns:
    max_len = 0
    col_letter = get_column_letter(col[0].column)
    for cell in col:
        val_str = str(cell.value or "")
        if len(val_str) > max_len:
            max_len = len(val_str)
    ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

ws.freeze_panes = "A2"

excel_path = BASE_DIR / "data" / "log_emro_wo.xlsx"
wb.save(excel_path)
print(f"Saved Excel to {excel_path}")

desktop_excel = Path(r"C:\Users\Thai Lion Air\Desktop\log_emro_wo.xlsx")
try:
    wb.save(desktop_excel)
    print(f"Saved copy to Desktop: {desktop_excel}")
except Exception as e:
    print(f"Could not save to desktop: {e}")
