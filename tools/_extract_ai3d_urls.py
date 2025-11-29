import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
JPATH = ROOT / 'ai3d_last_job.json'
OUT_URLS = ROOT / 'ai3d_urls_to_download.txt'

if not JPATH.exists():
    print('Missing', JPATH)
    raise SystemExit(1)

j = json.loads(JPATH.read_text(encoding='utf-8'))
jobid = None
if 'submit' in j and isinstance(j['submit'], dict):
    jobid = j['submit'].get('JobId')

# find last poll entry with ResultFile3Ds
urls = []
for entry in reversed(j.get('poll', [])):
    r = entry.get('ResultFile3Ds')
    if r:
        for item in r:
            u = item.get('Url')
            pu = item.get('PreviewImageUrl')
            if u:
                urls.append(u)
            if pu:
                urls.append(pu)
        break

# dedupe while preserving order
seen = set(); uniq = []
for u in urls:
    if u not in seen:
        seen.add(u); uniq.append(u)

OUT_URLS.write_text('\n'.join(uniq), encoding='utf-8')
print('JobId:', jobid if jobid else 'unknown')
print('Wrote', OUT_URLS, 'with', len(uniq), 'urls')
print('\n'.join(uniq))
