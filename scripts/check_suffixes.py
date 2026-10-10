from bs4 import BeautifulSoup

with open("data/gse_form_panel.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

cols = soup.find_all("div", id=lambda x: x and x.startswith("dw_wo_gse_eu_"))
for c in cols:
    cid = c.get("id", "")
    parts = cid.split("_")
    field_name = parts[-1]
    inp = c.find(["input", "textarea", "select"])
    inp_id = inp.get("id", "") if inp else "None"
    print(f"Field: {field_name:20s} | div_id: {cid:50s} | inp_id: {inp_id}")
