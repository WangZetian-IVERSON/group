import runpy
import time
from pathlib import Path

script = str(Path(__file__).parent.parent / 'app (1).py')
print('Loading app from', script)
mod = runpy.run_path(script, run_name='app_module')
run = mod.get('run_gradio_flow')
if not run:
    print('run_gradio_flow not found')
    raise SystemExit(1)

# pick an existing image as sketch input
tools = Path(__file__).parent
sketch_candidates = sorted(tools.glob('generated_gemini25_from_url_*.png'), key=lambda p: p.stat().st_mtime, reverse=True)
if sketch_candidates:
    sketch = str(sketch_candidates[0])
else:
    sketch = None

layout_prompt = '木地板 客厅, 瓷砖 卫生间; 色彩偏暖; 北欧风格; 大窗户.'
spaces = ['客厅', '卧室', '卫生间', '厨房']

print('Starting run_gradio_flow with sketch=', sketch)
res = run(layout_prompt, sketch, spaces[0], spaces[1], spaces[2], spaces[3], True, False, 'gemini-2.5-flash-image', '16:9', '')
print('run_gradio_flow returned:', type(res))
# res expected: gallery_entries, captions, model_preview_html, tripo_status
print('Gallery count:', len(res[0]) if res and res[0] else 0)
print('Captions:', res[1])
print('Initial tripo status:', res[3] if len(res) > 3 else 'n/a')

# wait and poll tripo_status.txt for up to 6 minutes
status_path = Path(__file__).parent.parent / 'tools' / 'tripo_status.txt'
last = None
for i in range(72):
    if status_path.exists():
        s = status_path.read_text(encoding='utf-8')
        if s != last:
            print('[tripo_status]', s)
            last = s
        if 'success' in s.lower() or 'model ready' in s.lower():
            print('Tripo succeeded; checking output folder')
            outdir = Path(__file__).parent / 'tripo_output'
            print('tripo_output contents:', list(outdir.iterdir()))
            break
    time.sleep(5)
else:
    print('Timeout waiting for tripo_status change')

print('Done')
