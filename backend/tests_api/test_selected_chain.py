import os
import sys
import time
import json
import requests
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

load_dotenv('backend/.env')
api_key = os.getenv('NVIDIA_NIM_API_KEY')

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# The user-selected models ordered by increasing latency (fastest first)
SELECTED_MODELS = [
    "meta/llama-3.2-11b-vision-instruct",           # ~0.28s
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", # ~1.70s
    "poolside/laguna-xs-2.1",                        # ~2.09s
    "meta/llama-3.2-90b-vision-instruct",           # ~2.84s
    "nvidia/nemotron-3-ultra-550b-a55b"              # ~7.44s
]

test_payload = {
    "messages": [
        {
            "role": "system",
            "content": "You are an expert emergency medical responder. Analyze symptoms and output JSON ONLY with keys: specialty, urgency, firstAid (list of steps), summary."
        },
        {
            "role": "user",
            "content": "Patient has severe chest pain, breathlessness, and left arm numbness."
        }
    ],
    "temperature": 0.1,
    "max_tokens": 400
}

print(f"=== TESTING SELECTED MODELS IN SPEED-ORDERED CHAIN ===\n")

for model in SELECTED_MODELS:
    payload = dict(test_payload)
    payload["model"] = model
    t0 = time.time()
    try:
        resp = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=8.0
        )
        elapsed = round(time.time() - t0, 2)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            print(f"[OK] {model:<45} | {elapsed:>5.2f}s | Output snippet: {content.replace(chr(10), ' ')[:90]}")
        else:
            print(f"[ERR {resp.status_code}] {model:<45} | {elapsed:>5.2f}s | {resp.text[:80]}")
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        print(f"[TIMEOUT/FAIL] {model:<45} | {elapsed:>5.2f}s | {str(e)[:50]}")
    
    time.sleep(1.6)
