"""Process collector fixtures and Windows integration tests (CR-21).

Unit tests cover the association heuristics with fake process trees for
OpenCode, Codex, Claude Code, Windows Terminal and VS Code integrated
terminals, plus first-sample CPU semantics. A real subprocess is spawned in
the Windows integration test to exercise the actual psutil CWD path.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fixtures.processes import (
    claude_nested,
    codex_in_subdirectory,
    fake_process_iter,
    opencode_direct,
    unrelated_agent,
    vscode_integrated_terminal_agent,
    windows_terminal_agent,
    windows_terminal_denied_cwd,
)

from idlerdream.collectors.processes import CpuSampler, ProcessCollector
from idlerdream.models import Project

AGENT_NAMES = {"opencode", "opencode.exe", "codex", "codex.exe", "claude", "claude.exe"}


def _collector(*processes, cpu: CpuSampler | None = None) -> ProcessCollector:
    return ProcessCollector(
        AGENT_NAMES,
        process_iter=fake_process_iter(*processes),
        cpu_sampler=cpu or CpuSampler(),
    )


def _project(tmp_path: Path) -> Project:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return Project(name="demo", path=str(workspace))


def test_opencode_direct_association(tmp_path: Path) -> None:
    process = opencode_direct(tmp_path / "workspace")
    agents = _collector(process).collect_for_project(_project(tmp_path))
    assert [item.pid for item in agents] == [process.pid]
    assert agents[0].association_confidence >= 0.65


def test_codex_subdirectory_association(tmp_path: Path) -> None:
    process = codex_in_subdirectory(tmp_path / "workspace")
    agents = _collector(process).collect_for_project(_project(tmp_path))
    assert agents[0].pid == process.pid
    assert agents[0].association_confidence >= 0.5


def test_claude_nested_association(tmp_path: Path) -> None:
    process = claude_nested(tmp_path / "workspace")
    agents = _collector(process).collect_for_project(_project(tmp_path))
    assert agents[0].pid == process.pid
    assert agents[0].association_confidence >= 0.5


def test_windows_terminal_tree_association(tmp_path: Path) -> None:
    process = windows_terminal_agent(tmp_path / "workspace")
    agents = _collector(process).collect_for_project(_project(tmp_path))
    assert agents[0].pid == process.pid
    assert agents[0].association_confidence >= 0.65
    assert agents[0].name == "opencode.exe"


def test_windows_terminal_denied_cwd_is_recovered_from_host(tmp_path: Path) -> None:
    """CWD AccessDenied on the Agent must not lose the association."""
    process = windows_terminal_denied_cwd(tmp_path / "workspace")
    agents = _collector(process).collect_for_project(_project(tmp_path))
    assert agents[0].pid == process.pid
    assert agents[0].association_confidence >= 0.25


def test_vscode_integrated_terminal_association(tmp_path: Path) -> None:
    process = vscode_integrated_terminal_agent(tmp_path / "workspace")
    agents = _collector(process).collect_for_project(_project(tmp_path))
    assert agents[0].pid == process.pid
    assert agents[0].association_confidence >= 0.8
    assert len(agents[0].children) == 0  # agent tree, not the host tree


def test_unrelated_agent_is_excluded(tmp_path: Path) -> None:
    process = unrelated_agent()
    agents = _collector(process).collect_for_project(_project(tmp_path))
    assert agents == []


def test_agents_sorted_by_confidence_descending(tmp_path: Path) -> None:
    direct = opencode_direct(tmp_path / "workspace")
    nested = claude_nested(tmp_path / "workspace")
    agents = _collector(direct, nested).collect_for_project(_project(tmp_path))
    confidences = [item.association_confidence for item in agents]
    assert confidences == sorted(confidences, reverse=True)


class _FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_cpu_sampler_first_sample_is_zero_then_delta() -> None:
    clock = _FakeClock()
    sampler = CpuSampler(clock=clock)
    assert sampler.sample(1, 100.0, cpu_total=5.0) == 0.0  # baseline only
    clock.now += 10.0
    assert sampler.sample(1, 100.0, cpu_total=15.0) == pytest.approx(100.0)
    clock.now += 10.0
    assert sampler.sample(1, 100.0, cpu_total=16.0) == pytest.approx(10.0)


def test_cpu_sampler_treats_new_process_as_new_baseline() -> None:
    clock = _FakeClock()
    sampler = CpuSampler(clock=clock)
    assert sampler.sample(1, 100.0, cpu_total=5.0) == 0.0
    clock.now += 10.0
    assert sampler.sample(1, 101.0, cpu_total=5.0) == 0.0  # create_time changed


def test_cpu_percent_populated_in_model_after_second_sample(tmp_path: Path) -> None:
    clock = _FakeClock()
    cpu = CpuSampler(clock=clock)
    collector = _collector(opencode_direct(tmp_path / "workspace"), cpu=cpu)
    project = _project(tmp_path)

    first = collector.collect_for_project(project)
    assert first[0].cpu_percent == 0.0  # first sample semantics: baseline only

    clock.now += 5.0
    second = collector.collect_for_project(project)
    assert second[0].cpu_percent > 0.0


@pytest.mark.skipif(os.name != "nt", reason="spawns a real Windows process")
def test_real_windows_process_cwd_association(tmp_path: Path) -> None:
    """Spawn a real process in the workspace and verify psutil CWD association."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        cwd=str(workspace),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        collector = ProcessCollector({"python", "python.exe"})
        deadline = time.monotonic() + 10
        matched = None
        while time.monotonic() < deadline:
            agents = collector.collect_for_project(
                Project(name="demo", path=str(workspace))
            )
            matched = next((item for item in agents if item.pid == child.pid), None)
            if matched is not None:
                break
            time.sleep(0.2)
        assert matched is not None, "spawned process was not associated to the workspace"
        assert matched.association_confidence >= 0.25
        assert matched.cwd is not None
        assert Path(matched.cwd).resolve(strict=False) == workspace.resolve(strict=False)
    finally:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
