from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from idlerdream.collectors.files import collect_workspace_digest
from idlerdream.collectors.tests import collect_test_facts
from idlerdream.collectors.vcs import collect_vcs_facts


def test_collect_junit_report(tmp_path: Path) -> None:
    report = tmp_path / "junit.xml"
    report.write_text(
        """<?xml version=\"1.0\"?>
<testsuite tests=\"6\" failures=\"1\" errors=\"1\" skipped=\"1\">
  <testcase name=\"ok\" />
</testsuite>
""",
        encoding="utf-8",
    )
    facts = collect_test_facts(tmp_path)
    assert facts.status == "failed"
    assert facts.passed == 3
    assert facts.failed == 2
    assert facts.skipped == 1
    assert facts.source_path == str(report)


def test_collect_json_report(tmp_path: Path) -> None:
    report = tmp_path / "test-results"
    report.mkdir()
    (report / "results.json").write_text(
        json.dumps({"numPassedTests": 8, "numFailedTests": 0, "numPendingTests": 2}),
        encoding="utf-8",
    )
    facts = collect_test_facts(tmp_path)
    assert facts.status == "passed"
    assert facts.passed == 8
    assert facts.failed == 0
    assert facts.skipped == 2


def test_workspace_digest_excludes_sensitive_ignored_and_symlinked_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "src").mkdir()
    (workspace / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (workspace / ".env").write_text("SECRET=do-not-read\n", encoding="utf-8")
    (workspace / "node_modules").mkdir()
    (workspace / "node_modules" / "package.js").write_text("noise", encoding="utf-8")

    outside = tmp_path / "outside.py"
    outside.write_text("outside", encoding="utf-8")
    link = workspace / "linked.py"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable in this environment")

    digest = collect_workspace_digest(workspace)
    assert digest.considered_files == 1
    assert digest.considered_paths == ["src/main.py"]
    assert len(digest.fingerprint) == 64


def test_workspace_digest_changes_when_candidate_file_changes(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "main.py"
    source.write_text("value = 1\n", encoding="utf-8")
    before = collect_workspace_digest(workspace)
    source.write_text("value = 2\n", encoding="utf-8")
    os.utime(source, None)
    after = collect_workspace_digest(workspace)
    assert before.fingerprint != after.fingerprint


def test_collect_git_facts(tmp_path: Path) -> None:
    if subprocess.run(["git", "--version"], capture_output=True, check=False).returncode != 0:
        pytest.skip("git is unavailable")

    workspace = tmp_path / "repo"
    workspace.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(workspace)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(workspace), "config", "user.email", "idlerdream@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(workspace), "config", "user.name", "IdlerDream Tests"], check=True
    )
    tracked = workspace / "tracked.txt"
    tracked.write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(workspace), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(workspace), "commit", "-m", "initial"], check=True, capture_output=True)

    tracked.write_text("changed\n", encoding="utf-8")
    (workspace / "new.txt").write_text("new\n", encoding="utf-8")
    facts = collect_vcs_facts(workspace)

    assert facts.kind == "git"
    assert facts.branch == "main"
    assert facts.head
    assert facts.changed_files == 1
    assert facts.untracked_files == 1


def test_newer_unsupported_json_does_not_mask_valid_junit(tmp_path: Path) -> None:
    junit = tmp_path / "junit.xml"
    junit.write_text('<testsuite tests="2" failures="0" errors="0" skipped="0"/>', encoding="utf-8")
    coverage = tmp_path / "coverage.json"
    coverage.write_text(json.dumps({"lines": {"pct": 99}}), encoding="utf-8")
    os.utime(coverage, (junit.stat().st_atime + 5, junit.stat().st_mtime + 5))
    facts = collect_test_facts(tmp_path)
    assert facts.status == "passed"
    assert facts.source_path == str(junit.resolve(strict=False))
