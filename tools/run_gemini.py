import os
import sys
import traceback
from pathlib import Path

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None

try:
    from PIL import Image
except Exception:
    Image = None


def main():
    # Try common env var names for a Google G
    # 
    # 
    # 
    # 
    # 
    # 
    # 
    # 
    # 
    # enAI API key
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("COMFY_GEMINI_API_KEY")
    out_path = Path(__file__).parent.parent / "generated_image.png"

    if genai is None:
        print("google-genai package is not installed. Please run pip install google-genai")
        sys.exit(2)

    if Image is None:
        print("Pillow is not installed. Please run pip install pillow")
        sys.exit(2)

    if not api_key:
        print("No API key found. Please set environment variable `GOOGLE_API_KEY` or `COMFY_GEMINI_API_KEY`.")
        print("Example (PowerShell): $env:GOOGLE_API_KEY = 'your_key_here' ; f:.\\comfy\\.venv\\Scripts\\python.exe tools\\run_gemini.py")
        sys.exit(1)

    try:
        # Instantiate client; pass api_key if supported by SDK
        try:
            client = genai.Client(api_key=api_key)
        except TypeError:
            # fallback if Client doesn't accept api_key param
            client = genai.Client()
            os.environ.setdefault("GOOGLE_API_KEY", api_key)

        prompt = (
            "Create a picture of a nano banana dish in a fancy restaurant with a Gemini theme"
        )

        print("Sending generation request...")
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt],
        )

        saved = False
        for i, part in enumerate(response.parts):
            if getattr(part, "text", None):
                print(part.text)
            elif getattr(part, "inline_data", None) is not None:
                image = part.as_image()
                # Save each image with index
                p = out_path.with_name(f"generated_image_{i}.png")
                image.save(p)
                print(f"Saved image to: {p}")
                saved = True

        if not saved:
            print("No image parts returned in response.")

    except Exception as e:
        print("Exception during generation:")
        traceback.print_exc()
        sys.exit(3)


if __name__ == "__main__":
    main()
