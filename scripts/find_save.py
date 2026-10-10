from bs4 import BeautifulSoup

with open("data/gse_form_panel.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

for elem in soup.find_all(lambda tag: "save" in tag.get_text().lower() if tag.name in ["a", "button", "span", "li"] else False):
    print(f"Tag: {elem.name} | id: {elem.get('id')} | class: {elem.get('class')} | text: {elem.get_text(strip=True)[:30]}")
