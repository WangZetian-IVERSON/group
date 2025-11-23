import importlib.util
from pathlib import Path
import traceback

app_path = Path(r"f:\comfy\app (1).py")
module_name = "app_one"

spec = importlib.util.spec_from_file_location(module_name, app_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

load_defaults = getattr(module, "load_defaults")
run_workflow = getattr(module, "run_workflow")

wf_name = "api_google_gemini_image__hardcoded_key.json"
print("Loading defaults for", wf_name)
defs = load_defaults(wf_name)
print("Defaults:", defs)
args = [wf_name] + defs
try:
    print("Running workflow...")
    res = run_workflow(*args)
    print("Run result:", res)
except Exception:
    print("Exception during run:")
    traceback.print_exc()
