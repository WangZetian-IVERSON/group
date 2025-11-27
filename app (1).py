import asyncio

# Ensure there's an asyncio event loop in this thread.
# Use get_running_loop() which raises RuntimeError if there is none
# (and does not emit the DeprecationWarning that get_event_loop() triggers).
import asyncio
from pathlib import Path
import json
import random
import uuid
from comfy_api_simplified import ComfyApiWrapper, ComfyWorkflowWrapper
import os
import httpx
import base64
import re
import uuid
import sys
import subprocess
import threading
import requests
from langchain_ollama import ChatOllama
import pymupdf4llm
import gradio as gr
import html
import time

# Ensure there's an asyncio event loop in this thread.
try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

basefolder = Path(__file__).parent
comfyui_flows = basefolder / "workflows"
docs = basefolder / "documents"
docs.mkdir(parents=True, exist_ok=True)

# Load local .env file (if present) and set environment variables for this process.
# This helps testing from VS Code / Gradio by making credentials available to this Python process.
# NOTE: The Comfy backend process must also be started with the same environment variable set
# (or otherwise configured) for server-side nodes (like GeminiImageNode) to use the credential.
env_path = basefolder / ".env"
if env_path.exists():
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k and v:
                    # explicitly set environment variables from .env so the running process definitely has them
                    try:
                        os.environ[k] = v
                    except Exception:
                        # fallback to setdefault if direct set fails
                        os.environ.setdefault(k, v)
    except Exception:
        pass

# Write a masked env check to tools/env_check.txt so we can verify keys are visible to the process
def _mask_key(s: str) -> str:
    if not s:
        return '<MISSING>'
    s = str(s)
    if len(s) <= 8:
        return s[:2] + '...' + s[-2:]
    return s[:4] + '...' + s[-4:]

def write_env_check():
    try:
        outdir = basefolder / 'tools'
        outdir.mkdir(parents=True, exist_ok=True)
        tripo = os.environ.get('TRIPO_API_KEY') or os.environ.get('TRIPO_KEY')
        nano = os.environ.get('NANO_API_KEY') or os.environ.get('GOOGLE_API_KEY') or os.environ.get('API_KEY')
        gemini_base = os.environ.get('GOOGLE_GEMINI_BASE_URL') or os.environ.get('NANO_API_URL') or os.environ.get('API_URL')
        lines = [
            f"TRIPO_API_KEY: {_mask_key(tripo)}",
            f"NANO_API_KEY: {_mask_key(nano)}",
            f"GOOGLE_GEMINI_BASE_URL: {_mask_key(gemini_base)}",
        ]
        (outdir / 'env_check.txt').write_text('\n'.join(lines), encoding='utf-8')
        print('[env_check] Wrote tools/env_check.txt with masked environment values')
    except Exception as e:
        print('[env_check] Failed to write env_check.txt:', e)

# Run env check once at startup
write_env_check()

# Tripo API key should be provided via environment variable `TRIPO_API_KEY`.
# For local testing you can set this in a `.env` file in the project root.

# Initialize API wrappers
# Allow overriding the backend URL via environment variable COMFY_API_URL (e.g. http://127.0.0.1:8000/)
comfy_api_url = os.environ.get("COMFY_API_URL", "http://127.0.0.1:8000/")
comfy_api = ComfyApiWrapper(comfy_api_url)
ollama = ChatOllama(model="llama3.2")
ollama_json = ChatOllama(model="llama3.2", format="json")

def list_workflows():
    # include workflows in workflows/ and also top-level json files (e.g., api_google_gemini_image.json)
    files = {p.name for p in comfyui_flows.glob("*.json")}
    files.update({p.name for p in basefolder.glob("*.json")})
    # remove this script itself if present
    files.discard(Path(__file__).name)
    return sorted(list(files))


def get_workflow_path(name: str) -> Path:
    p = comfyui_flows / name
    if p.exists():
        return p
    p2 = basefolder / name
    if p2.exists():
        return p2
    # fallback to comfyui_flows path
    return p

