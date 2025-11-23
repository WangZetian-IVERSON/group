import traceback
import httpx

endpoints = [
    "https://www.google.com/",
    "https://generativelanguage.googleapis.com/v1/models",
]

for url in endpoints:
    print(f"\nTesting: {url}")
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url)
            print(f"Status: {r.status_code}")
            print(f"Headers: {dict(r.headers) if r is not None else 'none'}")
    except Exception as e:
        print("Exception:")
        traceback.print_exc()
