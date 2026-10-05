import requests
import time

BASE_URL = "http://127.0.0.1:8000"

payload = {
    "symptoms": "My uncle was eating mutton and suddenly grabbed his throat, he can't talk, can't cough, and his face is turning slightly blue.",
    "latitude": 19.3719,
    "longitude": 72.8220,
    "radius_km": 20.0
}

print("POSTing to live FastAPI endpoint /ai/analyze...")
t0 = time.time()
resp = requests.post(f"{BASE_URL}/ai/analyze", json=payload, timeout=20)
elapsed = round(time.time() - t0, 2)

print(f"Status Code: {resp.status_code} (took {elapsed}s)")
data = resp.json()
print("Specialty:", data.get("specialty"))
print("Urgency:", data.get("urgency"))
print("Summary:", data.get("summary"))
print("First Aid Steps:")
for i, s in enumerate(data.get("firstAid", []), 1):
    print(f"  {i}. {s}")
print("Prerequisites:")
for p in data.get("prerequisites", []):
    print(f"  [+] {p}")
print(f"Hospital recommendations ({len(data.get('recommendedHospitals', []))} found):")
for h in data.get("recommendedHospitals", [])[:2]:
    print(f"  * {h.get('name')} | {h.get('distance_km')} km | Match: {h.get('ai_match_score')}%")
    print(f"    Reason: {h.get('ai_match_reason')}")
