import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

scenarios = [
    {
        "name": "Case 1: Severe Bleeding Glass Cut",
        "symptoms": "Stepped on a large piece of broken window glass, deep gash on the leg, bright red blood is gushing out rapidly and tissues are soaked immediately."
    },
    {
        "name": "Case 2: Scald Burn Boiling Water",
        "symptoms": "I accidentally spilled hot boiling tea on my forearm, the skin is bright red, burning like fire, and watery bubbles are popping up."
    },
    {
        "name": "Case 3: Routine Knee Pain",
        "symptoms": "I twisted my knee yesterday while jogging, mild swelling and slight pain when walking."
    }
]

for sc in scenarios:
    print(f"\n==================================================")
    print(f">> {sc['name']} <<")
    print(f"Complaint: {sc['symptoms']}")
    res = requests.post(f"{BASE_URL}/ai/analyze", json={
        "symptoms": sc["symptoms"],
        "latitude": 19.3719,
        "longitude": 72.8220,
        "radius_km": 20.0
    }, timeout=20)
    data = res.json()
    print(f"Specialty: {data.get('specialty')} | Urgency: {data.get('urgency')}")
    print(f"Summary: {data.get('summary')}")
    print("First Aid Step 1:", (data.get("firstAid") or ["None"])[0])
    hospitals = data.get("recommendedHospitals", [])
    seen = set()
    dups = [h["id"] for h in hospitals if h["id"] in seen or seen.add(h["id"])]
    print(f"Hospitals returned: {len(hospitals)} (Duplicates: {len(dups)})")
    if hospitals:
        top = hospitals[0]
        print(f"Top Hospital: {top['name']} ({top['ai_match_score']}%) -> Reason: {top['ai_match_reason']}")
