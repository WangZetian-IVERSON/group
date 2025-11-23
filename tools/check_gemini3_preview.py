import os
import sys
import json
import httpx
from pathlib import Path

API_URL = os.getenv('NANO_API_URL') or os.getenv('GOOGLE_GEMINI_BASE_URL') or 'https://newapi.pockgo.com'
API_URL = API_URL.rstrip('/')
API_KEY = os.getenv('NANO_API_KEY') or os.getenv('API_KEY') or os.getenv('GOOGLE_API_KEY')

if not API_KEY:
    print('Missing API key in environment (NANO_API_KEY / API_KEY / GOOGLE_API_KEY)')
    sys.exit(2)

client = httpx.Client(timeout=120.0)
headers = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}

endpoint = API_URL + '/v1/images/generations'
payload = {
    'model': 'gemini-3-pro-image-preview',
    'prompt': 'Test: tiny 1k flat colored floorplan thumbnail, abstract color blocks only.',
    'size': '1024x1024',
    'num_images': 1
}

out_path = (Path(__file__).resolve().parent / 'gemini3_preview_test.json')

print('POST', endpoint)
try:
    r = client.post(endpoint, headers=headers, json=payload)
    print('Status:', r.status_code)
    try:
        data = r.json()
        print(json.dumps(data, ensure_ascii=False)[:2000])
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        print('Saved full response to', out_path)
    except Exception:
        print('Non-JSON response:')
        print(r.text[:2000])
        out_path.write_text(r.text)
except Exception as e:
    print('Request failed:', e)
    sys.exit(1)
