import os
import json
import sys
from pathlib import Path

import httpx

API_URL = os.getenv('NANO_API_URL', 'https://nanoapi.poloai.top').rstrip('/')
API_KEY = os.getenv('NANO_API_KEY') or os.getenv('NANOAPI_KEY') or os.getenv('NANO_API_TOKEN')

if not API_KEY:
    print('No API key found in environment (NANO_API_KEY).')
    sys.exit(2)

out_file = Path(__file__).resolve().parent / 'models_test_results.json'

client = httpx.Client(timeout=60.0)
headers = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}

def fetch_models():
    url = API_URL + '/v1/models'
    r = client.get(url, headers=headers)
    r.raise_for_status()
    return r.json()

def test_image_model(model_id):
    endpoint = API_URL + '/v1/images/generations'
    payload = {
        'model': model_id,
        'prompt': 'A small test thumbnail (abstract color swirls).',
        'size': '256x256',
        'num_images': 1
    }
    try:
        r = client.post(endpoint, headers=headers, json=payload)
    except Exception as e:
        return {'ok': False, 'error': str(e)}
    result = {'status_code': r.status_code}
    try:
        data = r.json()
        result['response'] = data
        # find if there's image url or base64
        url = None
        if isinstance(data, dict):
            arr = data.get('data') or []
            if isinstance(arr, list) and len(arr) > 0 and isinstance(arr[0], dict):
                url = arr[0].get('url') or arr[0].get('image_url')
            # find b64
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
            result['has_url'] = bool(url)
            result['has_b64'] = bool(b64)
            result['ok'] = (r.status_code == 200) and (bool(url) or bool(b64))
        else:
            result['ok'] = (r.status_code == 200)
    except Exception:
        result['ok'] = (r.status_code == 200)
        result['raw_text'] = r.text[:2000]
    return result

def main():
    print('Fetching models from', API_URL)
    models_json = fetch_models()
    # Save a copy
    Path(__file__).resolve().parent.joinpath('models_list_from_test.json').write_text(json.dumps(models_json, ensure_ascii=False, indent=2))

    models = []
    if isinstance(models_json, dict) and 'data' in models_json:
        models = models_json['data']
    elif isinstance(models_json, list):
        models = models_json

    results = {}
    for m in models:
        mid = m.get('id') if isinstance(m, dict) else str(m)
        # some instances use 'supported_endpoint_types' to indicate capabilities
        supported = m.get('supported', []) if isinstance(m, dict) else []
        supported = supported or m.get('supported_endpoint_types', [])
        # infer image capability: explicit flag or supported endpoint or name contains 'image' or known models
        image_like = m.get('image_like', False) if isinstance(m, dict) else False
        if not image_like:
            if any(x in ('openai', 'image') for x in supported) or ('image' in (mid or '')) or 'seedream' in (mid or ''):
                image_like = True
        results[mid] = {'image_like': image_like, 'supported': supported}
        if image_like:
            print('Testing image generation for', mid)
            try:
                res = test_image_model(mid)
            except Exception as e:
                res = {'ok': False, 'error': str(e)}
            results[mid]['test'] = res

    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print('Saved results to', out_file)
    # Print concise summary
    for k,v in results.items():
        line = f"{k}: image_like={v.get('image_like')}"
        t = v.get('test')
        if t:
            line += f", ok={t.get('ok')} status={t.get('status_code')}"
        print(line)


if __name__ == '__main__':
    main()
