import importlib.util
from pathlib import Path
import json

BASE = Path(__file__).resolve().parent.parent
APP_PATH = BASE / 'app (1).py'

spec = importlib.util.spec_from_file_location('app_mod', str(APP_PATH))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

model = 'gemini-2.5-flash-image'
prompt = 'Convert this black-and-white architectural floor plan into a clean colored 2D floor-plan illustration, keeping walls, doors and furniture positions accurate.'
img = BASE / 'documents' / 'image (5).png'
if not img.exists():
    print('Input image missing:', img)
else:
    print('Calling api_generate_image with image:', img)
    try:
        out = mod.api_generate_image(model, prompt, str(img), aspect_ratio='16:9', size='1024x576')
        print('api_generate_image returned:', out)
    except Exception as e:
        print('api_generate_image raised:', e)

# list the tools directory for inspection
tools_dir = BASE / 'tools'
print('\nContents of tools/:')
for p in sorted(tools_dir.iterdir()):
    print(' -', p.name)

# show any recent gemini response files
for p in sorted(tools_dir.glob('gemini-2.5-flash-image_chat_response*.json'))[-3:]:
    print('\n--- Recent response file:', p.name)
    try:
        print(p.read_text(encoding='utf-8')[:1000])
    except Exception as e:
        print('  (failed to read)', e)