def run_workflow(selected_workflow, indoor_spaces, interior_materials, se1, se2, se3, se4, positive, negative, seed, steps, cfg, sampler, width, height, batch_size, filename_prefix, other_prompts, image_input, use_api=False, api_model=None, aspect_ratio='1:1'):
    """
    Build a temporary modified workflow JSON by applying the UI edits and run it.
    Returns images list and a captions string.
    """
    if not selected_workflow:
        return [], "No workflow selected"

    # load original workflow JSON (resolve whether it's in workflows/ or project root)
    orig_path = get_workflow_path(selected_workflow)
    try:
        # ensure we read using utf-8 to avoid encoding issues
        wf_obj = json.loads(orig_path.read_text(encoding='utf-8'))
    except Exception as e:
        return [], f"Failed to load workflow: {e}"

    # apply edits to specific node ids if present
    # node 70: string_b -> indoor spaces
    if "70" in wf_obj and indoor_spaces is not None:
        wf_obj["70"]["inputs"]["string_b"] = indoor_spaces

    # node 45: interior materials
    if "45" in wf_obj and interior_materials is not None:
        wf_obj["45"]["inputs"]["string_b"] = interior_materials

    # space effect labels for nodes 34,48,53,58
    for nid, val in [("34", se1), ("48", se2), ("53", se3), ("58", se4)]:
        if nid in wf_obj and val is not None:
            wf_obj[nid]["inputs"]["string_b"] = val

    # apply other common fields where present
    def set_if_present(key, value):
        for nid, node in wf_obj.items():
            inputs = node.get("inputs", {})
            if key in inputs and value is not None:
                inputs[key] = value

    set_if_present("seed", seed)
    set_if_present("steps", steps)
    set_if_present("cfg", cfg)
    set_if_present("sampler_name", sampler)
    set_if_present("width", width)
    set_if_present("height", height)
    set_if_present("batch_size", batch_size)
    set_if_present("filename_prefix", filename_prefix)

    # set positive/negative if there are CLIPTextEncode or similar nodes
    for nid, node in wf_obj.items():
        inputs = node.get("inputs", {})
        # try common keys
        if "positive" in inputs and positive is not None:
            inputs["positive"] = positive
        if "negative" in inputs and negative is not None:
            inputs["negative"] = negative
        # text fields
        if "text" in inputs and (positive or negative):
            # conservative: if node title hints at positive/negative, set accordingly
            title = node.get("_meta", {}).get("title", "").lower()
            if "positive" in title and positive is not None:
                inputs["text"] = positive
            elif "negative" in title and negative is not None:
                inputs["text"] = negative

    # other_prompts: expects JSON mapping of node_title->text
    try:
        other_map = json.loads(other_prompts) if other_prompts else {}
        if isinstance(other_map, dict):
            for nid, node in wf_obj.items():
                title = node.get("_meta", {}).get("title", "")
                # if a key matches title, and node has text input, set it
                if title in other_map and "inputs" in node and "text" in node["inputs"]:
                    node["inputs"]["text"] = other_map[title]
    except Exception:
        # ignore malformed JSON
        pass

    # image_input: if provided, write to documents and update any LoadImage nodes
    if image_input:
        try:
            # image_input is a filepath from gradio
            img_path = Path(image_input)
            if img_path.exists():
                dest = docs / img_path.name
                dest.write_bytes(img_path.read_bytes())
                # update nodes where key is 'image' or value is empty image field
                for nid, node in wf_obj.items():
                    inputs = node.get("inputs", {})
                    if "image" in inputs:
                        inputs["image"] = str(dest)
            else:
                # gradio may supply bytes-like -- try to save
                pass
        except Exception:
            pass

    # write modified workflow to a temp file
    tmp_path = comfyui_flows / f"{orig_path.stem}__modified__{uuid.uuid4().hex}.json"
    try:
        tmp_path.write_text(json.dumps(wf_obj, ensure_ascii=False, indent=2))
    except Exception as e:
        return [], f"Failed to write modified workflow: {e}"

    # If use_api is True, bypass Comfy image nodes and generate via API instead
    if use_api:
        images = []
        captions = []
        # Build a base prompt for colored floor plan
        base_prompt = ''
        if positive:
            base_prompt += positive + '. '
        if indoor_spaces:
            base_prompt += 'Indoor spaces: ' + indoor_spaces + '. '
        if interior_materials:
            base_prompt += 'Materials: ' + interior_materials + '. '
        base_prompt += 'Convert the provided black-and-white floor plan into a clean, colored 2D floor-plan illustration. Keep walls, doors and furniture accurate.'

        try:
            # generate colored floor-plan using the API; pass input image if provided
            ref_image = None
            if image_input:
                ref_image = api_generate_image(api_model or 'gemini-2.5-flash-image', base_prompt, image_input, aspect_ratio=aspect_ratio, size=f'{width}x{height}')
            else:
                ref_image = api_generate_image(api_model or 'gemini-2.5-flash-image', base_prompt, None, aspect_ratio=aspect_ratio, size=f'{width}x{height}')
            # NOTE: Do not append the colored floorplan to the returned images; keep it internal as reference.
        except Exception as e:
            return [], f'API generation failed: {e}'

        # generate space effect images
        for idx, sp in enumerate([se1, se2, se3, se4], start=1):
            if not sp:
                continue
            try:
                # Use the generated colored floorplan as reference for effect renders when available
                effect_prompt = sp
                img = api_generate_image(api_model or 'gemini-2.5-flash-image', effect_prompt, ref_image, aspect_ratio=aspect_ratio, size=f'{width}x{height}')
                if img:
                    images.append(img)
                    captions.append(f'效果图-{idx}')
            except Exception as e:
                captions.append(f'效果图-{idx} 生成失败: {e}')

        return images, '\n'.join(captions)

    # run workflow via Comfy as before
    wf = ComfyWorkflowWrapper(tmp_path)
    try:
        coro = comfy_api.queue_and_wait_images(wf, "Save Image")
        results = asyncio.run(coro)
    except Exception as e:
        # Provide a friendly message for common authorization errors
        msg = str(e)
        if "Unauthorized" in msg or "login" in msg.lower():
            hint = (
                "Comfy backend reported an authorization error. "
                "This workflow uses external Gemini nodes that require you to login or provide credentials in ComfyUI. "
                "Please open your ComfyUI backend, configure/login the Gemini/third-party node, then retry."
            )
            return [], f"Execution failed: {msg}\n\nHint: {hint}"
        return [], f"Workflow execution failed: {msg}"

    images = []
    captions = []
    items = list(results.items())

    # Heuristic grouping: if at least 7 images returned, map them to expected outputs
    # order: CAD平面图, 彩平图, 效果图 x4, 3D预览
    if len(items) >= 7:
        labels = ["CAD 平面图", "彩平图", "效果图-1", "效果图-2", "效果图-3", "效果图-4", "3D 预览"]
        for idx, (filename, image_data) in enumerate(items):
            images.append(image_data)
            if idx < len(labels):
                captions.append(f"{labels[idx]}: {filename}")
            else:
                captions.append(f"其他-{idx - len(labels) + 1}: {filename}")
    else:
        for filename, image_data in items:
            images.append(image_data)
            captions.append(filename)

    return images, "\n".join(captions)


