import os
import sys
from pathlib import Path
import importlib.util
import json

BASE = Path(__file__).resolve().parent.parent
APP_PATH = BASE / 'app (1).py'

def load_app_module(path: Path):
    spec = importlib.util.spec_from_file_location('app_main', str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def main():
    # ensure env vars are set by caller; otherwise use defaults
    api_base = os.environ.get('GOOGLE_GEMINI_BASE_URL') or os.environ.get('NANO_API_URL')
    api_key = os.environ.get('NANO_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    print('API base:', api_base)
    print('API key present:', bool(api_key))

    if not APP_PATH.exists():
        print('app (1).py not found at', APP_PATH)
        sys.exit(2)

    app = load_app_module(APP_PATH)

    # choose a workflow (first available)
    wf_list = app.list_workflows()
    if not wf_list:
        print('No workflows found in', app.comfyui_flows)
        selected = None
    else:
        selected = wf_list[0]

    # load defaults for selected workflow
    defaults = app.load_defaults(selected)
    # defaults ordering in load_defaults: indoor, materials, se34, se48, se53, se58, positive, negative, seed, steps, cfg, sampler, width, height, batch_size, filename_prefix, other_prompts, image_path
    indoor = defaults[0]
    materials = defaults[1]
    se1, se2, se3, se4 = defaults[2], defaults[3], defaults[4], defaults[5]
    positive = defaults[6]
    negative = defaults[7]
    seed = defaults[8]
    steps = defaults[9] or 20
    cfg = defaults[10] or 7.5
    sampler = defaults[11] or ''
    width = defaults[12] or 1024
    height = defaults[13] or 1024
    batch_size = defaults[14] or 1
    filename_prefix = defaults[15] or ''
    other_prompts = defaults[16] or '{}'

    # image to use
    img = BASE / 'documents' / 'image (5).png'
    if not img.exists():
        print('Input image not found:', img)
        img = None

    print('Running run_workflow with use_api=True, model=gemini-2.5-flash-image, aspect_ratio=16:9')
    images, captions = app.run_workflow(selected, indoor, materials, se1, se2, se3, se4, positive, negative, seed, steps, cfg, sampler, width, height, batch_size, filename_prefix, other_prompts, str(img) if img else None, use_api=True, api_model='gemini-2.5-flash-image', aspect_ratio='16:9')

    print('Returned captions:')
    print(captions)
    print('Returned images:')
    for it in images:
        print(' -', it)

    # save summary
    out = BASE / 'tools' / 'smoke_test_summary.json'
    out.write_text(json.dumps({'captions': captions, 'images': images}, ensure_ascii=False, indent=2))
    print('Summary written to', out)

if __name__ == '__main__':
    main()
