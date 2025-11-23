import importlib.util
from pathlib import Path
import json
import os

BASE = Path(__file__).resolve().parent.parent
APP_PATH = BASE / 'app (1).py'

spec = importlib.util.spec_from_file_location('app_mod', str(APP_PATH))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

layout_prompt = '木地板 客厅, 瓷砖 卫生间'
img = BASE / 'documents' / 'image (5).png'
if not img.exists():
    print('Input image missing:', img)
    img = None

print('Calling run_gradio_flow...')
res_images, captions, model_preview = mod.run_gradio_flow(layout_prompt, str(img) if img else None, '客厅', '卧室', '卫生间', '厨房', use_api=True, api_model='gemini-2.5-flash-image', aspect_ratio='16:9')
print('Captions:', captions)
print('Images:')
for p in res_images:
    print(' -', p)
print('Model preview (HTML):')
print(model_preview)

out = BASE / 'tools' / 'test_gradio_flow_summary.json'
out.write_text(json.dumps({'captions': captions, 'images': res_images, 'model_preview': model_preview}, ensure_ascii=False, indent=2))
print('Wrote summary to', out)
