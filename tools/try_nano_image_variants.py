import os
import json
import base64
import httpx

API_URL = os.getenv('NANO_API_URL', 'https://nanoapi.poloai.top').rstrip('/')
API_KEY = os.getenv('NANO_API_KEY') or os.getenv('NANOAPI_KEY') or os.getenv('NANO_API_TOKEN')

if not API_KEY:
    print('No NANO_API_KEY in environment')
    raise SystemExit(1)

headers = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}
client = httpx.Client(timeout=60.0)

models = [
    'gemini-2.5-flash-image',
    'gemini-2.5-flash-image-preview',
    'doubao-seedream-4-0-250828',
]

prompt = 'Create a picture of a nano banana dish in a fancy restaurant with a Gemini theme'

payload_variants = [
    lambda m: {'model': m, 'prompt': prompt, 'size': '1024x1024'},
    lambda m: {'model': m, 'text_prompts': [{'text': prompt}], 'size': '1024x1024'},
    lambda m: {'model': m, 'input': prompt},
    lambda m: {'model': m, 'prompts': prompt},
    lambda m: {'model': m, 'prompt': [{'text': prompt}]},
]

endpoint = API_URL + '/v1/images/generations'

def save_b64(b64, fname):
    try:
        data = base64.b64decode(b64)
        with open(fname, 'wb') as f:
            f.write(data)
        print('Saved', fname)
    except Exception as e:
        print('Failed to save', fname, e)

print('Testing image generation endpoint:', endpoint)
for model in models:
    for i, pv in enumerate(payload_variants):
        payload = pv(model)
        print('\n== Trying model:', model, 'variant', i)
        print('Payload:', json.dumps(payload, ensure_ascii=False))
        try:
            r = client.post(endpoint, headers=headers, json=payload)
            print('Status:', r.status_code)
            ct = r.headers.get('content-type','')
            if 'application/json' in ct:
                data = r.json()
                print('Response JSON (truncated):', json.dumps(data, ensure_ascii=False)[:2000])
                # Try to find b64_json or url
                def find_b64_urls(obj):
                    b64s = []
                    urls = []
                    if isinstance(obj, dict):
                        for k,v in obj.items():
                            if k == 'b64_json' and isinstance(v, str):
                                b64s.append(v)
                            if k in ('url','image_url') and isinstance(v, str):
                                urls.append(v)
                            bs, us = find_b64_urls(v)
                            b64s.extend(bs); urls.extend(us)
                    elif isinstance(obj, list):
                        for it in obj:
                            bs, us = find_b64_urls(it)
                            b64s.extend(bs); urls.extend(us)
                    return b64s, urls

                b64s, urls = find_b64_urls(data)
                if b64s:
                    for idx, b in enumerate(b64s):
                        save_b64(b, f'generated_nano_{model}_{i}_{idx}.png')
                if urls:
                    for idx, u in enumerate(urls):
                        print('Found URL:', u)
            else:
                print('Text response (truncated):', r.text[:1000])
        except Exception as e:
            print('Exception for model', model, 'variant', i, e)

print('\nDone testing image variants.')
