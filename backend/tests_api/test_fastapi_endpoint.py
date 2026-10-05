import requests

BASE_URL = "http://127.0.0.1:8000"

res = requests.post(f"{BASE_URL}/ai/analyze", json={
    "symptoms": "My uncle was eating mutton and suddenly grabbed his throat, he can't talk, can't cough, and his face is turning slightly blue.",
    "latitude": 19.3719,
    "longitude": 72.8220,
    "radius_km": 15.0
}, timeout=20)

print(f"Status: {res.status_code}")
data = res.json()
print("Specialty:", data.get("specialty"))
print("Urgency:", data.get("urgency"))
print("Summary:", data.get("summary"))
print("First Aid Steps:")
for idx, s in enumerate(data.get("firstAid", []), 1):
    print(f"  {idx}. {s}")
print(f"Recommended Hospitals ({len(data.get('recommendedHospitals', []))} found):")
for h in data.get("recommendedHospitals", [])[:2]:
    print(f"  * {h.get('name')} | Match: {h.get('ai_match_score')}% | Reason: {h.get('ai_match_reason')}")
