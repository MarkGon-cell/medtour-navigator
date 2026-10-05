import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.api.hybrid_first_aid_retriever import (
    PDF_PATH,
    retrieve_multi_chapter_sections
)

q = "Stepped on a large piece of broken window glass, deep gash on the leg, bright red blood is gushing out rapidly and tissues are soaked immediately."

# Check tokens in D.4 and D.3
from app.api.first_aid_extractor import parse_index_pages
index_entries = parse_index_pages(PDF_PATH)
for e in index_entries:
    if "bleeding" in e["topic"].lower() or "wound" in e["topic"].lower():
        print(f"Listed: {e['listed_page']:3d} | Actual: {e['actual_pdf_page']:3d} | Topic: {e['topic']}")
