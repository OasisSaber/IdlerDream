from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from uuid import UUID

from .models import CurrentProjectState, Project, SnapshotEvent


SCHEMA_VERSION = 1


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._migrate()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._connection
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _migrate(self) -> None:
        with self.transaction() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    path TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    project_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS current_project_state (
                    project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS snapshot_index (
                    snapshot_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    week_file TEXT NOT NULL,
                    byte_offset INTEGER NOT NULL,
                    byte_length INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    deleted INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_snapshot_project_time
                    ON snapshot_index(project_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS raw_report_keys (
                    report_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    week_file TEXT NOT NULL,
                    wrapped_key BLOB,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    destroyed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS agent_sessions (
                    session_id TEXT PRIMARY KEY,
                    project_id TEXT,
                    process_pid INTEGER NOT NULL,
                    session_json TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    exited_at TEXT
                );
                """
            )
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    def add_project(self, project: Project) -> Project:
        payload = project.model_dump_json()
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO projects(id, path, name, project_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    str(project.id),
                    project.path,
                    project.name,
                    payload,
                    project.created_at.isoformat(),
                    project.updated_at.isoformat(),
                ),
            )
        return project

    def update_project(self, project: Project) -> Project:
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE projects
                SET path = ?, name = ?, project_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    project.path,
                    project.name,
                    project.model_dump_json(),
                    project.updated_at.isoformat(),
                    str(project.id),
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Project not found: {project.id}")
        return project

    def get_project(self, project_id: UUID | str) -> Project | None:
        row = self._connection.execute(
            "SELECT project_json FROM projects WHERE id = ?", (str(project_id),)
        ).fetchone()
        return Project.model_validate_json(row["project_json"]) if row else None

    def list_projects(self) -> list[Project]:
        rows = self._connection.execute(
            "SELECT project_json FROM projects ORDER BY updated_at DESC"
        ).fetchall()
        return [Project.model_validate_json(row["project_json"]) for row in rows]

    def delete_project(self, project_id: UUID | str) -> None:
        with self.transaction() as connection:
            connection.execute("DELETE FROM projects WHERE id = ?", (str(project_id),))

    def upsert_current_state(self, state: CurrentProjectState) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO current_project_state(project_id, state_json, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (str(state.project_id), state.model_dump_json(), state.updated_at.isoformat()),
            )

    def get_current_state(self, project_id: UUID | str) -> CurrentProjectState | None:
        row = self._connection.execute(
            "SELECT state_json FROM current_project_state WHERE project_id = ?",
            (str(project_id),),
        ).fetchone()
        return CurrentProjectState.model_validate_json(row["state_json"]) if row else None

    def list_current_states(self) -> list[CurrentProjectState]:
        rows = self._connection.execute(
            "SELECT state_json FROM current_project_state ORDER BY updated_at DESC"
        ).fetchall()
        return [CurrentProjectState.model_validate_json(row["state_json"]) for row in rows]

    def insert_snapshot_index(
        self,
        event: SnapshotEvent,
        week_file: str,
        byte_offset: int,
        byte_length: int,
    ) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO snapshot_index(
                    snapshot_id, project_id, week_file, byte_offset, byte_length,
                    event_type, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.snapshot_id),
                    str(event.project_id),
                    week_file,
                    byte_offset,
                    byte_length,
                    event.event_type,
                    event.created_at.isoformat(),
                ),
            )

    def list_snapshot_locations(self, project_id: UUID | str) -> list[sqlite3.Row]:
        return self._connection.execute(
            """
            SELECT * FROM snapshot_index
            WHERE project_id = ? AND deleted = 0
            ORDER BY created_at DESC
            """,
            (str(project_id),),
        ).fetchall()

    def mark_snapshot_deleted(self, snapshot_id: UUID | str) -> None:
        with self.transaction() as connection:
            connection.execute(
                "UPDATE snapshot_index SET deleted = 1 WHERE snapshot_id = ?",
                (str(snapshot_id),),
            )

    def save_raw_report_key(
        self,
        report_id: str,
        project_id: str,
        week_file: str,
        wrapped_key: bytes,
        created_at: str,
        expires_at: str,
    ) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO raw_report_keys(
                    report_id, project_id, week_file, wrapped_key, created_at, expires_at
                ) VALUES(?, ?, ?, ?, ?, ?)
                """,
                (report_id, project_id, week_file, wrapped_key, created_at, expires_at),
            )

    def get_raw_report_key(self, report_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT * FROM raw_report_keys WHERE report_id = ?", (report_id,)
        ).fetchone()

    def destroy_raw_report_key(self, report_id: str, destroyed_at: str) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                UPDATE raw_report_keys
                SET wrapped_key = NULL, destroyed_at = ?
                WHERE report_id = ?
                """,
                (destroyed_at, report_id),
            )

    def expired_raw_reports(self, now_iso: str) -> list[sqlite3.Row]:
        return self._connection.execute(
            """
            SELECT * FROM raw_report_keys
            WHERE wrapped_key IS NOT NULL AND expires_at <= ?
            """,
            (now_iso,),
        ).fetchall()

    def export_debug_summary(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "projects": self._connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0],
            "snapshots": self._connection.execute(
                "SELECT COUNT(*) FROM snapshot_index WHERE deleted = 0"
            ).fetchone()[0],
            "raw_reports_live": self._connection.execute(
                "SELECT COUNT(*) FROM raw_report_keys WHERE wrapped_key IS NOT NULL"
            ).fetchone()[0],
        }
