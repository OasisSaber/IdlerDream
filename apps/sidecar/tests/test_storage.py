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


def test_reconcile_rebuilds_missing_index_rows(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3")
    project = Project(name="demo", path=str(tmp_path / "workspace"))
    database.add_project(project)
    store = SnapshotStore(tmp_path / "snapshots", database)
    events = [
        SnapshotEvent(project_id=project.id, event_type="inspection", state=CurrentProjectState(project_id=project.id))
        for _ in range(2)
    ]
    # Append both to the file but only index the first, simulating a crash
    # between the JSONL append and the SQLite insert.
    week_file = "2026-W32.jsonl"
    path = store.directory / week_file
    payloads = [(event.model_dump_json() + "\n").encode("utf-8") for event in events]
    with path.open("ab") as handle:
        handle.write(payloads[0])
    database.insert_snapshot_index(events[0], week_file, 0, len(payloads[0]))
    with path.open("ab") as handle:
        handle.write(payloads[1])

    counts = store.reconcile()
    assert counts["rows_rebuilt"] == 1
    loaded = store.list_project(project.id)
    assert {item.snapshot_id for item in loaded} == {event.snapshot_id for event in events}
    database.close()


def test_reconcile_truncates_incomplete_trailing_record(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3")
    project = Project(name="demo", path=str(tmp_path / "workspace"))
    database.add_project(project)
    store = SnapshotStore(tmp_path / "snapshots", database)
    event = SnapshotEvent(
        project_id=project.id, event_type="inspection", state=CurrentProjectState(project_id=project.id)
    )
    store.append(event)
    path = store.directory / "2026-W32.jsonl"
    with path.open("ab") as handle:
        handle.write(b'{"snapshot_id":"truncated')  # partial write

    counts = store.reconcile()
    assert counts["truncated"] == 1
    assert path.read_bytes().endswith(b"\n")
    loaded = store.list_project(project.id)
    assert loaded[0].snapshot_id == event.snapshot_id
    database.close()


def test_reconcile_fixes_missing_trailing_newline(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3")
    project = Project(name="demo", path=str(tmp_path / "workspace"))
    database.add_project(project)
    store = SnapshotStore(tmp_path / "snapshots", database)
    event = SnapshotEvent(
        project_id=project.id, event_type="inspection", state=CurrentProjectState(project_id=project.id)
    )
    week_file = "2026-W32.jsonl"
    payload = event.model_dump_json().encode("utf-8")  # no trailing newline
    path = store.directory / week_file
    path.write_bytes(payload)
    database.insert_snapshot_index(event, week_file, 0, len(payload))

    counts = store.reconcile()
    assert counts["newline_fixed"] == 1
    assert path.read_bytes().endswith(b"\n")
    assert store.list_project(project.id)[0].snapshot_id == event.snapshot_id
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
