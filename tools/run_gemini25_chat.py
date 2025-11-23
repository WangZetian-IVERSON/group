import os
import sys
import json
import base64
import re
from pathlib import Path

import httpx

API_URL = os.getenv('GOOGLE_GEMINI_BASE_URL') or os.getenv('NANO_API_URL') or 'https://newapi.pockgo.com'
API_URL = API_URL.rstrip('/')
API_KEY = os.getenv('NANO_API_KEY') or os.getenv('API_KEY') or os.getenv('GOOGLE_API_KEY')

if not API_KEY:
    print('Missing API key in environment (set NANO_API_KEY or GOOGLE_API_KEY).')
    sys.exit(2)

default_doc = Path(__file__).resolve().parent.parent / 'documents' / 'image (5).png'

# Parse CLI args flexibly:
# - If first arg is an existing file path, use it as input image and second arg as prompt (optional)
# - If first arg is not a path, treat it as prompt and use default_doc as input image
arg1 = sys.argv[1] if len(sys.argv) > 1 else None
arg2 = sys.argv[2] if len(sys.argv) > 2 else None
arg3 = sys.argv[3] if len(sys.argv) > 3 else None

in_path = default_doc
prompt_text = None
if arg1:
    candidate = Path(arg1)
    if candidate.exists():
        in_path = candidate
        # prompt may be in arg2
        if arg2:
            prompt_text = arg2
    else:
        # arg1 is not a path; treat as prompt
        prompt_text = arg1

if not prompt_text:
    # allow arg2 as prompt if provided
    if arg2 and Path(arg2).exists():
        # arg2 is a file path (we already handled arg1 as prompt case), leave prompt default
        prompt_text = None
    elif arg2:
        prompt_text = arg2

if not in_path.exists():
    print('Input file not found:', in_path)
    sys.exit(3)

with in_path.open('rb') as f:
    b = f.read()
b64 = base64.b64encode(b).decode('utf-8')
data_url = f'data:image/png;base64,{b64}'

default_prompt = "Convert this black-and-white architectural floor plan into a clean colored 2D floor-plan illustration, keeping walls, doors and furniture positions accurate."
if not prompt_text:
    prompt_text = default_prompt

# aspect ratio: if arg3 provided use it; else if arg2 looks like an aspect use it
aspect = "16:9"
if arg3:
    aspect = arg3
elif arg2 and not Path(arg2).exists():
    # if arg2 is non-path and arg1 was path, arg2 could be prompt; keep default aspect
    pass

payload = {
    "extra_body": {
        "imageConfig": {"aspectRatio": aspect}
    },
    "model": "gemini-2.5-flash-image",
    "messages": [
        {"role": "system", "content": json.dumps({"imageConfig": {"aspectRatio": aspect}})},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": data_url}}
            ]
        }
    ],
    "max_tokens": 150,
    "temperature": 0.7
}

headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
endpoint = API_URL + '/v1/chat/completions'

client = httpx.Client(timeout=300.0)

print('POST', endpoint)
try:
    r = client.post(endpoint, headers=headers, json=payload)
except Exception as e:
    print('Request error:', e)
    sys.exit(4)

print('Status:', r.status_code)
out_dir = Path(__file__).resolve().parent
resp_path = out_dir / 'gemini25_chat_response.json'
try:
    j = r.json()
    resp_path.write_text(json.dumps(j, ensure_ascii=False, indent=2))
    print('Saved JSON response to', resp_path)
except Exception:
    resp_path.write_text(r.text)
    print('Saved raw response to', resp_path)

# If provider returned insufficient quota, create a low-cost placeholder image so downstream flow can continue for testing
try:
    err_code = None
    if isinstance(j, dict):
        err_code = j.get('error', {}).get('code')
    if err_code == 'insufficient_user_quota':
        print('Provider reports insufficient_user_quota — creating placeholder image for downstream testing')
        # copy default_doc to a generated placeholder output so callers can proceed
        placeholder = out_dir / 'generated_gemini25_from_placeholder.png'
        try:
            with default_doc.open('rb') as sf, placeholder.open('wb') as df:
                df.write(sf.read())
            print('Wrote placeholder image to', placeholder)
            # also write a small debug file explaining fallback
            debug = {'fallback': 'insufficient_user_quota', 'note': 'Used local placeholder image to allow downstream testing.'}
            (out_dir / 'gemini_quota_fallback.json').write_text(json.dumps(debug, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as e:
            print('Failed to write placeholder image:', e)
except Exception:
    pass

# Try to find image URL(s) or data URL(s) in the JSON/text
text = ''
try:
    text = json.dumps(j)
except Exception:
    text = r.text

urls = re.findall(r'https?://[\w\-\.\/:?=&,%~+]+', text)
data_imgs = re.findall(r'data:image\/(?:png|jpeg);base64,[A-Za-z0-9+/=]+', text)

saved_images = []
if data_imgs:
    # save first data image
    img_b64 = data_imgs[0].split(',', 1)[1]
    out_file = out_dir / 'generated_gemini25_from_dataurl.png'
    with out_file.open('wb') as f:
        f.write(base64.b64decode(img_b64))
    saved_images.append(str(out_file))

if urls:
    # try to download first likely image URL
    for u in urls:
        if any(u.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.webp')):
            try:
                rr = client.get(u, timeout=120.0)
                rr.raise_for_status()
                out_file = out_dir / ('generated_gemini25_from_url_' + Path(u).name)
                with out_file.open('wb') as f:
                    f.write(rr.content)
                saved_images.append(str(out_file))
                break
            except Exception:
                continue

if saved_images:
    print('Saved images:', saved_images)
else:
    print('No image URL or data:image found in response. See', resp_path)
