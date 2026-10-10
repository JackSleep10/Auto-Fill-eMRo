from bs4 import BeautifulSoup

with open("data/gse_form_panel.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

gse_elem = soup.find(id=lambda x: x and "1558342" in x)
p = gse_elem
for i in range(5):
    p = p.parent
    if p:
        print(f"Level {i+1}: {p.name} class={p.get('class')} id={p.get('id')}")

if p:
    print("\nLevel 5 HTML:\n", p.prettify()[:2500])
