from __future__ import annotations

import shutil
from pathlib import Path

from ..models import VcsFacts
from ..utils.commands import run_command


def collect_vcs_facts(workspace: str | Path) -> VcsFacts:
    path = Path(workspace)
    if (path / ".jj").exists() or _is_jj_workspace(path):
        return _collect_jj(path)
    if (path / ".git").exists() or _is_git_workspace(path):
        return _collect_git(path)
    return VcsFacts(kind="none", status_summary="No Git or Jujutsu workspace detected.")


def _is_git_workspace(path: Path) -> bool:
    if not shutil.which("git"):
        return False
    result = run_command(["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"])
    return result.returncode == 0 and result.stdout.strip() == "true"


def _is_jj_workspace(path: Path) -> bool:
    if not shutil.which("jj"):
        return False
    result = run_command(["jj", "--repository", str(path), "root"])
    return result.returncode == 0


def _collect_git(path: Path) -> VcsFacts:
    if not shutil.which("git"):
        return VcsFacts(kind="git", command_error="git executable not found")

    head = run_command(["git", "-C", str(path), "rev-parse", "HEAD"])
    branch = run_command(["git", "-C", str(path), "branch", "--show-current"])
    status = run_command(
        ["git", "-C", str(path), "status", "--porcelain=v1", "--untracked-files=all"]
    )
    if status.returncode != 0:
        return VcsFacts(kind="git", command_error=status.stderr or "git status failed")

    changed = 0
    untracked = 0
    for line in status.stdout.splitlines():
        if not line:
            continue
        if line.startswith("??"):
            untracked += 1
        else:
            changed += 1

    summary = f"{changed} tracked changes, {untracked} untracked files"
    return VcsFacts(
        kind="git",
        head=head.stdout.strip() or None,
        branch=branch.stdout.strip() or None,
        changed_files=changed,
        untracked_files=untracked,
        status_summary=summary,
        command_error=head.stderr if head.returncode != 0 else None,
    )


def _collect_jj(path: Path) -> VcsFacts:
    if not shutil.which("jj"):
        return VcsFacts(kind="jj", command_error="jj executable not found")

    status = run_command(["jj", "--repository", str(path), "status"])
    change = run_command(
        [
            "jj",
            "--repository",
            str(path),
            "log",
            "-r",
            "@",
            "--no-graph",
            "-T",
            "change_id.short() ++ \" \" ++ commit_id.short()",
        ]
    )
    if status.returncode != 0:
        return VcsFacts(kind="jj", command_error=status.stderr or "jj status failed")

    changed = sum(
        1
        for line in status.stdout.splitlines()
        if line.startswith(("A ", "M ", "D ", "R ", "C "))
    )
    return VcsFacts(
        kind="jj",
        head=change.stdout.strip() or None,
        changed_files=changed,
        status_summary=status.stdout.strip()[:2000],
    )
