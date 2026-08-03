$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $Root "apps\sidecar")
python -m pip install -e ".[dev]"
pyinstaller --noconfirm --clean --onefile --name idlerdream-sidecar idlerdream/main.py
