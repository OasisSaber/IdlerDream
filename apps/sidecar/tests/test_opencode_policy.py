from __future__ import annotations

import json
from pathlib import Path

from idlerdream.inspection.opencode import OpenCodeAdapter


def test_opencode_policy_allows_reads_without_path_globs_and_denies_dangerous_tools(
    tmp_path: Path,
) -> None:
    adapter = OpenCodeAdapter(config_dir=tmp_path / "config")
    environment = adapter._isolated_environment()
    permission = json.loads(environment["OPENCODE_PERMISSION"])

    assert permission["read"] == "allow"
    assert permission["glob"] == "allow"
    assert permission["grep"] == "allow"
    assert permission["list"] == "allow"
    assert permission["external_directory"] == "deny"
    for tool in ("edit", "write", "patch", "bash", "task", "webfetch", "websearch", "skill"):
        assert permission[tool] == "deny"

    # Regression for issue #19: no workspace-specific path allowlist remains.
    serialized = json.dumps(permission)
    assert "/**" not in serialized
    assert "\\**" not in serialized


def test_prompt_does_not_expose_real_workspace_path(tmp_path: Path) -> None:
    from idlerdream.inspection.prompt import build_inspection_prompt
    from idlerdream.models import AgentProcess, FactBaseline, Project

    workspace = tmp_path / "private-workspace"
    workspace.mkdir()
    project = Project(name="demo", path=str(workspace), metadata={"private": str(workspace)})
    baseline = FactBaseline(
        project_id=project.id,
        workspace_path=str(workspace),
        workspace_fingerprint="fingerprint",
        considered_paths=["src/main.py"],
        agents=[
            AgentProcess(
                pid=7,
                name="opencode.exe",
                cwd=str(workspace),
                executable=str(workspace / "bin" / "opencode.exe"),
                command_summary=f"opencode --dir {workspace}",
            )
        ],
    )

    prompt = build_inspection_prompt(project, baseline, snapshot_manifest={"copied_files": 1})
    assert str(workspace) not in prompt
    assert "src/main.py" in prompt


def test_prepare_provider_auth_copies_only_requested_provider(tmp_path: Path) -> None:
    from idlerdream.inspection.opencode import prepare_provider_auth

    real_auth = tmp_path / "real-auth.json"
    real_auth.write_text(
        json.dumps(
            {
                "opencode-go": {"type": "api", "key": "sk-test-opencode"},
                "openai": {"type": "oauth", "access": "x"},
            }
        ),
        encoding="utf-8",
    )
    isolated = tmp_path / "isolated-home"
    warnings = prepare_provider_auth(
        "opencode-go/deepseek-v4-flash", isolated, real_auth
    )
    target = isolated / "data" / "opencode" / "auth.json"
    assert warnings == []
    assert target.is_file()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert set(payload) == {"opencode-go"}
    assert payload["opencode-go"]["key"] == "sk-test-opencode"


def test_prepare_provider_auth_missing_provider_warns(tmp_path: Path) -> None:
    from idlerdream.inspection.opencode import prepare_provider_auth

    real_auth = tmp_path / "real-auth.json"
    real_auth.write_text(
        json.dumps({"openai": {"type": "api", "key": "sk-x"}}), encoding="utf-8"
    )
    isolated = tmp_path / "isolated-home"
    warnings = prepare_provider_auth(
        "opencode-go/deepseek-v4-flash", isolated, real_auth
    )
    assert warnings
    assert not (isolated / "data" / "opencode" / "auth.json").exists()


def test_prepare_provider_auth_no_model_is_noop(tmp_path: Path) -> None:
    from idlerdream.inspection.opencode import prepare_provider_auth

    real_auth = tmp_path / "real-auth.json"
    real_auth.write_text(
        json.dumps({"opencode-go": {"type": "api", "key": "sk-x"}}),
        encoding="utf-8",
    )
    warnings = prepare_provider_auth(None, tmp_path / "isolated", real_auth)
    assert warnings == []
    assert not (tmp_path / "isolated" / "data").exists()


def test_default_opencode_model_reads_jsonc_with_urls(tmp_path: Path) -> None:
    from idlerdream.inspection.opencode import default_opencode_model

    (tmp_path / "opencode.jsonc").write_text(
        '{\n'
        '  "$schema": "https://opencode.ai/config.json",\n'
        '  "model": "opencode-go/deepseek-v4-flash", // default model\n'
        '  "permission": { "skill": { "*": "allow" } }\n'
        '}\n',
        encoding="utf-8",
    )
    assert default_opencode_model(tmp_path) == "opencode-go/deepseek-v4-flash"


def test_adapter_resolves_configured_default_model(tmp_path: Path) -> None:
    from idlerdream.inspection.opencode import OpenCodeAdapter

    (tmp_path / "opencode.json").write_text(
        json.dumps({"model": "provider/example"}), encoding="utf-8"
    )
    adapter = OpenCodeAdapter(config_dir=tmp_path / "inspector", user_config_dir=tmp_path)
    assert adapter.resolve_model() == "provider/example"


def test_adapter_explicit_model_wins_over_config(tmp_path: Path) -> None:
    from idlerdream.inspection.opencode import OpenCodeAdapter

    (tmp_path / "opencode.json").write_text(
        json.dumps({"model": "provider/example"}), encoding="utf-8"
    )
    adapter = OpenCodeAdapter(
        config_dir=tmp_path / "inspector",
        model="explicit/model",
        user_config_dir=tmp_path,
    )
    assert adapter.resolve_model() == "explicit/model"


def test_resolve_executable_follows_npm_cmd_shim(tmp_path: Path, monkeypatch) -> None:
    from idlerdream.inspection.opencode import _resolve_executable

    real = tmp_path / "node_modules" / "opencode-ai" / "bin" / "tool.exe"
    real.parent.mkdir(parents=True)
    real.write_bytes(b"MZ")
    (tmp_path / "tool.cmd").write_text(
        '@ECHO off\r\n'
        '"%dp0%\\node_modules\\opencode-ai\\bin\\tool.exe"   %*\r\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("PATH", str(tmp_path))
    assert Path(_resolve_executable("tool")).resolve() == real.resolve()


def test_resolve_executable_returns_exe_directly(tmp_path: Path, monkeypatch) -> None:
    from idlerdream.inspection.opencode import _resolve_executable

    real = tmp_path / "tool.exe"
    real.write_bytes(b"MZ")
    monkeypatch.setenv("PATH", str(tmp_path))
    assert _resolve_executable("tool.exe") == str(real)


def test_assistant_text_fragments_excludes_tool_outputs() -> None:
    from idlerdream.inspection.opencode import _assistant_text_fragments

    text_event = {
        "type": "text",
        "part": {"type": "text", "text": '{"core_status": "ok"}'},
    }
    tool_event = {
        "type": "tool_use",
        "part": {
            "type": "tool",
            "tool": "read",
            "state": {"output": "<path>x</path>\n1: {\"policy_version\": \"v1\"}"},
        },
    }
    step_event = {"type": "step_start", "part": {"type": "step-start"}}
    assert _assistant_text_fragments(text_event) == ['{"core_status": "ok"}']
    assert _assistant_text_fragments(tool_event) == []
    assert _assistant_text_fragments(step_event) == []
