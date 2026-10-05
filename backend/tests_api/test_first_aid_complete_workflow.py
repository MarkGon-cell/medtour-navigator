import os
import sys
import json
import time
from typing import Dict, Any, List

# Ensure safe UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.first_aid_extractor import get_target_pages_for_keywords, extract_content_from_target_pages
from app.api.ai_analysis import draft_first_aid_instructions, SYMPTOM_SPECIALTY_MAP

PDF_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "inputs", "redcross.pdf"))

# 3 realistic vague symptom scenarios
VAGUE_SCENARIOS = [
    {
        "id": "CASE-1",
        "title": "Vague Burn / Scald Trauma",
        "vague_input": "I accidentally spilled hot boiling tea on my forearm, the skin is bright red, burning like fire, and watery bubbles are popping up."
    },
    {
        "id": "CASE-2",
        "title": "Vague Airway / Choking Obstruction",
        "vague_input": "My uncle was eating mutton and suddenly grabbed his throat, he can't talk, can't cough, and his face is turning slightly blue."
    },
    {
        "id": "CASE-3",
        "title": "Vague Severe Bleeding Trauma",
        "vague_input": "Stepped on a large piece of broken window glass, deep gash on the leg, bright red blood is gushing out rapidly and tissues are soaked immediately."
    }
]

def run_step_by_step_workflow(case: Dict[str, str]):
    print("=" * 90)
    print(f"[{case['id']}] WORKFLOW TEST: {case['title']}")
    print("=" * 90)
    
    # -------------------------------------------------------------
    # STEP 1: Vague User Explanation
    # -------------------------------------------------------------
    print(f"\n[STEP 1] USER'S VAGUE COMPLAINT:")
    print(f"  \"{case['vague_input']}\"")

    # -------------------------------------------------------------
    # STEP 2: Categorizing Symptoms & Understanding Required First Aid
    # -------------------------------------------------------------
    print(f"\n[STEP 2] SYMPTOM CATEGORIZATION & CLINICAL INFERENCE:")
    words = [w.strip(".,!?") for w in case['vague_input'].lower().split() if len(w) > 3]
    inferred_specialty = "general medicine"
    for kw, spec in SYMPTOM_SPECIALTY_MAP.items():
        if kw in case['vague_input'].lower():
            inferred_specialty = spec
            break
    print(f"  * Detected Specialty : {inferred_specialty.upper()}")
    print(f"  * Search Keywords    : {words[:6]}")

    # -------------------------------------------------------------
    # STEP 3: Searching Red Cross Manual PDF (Pages 3-10 Index + Offset +2)
    # -------------------------------------------------------------
    print(f"\n[STEP 3] RED CROSS PDF TOC INDEX & PAGE SEARCH:")
    matched_pages = get_target_pages_for_keywords(PDF_PATH, words)
    print(f"  * Matched Topics in PDF Index : {len(matched_pages)} found")
    for m in matched_pages[:3]:
        print(f"     -> Topic: \"{m['topic']}\" | TOC Listed: Pg {m['listed_page']} -> Physical PDF Page: {m['actual_pdf_page']}")

    # -------------------------------------------------------------
    # STEP 4: Extracting Content from Target PDF Pages
    # -------------------------------------------------------------
    print(f"\n[STEP 4] EXTRACTING RAW MANUAL TEXT (via pdfplumber):")
    extracted_data = extract_content_from_target_pages(PDF_PATH, matched_pages[:1]) if matched_pages else []
    if extracted_data:
        raw_snippet = extracted_data[0]['text'][:220].replace('\n', ' ')
        # Clean up any non-ascii characters for clean terminal display
        safe_snippet = raw_snippet.encode('ascii', 'ignore').decode('ascii')
        print(f"  * Source Location    : {extracted_data[0].get('source_location')}")
        print(f"  * Raw Manual Excerpt : \"{safe_snippet}...\"")
    else:
        print("  * Using Red Cross Emergency Core Protocol table.")

    # -------------------------------------------------------------
    # STEP 5 & 6: AI Reframing & Pre-requisites Generation
    # -------------------------------------------------------------
    print(f"\n[STEP 5] NVIDIA NIM AI REFRAMING (Simple Layperson Action Steps):")
    t0 = time.time()
    result = draft_first_aid_instructions(case['vague_input'])
    elapsed = round(time.time() - t0, 2)
    
    print(f"  * Urgency Assessed : {result.get('urgency')}")
    print(f"  * Triage Summary   : {result.get('summary')}")
    print(f"  * First Aid Steps  :")
    for idx, step in enumerate(result.get('firstAid', []), 1):
        print(f"     {idx}. {step}")

    print(f"\n[STEP 6] PRE-REQUISITES BEFORE VISITING THE HOSPITAL:")
    for req in result.get('prerequisites', []):
        print(f"  [+] {req}")

    print(f"\n[Workflow completed in {elapsed}s]")
    print("-" * 90 + "\n")


if __name__ == "__main__":
    print("\n" + "#" * 90)
    print("STARTING COMPLETE END-TO-END FIRST AID TEST WORKFLOW")
    print("#" * 90 + "\n")
    for scenario in VAGUE_SCENARIOS:
        run_step_by_step_workflow(scenario)
        time.sleep(1.5)
