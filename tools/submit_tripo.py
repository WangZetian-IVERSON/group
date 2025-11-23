import os
import sys
import asyncio
import time
from pathlib import Path
import json

BASE = Path(__file__).resolve().parent
IN_IMG = BASE / 'submit_image_for_tripo.png'
OUT_DIR = BASE / 'tripo_output'
OUT_DIR.mkdir(parents=True, exist_ok=True)
STATUS = BASE / 'tripo_status.txt'
LAST_URL = BASE / 'last_model_url.txt'

API_KEY = os.environ.get('TRIPO_API_KEY') or os.environ.get('TRIPO_KEY')

async def submit_via_sdk(image_path, key):
    try:
        from tripo3d import TripoClient, TaskStatus
        try:
            client = TripoClient(key)
        except Exception:
            # try bypass impl
            from tripo3d.client_impl import ClientImpl
            client = TripoClient.__new__(TripoClient)
            client.api_key = key
            client.BASE_URL = getattr(TripoClient, 'BASE_URL', 'https://api.tripo3d.ai/v2/openapi')
            client._impl = ClientImpl(key, client.BASE_URL)

        STATUS.write_text('Tripo: submitting via SDK', encoding='utf-8')
        # prefer image_to_model
        if hasattr(client, 'image_to_model'):
            task_id = await client.image_to_model(image=str(image_path), prompt='生成一个室内空间的3d模型')
        else:
            # fallback to text_to_model with image (some SDKs accept image param here)
            task_id = await client.text_to_model(prompt='生成一个室内空间的3d模型', image=str(image_path))

        STATUS.write_text('Tripo: submitted, waiting for task', encoding='utf-8')
        task = await client.wait_for_task(task_id, verbose=True)
        if getattr(task, 'status', None) == TaskStatus.SUCCESS:
            files = await client.download_task_models(task, str(OUT_DIR))
            if files:
                fn = Path(files[0]).name
                url = f'http://127.0.0.1:8000/{fn}'
                LAST_URL.write_text(url, encoding='utf-8')
                STATUS.write_text('Tripo: success. Model ready at ' + url, encoding='utf-8')
                return True
            else:
                STATUS.write_text('Tripo: success but no files returned', encoding='utf-8')
                return False
        else:
            STATUS.write_text('Tripo: task ended with status: ' + str(getattr(task, 'status', 'unknown')))
            return False
    except Exception as e:
        STATUS.write_text('Tripo SDK error: ' + str(e), encoding='utf-8')
        return False


async def submit_via_http(image_path, key):
    import httpx
    try:
        STATUS.write_text('Tripo: submitting via HTTP fallback', encoding='utf-8')
        url = 'https://api.tripo3d.ai/v2/openapi/task'
        headers = {'Authorization': f'Bearer {key}'}
        files = {'image': ('submit.png', image_path.read_bytes(), 'image/png')}
        form = {'type': 'image_to_model', 'prompt': '生成一个室内空间的3d模型'}
        async with httpx.AsyncClient(timeout=300.0) as ac:
            r = await ac.post(url, headers=headers, data=form, files=files)
            try:
                STATUS.write_text(f'Tripo HTTP submit: {r.status_code}', encoding='utf-8')
            except Exception:
                pass
            if r.status_code not in (200,201):
                TEXT = r.text if r is not None else ''
                (BASE / f'tripo_http_debug_{int(time.time())}.json').write_text(json.dumps({'status': r.status_code, 'text': TEXT}, ensure_ascii=False), encoding='utf-8')
                return False
            jr = r.json()
            task_id = jr.get('id') or jr.get('task_id') or jr.get('data', {}).get('id')
            if not task_id:
                STATUS.write_text('Tripo HTTP: no task id returned', encoding='utf-8')
                return False
            STATUS.write_text('Tripo: task submitted (http), polling', encoding='utf-8')
            for _ in range(240):
                await asyncio.sleep(5)
                rr = await ac.get(f'https://api.tripo3d.ai/v2/openapi/task/{task_id}', headers=headers)
                try:
                    js = rr.json()
                except Exception:
                    js = {}
                status = js.get('status') or js.get('data', {}).get('status')
                if status and status.lower() in ('success','succeed'):
                    files_arr = js.get('data', {}).get('files') or js.get('files') or []
                    if files_arr:
                        first = files_arr[0]
                        download_url = first.get('url') or first.get('download_url') or first.get('uri')
                        if download_url:
                            rr2 = await ac.get(download_url)
                            if rr2.status_code == 200:
                                fn = OUT_DIR / Path(download_url).name
                                fn.write_bytes(rr2.content)
                                url2 = f'http://127.0.0.1:8000/{fn.name}'
                                LAST_URL.write_text(url2, encoding='utf-8')
                                STATUS.write_text('Tripo: success. Model ready at ' + url2, encoding='utf-8')
                                return True
                    STATUS.write_text('Tripo: task success but no files in response', encoding='utf-8')
                    return False
                if status and status.lower() in ('failed','error'):
                    STATUS.write_text('Tripo: task failed: ' + str(js), encoding='utf-8')
                    return False
            STATUS.write_text('Tripo: polling timeout', encoding='utf-8')
            return False
    except Exception as e:
        (BASE / f'tripo_http_exception_{int(time.time())}.json').write_text(json.dumps({'error': str(e)}, ensure_ascii=False), encoding='utf-8')
        STATUS.write_text('Tripo HTTP exception: ' + str(e), encoding='utf-8')
        return False


async def main():
    if not IN_IMG.exists():
        print('No input image found at', IN_IMG)
        print('Please place the image at this path or change the script to point to your image.')
        return
    if not API_KEY:
        print('No TRIPO_API_KEY found in environment or .env. Set TRIPO_API_KEY and retry.')
        return
    print('Submitting', IN_IMG)
    ok = await submit_via_sdk(IN_IMG, API_KEY)
    if not ok:
        print('SDK path failed, trying HTTP fallback')
        ok2 = await submit_via_http(IN_IMG, API_KEY)
        if not ok2:
            print('Both SDK and HTTP fallback failed. Check tools/tripo_status.txt and debug files.')
        else:
            print('HTTP fallback succeeded (see tools/tripo_status.txt)')
    else:
        print('SDK submission succeeded (see tools/tripo_status.txt)')

if __name__ == '__main__':
    asyncio.run(main())
