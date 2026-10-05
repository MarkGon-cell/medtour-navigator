import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.api.first_aid_extractor import parse_index_pages

PDF_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "inputs", "redcross.pdf"))
index_entries = parse_index_pages(PDF_PATH)

print(f"Total topics: {len(index_entries)}")
for i, e in enumerate(index_entries[:30]):
    print(f"Pg {e['actual_pdf_page']:3d} | {e['topic']}")
