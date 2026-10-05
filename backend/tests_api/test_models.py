import os
import time
import json
import sys
from openai import OpenAI
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

load_dotenv('backend/.env')
api_key = os.getenv('NVIDIA_NIM_API_KEY')

client = OpenAI(
    base_url='https://integrate.api.nvidia.com/v1',
    api_key=api_key,
    timeout=15.0
)

candidate_models = [
    'z-ai/glm-5.3-flash',
    'nvidia/nemotron-3.5-lightning-30b-a3b',
    'meta/llama-3.1-8b-instruct',
    'meta/llama-3.1-70b-instruct',
    'meta/llama-3.3-70b-instruct',
    'mistralai/mistral-large-2407',
    'mistralai/mixtral-8x7b-instruct-v0.1',
    'deepseek-ai/deepseek-r1'
]

test_prompt = 'Patient has acute burn on hand with blisters. Return JSON: {"specialty": "emergency", "urgency": "URGENT", "firstAid": ["Cool under running water 15 min", "Do not pop blisters"]}'

print(f"=== TESTING NVIDIA NIM MODELS (API KEY: {api_key[:8]}...) ===\n")

results = []

for model in candidate_models:
    print(f"Testing {model:<40} ... ", end='', flush=True)
    t0 = time.time()
    try:
        res = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a medical first responder assistant. Return valid JSON only."},
                {"role": "user", "content": test_prompt}
            ],
            temperature=0.1,
            max_tokens=300
        )
        elapsed = round(time.time() - t0, 2)
        content = res.choices[0].message.content or ""
        sample = content.strip().replace('\n', ' ')[:90]
        print(f"SUCCESS ({elapsed}s) -> {sample}")
        results.append({"model": model, "status": "SUCCESS", "latency_s": elapsed, "sample": sample})
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        err_msg = str(e).split('\n')[0][:70]
        print(f"FAILED ({elapsed}s) -> {err_msg}")
        results.append({"model": model, "status": "FAILED", "latency_s": elapsed, "error": err_msg})
    
    time.sleep(1.8)  # Safe delay respecting 40 RPM

print("\n" + "=" * 80)
print(f"{'MODEL NAME':<42} | {'STATUS':<8} | {'LATENCY':<9} | {'OUTPUT / ERROR'}")
print("=" * 80)
for r in results:
    extra = r.get("sample") if r["status"] == "SUCCESS" else r.get("error")
    print(f"{r['model']:<42} | {r['status']:<8} | {r['latency_s']:>6.2f}s  | {extra[:45]}")
print("=" * 80)
