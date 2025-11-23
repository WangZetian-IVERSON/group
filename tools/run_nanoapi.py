import os
import sys
import json
import httpx

API_URL = os.getenv('NANO_API_URL', 'https://nanoapi.poloai.top').rstrip('/')
API_KEY = os.getenv('NANO_API_KEY') or os.getenv('NANOAPI_KEY') or os.getenv('NANO_API_TOKEN')

if not API_KEY:
    print('No NANO_API_KEY found in environment. Set NANO_API_KEY or NANOAPI_KEY or NANO_API_TOKEN.')
    sys.exit(2)

headers = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json',
}

client = httpx.Client(timeout=20.0)

candidate_endpoints = [
    '/',
    '/v1/models',
    # common OpenAI-compatible text endpoints
    '/v1/chat/completions',
    '/v1/completions',
    '/v1/responses',
    # image endpoints (various providers use different paths)
    '/v1/images/generate',
    '/v1/images/generations',
    '/v1/images/edits',
    '/v1/images/variations',
    '/v1/images',
    # some proxies expose openai-compatible paths
    '/openai/images/generate',
]

print('Using API URL:', API_URL)
print('Testing endpoints with Authorization header (response bodies truncated)')

def try_post_json(url, payload):
    try:
        r = client.post(url, headers=headers, json=payload)
        return r
    except Exception:
        raise


def try_get(url):
    try:
        return client.get(url, headers=headers)
    except Exception:
        raise


def save_base64_image(b64str, filename):
    import base64
    data = base64.b64decode(b64str)
    with open(filename, 'wb') as f:
        f.write(data)


for ep in candidate_endpoints:
    url = API_URL + ep
    try:
        print('\n==', url)
        # Decide request type/payload heuristics
        if ep in ('/v1/chat/completions', '/v1/completions', '/v1/responses'):
            # try chat/responses/completions
            payload = None
            if ep == '/v1/chat/completions':
                payload = {
                    'model': 'gpt-4o-mini',
                    'messages': [{'role': 'user', 'content': 'Say hi and describe a nano banana dish.'}],
                    'max_tokens': 50,
                }
            elif ep == '/v1/completions':
                payload = {
                    'model': 'gpt-4o-mini',
                    'prompt': 'Describe a nano banana dish in a fancy restaurant.',
                    'max_tokens': 50,
                }
            else:
                payload = {
                    'model': 'gpt-4o-mini',
                    'input': 'Describe a nano banana dish in a fancy restaurant.'
                }
            r = try_post_json(url, payload)

        elif 'images' in ep or 'image' in ep:
            # try an image generation style payload
            payload = {
                'prompt': 'Create a picture of a nano banana dish in a fancy restaurant with a Gemini theme',
                'model': 'gemini-2.5-flash-image',
                'size': '1024x1024',
            }
            r = try_post_json(url, payload)
        else:
            r = try_get(url)

        print('Status:', r.status_code)
        ct = r.headers.get('content-type','')
        if 'application/json' in ct:
            data = r.json()
            print('JSON (truncated):')
            print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])
            # Check for base64 images in common places
            # OpenAI-style: data: [{b64_json: '...'}]
            if isinstance(data, dict):
                # search recursively for b64_json
                def find_b64(d):
                    results = []
                    if isinstance(d, dict):
                        for k,v in d.items():
                            if k == 'b64_json' and isinstance(v, str):
                                results.append(v)
                            else:
                                results.extend(find_b64(v))
                    elif isinstance(d, list):
                        for item in d:
                            results.extend(find_b64(item))
                    return results

                b64s = find_b64(data)
                for i,b in enumerate(b64s):
                    fname = f'generated_nanoapi_{i}.png'
                    save_base64_image(b, fname)
                    print('Saved image to', fname)

        else:
            txt = r.text
            print('Text (truncated):')
            print(txt[:2000])

    except Exception:
        print('Exception when calling', url)
        import traceback
        traceback.print_exc()

print('\nDone.')
