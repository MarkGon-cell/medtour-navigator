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

# Raw text excerpt from Red Cross Manual (Burns & Scalds / Choking)
RAW_REDCROSS_TEXT = """
RED CROSS MANUAL EXCERPT: BURNS AND SCALDS (Page 112)
1. Extinguish flames and remove the casualty from the source of heat.
2. Cool the burn immediately with cool or lukewarm gentle running water for at least 10 to 20 minutes.
3. Remove clothing and jewellery near the burnt area before the tissue begins to swell. Do not remove adhered clothing.
4. Cover the burn loosely with clean sterile dressing, clean non-fluffy cloth or clean plastic cling film.
5. Prevent hypothermia: keep the rest of the casualty warm.
6. DO NOT apply ice, iced water, butter, oils, or adhesive bandages directly on the burn.
7. DO NOT break blisters or interfere with the injured area.
"""

models = [
    "meta/llama-3.2-11b-vision-instruct",
    "poolside/laguna-xs-2.1",
    "nvidia/nemotron-3-ultra-550b-a55b"
]

prompt = (
    "You are an expert Red Cross emergency first aid instructor. "
    "Given the raw Red Cross manual excerpt below, reframe and expand the instructions into simple, clear, extensive, numbered active-voice steps for an anxious bystander. "
    "Output JSON ONLY with keys: 'condition', 'simple_summary', 'action_steps' (list of detailed steps), 'what_to_avoid' (list of dangerous mistakes)."
)

print("=" * 80)
print("EVALUATING MODEL QUALITY: REF蔭ING RED CROSS FIRST AID INSTRUCTIONS")
print("=" * 80)

for model in models:
    print(f"\n--- Model: {model} ---")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Manual Text:\n{RAW_REDCROSS_TEXT}"}
        ],
        "temperature": 0.1,
        "max_tokens": 700
    }
    
    t0 = time.time()
    try:
        resp = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=10.0
        )
        elapsed = round(time.time() - t0, 2)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            clean = content.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean)
            print(f"Speed: {elapsed}s")
            print(f"Summary: {data.get('simple_summary')}")
            print("\nAction Steps:")
            for i, step in enumerate(data.get("action_steps", []), 1):
                print(f"  {i}. {step}")
            print("\nWhat to Avoid:")
            for item in data.get("what_to_avoid", []):
                print(f"  * {item}")
        else:
            print(f"Error {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"Failed: {e}")
    
    time.sleep(2.0)
