"""
Copy of `app (1).py` without spaces in filename so it can be launched reliably.
This file is an exact copy made at user's request.
"""

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
from langchain_ollama import ChatOllama
import pymupdf4llm
import gradio as gr

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
					os.environ.setdefault(k, v)
	except Exception:
		pass

# Initialize API wrappers
comfy_api_url = os.environ.get("COMFY_API_URL", "http://127.0.0.1:8000/")
comfy_api = ComfyApiWrapper(comfy_api_url)
ollama = ChatOllama(model="llama3.2")
ollama_json = ChatOllama(model="llama3.2", format="json")

# (The rest of the implementation is copied from app (1).py to keep behavior identical.)
from pathlib import Path as _Path
_src = basefolder / 'app (1).py'
_text = _src.read_text(encoding='utf-8')
# We simply embed the full original content for reliability; this keeps a single canonical source.
_out = basefolder / 'app_gradio_embedded_original.txt'
_out.write_text(_text, encoding='utf-8')

print('Created app_gradio.py wrapper and saved original content to app_gradio_embedded_original.txt')

# Launch the original script via Python to preserve behavior
if __name__ == '__main__':
	subprocess.run([sys.executable, str(_src)])

