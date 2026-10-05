import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.first_aid_extractor import get_target_pages_for_keywords, extract_content_from_target_pages

PDF_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "inputs", "redcross.pdf"))

test_inputs = [
    ("Burn Case", "I accidentally spilled hot boiling tea on my forearm, the skin is bright red, burning like fire, and watery bubbles are popping up."),
    ("Choking Case", "My uncle was eating mutton and suddenly grabbed his throat, he can't talk, can't cough, and his face is turning slightly blue."),
    ("Bleeding Case", "Stepped on a large piece of broken window glass, deep gash on the leg, bright red blood is gushing out rapidly and tissues are soaked immediately.")
]

for name, user_text in test_inputs:
    print("=" * 80)
    print(f"CASE: {name}")
    print(f"User Input: \"{user_text}\"")
    
    words = [w.strip(".,!?") for w in user_text.lower().split() if len(w) > 3]
    matched = get_target_pages_for_keywords(PDF_PATH, words)
    print(f"\nTop 3 Matched Topics:")
    for m in matched[:3]:
        print(f"  - Topic: '{m['topic']}' | Listed Pg {m['listed_page']} -> Physical PDF Pg {m['actual_pdf_page']} (Score: {m['relevance_score']})")
    
    if matched:
        extracted = extract_content_from_target_pages(PDF_PATH, matched[:1])
        first = extracted[0]
        print(f"\nSTEP 4 EXTRACTED PAGE: {first['source_location']}")
        print(f"Heading: {first['heading']}")
        clean_text = first['text'][:350].replace('\n', ' ').encode('ascii', 'ignore').decode('ascii')
        print(f"Excerpt: \"{clean_text}...\"\n")
