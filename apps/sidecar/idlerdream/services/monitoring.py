from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from ..database import Database
from ..events import EventBus
from ..models import FactBaseline
from .facts import FactService
from .projects import ProjectService

AutoInspectCallback = Callable[[UUID, str], Awaitable[None]]


class MonitoringService:
    """Low-frequency reconciliation loop for the v0.1 vertical slice."""

    def __init__(
        self,
        projects: ProjectService,
        facts: FactService,
        database: Database,
        events: EventBus,
        auto_inspect: AutoInspectCallback | None = None,
        poll_seconds: float = 30.0,
        stable_seconds: float = 180.0,
        cooldown_seconds: float = 1800.0,
    ) -> None:
        self.projects = projects
        self.facts = facts
        self.database = database
        self.events = events
        self.auto_inspect = auto_inspect
        self.poll_seconds = poll_seconds
        self.stable_seconds = stable_seconds
        self.cooldown_seconds = cooldown_seconds
        self.runtime: dict[UUID, FactBaseline] = {}
        self._task: asyncio.Task[None] | None = None
        self._last_auto: dict[UUID, datetime] = {}
        self._pending: dict[UUID, asyncio.Task[None]] = {}
        self._pending_targets: dict[UUID, tuple[str, str]] = {}

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop(), name="workspace-monitor")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        for task in self._pending.values():
            task.cancel()
        await asyncio.gather(*([self._task] if self._task else []), *self._pending.values(), return_exceptions=True)
        self._pending.clear()
        self._pending_targets.clear()

    async def poll_once(self) -> None:
        for project in self.projects.list():
            if not project.enabled:
                continue
            previous = self.runtime.get(project.id)
            try:
                current = await self.facts.collect(project)
            except Exception as exc:
                await self.events.publish("monitor.error", {"project_id": str(project.id), "error": str(exc)})
                continue
            self.runtime[project.id] = current
            await self.events.publish("project.runtime.updated", {"project_id": str(project.id), "baseline": current.model_dump(mode="json")})
            if previous and (reason := _auto_trigger_reason(previous, current)):
                self._schedule_auto(project.id, reason, current.workspace_fingerprint)

    async def _loop(self) -> None:
        while True:
            await self.poll_once()
            await asyncio.sleep(self.poll_seconds)

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


def _auto_trigger_reason(previous: FactBaseline, current: FactBaseline) -> str | None:
    previous_pids = {item.pid for item in previous.agents}
    current_pids = {item.pid for item in current.agents}
    if previous_pids and previous_pids - current_pids:
        return "agent_exit"
    if previous.tests.status != current.tests.status and current.tests.status in {"passed", "failed"}:
        return "test_result_changed"
    return None
