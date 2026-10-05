import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.api.first_aid_extractor import parse_index_pages

PDF_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "inputs", "redcross.pdf"))
index_entries = parse_index_pages(PDF_PATH)

for e in index_entries:
    if "first aid" in e["topic"].lower() or "when can" in e["topic"].lower() or "box" in e["topic"].lower():
        print(f"Listed: {e['listed_page']:3d} | Actual PDF: {e['actual_pdf_page']:3d} | Topic: {e['topic']}")
