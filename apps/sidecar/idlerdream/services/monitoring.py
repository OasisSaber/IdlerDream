from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from ..collectors.files import WorkspaceDigest
from ..database import Database
from ..events import EventBus
from ..models import AgentProcess, AgentSession, FactBaseline, Project, TestFacts, VcsFacts
from .facts import FactService
from .projects import ProjectService

AutoInspectCallback = Callable[[UUID, str], Awaitable[None]]


@dataclass(slots=True)
class _DigestSample:
    digest: WorkspaceDigest
    observed_at: datetime


@dataclass(slots=True)
class _ReconcileSample:
    vcs: VcsFacts
    tests: TestFacts
    observed_at: datetime


class MonitoringService:
    """Bounded, independently scheduled monitoring loops (CR-20).

    The original loop collected every fact for every project sequentially, so
    one large repository delayed every other project and the 50-project target
    was unreachable. Monitoring is now split into three schedulers:

    - process sampling (fast, every ``process_seconds``);
    - VCS/test reconciliation (medium, every ``reconcile_seconds``);
    - deep workspace fingerprinting (slow, every ``deep_seconds``), with an
      immediate re-fingerprint when the Watchdog file watcher reports a change.

    Each scheduler runs projects with bounded concurrency so one slow project
    cannot stall the others, and the assembled baseline published on the event
    bus always mixes the freshest pieces from every scheduler.
    """

    def __init__(
        self,
        projects: ProjectService,
        facts: FactService,
        database: Database,
        events: EventBus,
        auto_inspect: AutoInspectCallback | None = None,
        *,
        process_seconds: float = 5.0,
        reconcile_seconds: float = 30.0,
        deep_seconds: float = 300.0,
        stable_seconds: float = 180.0,
        cooldown_seconds: float = 1800.0,
        max_concurrency: int = 4,
        file_watcher=None,
    ) -> None:
        self.projects = projects
        self.facts = facts
        self.database = database
        self.events = events
        self.auto_inspect = auto_inspect
        self.process_seconds = process_seconds
        self.reconcile_seconds = reconcile_seconds
        self.deep_seconds = deep_seconds
        self.stable_seconds = stable_seconds
        self.cooldown_seconds = cooldown_seconds
        self.max_concurrency = max(1, max_concurrency)
        self.file_watcher = file_watcher

        self.runtime: dict[UUID, FactBaseline] = {}
        self._agent_samples: dict[UUID, list[AgentProcess]] = {}
        self._reconcile_samples: dict[UUID, _ReconcileSample] = {}
        self._digest_samples: dict[UUID, _DigestSample] = {}
        self._tasks: list[asyncio.Task[None]] = []
        self._pending: dict[UUID, asyncio.Task[None]] = {}
        self._pending_targets: dict[UUID, tuple[str, str]] = {}
        self._last_auto: dict[UUID, datetime] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._loop = asyncio.get_running_loop()
        self._tasks = [
            asyncio.create_task(
                self._loop_runner(self._process_pass, self.process_seconds),
                name="monitor-processes",
            ),
            asyncio.create_task(
                self._loop_runner(self._reconcile_pass, self.reconcile_seconds),
                name="monitor-reconcile",
            ),
            asyncio.create_task(
                self._loop_runner(self._deep_pass, self.deep_seconds),
                name="monitor-deep",
            ),
        ]
        if self.file_watcher is not None and self.file_watcher.start(
            self._loop, self._on_file_change
        ):
            await self.events.publish("monitor.file_watcher", {"status": "started"})

    async def stop(self) -> None:
        self._started = False
        for task in self._tasks:
            task.cancel()
        for task in self._pending.values():
            task.cancel()
        await asyncio.gather(*self._tasks, *self._pending.values(), return_exceptions=True)
        self._tasks.clear()
        self._pending.clear()
        self._pending_targets.clear()
        if self.file_watcher is not None:
            self.file_watcher.stop()

    async def _loop_runner(self, pass_fn: Callable[[], Awaitable[None]], delay: float) -> None:
        while True:
            await pass_fn()
            await asyncio.sleep(delay)

    def _enabled_projects(self) -> list[Project]:
        return [project for project in self.projects.list() if project.enabled]

    async def _bounded_for_each(self, collector_name: str, collect, apply) -> None:
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def one(project: Project) -> None:
            async with semaphore:
                try:
                    result = await asyncio.to_thread(collect, project)
                except Exception as exc:  # noqa: BLE001 - one project must not stop the loop
                    await self.events.publish(
                        "monitor.error",
                        {
                            "project_id": str(project.id),
                            "collector": collector_name,
                            "error": str(exc),
                        },
                    )
                    return
                try:
                    await apply(project, result)
                except Exception as exc:  # noqa: BLE001 - assembly must not kill the loop
                    await self.events.publish(
                        "monitor.error",
                        {
                            "project_id": str(project.id),
                            "collector": collector_name,
                            "error": str(exc),
                        },
                    )

        await asyncio.gather(*(one(project) for project in self._enabled_projects()))

    async def _process_pass(self) -> None:
        await self._bounded_for_each(
            "processes", self.facts.collect_processes_sync, self._apply_agents
        )

    async def _reconcile_pass(self) -> None:
        await self._bounded_for_each(
            "reconcile", self.facts.collect_reconcile_sync, self._apply_reconcile
        )

    async def _deep_pass(self) -> None:
        await self._bounded_for_each(
            "digest", self.facts.collect_digest_sync, self._apply_digest
        )

    async def _apply_agents(self, project: Project, agents: list[AgentProcess]) -> None:
        self._agent_samples[project.id] = agents
        await self._apply_assembled(project)

    async def _apply_reconcile(self, project: Project, result: tuple[VcsFacts, TestFacts]) -> None:
        vcs, tests = result
        self._reconcile_samples[project.id] = _ReconcileSample(
            vcs=vcs, tests=tests, observed_at=datetime.now(UTC)
        )
        await self._apply_assembled(project)

    async def _apply_digest(self, project: Project, digest: WorkspaceDigest) -> None:
        self._digest_samples[project.id] = _DigestSample(
            digest=digest, observed_at=datetime.now(UTC)
        )
        await self._apply_assembled(project)

    async def _apply_assembled(self, project: Project) -> None:
        digest_sample = self._digest_samples.get(project.id)
        if digest_sample is None:
            # No fingerprint yet; publishing a half-assembled baseline would
            # claim an identity we cannot back with deterministic facts.
            return
        reconcile = self._reconcile_samples.get(project.id)
        current = self.facts.assemble_baseline(
            project,
            agents=self._agent_samples.get(project.id, []),
            digest=digest_sample.digest,
            vcs=reconcile.vcs if reconcile else None,
            tests=reconcile.tests if reconcile else None,
            observed_at=digest_sample.observed_at,
        )
        previous = self.runtime.get(project.id)
        self.runtime[project.id] = current
        if previous is None or _baseline_changed(previous, current):
            await self.events.publish(
                "project.runtime.updated",
                {
                    "project_id": str(project.id),
                    "baseline": current.model_dump(mode="json"),
                },
            )
        if previous is not None:
            self._record_exited_sessions(project, previous, current)
            if reason := _auto_trigger_reason(previous, current):
                self._schedule_auto(project.id, reason, current.workspace_fingerprint)

    def _record_exited_sessions(self, project: Project, previous: FactBaseline, current: FactBaseline) -> None:
        previous_by_pid = {agent.pid: agent for agent in previous.agents}
        exited = previous_by_pid.keys() - {agent.pid for agent in current.agents}
        for pid in exited:
            agent = previous_by_pid[pid]
            self.database.record_agent_session(
                AgentSession(
                    project_id=project.id,
                    process_pid=pid,
                    process=agent,
                    started_at=agent.started_at or previous.observed_at,
                    exited_at=datetime.now(UTC),
                )
            )

    async def _on_file_change(self, project_id: UUID) -> None:
        try:
            await self.events.publish("file.changed", {"project_id": str(project_id)})
            await self._refresh_project(project_id)
        except Exception as exc:  # noqa: BLE001 - watcher callback must never crash the loop
            await self.events.publish(
                "monitor.error",
                {
                    "project_id": str(project_id),
                    "collector": "file_watcher",
                    "error": str(exc),
                },
            )

    async def _refresh_project(self, project_id: UUID) -> None:
        project = next((item for item in self.projects.list() if item.id == project_id), None)
        if project is None or not project.enabled:
            return
        try:
            vcs, tests = await asyncio.to_thread(self.facts.collect_reconcile_sync, project)
            await self._apply_reconcile(project, (vcs, tests))
        except Exception as exc:  # noqa: BLE001 - degrade this project only
            await self.events.publish(
                "monitor.error",
                {"project_id": str(project_id), "collector": "reconcile", "error": str(exc)},
            )
        try:
            digest = await asyncio.to_thread(self.facts.collect_digest_sync, project)
            await self._apply_digest(project, digest)
        except Exception as exc:  # noqa: BLE001 - degrade this project only
            await self.events.publish(
                "monitor.error",
                {"project_id": str(project_id), "collector": "digest", "error": str(exc)},
            )

    def _schedule_auto(self, project_id: UUID, reason: str, fingerprint: str) -> None:
        if not self.auto_inspect:
            return
        last = self._last_auto.get(project_id)
        if last and datetime.now(UTC) - last < timedelta(seconds=self.cooldown_seconds):
            return

        # Replace the target while one stable-window task is pending. This avoids
        # dropping a newer meaningful change during the original wait period.
        self._pending_targets[project_id] = (reason, fingerprint)
        if project_id in self._pending:
            return

        async def delayed() -> None:
            try:
                while True:
                    target_reason, target_fingerprint = self._pending_targets[project_id]
                    await asyncio.sleep(self.stable_seconds)
                    latest = self._pending_targets.get(project_id)
                    current = self.runtime.get(project_id)
                    if latest != (target_reason, target_fingerprint):
                        continue
                    if not current or current.workspace_fingerprint != target_fingerprint:
                        # A newer baseline will reschedule with its own target.
                        return
                    self._last_auto[project_id] = datetime.now(UTC)
                    await self.auto_inspect(project_id, target_reason)
                    return
            finally:
                self._pending.pop(project_id, None)
                self._pending_targets.pop(project_id, None)

        self._pending[project_id] = asyncio.create_task(delayed(), name=f"auto-inspect-{project_id}")


def _baseline_changed(previous: FactBaseline, current: FactBaseline) -> bool:
    if previous.workspace_fingerprint != current.workspace_fingerprint:
        return True
    previous_pids = {item.pid for item in previous.agents}
    current_pids = {item.pid for item in current.agents}
    if previous_pids != current_pids:
        return True
    if previous.tests.status != current.tests.status:
        return True
    previous_vcs = (previous.vcs.head, previous.vcs.branch, previous.vcs.changed_files, previous.vcs.untracked_files)
    current_vcs = (current.vcs.head, current.vcs.branch, current.vcs.changed_files, current.vcs.untracked_files)
    return previous_vcs != current_vcs


def _auto_trigger_reason(previous: FactBaseline, current: FactBaseline) -> str | None:
    previous_pids = {item.pid for item in previous.agents}
    current_pids = {item.pid for item in current.agents}
    if previous_pids and previous_pids - current_pids:
        return "agent_exit"
    if previous.tests.status != current.tests.status and current.tests.status in {"passed", "failed"}:
        return "test_result_changed"
    return None
