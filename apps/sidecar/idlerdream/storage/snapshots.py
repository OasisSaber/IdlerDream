from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path
from uuid import UUID

from ..database import Database
from ..models import SnapshotEvent


class SnapshotStore:
    def __init__(self, directory: Path, database: Database) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.database = database
        self._lock = threading.RLock()

    def append(self, event: SnapshotEvent) -> Path:
        filename = _week_filename(event.created_at)
        path = self.directory / filename
        payload = (event.model_dump_json() + "\n").encode("utf-8")
        with self._lock:
            with path.open("ab") as handle:
                handle.seek(0, os.SEEK_END)
                offset = handle.tell()
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            self.database.insert_snapshot_index(event, filename, offset, len(payload))
        return path

    def list_project(self, project_id: UUID | str) -> list[SnapshotEvent]:
        events: list[SnapshotEvent] = []
        for row in self.database.list_snapshot_locations(project_id):
            path = self.directory / row["week_file"]
            try:
                with path.open("rb") as handle:
                    handle.seek(row["byte_offset"])
                    payload = handle.read(row["byte_length"])
                events.append(SnapshotEvent.model_validate_json(payload))
            except (OSError, ValueError):
                continue
        return events

    def latest(self, project_id: UUID | str) -> SnapshotEvent | None:
        events = self.list_project(project_id)
        return events[0] if events else None


def _week_filename(value: datetime) -> str:
    iso_year, iso_week, _ = value.isocalendar()
    return f"{iso_year}-W{iso_week:02d}.jsonl"
