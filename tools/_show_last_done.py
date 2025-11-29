import json
from pathlib import Path
jpath = Path(__file__).resolve().parent / 'ai3d_last_job.json'
if not jpath.exists():
    print('Missing', jpath)
    raise SystemExit(1)

j = json.loads(jpath.read_text(encoding='utf-8'))
polls = j.get('poll', [])
# find entries with Status DONE
done = [p for p in polls if str(p.get('Status','')).upper()=='DONE']
if not done:
    print('No DONE entries found')
    raise SystemExit(0)

print('Found', len(done), 'DONE entries. Showing last 2:')
for entry in done[-2:]:
    rid = entry.get('RequestId')
    print('\nRequestId:', rid)
    print('Status:', entry.get('Status'))
    rf = entry.get('ResultFile3Ds', [])
    for it in rf:
        url = it.get('Url')
        purl = it.get('PreviewImageUrl')
        print('- Type:', it.get('Type'))
        print('  Url:', url)
        print('  Preview:', purl)
        if url and 'ap-guangzhou' in url:
            print('  -> URL contains ap-guangzhou')
        elif url:
            print('  -> URL does NOT contain ap-guangzhou')

# also show submit job id and region guess
submit = j.get('submit', {})
print('\nSubmit JobId:', submit.get('JobId'))
print('-- End --')
