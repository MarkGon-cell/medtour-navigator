import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.api.hybrid_first_aid_retriever import (
    PDF_PATH,
    retrieve_multi_chapter_sections,
    extract_accurate_chapter_evidence
)

# Test query for deep bleeding
q = "Stepped on a large piece of broken window glass, deep gash on the leg, bright red blood is gushing out rapidly and tissues are soaked immediately."

print(f"Query: \"{q}\"")
sections = retrieve_multi_chapter_sections(q, max_sections=3)
for s in sections:
    print(f"Topic: {s['topic']} (Pg {s['actual_pdf_page']}, Score {s['score']})")
    
evidence = extract_accurate_chapter_evidence(PDF_PATH, sections)
for ev in evidence:
    print("\n--- Evidence ---")
    print(f"Heading: {ev['topic']} | Ref: {ev['source_ref']}")
    print(f"Snippet: {ev['text'][:250].replace(chr(10), ' ')}")
