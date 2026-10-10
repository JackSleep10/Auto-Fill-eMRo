from bs4 import BeautifulSoup

with open("data/gse_wo_new_detail.html", "r", encoding="utf-8", errors="ignore") as f:
    soup = BeautifulSoup(f, "html.parser")

print("--- BUTTONS ---")
for b in soup.find_all(["button", "a"]):
    text = b.get_text(strip=True)
    if any(k in text.lower() for k in ["save", "new detail", "find"]):
        print(f"[{b.name}] id='{b.get('id')}' class='{b.get('class')}' text='{text}'")

print("\n--- LABELS & THEIR TARGET INPUTS ---")
for label in soup.find_all("label"):
    text = label.get_text(strip=True)
    if any(k in text for k in ["Company", "Category", "GSE", "S/N", "Priority", "Expenditure", "Location", "Site"]):
        for_id = label.get("for")
        target_elem = soup.find(id=for_id) if for_id else None
        target_tag = target_elem.name if target_elem else "NONE"
        print(f"Label: '{text}' | for='{for_id}' | tag={target_tag}")
