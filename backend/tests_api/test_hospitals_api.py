import requests
import json
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_URL = "http://127.0.0.1:8000"

def test_fetch_nearby_hospitals():
    print("\n--- Testing Fetch Nearby Hospitals API ---")
    params = {
        "latitude": 19.3719,
        "longitude": 72.8220,
        "radius_km": 15,
        "emergency": False
    }
    
    response = requests.get(f"{BASE_URL}/hospitals/nearby", params=params)
    print(f"Status Code: {response.status_code}")
    hospitals = response.json()
    print(f"Total Hospitals Found: {len(hospitals)}")
    for h in hospitals[:5]:
        print(f"🏥 {h.get('name')} | Dist: {h.get('distance_km')}km | City: {h.get('city')} | Emergency: {h.get('emergency_available')}")
        
    assert response.status_code == 200
    print("✅ Hospitals Fetch test passed successfully!")

if __name__ == "__main__":
    test_fetch_nearby_hospitals()
