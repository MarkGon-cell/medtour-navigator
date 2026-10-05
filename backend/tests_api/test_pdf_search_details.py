import os
import sys

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.first_aid_extractor import get_target_pages_for_keywords, extract_content_from_target_pages

pdf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "inputs", "redcross.pdf"))

print(f"=== TESTING DYNAMIC RED CROSS PDF INDEX SEARCH ===")
print(f"PDF Path: {pdf_path}\n")

test_symptoms = [
    "I have severe burns and blisters from hot water",
    "Someone is choking and cannot breathe or speak",
    "Severe bleeding and deep wound on the leg",
    "Suspected fracture or broken arm from falling"
]

for sym in test_symptoms:
    print(f"Query: \"{sym}\"")
    words = [w.strip(".,!?") for w in sym.lower().split() if len(w) > 3]
    matched = get_target_pages_for_keywords(pdf_path, words)
    print(f"  -> Matched {len(matched)} Index Entries:")
    for m in matched:
        print(f"     * Topic: '{m['topic']}' | Listed Index Pg: {m['listed_page']} -> Physical PDF Page: {m['actual_pdf_page']}")
    
    if matched:
        extracted = extract_content_from_target_pages(pdf_path, matched[:1])
        snippet = extracted[0]['text'][:150].replace('\n', ' ')
        print(f"     * Raw Extracted Excerpt: \"{snippet}...\"\n")
    else:
        print("     * No direct index match found.\n")
