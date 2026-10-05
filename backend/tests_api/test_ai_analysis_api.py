import requests
import json
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_URL = "http://127.0.0.1:8000"

def test_ai_symptoms_analysis():
    print("\n--- Testing AI Symptoms Analysis & NVIDIA NIM Triage ---")
    payload = {
        "symptoms": "Severe continuous chest pain, sweating, radiation to left arm and dizziness",
        "latitude": 19.3719,
        "longitude": 72.8220,
        "radius_km": 25.0
    }
    
    response = requests.post(f"{BASE_URL}/ai/analyze", json=payload)
    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Detected Specialty: {data.get('specialty')}")
    print(f"Urgency Level: {data.get('urgency')}")
    print(f"First Aid Steps ({len(data.get('firstAid', []))} steps):")
    for step in data.get("firstAid", []):
        print(f"  - {step}")
    print(f"Matched Hospitals: {len(data.get('recommendedHospitals', []))}")
    for h in data.get("recommendedHospitals", [])[:3]:
        print(f"  * {h.get('name')} ({h.get('distance_km')} km away) [Emergency: {h.get('emergency_available')}]")
        
    assert response.status_code == 200
    assert "firstAid" in data
    print("✅ AI Analysis test passed successfully!")

if __name__ == "__main__":
    test_ai_symptoms_analysis()
