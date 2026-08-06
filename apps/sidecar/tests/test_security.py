from __future__ import annotations

import json
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
    redacted_value = redact_value({"password": "secret", "nested": {"token": "abc"}})
    assert redacted_value["password"] == "<redacted>"


def test_opencode_inspector_disables_dangerous_tools_and_isolates_home(tmp_path: Path) -> None:
    from idlerdream.inspection.opencode import OpenCodeAdapter

    adapter = OpenCodeAdapter(config_dir=tmp_path / "inspector")
    env = adapter._isolated_environment()
    permission = json.loads(env["OPENCODE_PERMISSION"])
    assert permission["bash"] == "deny"
    assert permission["edit"] == "deny"
    assert permission["task"] == "deny"
    assert permission["external_directory"] == "deny"
    assert env["HOME"] != str(Path.home())


def test_opencode_read_permission_uses_snapshot_not_workspace_path_globs(tmp_path: Path) -> None:
    from idlerdream.inspection.opencode import OpenCodeAdapter

    adapter = OpenCodeAdapter(config_dir=tmp_path / "inspector")
    permission = json.loads(adapter._isolated_environment()["OPENCODE_PERMISSION"])
    assert permission["read"] == "allow"
    assert permission["glob"] == "allow"
    assert permission["grep"] == "allow"
    assert permission["list"] == "allow"
    serialized = json.dumps(permission)
    assert "/**" not in serialized
    assert "\\**" not in serialized


def test_report_text_fields_are_redacted() -> None:
    from idlerdream.models import NextAction, NextActor
    from idlerdream.security.redaction import redact_report_text_fields

    report = type(
        "Report",
        (),
        {
            "summary": "auth uses api_key=supersecret123",
            "phase": "ok",
            "next_action": NextAction(
                actor=NextActor.USER,
                action="rotate token sk-proj-abcdefghijklmno123",
            ),
            "facts": [],
            "inferences": [],
            "uncertainties": [],
        },
    )()
    redact_report_text_fields(report)
    assert "supersecret123" not in report.summary
    assert "sk-proj" not in report.next_action.action
