"""PyInstaller entry point for the packaged IdlerDream Sidecar executable.

PyInstaller executes the entry script as ``__main__`` with no package context,
so passing ``idlerdream/main.py`` directly fails on the relative imports inside
the package (``from .api import ...``). This thin launcher imports the real
entry function through the package's normal module path, which makes the
relative imports resolve correctly. The installed console script
(``idlerdream-sidecar = idlerdream.main:run``) calls the same ``run()``.
"""

from idlerdream.main import run

if __name__ == "__main__":
    run()
