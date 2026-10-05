import os
import sys
import time
import json
import requests
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

load_dotenv('backend/.env')
api_key = os.getenv('NVIDIA_NIM_API_KEY')

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# 1. Fetch live list of all models
print(f"Fetching all models from NVIDIA NIM...")
models_resp = requests.get("https://integrate.api.nvidia.com/v1/models", headers=headers, timeout=100)
if models_resp.status_code != 200:
    print(f"Failed to fetch models: {models_resp.status_code}")
    sys.exit(1)

all_models = [m["id"] for m in models_resp.json().get("data", [])]
print(f"Total models to test: {len(all_models)}")
print("Running test across ALL models (Rate Limit: 40 RPM, 1.6s delay between calls)...\n")

test_payload = {
    "messages": [
        {"role": "user", "content": "Respond with the single word: OK"}
    ],
    "temperature": 0.1,
    "max_tokens": 15
}

results = []

for idx, model_id in enumerate(all_models, 1):
    payload = dict(test_payload)
    payload["model"] = model_id
    
    t0 = time.time()
    try:
        resp = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=12.0
        )
        elapsed = round(time.time() - t0, 2)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"].strip().replace("\n", " ")[:60]
            print(f"[{idx:2d}/{len(all_models)}] [SUCCESS] {model_id:<45} | {elapsed}s | Output: {content}")
            results.append({"model": model_id, "status": "WORKING (200 OK)", "latency": elapsed, "output": content})
        else:
            err = resp.json().get("title", resp.text[:40]) if resp.text.startswith("{") else resp.text[:40]
            print(f"[{idx:2d}/{len(all_models)}] [HTTP {resp.status_code}] {model_id:<45} | {elapsed}s | {err}")
            results.append({"model": model_id, "status": f"HTTP {resp.status_code}", "latency": elapsed, "output": err})
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        err_str = "Timeout (>8s)" if "timeout" in str(e).lower() else str(e)[:35]
        print(f"[{idx:2d}/{len(all_models)}] [ERROR]   {model_id:<45} | {elapsed}s | {err_str}")
        results.append({"model": model_id, "status": "TIMEOUT/ERROR", "latency": elapsed, "output": err_str})
    
    time.sleep(1.6)  # 1.6s delay = ~37.5 RPM (under 40 RPM limit)

# Save results to JSON file
out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs", "nvidia_all_models_tested.json"))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

working = [r for r in results if "200" in r["status"]]
print("\n" + "=" * 90)
print(f"TOTAL WORKING MODELS: {len(working)} / {len(all_models)}")
print("=" * 90)
for w in working:
    print(f"* {w['model']:<45} | Speed: {w['latency']}s | Output: {w['output']}")
print("=" * 90)
print(f"Full report saved to: {out_path}")
