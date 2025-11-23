import subprocess
import sys
from pathlib import Path
from PIL import Image

BASE = Path(__file__).resolve().parent
TOOLS = BASE / 'tools'
DOCS = BASE / 'documents'
DOCS.mkdir(exist_ok=True)

helper = TOOLS / 'run_gemini25_chat.py'
input_img = DOCS / 'image (5).png'

if not input_img.exists():
    print('Input image missing:', input_img)
    sys.exit(2)

print('Calling helper to generate image...')
cmd = [sys.executable, str(helper), str(input_img)]
subprocess.run(cmd, check=False)

# find generated file
cand = sorted(TOOLS.glob('generated_gemini25_from_*'), key=lambda p: p.stat().st_mtime, reverse=True)
if not cand:
    print('No generated file found in tools/')
    sys.exit(3)

print('Found generated file:', cand[0])
# try opening to ensure it's valid
try:
    im = Image.open(cand[0])
    print('Image size:', im.size, 'format:', im.format)
except Exception as e:
    print('Failed to open generated image:', e)
    sys.exit(4)

print('Success — generation via helper works. You can integrate this into Gradio.')
