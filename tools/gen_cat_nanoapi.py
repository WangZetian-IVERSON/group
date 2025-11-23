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

endpoint = API_URL + '/v1/images/generations'
model = 'doubao-seedream-4-0-250828'
prompt = 'A high-quality photo of a cute kitten sitting on a soft blanket, natural lighting, 4k'

payload = {
    'model': model,
    'prompt': prompt,
    'size': '1024x1024'
}

print('Requesting image generation...', endpoint)
try:
    r = client.post(endpoint, headers=headers, json=payload)
    print('Status:', r.status_code)
    r.raise_for_status()
except httpx.HTTPStatusError as e:
    print('HTTP error:', e.response.status_code)
    try:
        print('Response JSON:', e.response.json())
    except Exception:
        print('Response text:', e.response.text[:1000])
    raise SystemExit(1)
except Exception as e:
    print('Request exception:')
    import traceback
    traceback.print_exc()
    raise SystemExit(1)

# parse response
try:
    data = r.json()
except Exception:
    print('Failed to parse JSON response')
    print(r.text[:2000])
    raise SystemExit(1)

# find a url in response
url = None
if isinstance(data, dict):
    # usual format: data: [{"url": "..."}, ...]
    arr = data.get('data') or []
    if isinstance(arr, list) and len(arr) > 0:
        first = arr[0]
        if isinstance(first, dict):
            url = first.get('url') or first.get('image_url')

if not url:
    print('No image URL found in response JSON. Full response:')
    print(json.dumps(data, ensure_ascii=False)[:4000])
    raise SystemExit(1)

print('Found image URL:', url)
# download image
out_path = Path(__file__).resolve().parent.parent / 'generated_cat.png'
print('Downloading image to', out_path)
try:
    # Some returned URLs may require headers or cookies; simple GET should work
    with client.stream('GET', url, timeout=60.0) as resp:
        resp.raise_for_status()
        with open(out_path, 'wb') as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)
    print('Saved image:', out_path)
except Exception:
    print('Failed to download image:')
    import traceback
    traceback.print_exc()
    raise SystemExit(1)

print('Done.')
