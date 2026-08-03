$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $Root "apps\sidecar")
python -m pip install -e ".[dev]"
# The committed spec uses launcher.py as the PyInstaller entry point: a bare
# `idlerdream/main.py` entry is executed as `__main__` and its relative imports
# crash the packaged exe (CR-24 / issue #13).
python -m PyInstaller --noconfirm --clean idlerdream-sidecar.spec
