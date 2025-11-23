import os
import json
import httpx
import sys
from pathlib import Path

API_URL = os.getenv('NANO_API_URL', 'https://nanoapi.poloai.top').rstrip('/')
API_KEY = os.getenv('NANO_API_KEY') or os.getenv('NANOAPI_KEY') or os.getenv('NANO_API_TOKEN')
if not API_KEY:
    print('No NANO_API_KEY in environment')
    sys.exit(1)

headers = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}
client = httpx.Client(timeout=60.0)

model = 'nano-banana'
endpoint = API_URL + '/v1/images/generations'
prompt = 'Test image: a simple yellow banana on a white background'
payload = {'model': model, 'prompt': prompt, 'size': '512x512'}

print('Testing model:', model)
print('Endpoint:', endpoint)
print('Payload:', payload)
try:
    r = client.post(endpoint, headers=headers, json=payload)
    print('Status:', r.status_code)
    try:
        print('JSON response (truncated):', json.dumps(r.json(), ensure_ascii=False)[:2000])
    except Exception:
        print('Text response (truncated):', r.text[:2000])
    # If image URL present, print and optionally download
    try:
        data = r.json()
        arr = data.get('data') or []
        if arr and isinstance(arr, list):
            first = arr[0]
            if isinstance(first, dict):
                url = first.get('url') or first.get('image_url')
                if url:
                    print('Found image URL:', url)
                    out = Path(__file__).resolve().parent.parent / 'test_nano_banana.png'
                    with client.stream('GET', url) as resp:
                        resp.raise_for_status()
                        with open(out, 'wb') as f:
                            for chunk in resp.iter_bytes():
                                f.write(chunk)
                    print('Saved to', out)
    except Exception:
        pass
except Exception as e:
    print('Request failed:')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('Done')
