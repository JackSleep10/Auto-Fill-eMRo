import requests
import re
import json

url = "https://docs.google.com/spreadsheets/d/1i0hjTtfuJZX5EVIDxKNGcj4zr4qy3xuZHar1NAeYsQ0/edit"
r = requests.get(url, timeout=15)
matches = re.findall(r'(\d+),\[\"([^\"]+)\"', r.text)
# Look for bootstrapData
match = re.search(r'var bootstrapData = (\{.+?\});', r.text)
if match:
    data = json.loads(match.group(1))
    sheets = data.get("changes", {}).get("sheets", [])
    print("Sheets from bootstrapData:", sheets)

print("Saved HTML length:", len(r.text))
with open("data/sheet_edit.html", "w", encoding="utf-8") as f:
    f.write(r.text)
