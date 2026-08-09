from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass(slots=True)
class OpenCodeRunProfile:
    """Per-inspection OpenCode profile with deterministic cleanup.

    Each inspection receives a distinct HOME, XDG data directory and config
    directory. This prevents concurrent inspections from overwriting each
    other's provider credentials, session/cache files or runtime configuration.
    ``TemporaryDirectory`` also provides cleanup when an exception happens
    before the adapter reaches its explicit ``finally`` block.
    """

    _temporary_directory: tempfile.TemporaryDirectory
    root: Path
    home: Path
    config_dir: Path

    @classmethod
    def create(cls, base_dir: Path, job_id: str) -> OpenCodeRunProfile:
        runtime_root = Path(base_dir).resolve(strict=False) / "run-profiles"
        runtime_root.mkdir(parents=True, exist_ok=True)
        safe_job_id = (
            _SAFE_SEGMENT.sub("_", str(job_id)).strip("._")[:80] or "inspection"
        )
        temporary_directory = tempfile.TemporaryDirectory(
            prefix=f"{safe_job_id}-",
            dir=runtime_root,
        )
        root = Path(temporary_directory.name).resolve(strict=False)
        home = root / "home"
        config_dir = root / "config"
        for directory in (
            root,
            home,
            config_dir,
            home / "config",
            home / "data",
            home / "cache",
        ):
            directory.mkdir(parents=True, exist_ok=True)
            try:
                directory.chmod(0o700)
            except OSError:
                pass
        return cls(
            _temporary_directory=temporary_directory,
            root=root,
            home=home,
            config_dir=config_dir,
        )

    def cleanup(self) -> None:
        self._temporary_directory.cleanup()
