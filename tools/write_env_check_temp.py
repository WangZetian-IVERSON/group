import os
from pathlib import Path

def _mask_key(s: str) -> str:
    if not s:
        return '<MISSING>'
    s = str(s)
    if len(s) <= 8:
        return s[:2] + '...' + s[-2:]
    return s[:4] + '...' + s[-4:]

outdir = Path(__file__).parent
outdir.mkdir(parents=True, exist_ok=True)
tripo = os.environ.get('TRIPO_API_KEY') or os.environ.get('TRIPO_KEY')
nano = os.environ.get('NANO_API_KEY') or os.environ.get('GOOGLE_API_KEY') or os.environ.get('API_KEY')
gemini_base = os.environ.get('GOOGLE_GEMINI_BASE_URL') or os.environ.get('NANO_API_URL') or os.environ.get('API_URL')
lines = [
    f"TRIPO_API_KEY: {_mask_key(tripo)}",
    f"NANO_API_KEY: {_mask_key(nano)}",
    f"GOOGLE_GEMINI_BASE_URL: {_mask_key(gemini_base)}",
]
(outdir / 'env_check.txt').write_text('\n'.join(lines), encoding='utf-8')
print('WROTE', outdir / 'env_check.txt')
