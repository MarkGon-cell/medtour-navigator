import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.api.ai_analysis import draft_first_aid_instructions

TEST_CASES = [
    {
        "name": "CASE 1: Acute Choking / Mechanical Airway Obstruction",
        "input": "My uncle was eating mutton and suddenly grabbed his throat, he can't talk, can't cough, and his face is turning slightly blue."
    },
    {
        "name": "CASE 2: Severe Arterial Hemorrhage / Spurting Bleeding",
        "input": "Stepped on a large piece of broken window glass, deep gash on the leg, bright red blood is gushing out rapidly and tissues are soaked immediately."
    },
    {
        "name": "CASE 3: Thermal Scald / Watery Blisters",
        "input": "I accidentally spilled hot boiling tea on my forearm, the skin is bright red, burning like fire, and watery bubbles are popping up."
    }
]

print("=" * 100)
print("RUNNING END-TO-END VERIFICATION OF ROBUST TRIAGE & FIRST AID PIPELINE")
print("=" * 100)

for case in TEST_CASES:
    print(f"\n####################################################################################################")
    print(f">> {case['name']} <<")
    print(f"Complaint: \"{case['input']}\"")
    print("####################################################################################################")
    
    t0 = time.time()
    result = draft_first_aid_instructions(case['input'])
    elapsed = round(time.time() - t0, 2)
    
    print(f"\n[TRIAGE RESULT] (Completed in {elapsed}s):")
    print(f"  * Specialty : {result.get('specialty')}")
    print(f"  * Urgency   : {result.get('urgency')}")
    print(f"  * Summary   : {result.get('summary')}")
    print(f"\n  * Immediate First Aid Action Steps:")
    for idx, step in enumerate(result.get("firstAid", []), 1):
        print(f"     {idx}. {step}")
        
    print(f"\n  * Pre-Requisites Before Hospital Arrival:")
    for r in result.get("prerequisites", []):
        print(f"     [+] {r}")
