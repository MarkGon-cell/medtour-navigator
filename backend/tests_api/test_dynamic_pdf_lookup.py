import os
import sys
import time
import requests

from app.api.ai_analysis import draft_first_aid_instructions

symptoms = "I accidentally touched a hot exhaust pipe, my skin on my arm is blistered, red, and burning intensely."

print("Testing dynamic Red Cross PDF extraction and reframing...")
t0 = time.time()
result = draft_first_aid_instructions(symptoms)
elapsed = round(time.time() - t0, 2)

print(f"Time taken: {elapsed}s")
print(f"Specialty: {result.get('specialty')}")
print(f"Urgency: {result.get('urgency')}")
print(f"Summary: {result.get('summary')}")
print("First Aid Steps:")
for i, step in enumerate(result.get("firstAid", []), 1):
    print(f"  {i}. {step}")
print("Pre-requisites:")
for r in result.get("prerequisites", []):
    print(f"  * {r}")
