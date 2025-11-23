import os
import json
import sys
import httpx

API_URL = os.getenv('NANO_API_URL', 'https://nanoapi.poloai.top').rstrip('/')
API_KEY = os.getenv('NANO_API_KEY') or os.getenv('NANOAPI_KEY') or os.getenv('NANO_API_TOKEN')

if not API_KEY:
    print('Missing NANO_API_KEY in environment')
    sys.exit(2)

client = httpx.Client(timeout=120.0)
headers = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}

endpoint = API_URL + '/v1/images/generations'
payload = {
    'model': 'doubao-seedream-4-0-250828',
    'prompt': 'A small test thumbnail from a floorplan: clean colored 2D flat vector style.',
    'size': '1024x1024',
    'num_images': 1
}

print('Posting to', endpoint)
try:
    r = client.post(endpoint, headers=headers, json=payload)
    print('Status:', r.status_code)
    try:
        print(json.dumps(r.json(), ensure_ascii=False)[:2000])
    except Exception:
        print(r.text[:2000])
except Exception as e:
    print('Request failed:', e)
    sys.exit(1)
