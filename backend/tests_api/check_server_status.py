import requests

try:
    res = requests.get("http://127.0.0.1:8000/health", timeout=3)
    print(f"Server Health Check: {res.status_code} {res.json()}")
except Exception as e:
    print(f"Health Check Failed: {e}")
