import requests
import json
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_URL = "http://127.0.0.1:8000"

def test_sos_dispatch():
    print("\n--- Testing Emergency SOS API ---")
    payload = {
        "latitude": 19.3719,
        "longitude": 72.8220,
        "address": "Vasai West, Palghar, Maharashtra, India",
        "pincode": "401202",
        "message": "Chest pain and shortness of breath, need ambulance immediately",
        "contact_emergency_services": True
    }
    
    response = requests.post(f"{BASE_URL}/emergency/sos", json=payload)
    print(f"Status Code: {response.status_code}")
    print("Response JSON:")
    print(json.dumps(response.json(), indent=2))
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    print("✅ Emergency SOS test passed successfully!")

if __name__ == "__main__":
    test_sos_dispatch()
