import httpx
u='https://cloudflarer2.nananobanana.com/png/1763805594970_506.png'
try:
    r=httpx.get(u, timeout=30.0)
    print('status', r.status_code, 'len', len(r.content))
except Exception as e:
    print('error', repr(e))
