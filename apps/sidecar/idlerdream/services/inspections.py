from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from ..database import Database
from ..events import EventBus
from ..inspection.opencode import InspectionOutcome, MockInspectorAdapter, OpenCodeAdapter
from ..models import InspectionJob, SnapshotEvent
from ..state.merger import materially_changed, merge_state
from ..storage.raw_reports import RawReportStore
from ..storage.snapshots import SnapshotStore
from .facts import FactService
from .projects import ProjectService


class InspectionService:
    def __init__(
        self,
        project_service: ProjectService,
        fact_service: FactService,
        database: Database,
        snapshot_store: SnapshotStore,
        raw_report_store: RawReportStore,
        event_bus: EventBus,
        inspector: OpenCodeAdapter | MockInspectorAdapter,
        concurrency: int = 4,
    ) -> None:
        self.projects = project_service
        self.facts = fact_service
        self.database = database
        self.snapshots = snapshot_store
        self.raw_reports = raw_report_store
        self.events = event_bus
        self.inspector = inspector
        self._semaphore = asyncio.Semaphore(max(1, concurrency))
        self._jobs: dict[UUID, InspectionJob] = {}
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    def list_jobs(self) -> list[InspectionJob]:
        return sorted(self._jobs.values(), key=lambda item: str(item.id), reverse=True)

    def get_job(self, job_id: UUID | str) -> InspectionJob | None:
        return self._jobs.get(UUID(str(job_id)))

    async def start(self, project_id: UUID | str, source: str = "manual") -> InspectionJob:
        project = self.projects.get(project_id)
        for existing in self._jobs.values():
            if existing.project_id == project.id and existing.status in {"queued", "running"}:
                return existing
        job = InspectionJob(
            project_id=project.id,
            source=source,
            budget={"max_files": 40, "max_content_mb": 2, "max_tool_calls": 100},
        )
        self._jobs[job.id] = job
        task = asyncio.create_task(self._run(job), name=f"inspection-{job.id}")
        self._tasks[job.id] = task
        await self._publish_job(job)
        return job

    async def cancel(self, job_id: UUID | str) -> bool:
        job_uuid = UUID(str(job_id))
        job = self._jobs.get(job_uuid)
        if not job or job.status not in {"queued", "running"}:
            return False
        await self.inspector.cancel(str(job_uuid))
        task = self._tasks.get(job_uuid)
        if task and not task.done():
            task.cancel()
        job.status = "cancelled"
        job.stage = "cancelled"
        job.finished_at = datetime.now(UTC)
        await self._publish_job(job)
        return True

    async def _run(self, job: InspectionJob) -> None:
        try:
            async with self._semaphore:
                job.status = "running"
                job.stage = "collecting_baseline"
                job.started_at = datetime.now(UTC)
                await self._publish_job(job)
                project = self.projects.get(job.project_id)
                baseline = await self.facts.collect(project)

                async def on_progress(event_type: str, payload: dict[str, Any]) -> None:
                    job.stage = payload.get("stage") or payload.get("event_type") or event_type
                    job.last_activity = payload.get("summary") or job.stage
                    if job.started_at:
                        job.elapsed_seconds = (
                            datetime.now(UTC) - job.started_at
                        ).total_seconds()
                    await self._publish_job(job)

                job.stage = "semantic_inspection"
                await self._publish_job(job)
                outcome = await self.inspector.inspect(
                    str(job.id), project, baseline, on_progress=on_progress
                )
                job.warnings = list(outcome.warnings)
                end_baseline = await self.facts.collect(project)
                raw_report_id = self.raw_reports.save(
                    project.id,
                    {
                        "job": job.model_dump(mode="json"),
                        "baseline": baseline.model_dump(mode="json"),
                        "end_baseline": end_baseline.model_dump(mode="json"),
                        "events": outcome.raw_events,
                        "stderr_tail": outcome.stderr_tail,
                        "error": outcome.error,
                        "warnings": outcome.warnings,
                        "parse_diagnostics": outcome.diagnostics,
                        "inspection_snapshot": outcome.snapshot,
                    },
                    retention_days=7,
                )

                previous = self.database.get_current_state(project.id)
                if baseline.workspace_fingerprint != end_baseline.workspace_fingerprint:
                    outcome = InspectionOutcome(
                        report=None,
                        raw_events=outcome.raw_events,
                        stderr_tail=outcome.stderr_tail,
                        error="Workspace changed during inspection",
                        warnings=[*outcome.warnings, f"raw_report_id={raw_report_id}"],
                        diagnostics=outcome.diagnostics,
                        snapshot=outcome.snapshot,
                    )
                    job.status = "invalidated"
                state = merge_state(
                    project,
                    end_baseline,
                    outcome.report,
                    previous=previous,
                    inspection_error=outcome.error,
                )
                self.database.upsert_current_state(state)
                if materially_changed(previous, state):
                    event = SnapshotEvent(
                        project_id=project.id,
                        event_type=(
                            "inspection" if job.status != "invalidated" else "state_invalidated"
                        ),
                        state=state,
                        baseline_fingerprint=end_baseline.workspace_fingerprint,
                        analysis_version=(
                            outcome.report.analysis_version
                            if outcome.report
                            else {"adapter": "failed"}
                        ),
                    )
                    self.snapshots.append(event)
                if job.status != "invalidated":
                    job.status = "completed" if outcome.report else "failed"
                job.error = outcome.error
                job.stage = job.status
                job.finished_at = datetime.now(UTC)
                if job.started_at:
                    job.elapsed_seconds = (job.finished_at - job.started_at).total_seconds()
                await self.events.publish(
                    "project.state.updated",
                    {"project_id": str(project.id), "state": state.model_dump(mode="json")},
                )
                await self._publish_job(job)
        except asyncio.CancelledError:
            job.status = "cancelled"
            job.stage = "cancelled"
            job.finished_at = datetime.now(UTC)
            await self._publish_job(job)
        except Exception as exc:  # noqa: BLE001 - defensive boundary for the sidecar process
            job.status = "failed"
            job.stage = "failed"
            job.error = str(exc)
            job.finished_at = datetime.now(UTC)
            await self._publish_job(job)
        finally:
            self._tasks.pop(job.id, None)

    async def _publish_job(self, job: InspectionJob) -> None:
        await self.events.publish("inspection.job", job.model_dump(mode="json"))
