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

# The working models in speed-ordered chain (excluding safety/parse filters)
SPEED_ORDERED_CHAIN = [
    ("meta/llama-3.2-11b-vision-instruct", "Llama 3.2 11B (Fastest: ~0.28s - 2.5s)"),
    ("poolside/laguna-xs-2.1", "Poolside Laguna XS (Fast: ~2.09s)"),
    ("nvidia/nemotron-3-ultra-550b-a55b", "Nemotron Ultra 550B (Deep Reasoning: ~5.5s)")
]

VAGUE_SYMPTOM_TESTS = [
    {
        "title": "Vague Description 1: Heart Issue",
        "input": "I feel a strange heavy tightness in my chest like an elephant sitting on it, feeling dizzy and cold sweat on my forehead."
    },
    {
        "title": "Vague Description 2: Burn Trauma",
        "input": "Accidentally spilled boiling water on my arm, skin is super red, burning horribly and getting small watery bubbles."
    },
    {
        "title": "Vague Description 3: Trauma / Deep Laceration",
        "input": "Deep cut on my leg from broken glass, bright red blood is pouring out and won't stop with a tissue."
    }
]

system_prompt = (
    "You are an expert Red Cross emergency medical first aid instructor. "
    "Given a user's vague description of physical symptoms or injuries, infer the emergency condition, "
    "and reframe the official Red Cross manual instructions into simple, actionable, step-by-step guidance "
    "for an anxious bystander. Output JSON ONLY with keys: 'condition', 'urgency' ('EMERGENCY'|'URGENT'|'ROUTINE'), "
    "'specialty', 'summary', 'firstAid' (list of active-voice steps), 'prerequisites' (list of pre-hospital requirements)."
)

print("=" * 85)
print("TESTING NVIDIA NIM MODELS WITH VAGUE USER DESCRIPTIONS")
print("Chain: 1. meta/llama-3.2-11b  -> 2. poolside/laguna-xs-2.1  -> 3. nvidia/nemotron-3-ultra-550b")
print("Timeout per model: 8s max | Rate limit safe")
print("=" * 85)

for test in VAGUE_SYMPTOM_TESTS:
    print(f"\n=================================================================================")
    print(f">> {test['title']} <<")
    print(f"User Input: \"{test['input']}\"")
    print("=================================================================================")
    
    for model_id, model_name in SPEED_ORDERED_CHAIN:
        print(f"\n--- Model: {model_name} ---")
        t0 = time.time()
        try:
            payload = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"User complaint: {test['input']}"}
                ],
                "temperature": 0.1,
                "max_tokens": 600
            }
            resp = requests.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=8.0
            )
            elapsed = round(time.time() - t0, 2)
            if resp.status_code == 200:
                raw_text = resp.json()["choices"][0]["message"]["content"]
                clean_text = raw_text.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(clean_text)
                
                print(f"[SUCCESS] Latency: {elapsed}s | Inferred Condition: {parsed.get('condition', parsed.get('specialty'))} | Urgency: {parsed.get('urgency')}")
                print(f"Summary: {parsed.get('summary')}")
                print("First Aid Action Steps:")
                for idx, step in enumerate(parsed.get('firstAid', []), 1):
                    print(f"   {idx}. {step}")
                print("Pre-requisites:")
                for item in parsed.get('prerequisites', []):
                    print(f"   * {item}")
            else:
                print(f"[HTTP {resp.status_code}] Failed ({elapsed}s): {resp.text[:80]}")
        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            print(f"[FAILED] ({elapsed}s): {str(e)[:60]}")
            
        time.sleep(1.6) # Obey 40 RPM rate limit
