import os
import asyncio
from pathlib import Path
import json

BASE = Path(__file__).parent
IN_IMG = BASE / 'submit_image_for_tripo.png'
OUT_DIR = BASE / 'tripo_output'
OUT_DIR.mkdir(parents=True, exist_ok=True)
STATUS = BASE / 'tripo_status_sdk.txt'
LAST_URL = BASE / 'last_model_url.txt'

API_KEY = os.environ.get('TRIPO_API_KEY') or os.environ.get('TRIPO_KEY')

async def main():
    STATUS.write_text('Starting SDK submission...', encoding='utf-8')
    if not API_KEY:
        STATUS.write_text('No TRIPO_API_KEY in environment', encoding='utf-8')
        print('No TRIPO_API_KEY')
        return
    if not IN_IMG.exists():
        STATUS.write_text(f'Input image not found: {IN_IMG}', encoding='utf-8')
        print('No input image at', IN_IMG)
        return

    try:
        from tripo3d import TripoClient, TaskStatus
    except Exception as e:
        STATUS.write_text('Failed importing tripo3d SDK: ' + str(e), encoding='utf-8')
        raise

    try:
        client = TripoClient(API_KEY)
    except Exception as e:
        # attempt bypass if available
        try:
            from tripo3d.client_impl import ClientImpl
            client = TripoClient.__new__(TripoClient)
            client.api_key = API_KEY
            client.BASE_URL = getattr(TripoClient, 'BASE_URL', 'https://api.tripo3d.ai/v2/openapi')
            client._impl = ClientImpl(API_KEY, client.BASE_URL)
        except Exception as e2:
            STATUS.write_text('Failed to instantiate TripoClient: ' + str(e) + ' / ' + str(e2), encoding='utf-8')
            raise

    try:
        STATUS.write_text('Calling image_to_model...', encoding='utf-8')
        # Use default model_version and parameters; adjust if desired
        task_id = await client.image_to_model(image=str(IN_IMG))
        STATUS.write_text('Submitted task_id: ' + str(task_id), encoding='utf-8')
    except Exception as e:
        STATUS.write_text('SDK submit error: ' + str(e), encoding='utf-8')
        raise

    try:
        STATUS.write_text('Waiting for task...', encoding='utf-8')
        task = await client.wait_for_task(task_id, verbose=True)
        STATUS.write_text('Task finished: ' + str(getattr(task, 'status', 'unknown')), encoding='utf-8')
    except Exception as e:
        STATUS.write_text('Error waiting for task: ' + str(e), encoding='utf-8')
        raise

    try:
        if getattr(task, 'status', None) and str(getattr(task, 'status')).lower() in ('success','succeed'):
            files = await client.download_task_models(task, str(OUT_DIR))
            if files:
                fn = Path(files[0]).name
                url = f'http://127.0.0.1:8000/{fn}'
                LAST_URL.write_text(url, encoding='utf-8')
                STATUS.write_text('Success. Model ready at ' + url, encoding='utf-8')
                print('Success. Model URL:', url)
                return
            else:
                STATUS.write_text('No files returned from download_task_models', encoding='utf-8')
                print('No files')
                return
        else:
            STATUS.write_text('Task did not succeed: ' + str(getattr(task, 'status', 'unknown')), encoding='utf-8')
            print('Task failed or unknown status')
            return
    finally:
        try:
            await client.close()
        except Exception:
            pass

if __name__ == '__main__':
    asyncio.run(main())
