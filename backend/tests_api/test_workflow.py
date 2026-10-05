import requests
import json
import time
import sys

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

BASE_URL = "http://127.0.0.1:8000"

def test_full_workflow():
    print("=" * 60, flush=True)
    print(">>> RUNNING END-TO-END MEDTOUR WORKFLOW TEST <<<", flush=True)
    print("=" * 60, flush=True)
    
    # 1. Health check
    print("\n[Step 1] Check API Root Health", flush=True)
    res1 = requests.get(f"{BASE_URL}/", timeout=10)
    assert res1.status_code == 200, f"Expected 200, got {res1.status_code}: {res1.text}"
    print(f" [OK] Root API responded: {res1.json().get('message')}", flush=True)
    
    # 2. Nearby hospitals lookup
    print("\n[Step 2] Fetch Nearby Hospitals for GPS (19.3719, 72.8220)", flush=True)
    res2 = requests.get(f"{BASE_URL}/hospitals/nearby?latitude=19.3719&longitude=72.8220&radius_km=15", timeout=15)
    assert res2.status_code == 200, f"Expected 200, got {res2.status_code}: {res2.text}"
    hospitals = res2.json()
    print(f" [OK] Found {len(hospitals)} nearby hospitals in radius", flush=True)
    
    # 3. AI Triage / NVIDIA NIM Analysis
    print("\n[Step 3] Trigger AI Symptoms Triage", flush=True)
    res3 = requests.post(f"{BASE_URL}/ai/analyze", json={
        "symptoms": "High fever, shivering, body pain and cough for 3 days",
        "latitude": 19.3719,
        "longitude": 72.8220,
        "radius_km": 20
    }, timeout=35)
    assert res3.status_code == 200, f"Expected 200, got {res3.status_code}: {res3.text}"
    ai_data = res3.json()
    print(f" [OK] Specialty Identified: {ai_data.get('specialty')}", flush=True)
    print(f" [OK] First Aid Guidance Received: {len(ai_data.get('firstAid', []))} items", flush=True)
    
    # 4. Emergency SOS trigger
    print("\n[Step 4] Dispatch Emergency SOS Trigger", flush=True)
    res4 = requests.post(f"{BASE_URL}/emergency/sos", json={
        "latitude": 19.3719,
        "longitude": 72.8220,
        "address": "Vasai Road West, Mumbai Suburban, Maharashtra",
        "pincode": "401202",
        "message": "Critical patient needs ambulance dispatch immediately",
        "contact_emergency_services": True
    }, timeout=10)
    assert res4.status_code == 200, f"Expected 200, got {res4.status_code}: {res4.text}"
    sos_data = res4.json()
    print(f" [OK] SOS Status: {sos_data.get('status')}", flush=True)
    print(f" [OK] Google Maps: {sos_data.get('location', {}).get('google_maps')}", flush=True)
    print(f" [OK] Log File Written: {sos_data.get('log_path')}", flush=True)
    
    print("\n" + "=" * 60, flush=True)
    print(">>> ALL WORKFLOW STEPS PASSED SUCCESSFULLY! <<<", flush=True)
    print("=" * 60, flush=True)

if __name__ == "__main__":
    test_full_workflow()
