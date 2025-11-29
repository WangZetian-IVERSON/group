# Comfy — 本地开发环境说明




https://github.com/user-attachments/assets/e849bd85-f0e4-4be5-8702-7691b59f68e0

Project Introduction: 
This project is to simplify the interior design workflow, and interior design workers usually need to spend a lot of time connecting with customers.
For example, after the floor plan sketch is drawn, it needs to be connected with the user once, and after the model is built, it needs to be connected with the user once, and the intermediate program is quite time-consuming. 
In this project, users can generate color floor plans, renderings, and 3D models from floor sketches by entering the simplest prompts to describe the space and materials, and can make design ideas and communicate with customers in the shortest time

<img width="1024" height="1024" alt="nanobanana-edited-2025-11-29T09-53-36-229Z" src="https://github.com/user-attachments/assets/c5516307-820d-48ad-bea6-06ed89b3240d" />




下面的说明帮助你在 Windows (PowerShell) 上创建并使用项目虚拟环境，以及如何安装依赖。

1) 激活虚拟环境（PowerShell）

```powershell
# 第一次创建虚拟环境（如果尚未创建）
# 在项目根目录执行（可选，如果已经存在 .venv 可跳过）
python -m venv .venv

# 激活 venv
.\.venv\Scripts\Activate.ps1
```

2) 从 `requirements.txt` 安装依赖

```powershell
pip install -r requirements.txt
```

3) 运行项目（使用 Gradio UI）

```powershell
# 激活 venv 后
.\.venv\Scripts\Activate.ps1

# 启动 Gradio 应用
.\.venv\Scripts\python.exe "app (1).py"
```

注意：Comfy 后端 API 默认地址现在是 `http://127.0.0.1:8000/`（因为你提到 ComfyUI 监听 8000 端口）。如果你的后端运行在不同地址或端口，可以通过环境变量覆盖：

```powershell
# 在 PowerShell 中设置并启动
$env:COMFY_API_URL = 'http://127.0.0.1:8188/'  # 或者改成你的实际地址
.\.venv\Scripts\python.exe "app (1).py"
```

Using the Gemini API key locally
-------------------------------

This project can load a local `.env` file placed in the repository root. The file should contain lines like:

COMFY_GEMINI_API_KEY=your_api_key_here

I have created a `.env` file in the project root for you (it contains the key you provided). To make sure the Comfy backend (ComfyUI) can use the key, the backend process must be started with the same environment variable available. Example PowerShell workflow:

```powershell
# Load the COMFY_GEMINI_API_KEY value from .env and set it into the current session
$val = (Get-Content .env | Select-String -Pattern '^COMFY_GEMINI_API_KEY=').ToString() -replace '^COMFY_GEMINI_API_KEY=',''
$env:COMFY_GEMINI_API_KEY = $val
# 然后以该 PowerShell 会话启动 Comfy 后端，例如：
# .\start_comfy_backend.ps1
# 或者运行你平时用来启动 Comfy 的命令

# Now (re)start your Comfy backend so it inherits this environment variable.
# Exact restart depends on how you run ComfyUI; for example if you run a start script:
.\start_comfy_backend.ps1

# Or if you run it manually, ensure you start it from the same PowerShell session where
# $env:COMFY_GEMINI_API_KEY is set so the backend can read it.
```

If you prefer not to use an env file, you can also add the key into the ComfyUI plugin settings (if the Gemini plugin exposes a saved API key) via the ComfyUI web UI. After updating any credentials, restart the Comfy backend to ensure the API calls from saved workflows can access the credential.

注意与后续事项

- 我检测到 `app (1).py` 中导入了 `comfy_api_simplified`，但该模块在当前环境中不可用（可能是本地模块或私有包）。请确保该包存在于项目中或提供可通过 pip 安装的包名。
- 我已经在 `requirements.txt` 中导出当前虚拟环境的依赖，你可以使用上面的命令安装这些依赖。

如果你希望我：
- 把 `comfy_api_simplified` 加入仓库（例如把它作为本地模块），或
- 尝试从特定私有索引或本地路径安装该模块，
请告诉我你希望如何提供该包（例如：私有 PyPI URL、wheel 文件、或把源码放在仓库内）。
