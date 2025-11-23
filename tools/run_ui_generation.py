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
    print('Loading app module...')
    app = load_app_module(APP_PATH)

    # choose a workflow (prefer first)
    wf_list = app.list_workflows()
    selected = wf_list[0] if wf_list else None

    defaults = app.load_defaults(selected) if selected else [None]*18
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

    img = BASE / 'documents' / 'image (5).png'
    if not img.exists():
        print('Input image not found:', img)
        img = None

    print('Calling run_workflow with use_api=True, aspect_ratio=16:9')
    images, captions = app.run_workflow(selected, indoor, materials, se1, se2, se3, se4, positive, negative, seed, steps, cfg, sampler, width, height, batch_size, filename_prefix, other_prompts, str(img) if img else None, use_api=True, api_model=None, aspect_ratio='16:9')

    out = BASE / 'tools' / 'ui_gen_summary.json'
    out.write_text(json.dumps({'selected_workflow': selected, 'captions': captions, 'images': images}, ensure_ascii=False, indent=2))
    print('Summary written to', out)
    print('Images returned:')
    for it in images:
        print(' -', it)

if __name__ == '__main__':
    main()
