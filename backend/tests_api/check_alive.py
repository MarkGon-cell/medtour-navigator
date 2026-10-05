import requests

try:
    res = requests.get("http://127.0.0.1:8000/health", timeout=5)
    print(f"[HEALTH CHECK] Status Code: {res.status_code}")
    print(f"Response: {res.json()}")
except Exception as e:
    print(f"[HEALTH CHECK FAILED]: {e}")
