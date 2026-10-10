import sys
import re
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')
with open("data/current_sheet_view.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")
tabs = [t.get_text(strip=True) for t in soup.find_all("li", id=re.compile(r"sheet-button-.*"))]
print("Tabs in current sheet:", tabs)

# Search for any W/O numbers like 2346372 or 2346391
for m in re.finditer(r'(23463\d{2})', html):
    print("Found W/O in sheet:", m.group(1))

# Check any mention of TLM-TB-
for m in re.finditer(r'(TLM-TB-\d{3})', html):
    print("Found GSE in sheet:", m.group(1))
