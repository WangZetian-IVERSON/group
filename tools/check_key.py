import os
import httpx

key = os.getenv('GOOGLE_API_KEY')
if not key:
    print('No GOOGLE_API_KEY in environment')
    raise SystemExit(1)

url = f'https://generativelanguage.googleapis.com/v1/models?key={key}'
print('Requesting', url)
try:
    r = httpx.get(url, timeout=15.0)
    print('Status:', r.status_code)
    try:
        print('JSON:', r.json())
    except Exception:
        print('Text:', r.text[:1000])
except Exception as e:
    print('Exception while requesting:')
    import traceback
    traceback.print_exc()
    raise
