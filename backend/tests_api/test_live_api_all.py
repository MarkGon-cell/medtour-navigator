import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

TESTS = [
    {
        "name": "TEST 1: Choking / Airway Obstruction",
        "symptoms": "My uncle was eating mutton and suddenly grabbed his throat, he can't talk, can't cough, and his face is turning slightly blue."
    },
    {
        "name": "TEST 2: Arterial Bleeding",
        "symptoms": "Stepped on a large piece of broken window glass, deep gash on the leg, bright red blood is gushing out rapidly and tissues are soaked immediately."
    },
    {
        "name": "TEST 3: Boiling Water Scald",
        "symptoms": "I accidentally spilled hot boiling tea on my forearm, the skin is bright red, burning like fire, and watery bubbles are popping up."
    }
]

print("=" * 95)
print("TESTING LIVE FASTAPI /ai/analyze ENDPOINT WITH RED-FLAG AND DEEP RETRIEVAL PIPELINE")
print("=" * 95)

for t in TESTS:
    print(f"\n>> {t['name']} <<")
    print(f"Complaint: \"{t['symptoms']}\"")
    t0 = time.time()
    try:
        res = requests.post(f"{BASE_URL}/ai/analyze", json={
            "symptoms": t["symptoms"],
            "latitude": 19.3719,
            "longitude": 72.8220,
            "radius_km": 20.0
        }, timeout=25)
        elapsed = round(time.time() - t0, 2)
        print(f"Response ({res.status_code}) in {elapsed}s:")
        if res.status_code == 200:
            data = res.json()
            print(f"  * Specialty : {data.get('specialty')}")
            print(f"  * Urgency   : {data.get('urgency')}")
            print(f"  * Summary   : {data.get('summary')}")
            print(f"  * First Aid Steps:")
            for idx, step in enumerate(data.get("firstAid", []), 1):
                print(f"     {idx}. {step}")
            print(f"  * Pre-Requisites:")
            for req in data.get("prerequisites", []):
                print(f"     [+] {req}")
            print(f"  * Recommended Hospitals (Top 2):")
            for h in data.get("recommendedHospitals", [])[:2]:
                print(f"     - {h.get('name')} | Match: {h.get('ai_match_score')}% | Reason: {h.get('ai_match_reason')}")
        else:
            print("Error:", res.text)
    except Exception as e:
        print("Request failed:", e)
