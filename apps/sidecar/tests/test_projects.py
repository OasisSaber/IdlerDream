from pathlib import Path

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
