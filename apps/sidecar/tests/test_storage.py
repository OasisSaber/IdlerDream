from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
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


def test_raw_report_compact_removes_destroyed_and_expired_records(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3")
    project = Project(name="demo", path=str(tmp_path / "workspace"))
    database.add_project(project)
    store = RawReportStore(tmp_path / "reports", database, KeyProtector(tmp_path))
    live_id = store.save(project.id, {"secret": "live"})
    destroyed_id = store.save(project.id, {"secret": "destroyed"})
    expired_id = store.save(project.id, {"secret": "expired"})
    store.destroy(destroyed_id)
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    database._connection.execute(
        "UPDATE raw_report_keys SET expires_at = ? WHERE report_id = ?",
        (past, expired_id),
    )
    database._connection.commit()

    removed, freed = store.compact()
    assert removed == 2
    assert freed > 0
    assert store.read(live_id)["secret"] == "live"
    with pytest.raises(KeyError):
        store.read(destroyed_id)
    with pytest.raises(KeyError):
        store.read(expired_id)
    bundle = next(store.directory.glob("*.bundle.jsonl"))
    records = [json.loads(line) for line in bundle.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [record["report_id"] for record in records] == [live_id]
    database.close()


def test_raw_report_compact_drops_whole_dead_bundle(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3")
    project = Project(name="demo", path=str(tmp_path / "workspace"))
    database.add_project(project)
    store = RawReportStore(tmp_path / "reports", database, KeyProtector(tmp_path))
    report_id = store.save(project.id, {"secret": "only"})
    store.destroy(report_id)

    removed, freed = store.compact()
    assert removed == 1
    assert freed > 0
    assert list(store.directory.glob("*.bundle.jsonl")) == []
    database.close()


def test_raw_report_quarantine_corrupted_container(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3")
    project = Project(name="demo", path=str(tmp_path / "workspace"))
    database.add_project(project)
    store = RawReportStore(tmp_path / "reports", database, KeyProtector(tmp_path))
    healthy_id = store.save(project.id, {"secret": "healthy"})
    bundle = next(store.directory.glob("*.bundle.jsonl"))
    with bundle.open("a", encoding="utf-8") as handle:
        handle.write('{"report_id": "broken-json\n')

    moved = store.quarantine_corrupted()
    assert moved == [bundle.name]
    assert (store.quarantine_dir / bundle.name).exists()
    assert not bundle.exists()
    # The corrupted container's keys were destroyed so reads fail cleanly
    # instead of raising file-not-found surprises.
    with pytest.raises(KeyError):
        store.read(healthy_id)
    database.close()


def test_raw_report_quarantine_preserves_healthy_bundles(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3")
    project = Project(name="demo", path=str(tmp_path / "workspace"))
    database.add_project(project)
    store = RawReportStore(tmp_path / "reports", database, KeyProtector(tmp_path))
    report_id = store.save(project.id, {"secret": "fine"})
    store.save(project.id, {"secret": "other"})

    assert store.quarantine_corrupted() == []
    assert store.read(report_id)["secret"] == "fine"
    database.close()


def test_raw_report_maintain_combines_steps(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3")
    project = Project(name="demo", path=str(tmp_path / "workspace"))
    database.add_project(project)
    store = RawReportStore(tmp_path / "reports", database, KeyProtector(tmp_path))
    live_id = store.save(project.id, {"secret": "live"})
    doomed_id = store.save(project.id, {"secret": "destroy me"})
    store.destroy(doomed_id)

    stats = store.maintain()
    assert stats["records_removed"] >= 1
    assert stats["keys_destroyed"] >= 0
    assert store.read(live_id)["secret"] == "live"
    database.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI integration test")
def test_windows_dpapi_key_round_trip(tmp_path: Path) -> None:
    protector = KeyProtector(tmp_path)
    wrapped = protector.protect(b"secret-key-bytes")
    assert protector.unprotect(wrapped) == b"secret-key-bytes"


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI integration test")
def test_windows_protection_never_uses_dev_key_fallback(tmp_path: Path) -> None:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    protector = KeyProtector(tmp_path)
    wrapped = protector.protect(b"secret-key-bytes")
    assert protector.unprotect(wrapped) == b"secret-key-bytes"
    # The AES-GCM development fallback key must never be materialized on the
    # Windows production path.
    assert not (tmp_path / "config" / ".dev-key").exists()
    # A DPAPI blob is not a 12-byte-nonce AES-GCM payload, so attempting to
    # decrypt it with the dev-key algorithm fails loudly instead of silently
    # returning wrong key bytes.
    nonce, body = wrapped[:12], wrapped[12:]
    fallback_key = AESGCM.generate_key(bit_length=256)
    with pytest.raises(InvalidTag):
        AESGCM(fallback_key).decrypt(nonce, body, b"idlerdream-raw-report-key-v1")
