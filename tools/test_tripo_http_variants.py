import os, json, asyncio
import httpx
from pathlib import Path
BASE = Path(__file__).parent
img = BASE / 'submit_image_for_tripo.png'
if not img.exists():
    print('Missing input image', img)
    raise SystemExit(1)
key = os.environ.get('TRIPO_API_KEY') or os.environ.get('TRIPO_KEY')
if not key:
    print('No TRIPO_API_KEY in env')
    raise SystemExit(1)
print('Using TRIPO key present, testing variants...')
file_keys = ['image', 'file', 'image_file', 'upload']
form_variants = [
    {'type': 'image_to_model', 'prompt': '将这张3d的室内空间生成逼真材质的3d模型'},
    {'task_type': 'image_to_model', 'prompt': '将这张3d的室内空间生成逼真材质的3d模型'},
    {'type': 'image_to_model', 'inputs': json.dumps({'prompt': '将这张3d的室内空间生成逼真材质的3d模型'})},
    {'payload': json.dumps({'type': 'image_to_model', 'prompt': '将这张3d的室内空间生成逼真材质的3d模型'})},
]
url = 'https://api.tripo3d.ai/v2/openapi/task'
async def run():
    data = img.read_bytes()
    headers = {'Authorization': f'Bearer {key}'}
    async with httpx.AsyncClient(timeout=60.0) as ac:
        for fk in file_keys:
            for form in form_variants:
                files = {fk: ('hi_fi.png', data, 'image/png')}
                print('Trying file_key=',fk,'form=',form)
                try:
                    r = await ac.post(url, headers=headers, data=form, files=files)
                except Exception as e:
                    print('Request exception', e)
                    continue
                print('Status', r.status_code)
                try:
                    jt = r.json()
                    print('JSON:', json.dumps(jt, ensure_ascii=False))
                except Exception:
                    print('Text:', r.text[:500])
                if r.status_code in (200,201):
                    print('Success variant', fk, form)
                    return
        print('No variant succeeded')
asyncio.run(run())
