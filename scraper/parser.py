import re
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Any

class eMROParser:
    LABEL_MAPPINGS = {
        "location": ["location"],
        "bin": ["bin"],
        "condition": ["condition"],
        "qty": ["qty", "quantity"],
        "unit_cost": ["unit cost"],
        "secondary_cost": ["secondary cost"],
        "cur_exc_rate": ["cur exc rate", "exchange rate", "curr exc rate"],
        "ac": ["a/c", "aircraft"],
        "wo_so": ["w/o-s/o", "w/o - s/o", "wo/so", "w/o", "s/o", "wo-so"],
        "issued_to": ["issued to"],
        "issued_to_name": ["issued to name"],
        "order_type": ["order type", "orde type"],
        "order_no": ["order no"],
        "order_line": ["line"],
        "vendor_customer": ["vendor/customer", "vendor customer", "vendor"],
        "vendor_name": ["vendor name"],
        "reference": ["reference"],
        "transaction_no": ["transaction no", "trans no", "trans number", "transaction number"],
        "status": ["status"],
        "created_by": ["created by"],
        "created_date": ["created date"],
        "created_name": ["name"],
        "gl": ["g/l"],
        "defect_description": ["defect description"]
    }

    @staticmethod
    def parse_transaction_row(main_cells: Any, expanded_container_html: Optional[str] = None) -> Dict:
        """
        Parses a single row from the PrimeFaces DataTable, along with its expanded detail container if present.
        main_cells can be a list of BeautifulSoup tags or a list of plain strings.
        """
        data = {
            "transaction_type": "",
            "pn": "",
            "sn": "",
            "batch": "",
            "grb": "",
            "vendor_lot": "",
            "location": "",
            "bin": "",
            "condition": "",
            "qty": "",
            "unit_cost": "",
            "secondary_cost": "",
            "cur_exc_rate": "",
            "ac": "",
            "wo_so": "",
            "issued_to": "",
            "issued_to_name": "",
            "order_type": "",
            "order_no": "",
            "order_line": "",
            "vendor_customer": "",
            "vendor_name": "",
            "reference": "",
            "transaction_no": "",
            "status": "",
            "created_by": "",
            "created_date": "",
            "created_name": "",
            "gl": "",
            "defect_description": ""
        }

        # 1. Normalize main row cell texts
        cell_texts: List[str] = []
        if isinstance(main_cells, list):
            for c in main_cells:
                if hasattr(c, "get_text"):
                    cell_texts.append(c.get_text(strip=True))
                elif isinstance(c, str):
                    cell_texts.append(c.strip())
                else:
                    cell_texts.append(str(c).strip())

        # Match by known column positions in eMRO DataTable
        # Col 0: Select checkbox / icon
        # Col 1: Expand toggler [ > ]
        # Col 2: Transaction Type (e.g. ISSUED, INITIAL/RECEIVING, etc.)
        # Col 3: P/N (Part Number)
        # Col 4: S/N (Serial Number)
        # Col 5: Batch
        # Col 6: GRB
        # Col 7: Vendor Lot
        type_idx = -1
        for i, txt in enumerate(cell_texts):
            u = txt.upper()
            if any(kw in u for kw in ["ISSUED", "RECEIVING", "TRANSFER", "RTS", "PO", "BIN"]):
                type_idx = i
                break

        if type_idx != -1 and len(cell_texts) >= 7:
            data["transaction_type"] = cell_texts[type_idx]
            if len(cell_texts) > type_idx + 1:
                data["pn"] = cell_texts[type_idx + 1]
            if len(cell_texts) > type_idx + 2:
                data["sn"] = cell_texts[type_idx + 2]
            if len(cell_texts) > type_idx + 3:
                data["batch"] = cell_texts[type_idx + 3]
            if len(cell_texts) > type_idx + 4:
                data["grb"] = cell_texts[type_idx + 4]
            if len(cell_texts) > type_idx + 5:
                data["vendor_lot"] = cell_texts[type_idx + 5]
        else:
            cleaned_cells = [t for t in cell_texts if t and t.lower() not in ["select", "view", "edit", ">", "»"]]
            if len(cleaned_cells) >= 1:
                data["transaction_type"] = cleaned_cells[0]
            if len(cleaned_cells) >= 2:
                data["pn"] = cleaned_cells[1]
            if len(cleaned_cells) >= 3:
                data["batch"] = cleaned_cells[2]
            if len(cleaned_cells) >= 4:
                data["grb"] = cleaned_cells[3]

        # 2. Parse detail container if expanded
        if expanded_container_html:
            soup = BeautifulSoup(expanded_container_html, "html.parser")
            details = eMROParser._extract_details_from_soup(soup)
            data.update(details)

        return data

    @staticmethod
    def _extract_details_from_soup(soup: BeautifulSoup) -> Dict:
        extracted = {}

        def norm(s):
            if not s:
                return ""
            s = re.sub(r"[:*_]+", " ", str(s))
            s = re.sub(r"\s*/\s*", "/", s)
            s = re.sub(r"\s*-\s*", "-", s)
            s = re.sub(r"\s+", " ", s).strip().lower()
            return s

        alias_to_field = {}
        for field, aliases in eMROParser.LABEL_MAPPINGS.items():
            for a in aliases:
                alias_to_field[norm(a)] = field

        # Strategy 1: Grid / Column Container-Scoped Extraction
        # In PrimeFaces, each column (e.g. ui-g-*, ui-md-*, col-*, or td) contains
        # its OWN label and its OWN input. We search strictly within that container.
        for a_norm, field in alias_to_field.items():
            if field in extracted:
                continue

            # Find all elements matching this label
            for text_node in soup.find_all(string=lambda t: t and norm(t) == a_norm):
                parent = text_node.parent
                if not parent:
                    continue

                val_found = None
                curr = parent

                # Climb up towards the column / field wrapper, but do NOT enter row / table / root
                while curr and curr != soup:
                    # Look for input, textarea, select within curr
                    for inp in curr.find_all(["input", "textarea", "select"]):
                        if inp.name == "input" and inp.get("type", "").lower() in ["hidden", "submit", "button", "image"]:
                            continue
                        v = inp.get("value") or inp.get_text(strip=True) or ""
                        v = v.strip()
                        if v.lower() not in ["select", "view", "edit", "find"]:
                            val_found = v
                            break

                    if val_found is not None:
                        break

                    # Check next sibling element within the same column wrapper
                    sib = curr.find_next_sibling()
                    if sib:
                        sib_text = norm(sib.get_text())
                        has_other_label = any(a in sib_text for a in alias_to_field.keys())
                        if not has_other_label:
                            if sib.name in ["input", "textarea", "select"]:
                                if not (sib.name == "input" and sib.get("type", "").lower() in ["hidden", "submit", "button", "image"]):
                                    v = sib.get("value") or sib.get_text(strip=True) or ""
                                    if v.strip().lower() not in ["select", "view", "edit", "find"]:
                                        val_found = v.strip()
                                        break
                            else:
                                for sib_inp in sib.find_all(["input", "textarea", "select"]):
                                    if sib_inp.name == "input" and sib_inp.get("type", "").lower() in ["hidden", "submit", "button", "image"]:
                                        continue
                                    v = sib_inp.get("value") or sib_inp.get_text(strip=True) or ""
                                    if v.strip().lower() not in ["select", "view", "edit", "find"]:
                                        val_found = v.strip()
                                        break
                                if val_found is not None:
                                    break

                    # Stop climbing if we hit a column container boundary
                    classes = curr.get("class") or []
                    if curr.name in ["td", "th"] or any(c.startswith("ui-g-") or c.startswith("ui-md-") or "col" in c for c in classes):
                        break

                    # Also stop if curr's parent is a row (ui-g, row, tr)
                    parent_classes = (curr.parent.get("class") if curr.parent else []) or []
                    if curr.parent and (curr.parent.name in ["tr", "table"] or any(c in ["ui-g", "row", "p-grid"] for c in parent_classes)):
                        break

                    curr = curr.parent

                if val_found is not None:
                    extracted[field] = val_found
                    break

        # Strategy 2: Explicit label[for="id"] -> input[id="id"]
        for lbl in soup.find_all(["label", "span", "a"]):
            for_id = lbl.get("for")
            if not for_id:
                continue
            n_text = norm(lbl.get_text())
            f = alias_to_field.get(n_text)
            if f and f not in extracted:
                inp = soup.find(id=for_id) or soup.find(id=re.compile(re.escape(for_id)))
                if inp:
                    v = inp.get("value") or inp.get_text(strip=True) or ""
                    if v.strip().lower() not in ["select", "view", "edit", "find"]:
                        extracted[f] = v.strip()

        # Strategy 3: Pure Table Row Pairs (<tr> of only labels followed by <tr> of inputs)
        for tbl in soup.find_all("table"):
            trs = tbl.find_all("tr", recursive=False)
            for i in range(len(trs) - 1):
                lbl_tr = trs[i]
                val_tr = trs[i + 1]

                # Ensure lbl_tr has NO inputs and val_tr HAS inputs
                if lbl_tr.find(["input", "textarea", "select"]):
                    continue
                if not val_tr.find(["input", "textarea", "select"]):
                    continue

                lbl_cells = lbl_tr.find_all(["td", "th"], recursive=False)
                val_cells = val_tr.find_all(["td", "th"], recursive=False)

                for idx in range(min(len(lbl_cells), len(val_cells))):
                    f = alias_to_field.get(norm(lbl_cells[idx].get_text()))
                    if f and f not in extracted:
                        inp = val_cells[idx].find(["input", "textarea", "select"])
                        v = inp.get("value") or val_cells[idx].get_text(strip=True) or "" if inp else val_cells[idx].get_text(strip=True)
                        if v.strip().lower() not in ["select", "view", "edit", "find"]:
                            extracted[f] = v.strip()

        # Strategy 4: Fallback for Transaction NO (must be 7-9 digits starting with 4, NEVER "Select")
        curr_tno = extracted.get("transaction_no", "")
        if not curr_tno or not re.match(r"^4\d{7,8}$", curr_tno):
            for el in soup.find_all(["input", "span", "div"]):
                val = el.get("value", "") if el.name == "input" else el.get_text(strip=True)
                if re.match(r"^4\d{7,8}$", val.strip()):
                    extracted["transaction_no"] = val.strip()
                    break

        if extracted.get("transaction_no", "").lower() == "select":
            extracted["transaction_no"] = ""

        return extracted
