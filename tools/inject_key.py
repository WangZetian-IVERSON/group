from pathlib import Path
import json

base = Path(__file__).parent.parent
env_path = base / '.env'
wf_path = base / 'workflows' / 'api_google_gemini_image__hardcoded_key.json'

if not env_path.exists():
    raise SystemExit('.env not found')

text = env_path.read_text(encoding='utf-8')
key = None
for line in text.splitlines():
    if line.strip().startswith('COMFY_GEMINI_API_KEY='):
        key = line.split('=',1)[1].strip()
        break
if not key:
    raise SystemExit('COMFY_GEMINI_API_KEY not found in .env')

s = wf_path.read_text(encoding='utf-8')
if 'REDACTED_FOR_OUTPUT' not in s:
    print('No placeholder found; nothing to do')
else:
    s2 = s.replace('REDACTED_FOR_OUTPUT', key)
    wf_path.write_text(s2, encoding='utf-8')
    print('Done')
