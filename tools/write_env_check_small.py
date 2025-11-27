from pathlib import Path

def mask(s: str) -> str:
    if not s:
        return '<MISSING>'
    s = str(s)
    if len(s) <= 8:
        return s[:2] + '...' + s[-2:]
    return s[:4] + '...' + s[-4:]

base = Path(__file__).resolve().parent.parent
env_path = base / '.env'
outdir = base / 'tools'
outdir.mkdir(parents=True, exist_ok=True)
mask_file = outdir / 'env_check.txt'

vals = {}
if env_path.exists():
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        vals[k.strip()] = v.strip()

tripo = vals.get('TRIPO_API_KEY') or vals.get('TRIPO_KEY') or ''
nano = vals.get('NANO_API_KEY') or vals.get('GOOGLE_API_KEY') or vals.get('API_KEY') or ''
gemini = vals.get('GOOGLE_GEMINI_BASE_URL') or vals.get('NANO_API_URL') or vals.get('API_URL') or ''

lines = [
    f"TRIPO_API_KEY: {mask(tripo)}",
    f"NANO_API_KEY: {mask(nano)}",
    f"GOOGLE_GEMINI_BASE_URL: {mask(gemini)}",
]

mask_file.write_text('\n'.join(lines), encoding='utf-8')
print('[env_check_small] Wrote', str(mask_file))
