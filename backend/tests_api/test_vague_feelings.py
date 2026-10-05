import os
import sys
import json
import requests

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

BASE_URL = "http://127.0.0.1:8000"

VAGUE_SYMPTOM_QUERIES = [
    {
        "description": "Vague Feeling 1: Cardiac / Heart Emergency",
        "user_input": "I feel a strange heavy tightness in my chest like an elephant sitting on it, feeling dizzy and cold sweat on my forehead",
        "latitude": 19.3719,
        "longitude": 72.8220
    },
    {
        "description": "Vague Feeling 2: Acute Thermal Burn",
        "user_input": "Accidentally spilled boiling water on my arm, skin is super red, burning horribly and getting small watery bubbles",
        "latitude": 19.3719,
        "longitude": 72.8220
    },
    {
        "description": "Vague Feeling 3: Severe Trauma / Bleeding",
        "user_input": "Deep cut on my leg from broken glass, bright red blood is pouring out and won't stop with a tissue",
        "latitude": 19.3719,
        "longitude": 72.8220
    }
]

print("=" * 85)
print("TESTING FULL AI FIRST AID TRIAGE WORKFLOW FROM VAGUE USER FEELINGS")
print("=" * 85)

for test_case in VAGUE_SYMPTOM_QUERIES:
    print(f"\n>>> {test_case['description']} <<<")
    print(f"User Input: \"{test_case['user_input']}\"\n")
    
    payload = {
        "symptoms": test_case["user_input"],
        "latitude": test_case["latitude"],
        "longitude": test_case["longitude"],
        "radius_km": 20.0
    }
    
    try:
        response = requests.post(f"{BASE_URL}/ai/analyze", json=payload, timeout=15)
        if response.status_code == 200:
            data = response.json()
            print(f"Specialty Diagnosed : {data.get('specialty', '').upper()}")
            print(f"Urgency Level       : {data.get('urgency')}")
            print(f"Summary             : {data.get('summary')}")
            print("\nAI-Reframed Red Cross First Aid Instructions:")
            for idx, step in enumerate(data.get("firstAid", []), 1):
                print(f"  {idx}. {step}")
            
            print("\nPre-requisites Before Hospital Arrival:")
            for req in data.get("prerequisites", []):
                print(f"  * {req}")
            
            print(f"\nTop Recommended Hospitals (50%+ Match): {len(data.get('recommendedHospitals', []))}")
            for h in data.get("recommendedHospitals", [])[:2]:
                print(f"  - {h.get('name')} ({h.get('distance_km')} km away) [Match: {h.get('ai_match_score')}%]")
                print(f"    Reason: {h.get('ai_match_reason')}")
        else:
            print(f"Failed with Status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Request Error: {e}")
    
    print("-" * 85)
