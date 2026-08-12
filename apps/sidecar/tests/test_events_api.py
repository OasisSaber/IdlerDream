from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from idlerdream.api import AppContext, create_app
from idlerdream.config import Settings
from idlerdream.database import Database
from idlerdream.events import EventBus
from idlerdream.services.projects import ProjectService
from idlerdream.storage.snapshots import SnapshotStore


def _build_app(tmp_path: Path):
    settings = Settings(
        profile="test",
        data_dir=tmp_path / "data",
        read_token="read-token",
        control_token="control-token",
    )
    database = Database(tmp_path / "db.sqlite3")
    events = EventBus()
    projects = ProjectService(database)
    context = AppContext(
        settings=settings,
        database=database,
        projects=projects,
        inspections=None,  # type: ignore[arg-type]
        monitoring=None,  # type: ignore[arg-type]
        snapshots=SnapshotStore(tmp_path / "snapshots", database),
        raw_reports=None,  # type: ignore[arg-type]
        events=events,
    )
    return context, create_app(context)


def test_events_websocket_rejects_missing_token(tmp_path: Path) -> None:
    context, app = _build_app(tmp_path)
    client = TestClient(app)  # noqa: S106 - lifespan disabled; endpoint needs only app.state
    try:
        with client.websocket_connect("/api/v1/events") as websocket:
            # The endpoint closes with 4401 when the token is missing.
            assert websocket.receive()  # pragma: no cover - raises on close
    except Exception as exc:  # noqa: BLE001 - starlette raises WebSocketDisconnect
        from starlette.websockets import WebSocketDisconnect
        if isinstance(exc, WebSocketDisconnect):
            assert exc.code == 4401
        else:
            raise
    finally:
        context.database.close()


def test_events_websocket_streams_project_added(tmp_path: Path) -> None:
    context, app = _build_app(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    client = TestClient(app)
    try:
        with client.websocket_connect(
            "/api/v1/events?token=read-token"
        ) as websocket:
            asyncio.run(
                context.events.publish(
                    "project.added", {"project_id": "probe", "name": "demo"}
                )
            )
            message = websocket.receive_json()
            assert message["type"] == "project.added"
            assert message["payload"]["name"] == "demo"
    finally:
        context.database.close()
