import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

payload = {
    "symptoms": "My uncle was eating mutton and suddenly grabbed his throat, he can't talk, can't cough, and his face is turning slightly blue.",
    "latitude": 19.3719,
    "longitude": 72.8220,
    "radius_km": 20.0
}

print("Testing POST /ai/analyze with choking narrative...")
t0 = time.time()
res = requests.post(f"{BASE_URL}/ai/analyze", json=payload, timeout=20)
elapsed = round(time.time() - t0, 2)

print(f"Status: {res.status_code} ({elapsed}s)")
if res.status_code == 200:
    data = res.json()
    print("\n--- TRIAGE OUTPUT ---")
    print("Specialty:", data.get("specialty"))
    print("Urgency:", data.get("urgency"))
    print("Summary:", data.get("summary"))
    
    print("\n--- FIRST AID (Should be Heimlich / Back Blows, NOT Fever/Paracetamol) ---")
    for i, step in enumerate(data.get("firstAid", []), 1):
        print(f"  {i}. {step}")
        
    print("\n--- PRE-REQUISITES ---")
    for p in data.get("prerequisites", []):
        print(f"  [+] {p}")

    hospitals = data.get("recommendedHospitals", [])
    print(f"\n--- RECOMMENDED HOSPITALS ({len(hospitals)} total) ---")
    
    # Check duplicates
    seen_ids = set()
    duplicates = []
    for h in hospitals:
        hid = h.get("id")
        if hid in seen_ids:
            duplicates.append(h.get("name"))
        seen_ids.add(hid)
        
    print(f"Duplicate Hospital IDs Found: {len(duplicates)} ({duplicates})")
    
    for h in hospitals[:3]:
        print(f"\n* Hospital: {h.get('name')} (ID: {h.get('id')}) | {h.get('distance_km')} km")
        print(f"  Match Score: {h.get('ai_match_score')}%")
        print(f"  Match Reason: {h.get('ai_match_reason')}")
        print(f"  Specialties: {h.get('specialties')}")
else:
    print("Error:", res.text)
