import os
import sys
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

print(f"Fetching available models from NVIDIA NIM using API Key ({api_key[:8]}...)\n")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Accept": "application/json"
}

try:
    response = requests.get("https://integrate.api.nvidia.com/v1/models", headers=headers, timeout=15)
    if response.status_code == 200:
        data = response.json()
        models = data.get("data", [])
        print(f"Total Models Available on your API Key: {len(models)}\n")
        
        # Categorize models
        chat_models = [m["id"] for m in models if "id" in m]
        
        print("=" * 80)
        print("TOP AVAILABLE CHAT / REASONING MODELS ON NVIDIA NIM:")
        print("=" * 80)
        for idx, m_id in enumerate(sorted(chat_models), 1):
            print(f"{idx:3d}. {m_id}")
    else:
        print(f"Error {response.status_code}: {response.text}")
except Exception as e:
    print(f"Failed to fetch models: {e}")
