import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.api.first_aid_extractor import parse_index_pages

PDF_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "inputs", "redcross.pdf"))
index_entries = parse_index_pages(PDF_PATH)

print("Topics matching chok / breath / airway:")
for e in index_entries:
    t = e["topic"].lower()
    if any(k in t for k in ["chok", "breath", "airway", "bleed", "wound", "glass"]):
        print(f"Pg {e['actual_pdf_page']:3d} (TOC {e['listed_page']:3d}) | {e['topic']}")
