import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.api.hybrid_first_aid_retriever import (
    PDF_PATH,
    retrieve_multi_chapter_sections,
    extract_accurate_chapter_evidence
)

TEST_CASES = [
    {
        "name": "CASE 1: Vague Choking / Airway Obstruction",
        "query": "My uncle was eating mutton and suddenly grabbed his throat, he can't talk, can't cough, and his face is turning slightly blue."
    },
    {
        "name": "CASE 2: Vague Severe Bleeding / Deep Gash",
        "query": "Stepped on a large piece of broken window glass, deep gash on the leg, bright red blood is gushing out rapidly and tissues are soaked immediately."
    },
    {
        "name": "CASE 3: Vague Severe Burn / Scald Trauma",
        "query": "I accidentally spilled hot boiling tea on my forearm, the skin is bright red, burning like fire, and watery bubbles are popping up."
    }
]

print("=" * 95)
print("TESTING RETRIEVAL ENGINE WITH MEDICAL EXPANSION & MULTI-CHAPTER SYNTHESIS")
print("=" * 95)

for case in TEST_CASES:
    print(f"\n===========================================================================================")
    print(f">> {case['name']} <<")
    print(f"User Narrative: \"{case['query']}\"")
    print("===========================================================================================")
    
    sections = retrieve_multi_chapter_sections(case['query'], max_sections=3)
    print(f"\n[+] Matched Chapters & Sub-Chapters ({len(sections)} distinct sections):")
    for s in sections:
        print(f"    * Topic: '{s['topic']}' | TOC Pg: {s['listed_page']:3d} -> Physical PDF Pg: {s['actual_pdf_page']:3d} (BM25 Score: {s['score']})")
        
    evidence = extract_accurate_chapter_evidence(PDF_PATH, sections)
    print(f"\n[+] Extracted & Boundary-Isolated Manual Excerpts ({len(evidence)} excerpts):")
    for idx, ev in enumerate(evidence, 1):
        snippet = ev['text'][:220].replace('\n', ' ')
        print(f"    [{idx}] {ev['source_ref']}")
        print(f"        Heading : {ev['topic']}")
        print(f"        Content : \"{snippet}...\"\n")