def run_gradio_flow(layout_prompt, sketch_image, space1, space2, space3, space4, use_api=True, show_ref=False, api_model=None, aspect_ratio='16:9', enable_tripo=False, model_url=None):
    """
    Simplified flow for Gradio:
    1) Use `layout_prompt` + optional `sketch_image` to generate a hidden colored floorplan (reference image).
    2) For each non-empty space in (space1..4), generate an effect image using the colored floorplan as reference.
    Returns (images, captions, model_preview_html).
    """
    if not use_api:
        # When no external API is available, return an empty model preview (not HTML)
        return [], "External API is required for this simplified flow. Please enable Use external API.", '', 'Tripo: idle'

    model = api_model or 'gemini-2.5-flash-image'
    # Build base prompt for colored floorplan
    base_prompt = layout_prompt or ''
    if base_prompt and not base_prompt.strip().endswith('.'):
        base_prompt = base_prompt.strip() + '.'
    base_prompt += ' Convert the provided black-and-white floor plan into a clean, colored 2D floor-plan illustration. Keep walls, doors and furniture positions accurate.'

    # generate hidden colored floorplan
    # snapshot existing generated_gemini outputs so we can deterministically pick files created by this run
    outdir = basefolder / 'tools'
    outdir.mkdir(parents=True, exist_ok=True)
    prev_generated = {p.name for p in outdir.glob('generated_gemini25_from_*')}
    run_id = f"run_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    try:
        ref_image = api_generate_image(model, base_prompt, sketch_image, aspect_ratio=aspect_ratio, size='1024x576')
    except Exception as e:
        return [], f'Failed to generate colored floorplan: {e}', '', 'Tripo: idle'

    if not ref_image:
        return [], 'Colored floorplan generation returned no image.', '', 'Tripo: idle'

    # prepare space prompts and robustly generate effect images (with retries)
    spaces = [space1, space2, space3, space4]
    images = []
    captions = []
    run_log = []
    ts = int(time.time())
    run_log.append(f"Run at {time.ctime(ts)}")
    run_log.append(f"Base prompt: {base_prompt}")
    run_log.append(f"Ref image: {ref_image}")

    for idx, sp in enumerate(spaces, start=1):
        if not sp or not sp.strip():
            run_log.append(f"Space {idx} empty, skipping")
            continue
        effect_prompt = (
            f"Use the provided colored floorplan image strictly as a layout reference and produce a photorealistic, perspective interior render of the {sp}. "
            "This must be a human-eye-level (approx. 1.6m) perspective view as if standing inside the room — not a top-down plan or orthographic diagram. "
            "Do NOT output any floorplan, schematic, blueprint, or labeled diagram. Do NOT keep a birds-eye or plan projection. "
            "Show realistic materials, textures, accurate furniture placement, natural or interior lighting, shadows, and camera depth of field as in interior photography. "
            f"Style: photorealistic interior photograph for {sp}, high detail, realistic lighting, no text or labels."
        )
        run_log.append(f"Generating effect image for space {idx}: {sp}")
        out = None
        for attempt in range(3):
            try:
                out = api_generate_image(model, effect_prompt, ref_image, aspect_ratio=aspect_ratio, size='1024x576')
                if out:
                    run_log.append(f"Generated image for {sp}: {out}")
                    images.append(out)
                    captions.append(f"效果图-{idx}: {sp}")
                    break
                else:
                    run_log.append(f"Attempt {attempt+1} for {sp} returned no image")
            except Exception as e:
                run_log.append(f"Attempt {attempt+1} for {sp} failed: {e}")
        if not out:
            captions.append(f'效果图-{idx} 生成失败')

    # write run log for debugging
    try:
        outdir = basefolder / 'tools'
        outdir.mkdir(parents=True, exist_ok=True)
        log_path = outdir / f'run_gradio_flow_log_{ts}.txt'
        log_path.write_text('\n'.join(run_log), encoding='utf-8')
    except Exception:
        pass

    if not images:
        return [], 'No effect images were generated.', '', 'Tripo: idle'

    # build gallery entries as [image, caption] pairs so Gradio maps each image correctly
    gallery_entries = [[img, cap] for img, cap in zip(images, captions)]

    # if user requested to see the colored floorplan, prepend it to the gallery
    if show_ref and ref_image:
        # ensure the ref image exists on disk (helper returns a filepath)
        try:
            gallery_entries.insert(0, [ref_image, '彩平图（调试可见）'])
        except Exception:
            pass

    # Build model-viewer HTML if a remote model URL is provided, otherwise show a hint
    if model_url and str(model_url).strip():
        # sanitize URL for embedding
        safe_url = html.escape(str(model_url).strip(), quote=True)
        model_preview_html = f"""
<script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>
<div style="width:100%;height:560px;border:1px solid #ddd;background:#fafafa;display:flex;align-items:center;justify-content:center;">
  <model-viewer id="modelviewer" src="{safe_url}" alt="3D Model" style="width:100%;height:100%;" camera-controls auto-rotate interaction-prompt="auto" exposure="1" shadow-intensity="1"></model-viewer>
</div>
"""
    else:
        model_preview_html = '<div style="width:100%;height:560px;border:1px solid #ddd;display:flex;align-items:center;justify-content:center;color:#666;background:#fafafa;">3D preview: 尚无 3D 模型可预览。请在右侧或上方提供一个 glTF/GLB 模型 URL（以 https:// 开头）以进行预览。</div>'

    # Generate a deterministic hi-fidelity image from the colored floorplan (server-side, hidden)
    tripo_status_path = basefolder / 'tools' / 'tripo_status.txt'
    last_model_url_path = basefolder / 'tools' / 'last_model_url.txt'

    # hi-fi prompt used to generate the render to send to Tripo
    hi_fi_prompt = (
        "请参考提供的室内照片。生成一个高保真3D室内模型渲染，外观类似3D打印室内模型。保留建筑体量和关键纹理细节，适度游戏化风格。"
        "渲染要求：真实、基于物理的光影效果；45°等角视角；清晰定义材质（玻璃、金属、混凝土等）；纯白背景；无文字或线条。"
    )

    # attempt to create hi-fi image now (synchronous) so we have a deterministic file to submit to Tripo
    hi_fi_img = None
    try:
        outdir = basefolder / 'tools'
        outdir.mkdir(parents=True, exist_ok=True)
        hi_fi_path = outdir / f"{run_id}_hi_fi.png"
        # If a prior file exists for this run, remove it to ensure freshness
        if hi_fi_path.exists():
            try:
                hi_fi_path.unlink()
            except Exception:
                pass
        try:
            # generate hi-fi using the colored floorplan as reference
            gen = api_generate_image(api_model or 'gemini-2.5-flash-image', hi_fi_prompt, ref_image, aspect_ratio='1:1', size='1024x1024')
            if gen:
                # copy to deterministic path if helper returned a temp file
                try:
                    Path(gen).replace(hi_fi_path)
                    hi_fi_img = str(hi_fi_path)
                except Exception:
                    # fallback: copy bytes
                    try:
                        data = Path(gen).read_bytes()
                        hi_fi_path.write_bytes(data)
                        hi_fi_img = str(hi_fi_path)
                    except Exception:
                        hi_fi_img = str(gen)
        except Exception as e:
            try:
                tripo_status_path.write_text('Tripo: hi-fi generation failed: ' + str(e), encoding='utf-8')
            except Exception:
                pass

    except Exception:
        hi_fi_img = None

    def _background_tripo_work(hi_fi_image_path=None, api_key_env=None, prev_generated_names=None):
        try:
            # write queued status
            tripo_status_path.write_text('Tripo: queued', encoding='utf-8')
        except Exception:
            pass

        async def _runner():
                import base64 as _b64
                from pathlib import Path as _Path
                # Prefer using the Gemini-generated colored floorplan (the 6th generated gemini image)
                # Look for helper outputs in tools/ matching the helper naming convention and pick the 6th-from-newest
                # prefer using the explicitly provided hi-fidelity image path
                try:
                    hi_fi_img_local = hi_fi_image_path
                    if not hi_fi_img_local:
                        # if not provided, attempt to look for any generated gemini outputs as a last resort
                        out_tools = basefolder / 'tools'
                        gen_files = sorted(list(out_tools.glob('generated_gemini25_from_*')), key=lambda p: p.stat().st_mtime, reverse=True)
                        if gen_files:
                            hi_fi_img_local = str(gen_files[0])
                            try:
                                tripo_status_path.write_text('Tripo: using fallback Gemini image: ' + hi_fi_img_local, encoding='utf-8')
                            except Exception:
                                pass
                    if not hi_fi_img_local:
                        tripo_status_path.write_text('Tripo: no hi-fidelity image available for submission', encoding='utf-8')
                        return
                except Exception as e:
                    tripo_status_path.write_text('Tripo: error selecting Gemini image: ' + str(e), encoding='utf-8')
                    return

                # submit to Tripo using SDK if available, otherwise use HTTP fallback
                key = api_key_env or os.environ.get('TRIPO_API_KEY') or os.environ.get('TRIPO_KEY')
                if not key:
                    tripo_status_path.write_text('Tripo: no TRIPO_API_KEY set', encoding='utf-8')
                    return

                tripo_status_path.write_text('Tripo: submitting task', encoding='utf-8')

                # prefer SDK path — attempt normal SDK then SDK-bypass if required
                try:
                    from tripo3d import TripoClient, TaskStatus
                    try:
                        client = TripoClient(key)
                    except Exception:
                        # some SDK implementations enforce key prefix; instantiate bypass impl
                        try:
                            from tripo3d.client_impl import ClientImpl
                            client = TripoClient.__new__(TripoClient)
                            client.api_key = key
                            client.BASE_URL = getattr(TripoClient, 'BASE_URL', 'https://api.tripo3d.ai/v2/openapi')
                            client._impl = ClientImpl(key, client.BASE_URL)
                        except Exception:
                            raise

                    # try to use image_to_model if available; prefer image_to_model, then text_to_model
                    if hasattr(client, 'image_to_model'):
                        task_id = await client.image_to_model(image=str(_Path(hi_fi_img_local)), prompt='将这张3d的室内空间生成逼真材质的3d模型')
                    elif hasattr(client, 'text_to_model'):
                        task_id = await client.text_to_model(prompt='将这张3d的室内空间生成逼真材质的3d模型', image=str(_Path(hi_fi_img_local)))
                    else:
                        raise RuntimeError('Tripo SDK missing expected methods')

                    tripo_status_path.write_text('Tripo: task submitted, waiting...', encoding='utf-8')
                    task = await client.wait_for_task(task_id, verbose=True)
                    if task.status == TaskStatus.SUCCESS:
                        outdir = basefolder / 'tools' / 'tripo_output'
                        outdir.mkdir(parents=True, exist_ok=True)
                        files = await client.download_task_models(task, str(outdir))
                        if files:
                            # write last model URL for UI refresh
                            model_name = _Path(files[0]).name
                            url = f'http://127.0.0.1:8000/{model_name}'
                            last_model_url_path.write_text(url, encoding='utf-8')
                            tripo_status_path.write_text('Tripo: success. Model ready at ' + url, encoding='utf-8')
                            # attempt to ensure a static server is running (best-effort): spawn a background http.server
                            try:
                                # check if already running by trying to open the URL
                                import requests as _requests
                                r = _requests.get(url, timeout=3.0)
                                if r.status_code == 200:
                                    pass
                            except Exception:
                                # spawn a simple http.server in tripo_output (daemonized)
                                try:
                                    subprocess.Popen([sys.executable, '-m', 'http.server', '8000'], cwd=str(outdir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                except Exception:
                                    pass
                    else:
                        tripo_status_path.write_text('Tripo: task completed but not successful: ' + str(getattr(task, 'status', 'unknown')), encoding='utf-8')
                    await client.close()
                    return
                except Exception as e:
                    # SDK path failed — try HTTP fallback
                    try:
                        tripo_status_path.write_text('Tripo: SDK failed, attempting HTTP fallback: ' + str(e), encoding='utf-8')
                    except Exception:
                        pass

                # HTTP fallback: attempt multiple multipart/form-data schemas to match Tripo API expectations
                try:
                    data = _Path(hi_fi_img_local).read_bytes()
                    headers = {'Authorization': f'Bearer {key}'}
                    debug_path = basefolder / 'tools' / f'tripo_http_debug_{int(time.time())}.json'

                    # candidate field names for the file part and variations of form payload
                    file_keys = ['image', 'file', 'image_file', 'upload']
                    form_variants = [
                        {'type': 'image_to_model', 'prompt': '将这张3d的室内空间生成逼真材质的3d模型'},
                        {'task_type': 'image_to_model', 'prompt': '将这张3d的室内空间生成逼真材质的3d模型'},
                        {'type': 'image_to_model', 'inputs': json.dumps({'prompt': '将这张3d的室内空间生成逼真材质的3d模型'})},
                        {'payload': json.dumps({'type': 'image_to_model', 'prompt': '将这张3d的室内空间生成逼真材质的3d模型'})},
                    ]

                    async with httpx.AsyncClient(timeout=300.0) as ac:
                        last_exc = None
                        for fk in file_keys:
                            for form in form_variants:
                                files = {fk: ('hi_fi.png', data, 'image/png')}
                                debug = {'attempt': {'file_key': fk, 'form': form}, 'response': None}
                                try:
                                    r = await ac.post('https://api.tripo3d.ai/v2/openapi/task', headers=headers, data=form, files=files)
                                except Exception as e:
                                    last_exc = e
                                    debug['response'] = {'exception': str(e)}
                                    try:
                                        debug_path.write_text(json.dumps(debug, ensure_ascii=False, indent=2), encoding='utf-8')
                                    except Exception:
                                        pass
                                    continue

                                try:
                                    debug['response'] = {'status_code': r.status_code, 'text': r.text}
                                    debug_path.write_text(json.dumps(debug, ensure_ascii=False, indent=2), encoding='utf-8')
                                except Exception:
                                    pass

                                if r.status_code in (200, 201):
                                    try:
                                        jr = r.json()
                                    except Exception:
                                        jr = {}
                                    task_id = jr.get('id') or jr.get('task_id') or (jr.get('data') or {}).get('id')
                                    if not task_id:
                                        tripo_status_path.write_text('Tripo HTTP submit returned no task id', encoding='utf-8')
                                        return
                                    tripo_status_path.write_text('Tripo: task submitted (http), waiting...', encoding='utf-8')
                                    # poll for completion
                                    for _ in range(240):
                                        await asyncio.sleep(5)
                                        rr = await ac.get(f'https://api.tripo3d.ai/v2/openapi/task/{task_id}', headers=headers)
                                        try:
                                            js = rr.json()
                                        except Exception:
                                            js = {}
                                        status = js.get('status') or (js.get('data') or {}).get('status')
                                        if status and str(status).lower() in ('success', 'succeed'):
                                            files_arr = (js.get('data') or {}).get('files') or js.get('files') or []
                                            if files_arr:
                                                first = files_arr[0]
                                                download_url = first.get('url') or first.get('download_url') or first.get('uri')
                                                if download_url:
                                                    outdir = basefolder / 'tools' / 'tripo_output'
                                                    outdir.mkdir(parents=True, exist_ok=True)
                                                    rr2 = await ac.get(download_url)
                                                    if rr2.status_code == 200:
                                                        fn = outdir / (Path(download_url).name if '/' in download_url else f'{task_id}.glb')
                                                        fn.write_bytes(rr2.content)
                                                        url = f'http://127.0.0.1:8000/{fn.name}'
                                                        last_model_url_path.write_text(url, encoding='utf-8')
                                                        tripo_status_path.write_text('Tripo: success. Model ready at ' + url, encoding='utf-8')
                                                        try:
                                                            subprocess.Popen([sys.executable, '-m', 'http.server', '8000'], cwd=str(outdir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                                        except Exception:
                                                            pass
                                                        return
                                            tripo_status_path.write_text('Tripo: success but no files found in response', encoding='utf-8')
                                            return
                                        if status and str(status).lower() in ('failed', 'error'):
                                            tripo_status_path.write_text('Tripo: task failed', encoding='utf-8')
                                            return
                                    tripo_status_path.write_text('Tripo: timeout waiting for task', encoding='utf-8')
                                    return
                                else:
                                    # try next variant
                                    last_exc = RuntimeError(f'HTTP {r.status_code}: {r.text[:200]}')
                                    continue

                        # if we exit loops without success
                        tripo_status_path.write_text('Tripo HTTP fallback failed: ' + (str(last_exc) if last_exc else 'unknown'), encoding='utf-8')
                        return
                except Exception as e:
                    # write debug file on exception
                    try:
                        dbg = {'error': str(e)}
                        dbg_path = basefolder / 'tools' / f'tripo_http_exception_{int(time.time())}.json'
                        dbg_path.write_text(json.dumps(dbg, ensure_ascii=False, indent=2), encoding='utf-8')
                    except Exception:
                        pass
                    tripo_status_path.write_text('Tripo HTTP fallback failed: ' + str(e), encoding='utf-8')

        try:
            asyncio.run(_runner())
        except Exception:
            try:
                tripo_status_path.write_text('Tripo: background runner crashed', encoding='utf-8')
            except Exception:
                pass

    # start background worker thread only if TRIPO API key is available and user enabled Tripo
    try:
        tripo_key = os.environ.get('TRIPO_API_KEY') or os.environ.get('TRIPO_KEY')
        if tripo_key and enable_tripo:
            # pass the deterministic hi-fidelity image path (hi_fi_img) to the background worker
            thread = threading.Thread(target=_background_tripo_work, args=(hi_fi_img, tripo_key), daemon=True)
            thread.start()
            try:
                tripo_status_path.write_text('Tripo: started in background', encoding='utf-8')
            except Exception:
                pass
        else:
            try:
                if not tripo_key:
                    tripo_status_path.write_text('Tripo: no API key configured', encoding='utf-8')
                else:
                    tripo_status_path.write_text('Tripo: disabled by user (enable_tripo=False)', encoding='utf-8')
            except Exception:
                pass
    except Exception:
        pass

    # determine model path to return for Model3D component
    model_file_out = ''
    try:
        if last_model_url_path.exists():
            url = last_model_url_path.read_text(encoding='utf-8').strip()
            fname = Path(url).name
            candidate = basefolder / 'tools' / 'tripo_output' / fname
            if candidate.exists():
                model_file_out = str(candidate)
            else:
                model_file_out = url
    except Exception:
        model_file_out = ''

    # Sanitize gallery entries and model_file_out so Gradio only receives valid file paths or http(s) URLs.
    def _is_valid_path_or_url(v):
        try:
            if not v:
                return False
            if isinstance(v, (list, dict)):
                return False
            s = str(v).strip()
            # reject obvious HTML or markup
            if '<' in s or '>' in s or s.startswith('<'):
                return False
            # allow http/https URLs
            if s.startswith('http://') or s.startswith('https://'):
                return True
            # allow existing local files
            p = Path(s)
            return p.exists()
        except Exception:
            return False

    # Filter gallery entries: each entry is [img, caption]
    safe_gallery = []
    for ent in gallery_entries:
        try:
            img, cap = ent[0], ent[1] if len(ent) > 1 else ''
            if _is_valid_path_or_url(img):
                safe_gallery.append([img, cap])
            else:
                # skip invalid image entries
                continue
        except Exception:
            continue

    # Ensure model_file_out is valid; otherwise clear it so Model3D gets empty string
    if not _is_valid_path_or_url(model_file_out):
        model_file_out = ''

    tripo_status_text = tripo_status_path.read_text(encoding='utf-8') if tripo_status_path.exists() else 'Tripo: idle'

    return safe_gallery, '\n'.join(captions), model_file_out, tripo_status_text


def load_models_list_from_workspace():
    # try models_list.json in tools/
    p = basefolder / 'tools' / 'models_list.json'
    if p.exists():
        try:
            j = json.loads(p.read_text(encoding='utf-8'))
            # return list of ids
            if isinstance(j, dict) and 'data' in j:
                return [m.get('id') for m in j.get('data', []) if isinstance(m, dict)]
            if isinstance(j, list):
                return [m.get('id') if isinstance(m, dict) else str(m) for m in j]
        except Exception:
            return []
    return []


def api_generate_image(model, prompt, image_path=None, aspect_ratio='1:1', size=None):
    """
    Generate an image using either chat-style Gemini endpoint (for gemini models)
    or the images/generations endpoint for other models. Returns saved filepath or None.
    """
    api_base = os.environ.get('GOOGLE_GEMINI_BASE_URL') or os.environ.get('NANO_API_URL') or os.environ.get('API_URL') or 'https://newapi.pockgo.com'
    api_base = api_base.rstrip('/')
    api_key = os.environ.get('NANO_API_KEY') or os.environ.get('GOOGLE_API_KEY') or os.environ.get('API_KEY')
    if not api_key:
        raise RuntimeError('No API key set in environment (NANO_API_KEY or GOOGLE_API_KEY)')

    client = httpx.Client(timeout=300.0)
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

    # prepare image data URL if provided
    data_url = None
    if image_path:
        p = Path(image_path)
        if p.exists():
            data = p.read_bytes()
            b64 = base64.b64encode(data).decode('utf-8')
            if p.suffix.lower() in ('.jpg', '.jpeg'):
                data_url = f'data:image/jpeg;base64,{b64}'
            else:
                data_url = f'data:image/png;base64,{b64}'

    outdir = basefolder / 'tools'
    outdir.mkdir(parents=True, exist_ok=True)
    # If model appears to be a Gemini chat-style image model, delegate to the helper
    # but pass the actual prompt and aspect ratio so the helper can generate
    # different outputs (not always the hardcoded colored floorplan).
    if 'gemini' in (model or '').lower():
        helper = basefolder / 'tools' / 'run_gemini25_chat.py'
        if not helper.exists():
            return None

        # build command: [python, helper, <image_path?>, <prompt>, <aspect>]
        cmd = [sys.executable, str(helper)]
        if image_path:
            cmd.append(str(image_path))
        # ensure prompt is a plain string
        try:
            prompt_arg = prompt if isinstance(prompt, str) else str(prompt)
        except Exception:
            prompt_arg = ''
        cmd.append(prompt_arg)
        # pass aspect ratio as a third arg
        cmd.append(aspect_ratio or '16:9')

        # run helper with a couple of attempts (small retry for transient failures)
        for attempt in range(2):
            try:
                # snapshot existing generated files so we can identify newly created ones
                prev_set = {p.name for p in outdir.glob('generated_gemini25_from_*')}
                subprocess.run(cmd, check=False)
            except Exception:
                prev_set = {p.name for p in outdir.glob('generated_gemini25_from_*')}

            # find files created after the snapshot (new outputs)
            all_files = sorted(outdir.glob('generated_gemini25_from_*'), key=lambda p: p.stat().st_mtime, reverse=True)
            new_files = [p for p in all_files if p.name not in prev_set]
            if new_files:
                return str(new_files[0])

        # no new file created by the helper
        return None

    # other models: use /v1/images/generations
    endpoint = api_base + '/v1/images/generations'
    payload = {'model': model, 'prompt': prompt, 'size': (size if size else '1024x1024'), 'num_images': 1}
    if data_url:
        payload['image'] = data_url

    r = client.post(endpoint, headers=headers, json=payload)
    if r.status_code != 200:
        raise RuntimeError(f'API error {r.status_code}: {r.text[:1000]}')

    try:
        j = r.json()
    except Exception:
        j = None

    # save full response for debugging
    resp_path = outdir / f'images_generations_response_{uuid.uuid4().hex}.json'
    try:
        resp_path.write_text(json.dumps(j, ensure_ascii=False, indent=2))
    except Exception:
        try:
            resp_path.write_text(r.text)
        except Exception:
            pass

    # check for URL in data
    arr = (j.get('data') if isinstance(j, dict) else None) or []
    if arr and isinstance(arr, list) and isinstance(arr[0], dict):
        url = arr[0].get('url') or arr[0].get('image_url') or arr[0].get('uri')
        if url:
            rr = client.get(url, timeout=120.0)
            rr.raise_for_status()
            out_file = outdir / f'generated_api_{uuid.uuid4().hex}_{Path(url).name}'
            out_file.write_bytes(rr.content)
            return str(out_file)

    # find nested b64 like b64_json
    def find_b64(d):
        if isinstance(d, dict):
            for k, v in d.items():
                if k in ('b64_json', 'b64') and isinstance(v, str):
                    return v
                res = find_b64(v)
                if res:
                    return res
        elif isinstance(d, list):
            for it in d:
                res = find_b64(it)
                if res:
                    return res
        return None

    b64 = find_b64(j)
    if b64:
        out_file = outdir / f'generated_api_b64_{uuid.uuid4().hex}.png'
        out_file.write_bytes(base64.b64decode(b64))
        return str(out_file)

    return None
    
def structured_query(pdf_upload, prompt, json_mode):
    if pdf_upload is None:
        return "No PDF uploaded"

    try:
        # pdf_upload can be a tempfile-like object or a path
        if hasattr(pdf_upload, "name") and Path(pdf_upload.name).exists():
            src = Path(pdf_upload.name)
            dest = docs / f"{uuid.uuid4()}.pdf"
            dest.write_bytes(src.read_bytes())
        else:
            data = pdf_upload.read()
            dest = docs / f"{uuid.uuid4()}.pdf"
            dest.write_bytes(data)
    except Exception:
        return "Failed to save uploaded PDF"

    md_text = pymupdf4llm.to_markdown(dest)
    full_prompt = f"{md_text}\n{prompt}"

    if json_mode:
        response = ollama_json.invoke(full_prompt)
        try:
            return json.dumps(json.loads(response.content), indent=2)
        except Exception:
            return getattr(response, "content", str(response))
    else:
        response = ollama.invoke(full_prompt)
        return getattr(response, "content", str(response))

def extract_defaults_from_workflow(path: Path):
    # Return a mapping of common defaults found in the workflow JSON
    defaults = {
        "positive": "",
        "negative": "",
        "seed": None,
        "steps": None,
        "cfg": None,
        "sampler_name": "",
        "width": None,
        "height": None,
        "batch_size": None,
        "filename_prefix": "",
        "other_prompts": {},
        "image_path": None,
    }
    try:
        obj = json.loads(path.read_text())
    except Exception:
        return defaults

    # obj is mapping of node id -> node spec
    for nid, node in obj.items():
        inputs = node.get("inputs", {})
        meta = node.get("_meta", {})
        title = meta.get("title", "").lower()

        # common text fields
        if "text" in inputs:
            txt = inputs.get("text")
            # if text is a simple string, use it
            if isinstance(txt, str):
                if "positive" in title:
                    defaults["positive"] = txt
                elif "negative" in title:
                    defaults["negative"] = txt
                else:
                    defaults["other_prompts"][title or nid] = txt

        # numeric/simple inputs
        for key in ("seed", "steps", "cfg", "sampler_name", "width", "height", "batch_size", "filename_prefix"):
            if key in inputs:
                val = inputs.get(key)
                # if it's a primitive, set default
                if isinstance(val, (int, float, str)):
                    defaults[key] = val

        # look for image or filename inputs
        for k, v in inputs.items():
            if isinstance(v, str) and (".png" in v.lower() or ".jpg" in v.lower() or ".jpeg" in v.lower() or v.endswith('.webp')):
                p = Path(v)
                if p.exists():
                    defaults["image_path"] = str(p)
                else:
                    # maybe relative to workflows folder
                    p2 = path.parent / v
                    if p2.exists():
                        defaults["image_path"] = str(p2)

        # specific nodes for this project: capture predefined prompts if present
        # node ids used in your workflow: 70 (spaces list), 45 (interior materials),
        # 34/48/53/58 are individual effect labels
        if nid == "70":
            b = inputs.get("string_b")
            if isinstance(b, str):
                defaults["indoor_spaces"] = b
        if nid == "45":
            b = inputs.get("string_b")
            if isinstance(b, str):
                defaults["interior_materials"] = b
        if nid in ("34", "48", "53", "58"):
            b = inputs.get("string_b")
            if isinstance(b, str):
                # store in list under space_effects key
                defaults.setdefault("space_effects", {})[nid] = b

    return defaults


def load_defaults(selected_workflow):
    if not selected_workflow:
        # return empty/default values for all components
        return ["", "", None, None, None, "", None, None, None, "", "", None]

    wf_path = get_workflow_path(selected_workflow)
    d = extract_defaults_from_workflow(wf_path)
    # new order: indoor_spaces, interior_materials, space_effects(4), positive, negative, seed, steps, cfg, sampler, width, height, batch_size, filename_prefix, other_prompts, image
    other_prompts_str = json.dumps(d.get("other_prompts", {}), ensure_ascii=False, indent=2)
    indoor = d.get("indoor_spaces", "")
    materials = d.get("interior_materials", "")
    se = d.get("space_effects", {})
    # map node ids to a deterministic order: 34,48,53,58
    se34 = se.get("34", "左边客厅效果图")
    se48 = se.get("48", "卧室效果图")
    se53 = se.get("53", "卫生间效果图")
    se58 = se.get("58", "厨房效果图")

    return [indoor, materials, se34, se48, se53, se58, d.get("positive", ""), d.get("negative", ""), d.get("seed"), d.get("steps"), d.get("cfg"), d.get("sampler_name", ""), d.get("width"), d.get("height"), d.get("batch_size"), d.get("filename_prefix", ""), other_prompts_str, d.get("image_path")]


def build_ui():
    with gr.Blocks() as demo:
        gr.Markdown("# 简化流程：上传草图 → 填写材质与空间 → 生成 4 张效果图\n# Simplified Flow: Upload sketch → specify materials & spaces → generate 4 effect images")

        gr.Markdown("### 1) 彩平图（自动生成，用户不可见）\n### 1) Colored floorplan (generated, hidden from user)")
        layout_prompt = gr.Textbox(label="空间与材质（示例：木地板 客厅, 瓷砖 卫生间） / Spaces & Materials (e.g. wood floor living room, tile bathroom)", placeholder="例如：木地板 客厅, 瓷砖 卫生间 / e.g.: wood floor living room, tile bathroom", lines=1)
        sketch = gr.Image(label="上传草图（黑白平面图） / Upload sketch (B&W floorplan)", type="filepath")

        gr.Markdown("### 2) 指定要生成的 4 个空间效果图（只保留这四个）\n### 2) Specify 4 room effect renders (only these four will be generated)")
        space1 = gr.Textbox(label="空间 1 / Space 1", placeholder="例如：客厅 / e.g.: Living room")
        space2 = gr.Textbox(label="空间 2 / Space 2", placeholder="例如：卧室 / e.g.: Bedroom")
        space3 = gr.Textbox(label="空间 3 / Space 3", placeholder="例如：卫生间 / e.g.: Bathroom")
        space4 = gr.Textbox(label="空间 4 / Space 4", placeholder="例如：厨房 / e.g.: Kitchen")

        use_api = gr.Checkbox(label="使用外部 API（必需） / Use external API for image nodes (required)", value=True)
        show_colored = gr.Checkbox(label="显示彩平图（调试） / Show colored floorplan (debug)", value=False)
        aspect_ratio = gr.Dropdown(label="长宽比 / Aspect Ratio", choices=["16:9","1:1","3:2","9:16"], value="16:9")
        # If a local tripo output exists, default the Model URL to the local static server path.
        # Update default model to the most recently downloaded Tripo output so the UI previews it on load
        default_model_filename = 'eaa56d7f-2bcc-4469-a704-28dd5f51344e_pbr.glb'
        default_model_url = f'http://127.0.0.1:8000/{default_model_filename}'
        model_url = gr.Textbox(label="Model URL (glTF/GLB) / 模型 URL（glTF/GLB）", placeholder="https://example.com/model.glb", lines=1, value=default_model_url)
        tripo_enable = gr.Checkbox(label="启用 3D 生成功能（Tripo） / Enable 3D generation (Tripo)", value=False)

        run_button = gr.Button("Run / 运行")
        gallery = gr.Gallery(label="Results / 结果", elem_id="gallery")
        captions = gr.Textbox(label="Captions / 说明")

        # place a divider and then a large preview area at the bottom
        gr.Markdown("---")
        gr.Markdown("**3D Preview (自动预览) / 3D 预览（自动）**")
        # large placeholder HTML container (full width, fixed height)
        # If default_model_url is set, show the model-viewer immediately so you can preview locally-hosted GLB
        model_viewer_html = (
            "<script type=\"module\" src=\"https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js\"></script>"
            f"<div style=\"width:100%;height:560px;border:1px solid #ddd;background:#fafafa;display:flex;align-items:center;justify-content:center;\">"
            f"  <model-viewer id=\"modelviewer\" src=\"{default_model_url}\" alt=\"3D Model\" style=\"width:100%;height:100%;\" camera-controls auto-rotate interaction-prompt=\"auto\" exposure=\"1\" shadow-intensity=\"1\"></model-viewer>"
            "</div>"
        )
        # Use Gradio's Model3D output so we can display .glb/.gltf files directly
        model_preview = gr.Model3D(label="3D Model Preview / 3D 模型预览")

        # Tripo status and manual refresh
        tripo_status = gr.Textbox(label='Tripo Status / Tripo 状态', lines=1, value='Idle')
        check_preview_btn = gr.Button('Check 3D Preview / 刷新 3D 预览')

        def check_model_preview():
            status_path = basefolder / 'tools' / 'tripo_status.txt'
            url_path = basefolder / 'tools' / 'last_model_url.txt'
            status = status_path.read_text(encoding='utf-8') if status_path.exists() else 'Tripo: idle'
            # prefer local downloaded model in tools/tripo_output; if last_model_url.txt exists, resolve filename
            if url_path.exists():
                url = url_path.read_text(encoding='utf-8').strip()
                try:
                    fname = Path(url).name
                    candidate = basefolder / 'tools' / 'tripo_output' / fname
                    if candidate.exists():
                        return str(candidate), status
                    # fall back to returning the URL (gradio may load remote URL)
                    return url, status
                except Exception:
                    return '', status
            # no model yet
            return '', status

        # wire Run to simplified flow
        # run_gradio_flow now returns (gallery_entries, captions, model_file_path_or_url, tripo_status)
        run_button.click(fn=run_gradio_flow, inputs=[layout_prompt, sketch, space1, space2, space3, space4, use_api, show_colored, gr.State(value='gemini-2.5-flash-image'), aspect_ratio, tripo_enable, model_url], outputs=[gallery, captions, model_preview, tripo_status])

        # wire check preview button
        check_preview_btn.click(fn=check_model_preview, inputs=[], outputs=[model_preview, tripo_status])

    return demo

if __name__ == "__main__":
    demo = build_ui()
    demo.launch()