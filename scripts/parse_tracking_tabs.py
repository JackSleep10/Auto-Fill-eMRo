import re
import json

with open("data/tracking_sheet.html", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

out_lines = []

# Search for bootstrapData
match = re.search(r"var bootstrapData = ({.+?});</script>", text)
if match:
    try:
        data = json.loads(match.group(1))
        sheets = data.get("changes", {}).get("sheets", [])
        out_lines.append(f"Found {len(sheets)} sheets in bootstrapData:")
        for s in sheets:
            out_lines.append(f"  ID: {s.get('id')} | Name: {s.get('name')}")
    except Exception as e:
        out_lines.append(f"bootstrapData parse error: {e}")

# Regex search for tab patterns
matches = re.findall(r'\[(\d+),\d+,"([^"]+)",\d+\]', text)
out_lines.append(f"Matches count: {len(matches)}")
for m in matches[:50]:
    out_lines.append(f"  Tab: {m}")

# Search for specific gid from user's URL: gid=2018892674
pos = text.find("2018892674")
if pos != -1:
    snippet = text[max(0, pos-150):min(len(text), pos+150)]
    out_lines.append(f"Found 2018892674 snippet: {snippet}")

with open("data/sheet_tabs_info.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines))

print("Done writing data/sheet_tabs_info.txt")
