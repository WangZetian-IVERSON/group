import os
import asyncio
from pathlib import Path
import json

BASE = Path(__file__).parent
IN_IMG = BASE / 'submit_image_for_tripo.png'
OUT_DIR = BASE / 'tripo_output'
OUT_DIR.mkdir(parents=True, exist_ok=True)
STATUS = BASE / 'tripo_status_sdk_v2.txt'
LAST_URL = BASE / 'last_model_url.txt'

API_KEY = os.environ.get('TRIPO_API_KEY') or os.environ.get('TRIPO_KEY')

async def main():
    STATUS.write_text('Starting SDK submission v2...', encoding='utf-8')
    if not API_KEY:
        STATUS.write_text('No TRIPO_API_KEY in environment', encoding='utf-8')
        return
    if not IN_IMG.exists():
        STATUS.write_text(f'Input image not found: {IN_IMG}', encoding='utf-8')
        return

    from tripo3d import TripoClient, TaskStatus
    client = TripoClient(API_KEY)

    try:
        STATUS.write_text('Submitting image_to_model (v2)...', encoding='utf-8')
        task_id = await client.image_to_model(image=str(IN_IMG))
        STATUS.write_text('Submitted task_id: ' + str(task_id), encoding='utf-8')
    except Exception as e:
        STATUS.write_text('SDK submit exception: ' + str(e), encoding='utf-8')
        raise

    try:
        STATUS.write_text('Waiting for task...', encoding='utf-8')
        task = await client.wait_for_task(task_id, verbose=True)
        st = getattr(task, 'status', None)
        STATUS.write_text('Raw task.status: ' + str(st), encoding='utf-8')
        ok = False
        try:
            if st == TaskStatus.SUCCESS:
                ok = True
            else:
                s = str(st).lower() if st is not None else ''
                if 'success' in s or 'succeed' in s:
                    ok = True
        except Exception:
            pass

        if ok:
            STATUS.write_text('Task reported success; attempting download...', encoding='utf-8')
            files = await client.download_task_models(task, str(OUT_DIR))
            STATUS.write_text('download_task_models returned: ' + json.dumps(files, ensure_ascii=False), encoding='utf-8')
            if files:
                fn = Path(files[0]).name
                url = f'http://127.0.0.1:8000/{fn}'
                LAST_URL.write_text(url, encoding='utf-8')
                STATUS.write_text('Success. Model ready at ' + url, encoding='utf-8')
                print('Success. Model URL:', url)
                return
            else:
                STATUS.write_text('No files found after success status', encoding='utf-8')
        else:
            STATUS.write_text('Task did not report success: ' + str(st), encoding='utf-8')
    finally:
        try:
            await client.close()
        except Exception:
            pass

if __name__ == '__main__':
    asyncio.run(main())
