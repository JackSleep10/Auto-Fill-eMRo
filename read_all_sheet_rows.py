import urllib.request
import csv
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
url = 'https://docs.google.com/spreadsheets/d/1luje0x1QXrhhucSvmO6h_k5Es91X8rCcJeP2Fet7uYs/gviz/tq?tqx=out:csv'
content = urllib.request.urlopen(url).read().decode('utf-8')

reader = csv.reader(io.StringIO(content))
rows = list(reader)
print(f"Total rows in sheet: {len(rows)}")
for idx, r in enumerate(rows):
    print(f"Row {idx+1}: {r[:5]}")
