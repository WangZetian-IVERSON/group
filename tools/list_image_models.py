import os
import httpx
import json

API_URL = os.getenv('NANO_API_URL', 'https://nanoapi.poloai.top').rstrip('/')
API_KEY = os.getenv('NANO_API_KEY') or os.getenv('NANOAPI_KEY') or os.getenv('NANO_API_TOKEN')
if not API_KEY:
    print('No NANO_API_KEY in environment')
    raise SystemExit(1)

headers = {'Authorization': f'Bearer {API_KEY}'}
client = httpx.Client(timeout=20.0)

url = API_URL + '/v1/models'
print('Querying', url)
resp = client.get(url, headers=headers)
print('Status:', resp.status_code)
if resp.status_code != 200:
    try:
        print('Response JSON:', json.dumps(resp.json(), ensure_ascii=False, indent=2))
    except Exception:
        print('Response text:', resp.text[:2000])
    raise SystemExit(1)

data = resp.json()
models = data.get('data') or []

candidates = []
print('\nFound models:')
for m in models:
    mid = m.get('id')
    owned = m.get('owned_by')
    se = m.get('supported_endpoint_types')
    created = m.get('created')
    # heuristics for image models
    name = (mid or '').lower()
    is_image_like = False
    keywords = ['image','img','dream','seedream','doubao','stable','sd','vision','photo','render']
    for k in keywords:
        if k in name:
            is_image_like = True
            break
    # also if supported_endpoint_types contains 'openai' that may include images
    print(f"- {mid}  owned_by={owned}  supported={se}  image_like={is_image_like}")
    if is_image_like:
        candidates.append(m)

print('\nImage-like candidate models:')
for m in candidates:
    print('-', m.get('id'))

print('\nFull model list saved to workspace as tools/models_list.json')
with open('tools/models_list.json','w',encoding='utf-8') as f:
    json.dump(models,f,ensure_ascii=False,indent=2)

print('Done.')
