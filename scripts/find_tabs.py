import re

with open("data/sheet_edit.html", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

# Pattern for sheet tabs in Google Sheets: [gid, null, "SheetName"] or similar
tabs = re.findall(r'\[(\d+),\d+,"([^"]+)"', text)
print("Found tabs:", set(tabs))
matches = re.findall(r'name:"([^"]+)",sheetId:(\d+)', text)
print("Matches 2:", matches)
matches3 = re.findall(r'\[(\d+),\["([^"]+)"\]', text)
print("Matches 3:", matches3)
