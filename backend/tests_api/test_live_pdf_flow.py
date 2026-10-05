import os
import sys
import time

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.ai_analysis import draft_first_aid_instructions

symptoms = "I accidentally spilled boiling hot tea on my forearm, it is painful and blistered."

print(f"Testing live Red Cross PDF indexing and NVIDIA reframing for: \"{symptoms}\"\\n")
t0 = time.time()
result = draft_first_aid_instructions(symptoms)
elapsed = round(time.time() - t0, 2)

print(f"[Done in {elapsed}s]")
print(f"Specialty: {result.get('specialty')}")
print(f"Urgency: {result.get('urgency')}")
print(f"Summary: {result.get('summary')}")
print("\nFirst Aid Steps:")
for i, step in enumerate(result.get("firstAid", []), 1):
    print(f"  {i}. {step}")
print("\nPre-requisites:")
for r in result.get("prerequisites", []):
    print(f"  * {r}")
