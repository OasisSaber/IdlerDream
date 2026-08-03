from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ..security.redaction import redact_text


@dataclass(slots=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


def run_command(
    args: Sequence[str],
    *,
    cwd: str | Path | None = None,
    timeout: float = 15.0,
    env: dict[str, str] | None = None,
) -> CommandResult:
    safe_env = os.environ.copy()
    if env:
        safe_env.update(env)
    try:
        completed = subprocess.run(
            list(args),
            cwd=str(cwd) if cwd else None,
            env=safe_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
        )
        return CommandResult(
            args=tuple(args),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=redact_text(completed.stderr),
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            args=tuple(args),
            returncode=-1,
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr="Command timed out",
            timed_out=True,
        )
    except OSError as exc:
        return CommandResult(
            args=tuple(args),
            returncode=-1,
            stdout="",
            stderr=redact_text(str(exc)),
        )
