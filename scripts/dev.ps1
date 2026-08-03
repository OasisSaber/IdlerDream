$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $Root "apps\sidecar"
$env:IDLERDREAM_MOCK_INSPECTOR = "1"
$env:IDLERDREAM_DEV_CONTROL_HTTP = "1"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root'; python -m idlerdream.main"
Set-Location $Root
npm run dev
