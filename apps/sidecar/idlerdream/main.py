from __future__ import annotations

import uvicorn

from .api import AppContext, create_app
from .collectors.processes import ProcessCollector
from .config import Settings
from .database import Database
from .events import EventBus
from .inspection.opencode import MockInspectorAdapter, OpenCodeAdapter
from .services.facts import FactService
from .services.inspections import InspectionService
from .services.monitoring import MonitoringService
from .services.projects import ProjectService
from .storage.raw_reports import KeyProtector, RawReportStore
from .storage.snapshots import SnapshotStore


def build_context(settings: Settings | None = None) -> AppContext:
    settings = settings or Settings.from_env()
    settings.ensure_directories()
    database = Database(settings.data_dir / "database" / "idlerdream.sqlite3")
    events = EventBus()
    projects = ProjectService(database)
    process_collector = ProcessCollector(settings.agent_names)
    facts = FactService(process_collector, settings.ignore_dirs)
    snapshots = SnapshotStore(settings.data_dir / "snapshots", database)
    raw_reports = RawReportStore(
        settings.data_dir / "raw-reports", database, KeyProtector(settings.data_dir)
    )
    # Reconcile weekly JSONL with the SQLite index before serving. This repairs
    # crash artifacts where the file append and index insert were not atomic.
    snapshots.reconcile()
    inspector = (
        MockInspectorAdapter()
        if settings.mock_inspector
        else OpenCodeAdapter(
            settings.opencode_executable,
            model=settings.opencode_model,
            timeout_seconds=settings.opencode_timeout_seconds,
            config_dir=settings.data_dir / "config" / "opencode-inspector",
        )
    )
    inspections = InspectionService(
        projects,
        facts,
        database,
        snapshots,
        raw_reports,
        events,
        inspector,
        concurrency=settings.inspection_concurrency,
    )

    async def auto_inspect(project_id, reason: str) -> None:
        await events.publish(
            "inspection.auto.triggered", {"project_id": str(project_id), "reason": reason}
        )
        await inspections.start(project_id, source="automatic")

    monitoring = MonitoringService(projects, facts, database, events, auto_inspect=auto_inspect)
    return AppContext(
        settings=settings,
        database=database,
        projects=projects,
        inspections=inspections,
        monitoring=monitoring,
        snapshots=snapshots,
        raw_reports=raw_reports,
        events=events,
    )


def run() -> None:
    context = build_context()
    app = create_app(context)
    uvicorn.run(
        app,
        host=context.settings.api_host,
        port=context.settings.api_port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    run()
