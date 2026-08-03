from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ..config import DEFAULT_IGNORE_DIRS
from ..security.paths import is_sensitive_path
from ..utils.commands import run_command

TEXT_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".jsonc",
    ".toml",
    ".yaml",
    ".yml",
    ".md",
    ".txt",
    ".css",
    ".scss",
    ".html",
    ".sql",
    ".rs",
    ".go",
    ".java",
    ".kt",
    ".swift",
    ".cpp",
    ".c",
    ".h",
    ".cs",
    ".sh",
    ".ps1",
}


@dataclass(slots=True)
class WorkspaceDigest:
    fingerprint: str
    considered_paths: list[str]
    considered_files: int
    warnings: list[str]


def collect_workspace_digest(
    workspace: str | Path,
    *,
    ignore_dirs: set[str] | None = None,
    max_files: int = 100_000,
    content_hash_budget_bytes: int = 32 * 1024 * 1024,
) -> WorkspaceDigest:
    root = Path(workspace).resolve(strict=False)
    ignored = set(ignore_dirs or DEFAULT_IGNORE_DIRS)
    warnings: list[str] = []
    paths = _candidate_paths(root, ignored, max_files, warnings)
    hasher = hashlib.sha256()
    considered_paths: list[str] = []
    count = 0
    remaining_content_budget = max(0, content_hash_budget_bytes)
    content_budget_exhausted = False

    for path in paths:
        try:
            stat = path.stat()
        except OSError:
            continue
        relative = path.relative_to(root).as_posix()
        hasher.update(relative.encode("utf-8", errors="replace"))
        hasher.update(str(stat.st_size).encode())
        hasher.update(str(stat.st_mtime_ns).encode())
        # Metadata alone can miss a same-size rewrite on filesystems with coarse
        # timestamp resolution. Hash file content while the bounded I/O budget
        # allows it, then fall back to metadata for the remainder of very large
        # workspaces.
        if stat.st_size <= remaining_content_budget:
            try:
                with path.open("rb") as handle:
                    while chunk := handle.read(64 * 1024):
                        hasher.update(chunk)
                remaining_content_budget -= stat.st_size
            except OSError:
                warnings.append(f"Could not read {relative} while fingerprinting")
        elif not content_budget_exhausted:
            warnings.append(
                f"Content hashing capped at {content_hash_budget_bytes} bytes; "
                "remaining files use metadata only"
            )
            content_budget_exhausted = True
        count += 1
        if len(considered_paths) < 200:
            considered_paths.append(relative)

    return WorkspaceDigest(
        fingerprint=hasher.hexdigest(),
        considered_paths=considered_paths,
        considered_files=count,
        warnings=warnings,
    )


def _candidate_paths(
    root: Path,
    ignore_dirs: set[str],
    max_files: int,
    warnings: list[str],
) -> Iterable[Path]:
    git_paths = _git_tracked_and_untracked(root)
    if git_paths is not None:
        yielded = 0
        for relative in git_paths:
            path = root / relative
            if _is_candidate(path, root, ignore_dirs):
                yield path
                yielded += 1
                if yielded >= max_files:
                    warnings.append(f"File scan capped at {max_files} entries")
                    return
        return

    yielded = 0
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in ignore_dirs and not (Path(current) / name).is_symlink()
        ]
        for name in filenames:
            path = Path(current) / name
            if _is_candidate(path, root, ignore_dirs):
                yield path
                yielded += 1
                if yielded >= max_files:
                    warnings.append(f"File scan capped at {max_files} entries")
                    return


def _git_tracked_and_untracked(root: Path) -> list[str] | None:
    if not (root / ".git").exists():
        return None
    result = run_command(
        [
            "git",
            "-C",
            str(root),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        timeout=30,
    )
    if result.returncode != 0:
        return None
    return [item for item in result.stdout.split("\0") if item]


def _is_candidate(path: Path, root: Path, ignore_dirs: set[str]) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    if path.is_symlink() or is_sensitive_path(path):
        return False
    if any(part in ignore_dirs for part in relative.parts[:-1]):
        return False
    if path.suffix.lower() not in TEXT_EXTENSIONS and path.name not in {
        "Dockerfile",
        "Makefile",
        "README",
        "LICENSE",
    }:
        return False
    try:
        return path.is_file() and path.stat().st_size <= 5 * 1024 * 1024
    except OSError:
        return False
