import os
import sys
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.api.robust_triage_engine import (
    PDF_PATH,
    evaluate_emergency_red_flags,
    retrieve_procedural_sections,
    extract_precise_leaf_evidence
)

TEST_SCENARIOS = [
    {
        "id": "CASE 1: Acute Choking",
        "query": "My uncle was eating mutton and suddenly grabbed his throat, he can't talk, can't cough, and his face is turning slightly blue.",
        "expected_leaf": "C.5",
        "expected_specialty": "EMERGENCY",
        "expected_urgency": "EMERGENCY"
    },
    {
        "id": "CASE 2: Arterial Hemorrhage / Spurting Bleeding",
        "query": "Stepped on a large piece of broken window glass, deep gash on the leg, bright red blood is gushing out rapidly and tissues are soaked immediately.",
        "expected_leaf": "D.4",
        "expected_specialty": "EMERGENCY",
        "expected_urgency": "EMERGENCY"
    },
    {
        "id": "CASE 3: Thermal Scald / Watery Blisters",
        "query": "I accidentally spilled hot boiling tea on my forearm, the skin is bright red, burning like fire, and watery bubbles are popping up.",
        "expected_leaf": "H.3.4",
        "expected_specialty": "EMERGENCY",
        "expected_urgency": "EMERGENCY"
    }
]

print("=" * 100)
print("VERIFYING DETERMINISTIC SAFETY FILTER + DEEP LEAF-NODE RETRIEVAL")
print("=" * 100)

for sc in TEST_SCENARIOS:
    print(f"\n####################################################################################################")
    print(f">> {sc['id']} <<")
    print(f"Narrative Input: \"{sc['query']}\"")
    print("####################################################################################################")

    # Phase 1: Red-Flag Triage
    red_flag = evaluate_emergency_red_flags(sc["query"])
    print(f"\n[PHASE 1: Red-Flag Safety Filter]:")
    print(f"  * Is Emergency       : {red_flag.get('is_emergency')}")
    print(f"  * Matched Category   : {red_flag.get('category')}")
    print(f"  * Primary Condition  : {red_flag.get('primary_condition')}")
    print(f"  * Forced Specialty   : {red_flag.get('forced_specialty')}")
    print(f"  * Forced Urgency     : {red_flag.get('forced_urgency')}")

    # Phase 2 & 3: Deep Leaf Node TOC Retrieval
    leaves = retrieve_procedural_sections(sc["query"], max_sections=3)
    print(f"\n[PHASE 2 & 3: Deep Procedural Leaf-Node Retrieval]:")
    for idx, leaf in enumerate(leaves, 1):
        print(f"  [{idx}] Topic: \"{leaf['topic']}\" | TOC Pg {leaf['listed_page']:3d} -> PDF Pg {leaf['actual_pdf_page']:3d} (Score: {leaf['score']})")

    # Phase 4: Boundary-Isolated Text Extraction
    evidence = extract_precise_leaf_evidence(PDF_PATH, leaves)
    print(f"\n[PHASE 4: Sliced Leaf Procedure Evidence]:")
    for idx, ev in enumerate(evidence, 1):
        clean_snip = ev['text'][:180].replace('\n', ' ')
        print(f"  [{idx}] {ev['source_ref']}")
        print(f"      Heading: {ev['topic']}")
        print(f"      Excerpt: \"{clean_snip}...\"\n")
