import httpx,sys
url='http://127.0.0.1:8000/eaa56d7f-2bcc-4469-a704-28dd5f51344e_pbr.glb'
try:
    r=httpx.get(url, timeout=5.0)
    print('GET', url, '=>', r.status_code)
    sys.exit(0 if r.status_code==200 else 2)
except Exception as e:
    print('ERROR', e)
    sys.exit(3)
