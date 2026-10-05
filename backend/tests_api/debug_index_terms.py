import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.api.first_aid_extractor import parse_index_pages

PDF_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "inputs", "redcross.pdf"))
index_entries = parse_index_pages(PDF_PATH)

print("--- Checking 'stop' in index entries ---")
for e in index_entries:
    if "stop" in e["topic"].lower():
        print(e)

print("\n--- Checking 'bleeding' in index entries ---")
for e in index_entries:
    if "bleed" in e["topic"].lower() or "blood" in e["topic"].lower():
        print(e)
