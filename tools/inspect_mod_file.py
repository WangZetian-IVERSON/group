from pathlib import Path
p=Path('workflows')
mods=list(p.glob('*__modified__*.json'))
if not mods:
    print('NO_MOD_FILE')
    raise SystemExit(0)
fp=mods[-1]
print('file=',fp)
content_bytes=fp.read_bytes()
print('size=',len(content_bytes))
encs=['utf-8','utf-8-sig','cp936','gbk','latin-1','cp1252']
for e in encs:
    try:
        s=content_bytes.decode(e)
        print(f'OK decode with {e}: first100={s[:100]!r}')
    except Exception as ex:
        print(f'FAIL decode with {e}:', type(ex).__name__, ex)
print('\npreview with utf-8 replace:\n')
print(content_bytes.decode('utf-8','replace')[:500])
