import re
import requests
import json

# 1. Inspect the new W/O tracking sheet:
sheet_url = "https://docs.google.com/spreadsheets/d/1luje0x1QXrhhucSvmO6h_k5Es91X8rCcJeP2Fet7uYs/edit?gid=2018892674"
r = requests.get(sheet_url)
print("Sheet fetch status:", r.status_code)

# Find all sheet tabs (names and gids)
tabs = re.findall(r'\[(\d+),0,"([^"]+)"', r.text)
print("Found tabs pattern 1:", tabs)
if not tabs:
    # try another pattern
    tabs = re.findall(r'name:"([^"]+)",sheetId:(\d+)', r.text)
    print("Found tabs pattern 2:", tabs)

# Save HTML
with open("data/tracking_sheet.html", "w", encoding="utf-8") as f:
    f.write(r.text)

# Also fetch gid=2018892674 CSV
csv_url = "https://docs.google.com/spreadsheets/d/1luje0x1QXrhhucSvmO6h_k5Es91X8rCcJeP2Fet7uYs/export?format=csv&gid=2018892674"
r_csv = requests.get(csv_url)
with open("data/tracking_sheet_sample.csv", "w", encoding="utf-8") as f:
    f.write(r_csv.text)
print("Saved tracking_sheet_sample.csv, lines:", len(r_csv.text.splitlines()))

# 2. Inspect GSE Master list sheet to see why only 884 rows were pulled
master_url = "https://docs.google.com/spreadsheets/d/1i0hjTtfuJZX5EVIDxKNGcj4zr4qy3xuZHar1NAeYsQ0/export?format=csv"
r_m = requests.get(master_url)
print("Master list export lines:", len(r_m.text.splitlines()))

# Check HTML of master sheet to see what other tabs exist or how many rows
master_html_url = "https://docs.google.com/spreadsheets/d/1i0hjTtfuJZX5EVIDxKNGcj4zr4qy3xuZHar1NAeYsQ0/edit"
r_m_html = requests.get(master_html_url)
with open("data/master_sheet.html", "w", encoding="utf-8") as f:
    f.write(r_m_html.text)
