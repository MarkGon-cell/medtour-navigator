import os
import sys
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.api.hybrid_first_aid_retriever import (
    PDF_PATH,
    retrieve_multi_chapter_sections,
    extract_accurate_chapter_evidence
)
from app.api.ai_analysis import draft_first_aid_instructions

VAGUE_TEST_CASES = [
    {
        "id": "CASE 1",
        "name": "Severe Bleeding & Deep Glass Laceration",
        "input": "Stepped on a large piece of broken window glass, deep gash on the leg, bright red blood is gushing out rapidly and tissues are soaked immediately."
    },
    {
        "id": "CASE 2",
        "name": "Choking & Airway Obstruction",
        "input": "My uncle was eating mutton and suddenly grabbed his throat, he can't talk, can't cough, and his face is turning slightly blue."
    },
    {
        "id": "CASE 3",
        "name": "Scald / Thermal Burn with Blisters",
        "input": "I accidentally spilled hot boiling tea on my forearm, the skin is bright red, burning like fire, and watery bubbles are popping up."
    }
]

print("=" * 95)
print("COMPLETE END-TO-END MULTI-CHAPTER FIRST AID WORKFLOW DEMO")
print("=" * 95)

for case in VAGUE_TEST_CASES:
    print(f"\n###########################################################################################")
    print(f">> [{case['id']}] {case['name']} <<")
    print(f"Narrative Complaint: \"{case['input']}\"")
    print("###########################################################################################")
    
    # 1. Multi-Chapter Dynamic Retrieval
    sections = retrieve_multi_chapter_sections(case['input'], max_sections=3)
    print(f"\n[1. Multi-Chapter Evidence Retrieved]:")
    for s in sections:
        print(f"    * Topic: '{s['topic']}' | TOC Pg {s['listed_page']:3d} -> Physical PDF Pg {s['actual_pdf_page']:3d}")
        
    # 2. Precise Text Extraction across Sub-Chapters
    evidence = extract_accurate_chapter_evidence(PDF_PATH, sections)
    print(f"\n[2. Synthesized Manual Context]: Extracted {len(evidence)} distinct procedural chapters.")
    
    # 3. AI Reframing & Pre-requisites Synthesis
    t0 = time.time()
    triage_result = draft_first_aid_instructions(case['input'])
    elapsed = round(time.time() - t0, 2)
    
    print(f"\n[3. AI Synthesized & Reframed First Aid Steps] (Speed: {elapsed}s):")
    print(f"    * Inferred Specialty : {triage_result.get('specialty', '').upper()}")
    print(f"    * Urgency Level      : {triage_result.get('urgency')}")
    print(f"    * Summary            : {triage_result.get('summary')}")
    print(f"    * Step-by-Step Action Plan:")
    for idx, step in enumerate(triage_result.get('firstAid', []), 1):
        print(f"        {idx}. {step}")
        
    print(f"\n[4. Pre-Requisites Before Hospital Arrival]:")
    for r in triage_result.get('prerequisites', []):
        print(f"    [+] {r}")
