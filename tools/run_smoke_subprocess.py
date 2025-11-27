import json
import os
import sys
from pathlib import Path

# Ensure we don't leak environment content; run in a quiet mode
os.environ.pop('NANO_API_KEY', None)
os.environ.pop('GOOGLE_API_KEY', None)
# but do not remove TRIPO etc since not used in smoke

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    import importlib
    app = importlib.import_module('app (1)'.replace(' ', ' '))
except Exception as e:
    # fallback: use importlib.util to load by path
    from importlib import util
    p = Path(__file__).resolve().parent.parent / 'app (1).py'
    spec = util.spec_from_file_location('app_module', str(p))
    app = util.module_from_spec(spec)
    spec.loader.exec_module(app)

# Call run_gradio_flow with use_api=False to avoid external calls
try:
    res = app.run_gradio_flow(
        layout_prompt='Smoke test prompt',
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
except Exception as e:
    print(json.dumps({'error': str(e)}))
    sys.exit(1)

# res is (gallery_entries, captions_str, model_file_out, tripo_status)
gallery, captions, model_out, tripo_status = res
# summarize gallery: number of items, and first item path (if any)
summary = {
    'gallery_count': len(gallery) if isinstance(gallery, (list,tuple)) else 0,
    'first_gallery_item': None,
    'captions_preview': captions.split('\n')[:5] if isinstance(captions, str) else None,
    'model_out': model_out if isinstance(model_out, str) and model_out else None,
    'tripo_status': tripo_status,
}
if isinstance(gallery, (list,tuple)) and gallery:
    try:
        summary['first_gallery_item'] = gallery[0][0]
    except Exception:
        summary['first_gallery_item'] = None

print(json.dumps(summary, ensure_ascii=False, indent=2))
