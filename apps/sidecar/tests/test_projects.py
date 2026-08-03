from pathlib import Path

import pytest

from idlerdream.database import Database
from idlerdream.services.projects import ProjectService


def test_discovery_includes_selected_root(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    database = Database(tmp_path / "db.sqlite3")
    try:
        service = ProjectService(database)
        results = service.discover(str(root))
        assert any(item["path"] == str(root.resolve(strict=False)) for item in results)
    finally:
        database.close()


def test_remove_is_two_stage_and_never_deletes_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    marker = workspace / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    database = Database(tmp_path / "db.sqlite3")
    try:
        service = ProjectService(database)
        project = service.add(str(workspace))
        service.remove(project.id)
        removed = service.list_removed()
        assert len(removed) == 1
        assert removed[0].id == project.id
        assert removed[0].removed_at is not None
        # Not visible in the active list.
        assert all(item.id != project.id for item in service.list())
        # The workspace directory is untouched.
        assert marker.exists()
    finally:
        database.close()


def test_restore_brings_project_back(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    database = Database(tmp_path / "db.sqlite3")
    try:
        service = ProjectService(database)
        project = service.add(str(workspace))
        service.remove(project.id)
        restored = service.restore(project.id)
        assert restored.removed_at is None
        assert any(item.id == project.id for item in service.list())
        assert not service.list_removed()
    finally:
        database.close()


def test_purge_removes_project_row_but_keeps_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    database = Database(tmp_path / "db.sqlite3")
    try:
        service = ProjectService(database)
        project = service.add(str(workspace))
        service.remove(project.id)
        service.purge(project.id)
        assert not service.list_removed()
        with pytest.raises(KeyError):
            service.get(project.id)
        assert workspace.exists()
    finally:
        database.close()


def test_removed_at_survives_database_reopen(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    database = Database(tmp_path / "db.sqlite3")
    service = ProjectService(database)
    project = service.add(str(workspace))
    service.remove(project.id)
    database.close()

    reopened = Database(tmp_path / "db.sqlite3")
    try:
        assert len(ProjectService(reopened).list_removed()) == 1
    finally:
        reopened.close()
