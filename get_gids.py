import urllib.request
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
url = 'https://docs.google.com/spreadsheets/d/1luje0x1QXrhhucSvmO6h_k5Es91X8rCcJeP2Fet7uYs/edit'
html = urllib.request.urlopen(url).read().decode('utf-8')

# Look for sheetId or gid in HTML
gids = re.findall(r'sheetId":(\d+)', html)
if not gids:
    gids = re.findall(r'\"gid\":(\d+)', html)
if not gids:
    gids = re.findall(r'gid=(\d+)', html)
print("Unique GIDs found:", set(gids))
