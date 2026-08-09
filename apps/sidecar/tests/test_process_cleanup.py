"""Regression: exception paths must not leak a running OpenCode process.

CR21 follow-up review (PR #21 final CodeReview) found that a callback or
parser exception could leave the OpenCode child process running while the
profile/snapshot were already cleaned up. The inspect() finally block now
terminates a still-running process (CTRL_BREAK on Windows, terminate
elsewhere, process-tree fallback) before cleanup.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from idlerdream.inspection.opencode import OpenCodeAdapter
from idlerdream.models import FactBaseline, Project


class FakeProcess:
    """A subprocess stand-in that never exits on its own."""

    def __init__(self) -> None:
        self.pid = 424242
        self.returncode: int | None = None
        self._terminated = False
        self._killed = False
        self._exit_event = asyncio.Event()
        # stdout/stderr streams that close immediately (no events).
        self.stdout = _EmptyStream()
        self.stderr = _EmptyStream()

    def send_signal(self, sig: object) -> None:
        self._terminated = True
        self.returncode = 1
        self._exit_event.set()

    def terminate(self) -> None:
        self._terminated = True
        self.returncode = 1
        self._exit_event.set()

    async def wait(self) -> int:
        # Simulate a real child: block until terminated, then report the code.
        # An already-exited process returns immediately.
        if self.returncode is None:
            await self._exit_event.wait()
        return self.returncode if self.returncode is not None else 1

    @property
    def terminated(self) -> bool:
        return self._terminated


class _EmptyStream:
    async def readline(self) -> bytes:
        return b""


class _OneEventStream:
    """Emits a single assistant-text event, then EOF."""

    def __init__(self) -> None:
        import json

        self._payload = json.dumps(
            {
                "type": "text",
                "part": {"type": "text", "text": "assistant text"},
            }
        ).encode()
        self._sent = False

    async def readline(self) -> bytes:
        if not self._sent:
            self._sent = True
            return self._payload
        return b""


def _make_project(tmp_path: Path) -> Project:
    return Project(name="cleanup", path=str(tmp_path), metadata={"private": str(tmp_path)})


def _make_baseline(project: Project) -> FactBaseline:
    return FactBaseline(
        project_id=project.id,
        workspace_path=project.path,
        workspace_fingerprint="fp-cleanup",
        considered_paths=["README.md"],
    )


def test_callback_exception_terminates_process_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        (workspace / "README.md").write_text("# cleanup fixture", encoding="utf-8")
        project = _make_project(workspace)

        fake = FakeProcess()
        fake.stdout = _OneEventStream()  # emit one event so on_progress fires mid-run
        created: list[FakeProcess] = []

        async def fake_create_subprocess_exec(*args, **kwargs):
            created.append(fake)
            return fake

        # opencode.py calls asyncio.create_subprocess_exec (module-level
        # binding), so patch that name directly.
        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

        calls = 0

        async def boom(stage: str, payload: dict) -> None:
            nonlocal calls
            calls += 1
            if stage == "snapshot_ready":
                return  # allow setup; fail while the process is running
            raise RuntimeError("callback failure")

        adapter = OpenCodeAdapter(config_dir=tmp_path / "cfg", model="probe/model")
        with pytest.raises(RuntimeError, match="callback failure"):
            await adapter.inspect(
                "job-callback", project, _make_baseline(project), on_progress=boom
            )

        assert created, "inspect() must use the mocked subprocess creator"
        assert fake.terminated, (
            f"running process must be terminated on exception path "
            f"(returncode={fake.returncode}, running_map={list(adapter._running)})"
        )
        assert adapter._running == {}, "job must be removed from the running map"

        # Profile and snapshot must be cleaned even though inspect() raised.
        run_profiles = adapter.config_dir / "run-profiles"
        snapshots = adapter.config_dir / "inspection-snapshots"
        if run_profiles.exists():
            assert list(run_profiles.iterdir()) == [], "no leftover run profiles"
        if snapshots.exists():
            assert not (snapshots / "job-callback").exists(), "no leftover snapshot"

    asyncio.run(scenario())


def test_normal_exit_needs_no_forced_termination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        workspace = tmp_path / "ws2"
        workspace.mkdir()
        (workspace / "README.md").write_text("# normal fixture", encoding="utf-8")
        project = _make_project(workspace)

        class ExitedProcess(FakeProcess):
            def __init__(self) -> None:
                super().__init__()
                self.returncode = 0  # already exited

        fake = ExitedProcess()

        async def fake_create_subprocess_exec(*args, **kwargs):
            return fake

        # Same module-level binding as production code (asyncio.create_subprocess_exec).
        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

        # No assistant text -> no report, but the already-exited process must
        # not be signalled and no exception may surface.
        adapter = OpenCodeAdapter(config_dir=tmp_path / "cfg2", model="probe/model")
        outcome = await adapter.inspect("job-normal", project, _make_baseline(project))
        assert not fake.terminated, "already-exited process must not be signalled"
        assert outcome.report is None

    asyncio.run(scenario())
