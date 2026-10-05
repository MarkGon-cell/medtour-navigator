import os
import sys
import json
from app.api.first_aid_extractor import build_complete_first_aid_database

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

pdf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "inputs", "redcross.pdf"))
out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs", "redcross_first_aid_guides.json"))

print(f"Building Red Cross knowledge base from: {pdf_path}")
print(f"Output destination: {out_path}")

try:
    guides = build_complete_first_aid_database(pdf_path, out_path)
    print(f"Successfully indexed and generated {len(guides)} Red Cross condition guides into {out_path}!")
except Exception as e:
    print(f"Failed: {e}")
