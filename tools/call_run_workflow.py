import importlib.util
import traceback
from pathlib import Path

app_path = Path(r"f:\comfy\app (1).py")
module_name = "app_one"

spec = importlib.util.spec_from_file_location(module_name, app_path)
module = importlib.util.module_from_spec(spec)
# This will execute the file but with __name__ = module_name, so the if __name__=="__main__" block won't run
spec.loader.exec_module(module)

# get functions
load_defaults = getattr(module, "load_defaults")
run_workflow = getattr(module, "run_workflow")

# choose a workflow in the repo (prefer the root file)
wf_name = "api_google_gemini_image.json"

print("Loading defaults for", wf_name)
defs = load_defaults(wf_name)
print("Defaults:", defs)

# Map returned defaults to run_workflow args
# load_defaults returns: [indoor, materials, se34, se48, se53, se58, positive, negative, seed, steps, cfg, sampler, width, height, batch_size, filename_prefix, other_prompts_str, image_path]
args = [wf_name] + defs

try:
    print("Running workflow...")
    res = run_workflow(*args)
    print("Run result:", res)
except Exception as e:
    print("Exception during run:")
    traceback.print_exc()
    # also print exception message
    print(str(e))
