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

# Remaining candidate models from the 81 available list
CANDIDATE_CHAT_MODELS = [
    "meta/llama-3.2-11b-vision-instruct",
    "meta/llama-3.2-90b-vision-instruct",
    "meta/llama-guard-4-12b",
    "ibm/granite-3.0-8b-instruct",
    "ibm/granite-3.0-3b-a800m-instruct",
    "google/gemma-3-12b-it",
    "google/gemma-3-4b-it",
    "google/gemma-4-31b-it",
    "google/gemma-2b",
    "databricks/dbrx-instruct",
    "ai21labs/jamba-1.5-large-instruct",
    "01-ai/yi-large",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "poolside/laguna-xs-2.1"
]

print(f"Testing {len(CANDIDATE_CHAT_MODELS)} chat models with 4s timeout (40 RPM limit)...\\n")

working_models = []

for model in CANDIDATE_CHAT_MODELS:
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Return the JSON: {\"status\": \"OK\"}"}
        ],
        "temperature": 0.1,
        "max_tokens": 50
    }
    t0 = time.time()
    try:
        resp = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=5.0
        )
        elapsed = round(time.time() - t0, 2)
        if resp.status_code == 200:
            out = resp.json()["choices"][0]["message"]["content"].strip().replace("\n", " ")[:60]
            print(f"[SUCCESS {elapsed:>4.2f}s] {model:<46} -> {out}")
            working_models.append((model, elapsed, out))
        else:
            print(f"[HTTP {resp.status_code} {elapsed:>4.2f}s] {model:<46} -> {resp.text[:40]}")
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        err = "Timeout (>5s)" if "timeout" in str(e).lower() else str(e)[:30]
        print(f"[FAILED {elapsed:>4.2f}s] {model:<46} -> {err}")
        
    time.sleep(1.6)

print("\n" + "=" * 80)
print("FASTEST AVAILABLE WORKING MODELS:")
print("=" * 80)
for m, s, o in sorted(working_models, key=lambda x: x[1]):
    print(f"* {m:<45} | Speed: {s:>5.2f}s | Output: {o}")
