from __future__ import annotations

from pathlib import Path

import pytest

from idlerdream.security.paths import ensure_within_workspace, is_sensitive_path
from idlerdream.security.redaction import redact_text, redact_value


def test_sensitive_paths_are_rejected() -> None:
    assert is_sensitive_path(".env.local")
    assert is_sensitive_path("credentials.json")
    assert is_sensitive_path(Path("C:/Users/test/.aws/credentials"))
    assert not is_sensitive_path("src/config.ts")


def test_workspace_escape_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    allowed = workspace / "src" / "main.py"
    assert ensure_within_workspace(allowed, workspace) == allowed.resolve(strict=False)
    with pytest.raises(PermissionError):
        ensure_within_workspace(tmp_path / "other.txt", workspace)


def test_redaction_removes_common_secrets() -> None:
    text = "api_key=abcdef token:xyz Bearer aaa.bbb.ccc sk-proj-123456789012345"
    redacted = redact_text(text)
    assert "abcdef" not in redacted
    assert "aaa.bbb.ccc" not in redacted
    assert "sk-proj" not in redacted
    assert redact_value({"password": "secret", "nested": {"token": "abc"}})["password"] == "<redacted>"


def test_opencode_inspector_disables_shell_and_isolates_home(tmp_path: Path) -> None:
    import json
    from idlerdream.inspection.opencode import OpenCodeAdapter
    from idlerdream.models import Project

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    adapter = OpenCodeAdapter(config_dir=tmp_path / "inspector")
    env = adapter._isolated_environment(Project(name="demo", path=str(workspace)))
    permission = json.loads(env["OPENCODE_PERMISSION"])
    assert permission["bash"] == "deny"
    assert permission["edit"] == "deny"
    assert env["HOME"] != str(Path.home())
    assert str(workspace.resolve(strict=False).as_posix()) in json.dumps(permission)
