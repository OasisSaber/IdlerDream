from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from ..database import Database
from ..models import CurrentProjectState, Project


class ProjectService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, path: str, name: str | None = None, **overrides) -> Project:
        workspace = Path(path).expanduser().resolve(strict=False)
        if not workspace.exists() or not workspace.is_dir():
            raise ValueError(f"Workspace directory does not exist: {workspace}")
        project = Project(name=name or workspace.name, path=str(workspace), **overrides)
        self.database.add_project(project)
        self.database.upsert_current_state(CurrentProjectState(project_id=project.id))
        return project

    def get(self, project_id: UUID | str) -> Project:
        project = self.database.get_project(project_id)
        if not project:
            raise KeyError(f"Project not found: {project_id}")
        return project

    def list(self) -> list[Project]:
        return self.database.list_projects()

    def list_removed(self) -> list[Project]:
        return self.database.list_removed_projects()

    def update(self, project: Project) -> Project:
        project.updated_at = datetime.now(UTC)
        return self.database.update_project(project)

    def remove(self, project_id: UUID | str) -> Project:
        """Move a project to the recycle bin.

        The workspace directory is never deleted. Snapshot history and the
        current state are retained until the project is permanently purged.
        """
        project = self.get(project_id)
        if project.removed_at is not None:
            return project
        project.removed_at = datetime.now(UTC)
        project.updated_at = datetime.now(UTC)
        self.database.mark_project_removed(project_id, project.removed_at.isoformat())
        return self.database.update_project(project)

    def restore(self, project_id: UUID | str) -> Project:
        project = self.get(project_id)
        if project.removed_at is None:
            return project
        project.removed_at = None
        self.database.restore_project(project_id)
        return self.database.update_project(project)

    def purge(self, project_id: UUID | str) -> None:
        """Permanently delete the project row, its current state and snapshot
        index entries. The workspace directory itself is never touched."""
        self.get(project_id)
        self.database.purge_project(project_id)

    def discover(self, root: str, max_depth: int = 4) -> list[dict[str, str]]:
        base = Path(root).expanduser().resolve(strict=False)
        if not base.exists() or not base.is_dir():
            raise ValueError(f"Discovery root does not exist: {base}")
        results: list[dict[str, str]] = []
        for path in _walk_limited(base, max_depth=max_depth):
            markers = [
                marker
                for marker in (".git", ".jj", "package.json", "pyproject.toml", "Cargo.toml")
                if (path / marker).exists()
            ]
            if markers:
                results.append({"path": str(path), "name": path.name, "markers": ", ".join(markers)})
        deduplicated: dict[str, dict[str, str]] = {}
        for result in results:
            deduplicated[result["path"]] = result
        return list(deduplicated.values())


def _walk_limited(root: Path, max_depth: int):
    queue: list[tuple[Path, int]] = [(root, 0)]
    ignored = {"node_modules", ".venv", "venv", "dist", "build", ".git", ".jj"}
    while queue:
        current, depth = queue.pop(0)
        yield current
        if depth >= max_depth:
            continue
        try:
            children = [item for item in current.iterdir() if item.is_dir() and item.name not in ignored]
        except OSError:
            continue
        queue.extend((child, depth + 1) for child in children)
