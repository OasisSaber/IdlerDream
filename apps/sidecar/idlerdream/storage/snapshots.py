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

    def reconcile(self) -> dict[str, int]:
        """Reconcile weekly JSONL files with the SQLite snapshot index.

        A crash between the JSONL append and the SQLite insert leaves an orphan
        record; the reverse path (missing file content) is also recoverable.
        This scans every week file and:

        - truncates an incomplete trailing record left by a crashed append;
        - appends a missing newline when the trailing record is complete JSON;
        - rebuilds missing index rows from valid records using ``snapshot_id``.

        Returns counts: ``files`` scanned, ``rows_rebuilt``, ``truncated``
        trailing records removed, ``newline_fixed``.
        """
        with self._lock:
            counts = {"files": 0, "rows_rebuilt": 0, "truncated": 0, "newline_fixed": 0}
            for path in sorted(self.directory.glob("*-W*.jsonl")):
                counts["files"] += 1
                records: list[tuple[SnapshotEvent, int, int]] = []
                trailing_fragment: tuple[SnapshotEvent, int, int] | None = None
                truncated_end: int | None = None
                with path.open("rb") as handle:
                    offset = 0
                    while True:
                        line = handle.readline()
                        if not line:
                            break
                        if line.endswith(b"\n"):
                            payload = line[:-1]
                        else:
                            payload = line
                        try:
                            event = SnapshotEvent.model_validate_json(payload.decode("utf-8"))
                        except ValueError:
                            event = None
                        if line.endswith(b"\n"):
                            if event is not None:
                                records.append((event, offset, len(line)))
                            offset += len(line)
                            truncated_end = offset
                        elif event is not None:
                            # Complete JSON written without its trailing newline.
                            trailing_fragment = (event, offset, len(line))
                            records.append(trailing_fragment)
                            truncated_end = offset + len(line)
                        else:
                            # Partial write from a crashed append: drop it.
                            truncated_end = offset
                        if not line.endswith(b"\n"):
                            break

                file_end = path.stat().st_size
                if truncated_end is not None and file_end > truncated_end:
                    with path.open("r+b") as handle:
                        handle.truncate(truncated_end)
                    counts["truncated"] += 1
                if trailing_fragment is not None:
                    with path.open("ab") as handle:
                        handle.write(b"\n")
                    counts["newline_fixed"] += 1
                for event, offset, length in records:
                    if self.database.get_snapshot_index(event.snapshot_id) is None:
                        self.database.insert_snapshot_index(
                            event, path.name, offset, length
                        )
                        counts["rows_rebuilt"] += 1
            return counts


def _week_filename(value: datetime) -> str:
    iso_year, iso_week, _ = value.isocalendar()
    return f"{iso_year}-W{iso_week:02d}.jsonl"
