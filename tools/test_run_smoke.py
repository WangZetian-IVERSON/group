import importlib.util
from pathlib import Path

p = Path(__file__).resolve().parent.parent / 'app (1).py'
if not p.exists():
    print('app (1).py not found at', p)
    raise SystemExit(1)

spec = importlib.util.spec_from_file_location('app_module', str(p))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Call run_gradio_flow with use_api=False to trigger the early-return path and ensure no HTML returned as model preview
res = mod.run_gradio_flow(
    layout_prompt='Test layout prompt',
    sketch_image=None,
    space1='Living room',
    space2='Bedroom',
    space3='Bathroom',
    space4='Kitchen',
    use_api=False,
    show_ref=False,
    api_model=None,
    aspect_ratio='16:9',
    enable_tripo=False,
    model_url=''
)

print('run_gradio_flow returned (types):')
print('  gallery type:', type(res[0]), 'len:', (len(res[0]) if isinstance(res[0], (list,tuple)) else 'N/A'))
print('  captions type:', type(res[1]))
print('  model preview type/value:', type(res[2]), repr(res[2]))
print('  tripo status type/value:', type(res[3]), repr(res[3]))
