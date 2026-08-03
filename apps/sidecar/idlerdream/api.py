from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings
from .control import ControlServer
from .database import Database
from .events import EventBus
from .services.inspections import InspectionService
from .services.monitoring import MonitoringService
from .services.projects import ProjectService
from .storage.raw_reports import RawReportStore
from .storage.snapshots import SnapshotStore


@dataclass(slots=True)
class AppContext:
    settings: Settings
    database: Database
    projects: ProjectService
    inspections: InspectionService
    monitoring: MonitoringService
    snapshots: SnapshotStore
    raw_reports: RawReportStore
    events: EventBus
    control: ControlServer | None = None


async def handle_control(context: AppContext, request: dict[str, Any]) -> dict[str, Any]:
    command = request.get("command")
    payload = request.get("payload") or {}
    if command == "ping":
        return {"status": "ok"}
    if command == "project.add":
        project = context.projects.add(payload["path"], payload.get("name"))
        await context.events.publish("project.added", project.model_dump(mode="json"))
        return project.model_dump(mode="json")
    if command == "project.discover":
        return {"candidates": context.projects.discover(payload["root"], payload.get("max_depth", 4))}
    if command == "project.remove":
        context.projects.remove(payload["project_id"])
        await context.events.publish("project.removed", {"project_id": payload["project_id"]})
        return {"project_id": payload["project_id"]}
    if command == "inspection.start":
        job = await context.inspections.start(payload["project_id"], source=payload.get("source", "manual"))
        return job.model_dump(mode="json")
    if command == "inspection.cancel":
        return {"cancelled": await context.inspections.cancel(payload["job_id"])}
    raise ValueError(f"Unknown control command: {command}")


def create_app(context: AppContext) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        control = ControlServer(
            lambda request: handle_control(context, request),
            context.settings.control_token,
            profile=context.settings.profile,
            host=context.settings.control_host,
            port=context.settings.control_port,
        )
        context.control = control
        await control.start()
        context.raw_reports.destroy_expired()
        await context.monitoring.start()
        try:
            yield
        finally:
            await context.monitoring.stop()
            await control.stop()
            context.database.close()

    app = FastAPI(title="IdlerDream Sidecar", version="0.1.0", lifespan=lifespan)

    async def require_read_token(
        token: Annotated[str | None, Header(alias="X-IdlerDream-Read-Token")] = None,
    ) -> None:
        if token is None or not secrets.compare_digest(token, context.settings.read_token):
            raise HTTPException(status_code=401, detail="Unauthorized read request")

    app.state.context = context
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "idlerdream://app", "null"],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Content-Type", "X-IdlerDream-Read-Token"],
    )

    @app.get("/health", dependencies=[Depends(require_read_token)])
    async def health() -> dict[str, Any]:
        version = await context.inspections.inspector.version()
        return {
            "status": "ok",
            "profile": context.settings.profile,
            "opencode_available": context.inspections.inspector.available(),
            "opencode_version": version,
            "mock_inspector": context.settings.mock_inspector,
            "database": context.database.export_debug_summary(),
        }

    @app.get("/api/v1/projects", dependencies=[Depends(require_read_token)])
    async def list_projects() -> list[dict[str, Any]]:
        return [
            {
                "project": project.model_dump(mode="json"),
                "state": (state.model_dump(mode="json") if (state := context.database.get_current_state(project.id)) else None),
                "runtime": (runtime.model_dump(mode="json") if (runtime := context.monitoring.runtime.get(project.id)) else None),
            }
            for project in context.projects.list()
        ]

    @app.get("/api/v1/projects/{project_id}", dependencies=[Depends(require_read_token)])
    async def get_project(project_id: UUID) -> dict[str, Any]:
        try:
            project = context.projects.get(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        state = context.database.get_current_state(project.id)
        runtime = context.monitoring.runtime.get(project.id)
        return {
            "project": project.model_dump(mode="json"),
            "state": state.model_dump(mode="json") if state else None,
            "runtime": runtime.model_dump(mode="json") if runtime else None,
            "history": [event.model_dump(mode="json") for event in context.snapshots.list_project(project.id)],
        }

    @app.get("/api/v1/inspections", dependencies=[Depends(require_read_token)])
    async def list_inspections() -> list[dict[str, Any]]:
        return [job.model_dump(mode="json") for job in context.inspections.list_jobs()]

    @app.websocket("/api/v1/events")
    async def events(websocket: WebSocket) -> None:
        token = websocket.query_params.get("token")
        if token is None or not secrets.compare_digest(token, context.settings.read_token):
            await websocket.close(code=4401)
            return
        await websocket.accept()
        try:
            async for event in context.events.subscribe():
                await websocket.send_json({"type": event.type, "payload": event.payload, "created_at": event.created_at})
        except WebSocketDisconnect:
            return

    if context.settings.dev_control_http:
        @app.post("/dev/control")
        async def dev_control(request: dict[str, Any]) -> dict[str, Any]:
            token = str(request.get("token", ""))
            if not secrets.compare_digest(token, context.settings.control_token):
                raise HTTPException(status_code=401, detail="Unauthorized")
            return await handle_control(context, request)

    return app
