"""Test Tripo API key and submit a simple text_to_model task.

Usage:
  python tools/test_tripo.py            # uses TRIPO_API_KEY env variable
  python tools/test_tripo.py your_key  # uses provided key

The script does two checks:
  1) Direct HTTP POST to /task with Authorization Bearer <key>
  2) (Optional) SDK attempt with a runtime bypass to test SDK-path (only if --sdk-bypass provided)

Note: The SDK normally expects keys starting with 'tsk_'. The bypass path instantiates the SDK client implementation directly.
"""

import sys
import asyncio
import json
from pathlib import Path
import httpx

API_BASE = "https://api.tripo3d.ai/v2/openapi"


def try_http(key: str):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"type": "text_to_model", "prompt": "a small cat", "negative_prompt": "low quality, blurry"}
    print("== Direct HTTP test ==")
    try:
        r = httpx.post(f"{API_BASE}/task", headers=headers, json=payload, timeout=30.0)
    except Exception as e:
        print("HTTP request failed:", e)
        return None
    print("Status:", r.status_code)
    try:
        print(r.json())
    except Exception:
        print(r.text[:1000])
    return r


async def try_sdk_bypass(key: str, outdir: str = "./tools/tripo_output"):
    print("== SDK bypass test ==")
    try:
        from tripo3d import TripoClient, TaskStatus
        from tripo3d.client_impl import ClientImpl
    except Exception as e:
        print("Failed to import tripo3d SDK:", e)
        return

    Path(outdir).mkdir(parents=True, exist_ok=True)

    # instantiate without running TripoClient.__init__ which enforces key prefix
    client = TripoClient.__new__(TripoClient)
    client.api_key = key
    client.BASE_URL = getattr(TripoClient, 'BASE_URL', API_BASE)
    client._impl = ClientImpl(key, client.BASE_URL)

    try:
        task_id = await client.text_to_model(prompt="a small cat", negative_prompt="low quality, blurry")
        print('Task ID:', task_id)
    except Exception as e:
        print('Create task failed:', repr(e))
        await client.close()
        return

    try:
        task = await client.wait_for_task(task_id, verbose=True)
        print('Final status:', task.status)
        if task.status == TaskStatus.SUCCESS:
            files = await client.download_task_models(task, outdir)
            print('Downloaded files:', files)
        else:
            print('Task completed not-success:', getattr(task, '__dict__', str(task)))
    except Exception as e:
        print('Waiting/downloading failed:', repr(e))
    finally:
        await client.close()


if __name__ == '__main__':
    key = None
    sdk_bypass = False
    for a in sys.argv[1:]:
        if a == '--sdk-bypass':
            sdk_bypass = True
        else:
            key = a

    if not key:
        key = sys.environ.get('TRIPO_API_KEY') or sys.environ.get('TRIPO_KEY') or None

    if not key:
        print('Usage: python tools/test_tripo.py [API_KEY] [--sdk-bypass]')
        print('Set TRIPO_API_KEY env var or pass the key as the first arg.')
        sys.exit(1)

    print('Using key prefix:', key[:4])
    http_resp = try_http(key)
    if sdk_bypass:
        asyncio.run(try_sdk_bypass(key))
    else:
        print('\nTo try the SDK bypass (only for testing), run with --sdk-bypass')
