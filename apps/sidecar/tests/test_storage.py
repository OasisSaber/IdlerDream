from __future__ import annotations

from pathlib import Path

import pytest

from idlerdream.database import Database
from idlerdream.models import CurrentProjectState, Project, SnapshotEvent
from idlerdream.storage.raw_reports import KeyProtector, RawReportStore
from idlerdream.storage.snapshots import SnapshotStore


def test_snapshot_round_trip(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3")
    project = Project(name="demo", path=str(tmp_path / "workspace"))
    database.add_project(project)
    state = CurrentProjectState(project_id=project.id)
    store = SnapshotStore(tmp_path / "snapshots", database)
    event = SnapshotEvent(project_id=project.id, event_type="inspection", state=state)
    store.append(event)
    loaded = store.list_project(project.id)
    assert loaded[0].snapshot_id == event.snapshot_id
    database.close()


def test_raw_report_crypto_destroy(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3")
    project = Project(name="demo", path=str(tmp_path / "workspace"))
    database.add_project(project)
    store = RawReportStore(tmp_path / "reports", database, KeyProtector(tmp_path))
    report_id = store.save(project.id, {"secret": "body"})
    assert store.read(report_id)["secret"] == "body"
    store.destroy(report_id)
    with pytest.raises(KeyError):
        store.read(report_id)
    database.close()
