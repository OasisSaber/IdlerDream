"""Monitoring scheduler tests (CR-20).

The monitoring service must no longer fingerprint every project sequentially in
one loop. These tests verify the split schedulers, the assembled baseline, the
Watchdog file-change refresh path, automatic-inspection triggers and
exited-session aggregation.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from pathlib import Path
from uuid import UUID

import pytest

from idlerdream import models
from idlerdream.collectors.files import WorkspaceDigest
from idlerdream.database import Database
from idlerdream.events import EventBus
from idlerdream.models import AgentProcess, FactBaseline, Project, VcsFacts
from idlerdream.services.file_watcher import FileEventWatcher
from idlerdream.services.monitoring import MonitoringService, _auto_trigger_reason
from idlerdream.services.projects import ProjectService


class FakeFactService:
    def __init__(self) -> None:
        self.process_calls = 0
        self.reconcile_calls = 0
        self.digest_calls = 0
        self.agents: dict[UUID, list[AgentProcess]] = {}
        self.reconcile: dict[UUID, tuple[VcsFacts, models.TestFacts]] = {}
        self.digests: dict[UUID, WorkspaceDigest] = {}

    def collect_processes_sync(self, project: Project) -> list[AgentProcess]:
        self.process_calls += 1
        return self.agents.get(project.id, [])

    def collect_reconcile_sync(self, project: Project) -> tuple[VcsFacts, models.TestFacts]:
        self.reconcile_calls += 1
        return self.reconcile.get(project.id, (VcsFacts(), models.TestFacts(status="not_found")))

    def collect_digest_sync(self, project: Project) -> WorkspaceDigest:
        self.digest_calls += 1
        return self.digests.get(
            project.id,
            WorkspaceDigest(
                fingerprint=f"fp-{project.id}", considered_paths=[], considered_files=0, warnings=[]
            ),
        )

    def assemble_baseline(
        self,
        project: Project,
        *,
        agents=None,
        digest: WorkspaceDigest,
        vcs=None,
        tests=None,
        observed_at=None,
        warnings=None,
    ) -> FactBaseline:
        return FactBaseline(
            project_id=project.id,
            workspace_path=str(Path(project.path).resolve(strict=False)),
            workspace_fingerprint=digest.fingerprint,
            vcs=vcs or VcsFacts(),
            tests=tests or models.TestFacts(status="not_found"),
            considered_paths=digest.considered_paths,
            file_count_considered=digest.considered_files,
            agents=agents or [],
            warnings=list(warnings or []),
            observed_at=observed_at,
        )


class RecordingBus(EventBus):
    def __init__(self) -> None:
        super().__init__()
        self.published: list[tuple[str, dict]] = []

    async def publish(self, event_type: str, payload: dict) -> None:
        self.published.append((event_type, payload))
        await super().publish(event_type, payload)


def _agent(pid: int) -> AgentProcess:
    return AgentProcess(pid=pid, name="opencode.exe", cwd="C:\\ws")


def _run(coro) -> None:
    asyncio.run(coro)


def _setup(tmp_path: Path) -> tuple[Project, Database, FakeFactService, RecordingBus, ProjectService]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    database = Database(tmp_path / "db.sqlite3")
    projects = ProjectService(database)
    project = projects.add(str(workspace), "demo")
    facts = FakeFactService()
    events = RecordingBus()
    return project, database, facts, events, projects


def test_baseline_assembled_from_independent_scheduler_pieces(tmp_path: Path) -> None:
    project, database, facts, events, projects = _setup(tmp_path)
    facts.agents[project.id] = [_agent(101)]
    facts.reconcile[project.id] = (
        VcsFacts(kind="git", branch="main", changed_files=2, status_summary="2 changes"),
        models.TestFacts(status="passed", passed=5, failed=0),
    )
    facts.digests[project.id] = WorkspaceDigest(
        fingerprint="abc123", considered_paths=["main.py"], considered_files=1, warnings=[]
    )
    monitoring = MonitoringService(projects, facts, database, events)

    async def run() -> None:
        await monitoring.start()
        await asyncio.sleep(0.3)  # let all three schedulers complete one pass
        baseline = monitoring.runtime.get(project.id)
        assert baseline is not None
        assert baseline.workspace_fingerprint == "abc123"
        assert baseline.agents[0].pid == 101
        assert baseline.tests.status == "passed"
        assert baseline.vcs.branch == "main"
        assert facts.process_calls >= 1
        assert facts.reconcile_calls >= 1
        assert facts.digest_calls >= 1
        await monitoring.stop()

    asyncio.run(run())
    database.close()


def test_runtime_event_published_once_per_material_change(tmp_path: Path) -> None:
    _project, database, facts, events, projects = _setup(tmp_path)
    monitoring = MonitoringService(projects, facts, database, events, process_seconds=60)

    async def run() -> None:
        # digest + reconcile first so the first process pass can publish
        await monitoring._deep_pass()
        await monitoring._reconcile_pass()
        await monitoring._process_pass()
        await monitoring._process_pass()  # unchanged -> no new event
        updates = [
            event for event in events.published if event[0] == "project.runtime.updated"
        ]
        assert len(updates) == 1
        await monitoring.stop()

    asyncio.run(run())
    database.close()


def test_auto_inspect_triggered_on_agent_exit(tmp_path: Path) -> None:
    project, database, facts, events, projects = _setup(tmp_path)
    triggered: list[tuple[UUID, str]] = []

    async def auto_inspect(project_id: UUID, reason: str) -> None:
        triggered.append((project_id, reason))

    monitoring = MonitoringService(
        projects,
        facts,
        database,
        events,
        auto_inspect=auto_inspect,
        process_seconds=60,
        stable_seconds=0.01,
        cooldown_seconds=0,
    )

    async def run() -> None:
        facts.agents[project.id] = [_agent(101)]
        await monitoring._deep_pass()
        await monitoring._reconcile_pass()
        await monitoring._process_pass()
        # Agent exits between passes.
        facts.agents[project.id] = []
        await monitoring._process_pass()
        await asyncio.sleep(0.2)
        assert triggered == [(project.id, "agent_exit")]
        sessions = database.list_agent_sessions(project.id)
        assert len(sessions) == 1
        assert sessions[0].process_pid == 101
        assert sessions[0].exited_at is not None
        await monitoring.stop()

    asyncio.run(run())
    database.close()


def test_auto_inspect_triggered_on_test_result_change(tmp_path: Path) -> None:
    project, database, facts, events, projects = _setup(tmp_path)
    triggered: list[tuple[UUID, str]] = []

    async def auto_inspect(project_id: UUID, reason: str) -> None:
        triggered.append((project_id, reason))

    monitoring = MonitoringService(
        projects,
        facts,
        database,
        events,
        auto_inspect=auto_inspect,
        process_seconds=60,
        stable_seconds=0.01,
        cooldown_seconds=0,
    )

    async def run() -> None:
        facts.reconcile[project.id] = (VcsFacts(), models.TestFacts(status="failed", failed=1))
        await monitoring._deep_pass()
        await monitoring._reconcile_pass()
        facts.reconcile[project.id] = (VcsFacts(), models.TestFacts(status="passed", passed=3))
        await monitoring._reconcile_pass()
        await asyncio.sleep(0.2)
        assert triggered == [(project.id, "test_result_changed")]
        await monitoring.stop()

    asyncio.run(run())
    database.close()


def test_auto_trigger_reason_requires_previous_pids(tmp_path: Path) -> None:
    previous = FactBaseline(
        project_id=UUID(int=1),
        workspace_path=str(tmp_path),
        workspace_fingerprint="a",
        agents=[_agent(1)],
    )
    current = FactBaseline(
        project_id=UUID(int=1),
        workspace_path=str(tmp_path),
        workspace_fingerprint="a",
        agents=[],
    )
    assert _auto_trigger_reason(previous, current) == "agent_exit"
    assert _auto_trigger_reason(current, previous) is None


def test_file_change_callback_refreshes_only_that_project(tmp_path: Path) -> None:
    project, database, facts, events, projects = _setup(tmp_path)
    other_workspace = tmp_path / "other"
    other_workspace.mkdir()
    other = projects.add(str(other_workspace), "other")
    monitoring = MonitoringService(projects, facts, database, events, process_seconds=60)

    async def run() -> None:
        before = facts.reconcile_calls
        await monitoring._on_file_change(project.id)
        assert facts.reconcile_calls == before + 1
        assert facts.digest_calls >= 1
        assert monitoring.runtime.get(project.id) is not None
        # The other project was not touched by the callback.
        assert monitoring.runtime.get(other.id) is None
        await monitoring.stop()

    asyncio.run(run())
    database.close()


def test_one_project_failure_does_not_abort_the_loop(tmp_path: Path) -> None:
    _project, database, facts, events, projects = _setup(tmp_path)
    other_workspace = tmp_path / "other"
    other_workspace.mkdir()
    other = projects.add(str(other_workspace), "other")

    def boom(project: Project) -> list[AgentProcess]:
        if project.id == other.id:
            raise RuntimeError("collector exploded")
        return facts.agents.get(project.id, [])

    facts.collect_processes_sync = boom
    monitoring = MonitoringService(projects, facts, database, events, process_seconds=60)

    async def run() -> None:
        await monitoring._process_pass()
        errors = [event for event in events.published if event[0] == "monitor.error"]
        assert any("exploded" in str(error) for _, error in errors)
        await monitoring.stop()

    asyncio.run(run())
    database.close()


@pytest.mark.skipif(os.name != "nt", reason="Watchdog integration runs on Windows")
def test_file_event_watcher_fires_debounced_callback(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    database = Database(tmp_path / "db.sqlite3")
    projects = ProjectService(database)
    project = projects.add(str(workspace), "demo")
    watcher = FileEventWatcher(projects, debounce_seconds=0.1)
    fired: list[UUID] = []

    async def callback(project_id: UUID) -> None:
        fired.append(project_id)

    loop = asyncio.new_event_loop()
    runner = threading.Thread(target=loop.run_forever, daemon=True)
    runner.start()
    try:
        assert watcher.start(loop, callback) is True
        (workspace / "main.py").write_text("print(1)\n", encoding="utf-8")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not fired:
            time.sleep(0.1)
        assert fired == [project.id]
    finally:
        watcher.stop()
        loop.call_soon_threadsafe(loop.stop)
        runner.join(timeout=5)
        database.close()


@pytest.mark.skipif(os.name != "nt", reason="Watchdog integration runs on Windows")
def test_file_event_watcher_ignores_ignored_dirs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    database = Database(tmp_path / "db.sqlite3")
    projects = ProjectService(database)
    projects.add(str(workspace), "demo")
    watcher = FileEventWatcher(projects, debounce_seconds=0.1)
    fired: list[UUID] = []

    async def callback(project_id: UUID) -> None:
        fired.append(project_id)

    loop = asyncio.new_event_loop()
    runner = threading.Thread(target=loop.run_forever, daemon=True)
    runner.start()
    try:
        assert watcher.start(loop, callback) is True
        node_modules = workspace / "node_modules"
        node_modules.mkdir()
        (node_modules / "dep.js").write_text("noise\n", encoding="utf-8")
        time.sleep(0.8)
        assert fired == []
    finally:
        watcher.stop()
        loop.call_soon_threadsafe(loop.stop)
        runner.join(timeout=5)
        database.close()


def test_cooldown_blocks_repeat_auto_inspect(tmp_path: Path) -> None:
    """A second trigger inside the cooldown window must not schedule (CR-20)."""
    project, database, facts, events, projects = _setup(tmp_path)
    triggered: list[tuple[UUID, str]] = []

    async def auto_inspect(project_id: UUID, reason: str) -> None:
        triggered.append((project_id, reason))

    monitoring = MonitoringService(
        projects,
        facts,
        database,
        events,
        auto_inspect=auto_inspect,
        process_seconds=60,
        stable_seconds=0.01,
        cooldown_seconds=0.4,
    )

    async def run() -> None:
        # First exit: schedules and fires (cooldown starts).
        facts.agents[project.id] = [_agent(101)]
        await monitoring._deep_pass()
        await monitoring._reconcile_pass()
        await monitoring._process_pass()
        facts.agents[project.id] = []
        await monitoring._process_pass()
        await asyncio.sleep(0.2)
        assert triggered == [(project.id, "agent_exit")]

        # Second exit within cooldown: must be suppressed.
        facts.agents[project.id] = [_agent(202)]
        await monitoring._process_pass()
        facts.agents[project.id] = []
        await monitoring._process_pass()
        await asyncio.sleep(0.2)
        assert triggered == [(project.id, "agent_exit")], "cooldown must suppress repeat trigger"

        # After cooldown expires, a new exit may trigger again.
        await asyncio.sleep(0.45)
        facts.agents[project.id] = [_agent(303)]
        await monitoring._process_pass()
        facts.agents[project.id] = []
        await monitoring._process_pass()
        await asyncio.sleep(0.2)
        assert triggered == [(project.id, "agent_exit"), (project.id, "agent_exit")]
        await monitoring.stop()

    asyncio.run(run())
    database.close()


def test_identical_baseline_does_not_reschedule(tmp_path: Path) -> None:
    """Repeated identical passes must not fire auto-inspection (CR-20 dedup)."""
    project, database, facts, events, projects = _setup(tmp_path)
    triggered: list[tuple[UUID, str]] = []

    async def auto_inspect(project_id: UUID, reason: str) -> None:
        triggered.append((project_id, reason))

    monitoring = MonitoringService(
        projects,
        facts,
        database,
        events,
        auto_inspect=auto_inspect,
        process_seconds=60,
        stable_seconds=0.01,
        cooldown_seconds=0,
    )

    async def run() -> None:
        facts.agents[project.id] = [_agent(101)]
        await monitoring._deep_pass()
        await monitoring._reconcile_pass()
        await monitoring._process_pass()
        facts.agents[project.id] = []
        await monitoring._process_pass()
        await asyncio.sleep(0.2)
        assert triggered == [(project.id, "agent_exit")]

        # Same state repeated (no agents, same digest/reconcile): no trigger.
        await monitoring._deep_pass()
        await monitoring._reconcile_pass()
        await monitoring._process_pass()
        await asyncio.sleep(0.2)
        assert triggered == [(project.id, "agent_exit")], "identical baseline must not retrigger"
        await monitoring.stop()

    asyncio.run(run())
    database.close()


def test_pending_target_replaced_by_newer_change(tmp_path: Path) -> None:
    """A newer change during the stable window replaces the pending target."""
    project, database, facts, events, projects = _setup(tmp_path)
    triggered: list[tuple[UUID, str]] = []

    async def auto_inspect(project_id: UUID, reason: str) -> None:
        triggered.append((project_id, reason))

    monitoring = MonitoringService(
        projects,
        facts,
        database,
        events,
        auto_inspect=auto_inspect,
        process_seconds=60,
        stable_seconds=0.3,
        cooldown_seconds=0,
    )

    async def run() -> None:
        facts.agents[project.id] = [_agent(101)]
        await monitoring._deep_pass()
        await monitoring._reconcile_pass()
        await monitoring._process_pass()
        facts.agents[project.id] = []
        await monitoring._process_pass()  # schedules agent_exit target
        await asyncio.sleep(0.05)  # inside the stable window

        # Newer, more meaningful change replaces the pending target.
        facts.reconcile[project.id] = (VcsFacts(), models.TestFacts(status="failed", failed=1))
        await monitoring._reconcile_pass()
        facts.reconcile[project.id] = (VcsFacts(), models.TestFacts(status="passed", passed=3))
        await monitoring._reconcile_pass()

        await asyncio.sleep(0.6)  # stable window expires
        assert triggered == [(project.id, "test_result_changed")], (
            "only the newest target may fire, exactly once"
        )
        await monitoring.stop()

    asyncio.run(run())
    database.close()
