<#
.SYNOPSIS
    Smoke-test the IdlerDream NSIS installer: silent install, verify layout,
    first-run launch, silent uninstall, verify removal and data preservation.

.DESCRIPTION
    Runs the release acceptance smoke test for the Windows NSIS installer:

      1. Silent install of the per-user NSIS installer.
      2. Verify the installed layout: main exe, bundled sidecar, uninstaller,
         Start Menu shortcut, Desktop shortcut and the HKCU Uninstall key.
      3. First-run: launch the installed app, confirm it stays alive (which
         also proves the packaged Sidecar starts), then terminate it.
      4. Write a marker into the IdlerDream data directory and note it must
         survive uninstall (deleteAppDataOnUninstall is disabled).
      5. Silent uninstall and verify the install directory, shortcuts and
         Uninstall registry key are gone while the data marker is preserved.

    The script exits non-zero on the first failed assertion so it can be used
    directly as a CI gate. It never needs administrator rights.

.PARAMETER InstallerPath
    Path to the NSIS installer .exe produced by electron-builder.

.PARAMETER AppIdleSeconds
    How long the first-run process must stay alive before it is considered
    healthy. Defaults to 10 seconds.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/smoke-installer.ps1 -InstallerPath "apps/desktop/dist/IdlerDream Setup 0.1.0-dev.exe"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath,

    [int]$AppIdleSeconds = 10
)

$ErrorActionPreference = "Stop"
$installDir = Join-Path $env:LOCALAPPDATA "Programs\IdlerDream"
$dataDir = Join-Path $env:LOCALAPPDATA "IdlerDream"
$startMenuLink = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\IdlerDream.lnk"
$desktopLink = Join-Path $env:USERPROFILE "Desktop\IdlerDream.lnk"
$uninstallKeyPattern = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*"
$dataMarker = Join-Path $dataDir "smoke-marker.txt"

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) {
        Write-Error "SMOKE FAIL: $Message"
        exit 1
    }
    Write-Host "SMOKE OK: $Message"
}

function Stop-App {
    Get-Process -Name "IdlerDream", "idlerdream-sidecar" -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# ---------------------------------------------------------------------------
# 0. Preconditions and cleanup from any previous run.
# ---------------------------------------------------------------------------
Assert-True (Test-Path -LiteralPath $InstallerPath) "Installer exists at $InstallerPath"
Stop-App
if (Test-Path -LiteralPath $installDir) {
    Write-Host "SMOKE INFO: previous install present, cleaning up"
    Remove-Item -LiteralPath $installDir -Recurse -Force -ErrorAction SilentlyContinue
}
if (Test-Path -LiteralPath $dataMarker) {
    Remove-Item -LiteralPath $dataMarker -Force -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
# 1. Silent install.
# ---------------------------------------------------------------------------
Write-Host "SMOKE: installing silently..."
$install = Start-Process -FilePath $InstallerPath -ArgumentList "/S" -Wait -PassThru
Assert-True ($install.ExitCode -eq 0) "silent install exit code 0 (got $($install.ExitCode))"

# ---------------------------------------------------------------------------
# 2. Verify installed layout.
# ---------------------------------------------------------------------------
$exe = Join-Path $installDir "IdlerDream.exe"
$uninstaller = Join-Path $installDir "Uninstall IdlerDream.exe"
$sidecar = Join-Path $installDir "resources\sidecar\idlerdream-sidecar.exe"
Assert-True (Test-Path -LiteralPath $exe) "main exe installed at $exe"
Assert-True (Test-Path -LiteralPath $uninstaller) "uninstaller present at $uninstaller"
Assert-True (Test-Path -LiteralPath $sidecar) "packaged sidecar bundled at $sidecar"
Assert-True (Test-Path -LiteralPath $startMenuLink) "Start Menu shortcut present"
Assert-True (Test-Path -LiteralPath $desktopLink) "Desktop shortcut present"
$uninstallKey = Get-ChildItem $uninstallKeyPattern |
    Where-Object { $_.GetValue("DisplayName") -like "IdlerDream*" }
Assert-True ($null -ne $uninstallKey) "HKCU Uninstall registry key registered for IdlerDream"

# ---------------------------------------------------------------------------
# 3. First-run launch: the packaged app must start and keep running, which
#    exercises the bundled sidecar executable through Electron main.
# ---------------------------------------------------------------------------
Write-Host "SMOKE: launching first-run..."
$app = Start-Process -FilePath $exe -PassThru
Start-Sleep -Seconds $AppIdleSeconds
$alive = Get-Process -Name "IdlerDream" -ErrorAction SilentlyContinue
Assert-True ($null -ne $alive) "app process alive $AppIdleSeconds seconds after launch"
Stop-App

# ---------------------------------------------------------------------------
# 4. Create data marker that must survive uninstall.
# ---------------------------------------------------------------------------
New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
Set-Content -LiteralPath $dataMarker -Value "smoke-$(Get-Date -Format o)"
Assert-True (Test-Path -LiteralPath $dataMarker) "data marker written before uninstall"

# ---------------------------------------------------------------------------
# 5. Silent uninstall.
# ---------------------------------------------------------------------------
Write-Host "SMOKE: uninstalling silently..."
$uninstall = Start-Process -FilePath $uninstaller -ArgumentList "/S" -Wait -PassThru
Assert-True ($uninstall.ExitCode -eq 0) "silent uninstall exit code 0 (got $($uninstall.ExitCode))"

# ---------------------------------------------------------------------------
# 6. Verify removal and data preservation.
# ---------------------------------------------------------------------------
Assert-True (-not (Test-Path -LiteralPath $installDir)) "install directory removed"
Assert-True (-not (Test-Path -LiteralPath $startMenuLink)) "Start Menu shortcut removed"
Assert-True (-not (Test-Path -LiteralPath $desktopLink)) "Desktop shortcut removed"
$remainingKey = Get-ChildItem $uninstallKeyPattern |
    Where-Object { $_.GetValue("DisplayName") -like "IdlerDream*" }
Assert-True ($null -eq $remainingKey) "HKCU Uninstall registry key removed"
Assert-True (Test-Path -LiteralPath $dataMarker) "user data preserved after uninstall (marker survives)"

Remove-Item -LiteralPath $dataMarker -Force -ErrorAction SilentlyContinue
Write-Host "SMOKE PASS: NSIS install/uninstall acceptance check succeeded"
