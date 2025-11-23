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
client = httpx.Client(timeout=120.0)

endpoint = API_URL + '/v1/images/generations'
model = 'doubao-seedream-4-0-250828'

# Tailored prompt: preserve floorplan materials and space layout exactly, render right-bottom bedroom
prompt = (
    "Photorealistic interior rendering of the right-bottom bedroom shown in the attached floorplan. "
    "Do NOT change the floorplan geometry, arrangement or materials: keep the medium-tone hardwood floor, the window/balcony placement, "
    "the bed position and the built-in features exactly as in the floorplan. "
    "Render a cozy modern bedroom with a double bed against the right wall, neutral light bedding, two small bedside tables, "
    "a simple wardrobe matching the existing plan, and a small rug. Natural daylight enters from the window; camera at eye-level 45-degree perspective, "
    "realistic textures, correct perspective, soft natural shadows, photorealistic, high detail (4k)."
)

payload = {
    'model': model,
    'prompt': prompt,
    'size': '1024x1024'
}

out_path = Path(__file__).resolve().parent.parent / 'bedroom_render.png'

print('Requesting bedroom render...')
try:
    r = client.post(endpoint, headers=headers, json=payload)
    print('Status:', r.status_code)
    r.raise_for_status()
except httpx.HTTPStatusError as e:
    print('HTTP error:', e.response.status_code)
    try:
        print('Response JSON:', json.dumps(e.response.json(), ensure_ascii=False, indent=2))
    except Exception:
        print('Response text:', e.response.text[:2000])
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
    arr = data.get('data') or []
    if isinstance(arr, list) and len(arr) > 0:
        first = arr[0]
        if isinstance(first, dict):
            url = first.get('url') or first.get('image_url')

if not url:
    # try find b64
    def find_b64(d):
        if isinstance(d, dict):
            for k,v in d.items():
                if k == 'b64_json' and isinstance(v, str):
                    return v
                res = find_b64(v)
                if res:
                    return res
        elif isinstance(d, list):
            for it in d:
                res = find_b64(it)
                if res:
                    return res
        return None
    b64 = find_b64(data)
    if b64:
        try:
            import base64
            with open(out_path, 'wb') as f:
                f.write(base64.b64decode(b64))
            print('Saved image (from b64) to', out_path)
            print('Done.')
            raise SystemExit(0)
        except Exception:
            print('Failed to save base64 image')
            raise SystemExit(1)

if not url:
    print('No image URL or base64 found. Full response:')
    print(json.dumps(data, ensure_ascii=False)[:4000])
    raise SystemExit(1)

print('Found image URL:', url)
# download image
print('Downloading image to', out_path)
try:
    with client.stream('GET', url, timeout=120.0) as resp:
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
