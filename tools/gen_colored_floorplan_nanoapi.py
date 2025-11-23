import os
import sys
import json
import base64
from pathlib import Path

import httpx

API_URL = os.environ.get("NANO_API_URL", "https://nanoapi.poloai.top")
API_KEY = os.environ.get("NANO_API_KEY")
MODEL = "doubao-seedream-4-0-250828"


def read_image_b64(path: Path) -> str:
    with path.open("rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def save_image_from_dataurl(dataurl: str, out_path: Path):
    # dataurl may be 'data:image/png;base64,...' or a raw base64 string
    if dataurl.startswith("data:"):
        parts = dataurl.split(",", 1)
        b64 = parts[1]
    else:
        b64 = dataurl
    data = base64.b64decode(b64)
    with out_path.open("wb") as f:
        f.write(data)


def main():
    if not API_KEY:
        print("Error: NANO_API_KEY environment variable is required.")
        sys.exit(2)

    # input image path (floorplan) - default uses workspace file if present
    default_input = Path("floorplan_input.png")
    # Accept first CLI arg as input image path
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
    else:
        # try to find an image in workspace (the user's attachment)
        # check common names used earlier: 'floorplan.png', 'floorplan.jpg'
        candidates = [Path("floorplan.png"), Path("floorplan.jpg"), Path("attachment.png"), Path("plan.png"), Path("plan.jpg")]
        if default_input.exists():
            input_path = default_input
        else:
            found = None
            for c in candidates:
                if c.exists():
                    found = c
                    break
            if found:
                input_path = found
            else:
                # fallback to the user-supplied path in workspace (attachment from UI saved earlier)
                # If none found, instruct user
                print("No input image found. Provide path as first arg (e.g. tools/gen_colored_floorplan_nanoapi.py path/to/plan.png)")
                sys.exit(3)

    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        sys.exit(4)

    out_path = Path("generated_floorplan_colored.png")

    prompt = (
        "Convert the provided black-and-white architectural floor plan into a clean, colored, readable 2D floor-plan illustration. "
        "Keep walls, doors and furniture layout accurate. Use soft pastel colors for rooms: living room (warm beige), bedroom (light blue), kitchen (soft yellow), bathroom (light gray). "
        "Add clear labels for rooms (living room, bedroom, kitchen, bathroom) in a simple sans-serif font, and a neat legend showing colors for each room. "
        "Output should be a flat 2D vector-like PNG with high contrast lines and clean fills, resolution ~1024x1024. "
        "Do not add extra furniture beyond what is on the input image."
    )

    img_b64 = read_image_b64(input_path)

    payload = {
        "model": MODEL,
        "prompt": prompt,
        # pass the input image as an 'image' or 'image[]' depending on server; try common field 'image'
        "image": img_b64,
        "size": "1024x1024",
        # some instances accept additional params
        "quality": "high",
        "num_images": 1,
    }

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    # use the same endpoint form that worked in other tools
    url = API_URL.rstrip("/") + "/v1/images/generations"

    print(f"Querying {url} with model={MODEL}")

    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=120)
    except Exception as e:
        print("Request error:", e)
        sys.exit(5)

    print("Status:", resp.status_code)
    if resp.status_code != 200:
        try:
            print(resp.json())
        except Exception:
            print(resp.text)
        sys.exit(6)

    data = resp.json()

    # Response may include 'data' list with 'b64_json' or 'url'. Handle common shapes.
    image_data = None
    if isinstance(data, dict) and "data" in data:
        d0 = data["data"][0]
        if isinstance(d0, dict) and "b64_json" in d0:
            image_data = d0["b64_json"]
        elif isinstance(d0, dict) and "url" in d0:
            # download the url
            img_url = d0["url"]
            print("Downloading returned URL:", img_url)
            r2 = httpx.get(img_url, timeout=120)
            if r2.status_code == 200:
                with out_path.open("wb") as f:
                    f.write(r2.content)
                print("Saved to", out_path)
                return
            else:
                print("Failed to download image URL", r2.status_code)
                sys.exit(7)
        elif isinstance(d0, str):
            image_data = d0

    # some servers return 'image' field directly
    if not image_data and isinstance(data, dict):
        for k in ("image", "b64", "base64"):
            if k in data:
                image_data = data[k]
                break

    if not image_data:
        print("No image data found in response:")
        print(json.dumps(data)[:2000])
        sys.exit(8)

    save_image_from_dataurl(image_data, out_path)
    print("Saved to", out_path)


if __name__ == "__main__":
    main()
