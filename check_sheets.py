import urllib.request
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
url = 'https://docs.google.com/spreadsheets/d/1luje0x1QXrhhucSvmO6h_k5Es91X8rCcJeP2Fet7uYs/edit'
html = urllib.request.urlopen(url).read().decode('utf-8')

# Search for patterns containing sheet names
candidates = set(re.findall(r'[\"\']([A-Za-z0-9_\s\u0E00-\u0E7F\-]{2,30})[\"\']', html))
relevant = [c for c in candidates if any(k in c for k in ['OCT', 'NOV', 'DEC', 'GSE', 'หน้า', 'Sheet', 'ข้อมูล'])]
print("Relevant names found:", relevant)
