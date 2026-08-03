# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the IdlerDream Sidecar executable (CR-24).

Build from anywhere, paths resolve relative to this spec file:

    python -m PyInstaller --noconfirm --clean apps/sidecar/idlerdream-sidecar.spec

The ``launcher.py`` script is the PyInstaller entry point. PyInstaller cannot
use ``idlerdream.main.py`` directly because it executes the entry script as
``__main__`` and the package's relative imports then fail. The launcher imports
``idlerdream.main:run`` (the same function as the installed console script),
so relative imports inside the ``idlerdream`` package resolve correctly.
"""

from pathlib import Path

ROOT = Path(SPECPATH).resolve()

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="idlerdream-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
