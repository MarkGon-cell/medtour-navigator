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

# Top models chosen from your 81 available models
MODELS_TO_BENCHMARK = [
    ("writer/palmyra-med-70b", "Specialized Medical LLM (70B)"),
    ("z-ai/glm-5.3-flash", "High-Speed Flash Model"),
    ("deepseek-ai/deepseek-v4.1-flash", "DeepSeek Flash Triage"),
    ("nvidia/nemotron-3.5-lightning-30b-a3b", "NVIDIA Nemotron Lightning 30B"),
    ("nvidia/llama-3.1-nemotron-70b-instruct", "NVIDIA Nemotron 70B Instruct"),
    ("mistralai/mistral-large-2-instruct", "Mistral Large 2 (Flagship)"),
    ("mistralai/mistral-7b-instruct-v0.3", "Mistral 7B Fast"),
    ("google/gemma-3-12b-it", "Google Gemma 3 12B"),
]

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

test_payload_template = {
    "messages": [
        {
            "role": "system",
            "content": "You are a medical triage assistant. Analyze symptoms and output JSON only with keys: specialty, urgency, firstAid (list of steps), summary."
        },
        {
            "role": "user",
            "content": "Patient has severe acute chest pain radiating to left arm and sweating."
        }
    ],
    "temperature": 0.1,
    "max_tokens": 400
}

print(f"=== BENCHMARKING TOP CANDIDATE MODELS (Rate Limit: 40 RPM) ===\n")
results = []

for model_id, desc in MODELS_TO_BENCHMARK:
    print(f"Testing {model_id} ({desc})...", flush=True)
    payload = dict(test_payload_template)
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
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            # Validate JSON
            is_json = False
            try:
                # clean fences
                clean = content.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(clean)
                is_json = "specialty" in parsed or "firstAid" in parsed
            except Exception:
                pass
            
            print(f"  [SUCCESS] Latency: {elapsed}s | Valid JSON: {is_json}")
            results.append({
                "model": model_id,
                "desc": desc,
                "status": "PASS",
                "latency": f"{elapsed}s",
                "json_valid": "YES" if is_json else "NO",
                "sample": content.replace("\n", " ")[:85]
            })
        else:
            print(f"  [ERROR] Status {resp.status_code}: {resp.text[:80]}")
            results.append({
                "model": model_id,
                "desc": desc,
                "status": f"HTTP {resp.status_code}",
                "latency": f"{elapsed}s",
                "json_valid": "NO",
                "sample": resp.text[:80]
            })
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        print(f"  [FAILED] {str(e)[:70]}")
        results.append({
            "model": model_id,
            "desc": desc,
            "status": "TIMEOUT/ERROR",
            "latency": f"{elapsed}s",
            "json_valid": "NO",
            "sample": str(e)[:70]
        })
        
    time.sleep(2.0)  # Sleep 2s to strictly obey 40 RPM limit

print("\n" + "=" * 90)
print(f"{'MODEL ID':<42} | {'STATUS':<10} | {'SPEED':<8} | {'JSON':<5} | {'DESCRIPTION'}")
print("=" * 90)
for r in results:
    print(f"{r['model']:<42} | {r['status']:<10} | {r['latency']:<8} | {r['json_valid']:<5} | {r['desc']}")
print("=" * 90)
