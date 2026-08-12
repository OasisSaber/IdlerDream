"""CR-15 Inspector service tests.

Covers the Onboarding/Settings backend contracts:
- credential storage (forced to the DPAPI fallback so tests never touch the
  real Windows Credential Manager);
- non-sensitive config persistence and verdict invalidation;
- status assembly, the deep-inspection gate and the connectivity/compatibility
  state transitions;
- the ``inspector.*`` control-channel commands;
- the compatibility probe evidence (decoy fixture + filtered-snapshot manifest)
  and its launch-failure path.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest

from idlerdream.api import AppContext, handle_control
from idlerdream.inspection.compatibility import (
    MARKER,
    CompatibilityService,
    _SECRET_SENTINEL,
)
from idlerdream.models import CompatibilityResult, InspectorConfig
from idlerdream.security.credentials import CredentialStore
from idlerdream.services.inspector import (
    InspectorCompatibilityError,
    InspectorService,
)


@pytest.fixture(autouse=True)
def _force_fallback_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never write to the real Windows Credential Manager from tests."""
    monkeypatch.setattr(
        "idlerdream.security.credentials._load_advapi32", lambda: None
    )


class _FakeAdapter:
    """Duck-typed OpenCodeAdapter replacement (no real binary involved)."""

    def __init__(
        self,
        *,
        available: bool = True,
        version: str | None = "0.9.0",
        executable: str = "C:\\fake\\opencode.exe",
    ) -> None:
        self._available = available
        self._version = version
        self._executable = executable

    def available(self) -> bool:
        return self._available

    def _executable_path(self) -> str:
        return self._executable

    async def version(self) -> str | None:
        return self._version


class _FakeCompatibility:
    def __init__(self, result: CompatibilityResult) -> None:
        self._result = result

    async def run(self) -> CompatibilityResult:
        return self._result


def _service(tmp_path: Path, **kwargs: Any) -> InspectorService:
    return InspectorService(tmp_path, **kwargs)


def _context(inspector: InspectorService) -> AppContext:
    # inspector.* commands only touch context.inspector; the other services
    # are intentionally left as None to keep the unit focused.
    return AppContext(
        settings=None,
        database=None,
        projects=None,
        inspections=None,
        monitoring=None,
        snapshots=None,
        raw_reports=None,
        events=None,
        inspector=inspector,
    )


async def _control(inspector: InspectorService, command: str, payload: dict[str, Any]) -> dict[str, Any]:
    return await handle_control(_context(inspector), {"command": command, "payload": payload})


# -- credentials ------------------------------------------------------------


def test_credential_store_fallback_round_trip(tmp_path: Path) -> None:
    store = CredentialStore(tmp_path)
    assert store.configured("deepseek") is False
    assert store.get("deepseek") is None

    store.set("deepseek", "sk-test-123")
    assert store.configured("deepseek") is True
    assert store.get("deepseek") == "sk-test-123"

    # A fresh store instance must read the same protected file.
    reopened = CredentialStore(tmp_path)
    assert reopened.get("deepseek") == "sk-test-123"

    assert reopened.delete("deepseek") is True
    assert reopened.configured("deepseek") is False
    assert reopened.delete("deepseek") is False

    # The secret must never be stored in the clear.
    (tmp_path / "credentials" / "deepseek.enc").write_bytes(b"x")
    store.set("deepseek", "sk-test-456")
    raw = (tmp_path / "credentials" / "deepseek.enc").read_bytes()
    assert b"sk-test-456" not in raw


def test_credential_store_rejects_empty_secret_and_bad_provider(tmp_path: Path) -> None:
    store = CredentialStore(tmp_path)
    with pytest.raises(ValueError):
        store.set("deepseek", "")
    with pytest.raises(ValueError):
        store.set("", "secret")
    with pytest.raises(ValueError):
        store.set("deepseek/openai", "secret")
    with pytest.raises(ValueError):
        store.set("deepseek\\openai", "secret")


# -- configuration persistence ----------------------------------------------


def test_config_round_trips_across_service_instances(tmp_path: Path) -> None:
    service = _service(tmp_path, executable="opencode-test", model="m1")
    # Constructor defaults are adapter defaults, not persisted config.
    assert service.get_config().opencode_executable is None
    assert service._adapter_for().executable == "opencode-test"

    service.update_config(
        InspectorConfig(
            provider="deepseek",
            base_url="https://api.example.com/v1",
            model="deepseek/v4",
        )
    )
    reopened = _service(tmp_path, executable="opencode-test")
    config = reopened.get_config()
    assert config.provider == "deepseek"
    assert config.base_url == "https://api.example.com/v1"
    assert config.model == "deepseek/v4"
    assert config.opencode_executable is None  # never persisted


def test_config_change_invalidates_compatibility_verdict(tmp_path: Path) -> None:
    service = _service(tmp_path, adapter=_FakeAdapter())
    service._state["compatibility_status"] = "verified"
    service._state["deep_inspection_enabled"] = True
    service._state["verified_model"] = "deepseek/v4"

    service.update_config(InspectorConfig(model="other/model"))
    assert service._state["compatibility_status"] == "unverified"
    assert service._state["deep_inspection_enabled"] is False
    assert "compatibility_checked_at" not in service._state

    status = asyncio.run(service.status())
    assert status.compatibility_status == "unverified"
    assert status.deep_inspection_enabled is False


# -- status -----------------------------------------------------------------


def test_status_reports_detection_and_warnings(tmp_path: Path) -> None:
    service = _service(tmp_path, adapter=_FakeAdapter())
    status = asyncio.run(service.status())
    assert status.opencode_available is True
    assert status.opencode_version == "0.9.0"
    assert status.opencode_executable == "C:\\fake\\opencode.exe"
    assert status.credential_configured is False
    assert status.deep_inspection_enabled is False
    assert "Model not configured" in status.warnings

    service.update_config(InspectorConfig(provider="deepseek", model="deepseek/v4"))
    status = asyncio.run(service.status())
    assert status.provider == "deepseek"
    assert status.model == "deepseek/v4"
    assert "Provider credential missing" in status.warnings

    asyncio.run(_control(service, "inspector.credential.set", {"provider": "deepseek", "api_key": "sk-x"}))
    status = asyncio.run(service.status())
    assert status.credential_configured is True
    assert status.warnings == []


def test_status_flags_missing_executable(tmp_path: Path) -> None:
    service = _service(tmp_path, adapter=_FakeAdapter(available=False, version=None))
    status = asyncio.run(service.status())
    assert status.opencode_available is False
    assert status.opencode_version is None
    assert "OpenCode executable not found" in status.warnings


# -- deep inspection gate ---------------------------------------------------


def test_deep_gate_blocks_until_verified_and_enabled(tmp_path: Path) -> None:
    service = _service(tmp_path, adapter=_FakeAdapter())
    with pytest.raises(InspectorCompatibilityError):
        service.assert_deep_inspection_allowed()

    service._state["compatibility_status"] = "verified"
    service._state["deep_inspection_enabled"] = False
    with pytest.raises(InspectorCompatibilityError):
        service.assert_deep_inspection_allowed()

    service._state["deep_inspection_enabled"] = True
    service.assert_deep_inspection_allowed()  # must not raise


def test_compatibility_test_enables_deep_inspection_on_verified(tmp_path: Path) -> None:
    service = _service(
        tmp_path,
        adapter=_FakeAdapter(),
        compatibility=_FakeCompatibility(CompatibilityResult(status="verified")),
    )
    result = asyncio.run(service.compatibility_test())
    assert result.status == "verified"
    assert service._state["compatibility_status"] == "verified"
    assert service._state["deep_inspection_enabled"] is True
    assert service._state["compatibility_checked_at"] is not None
    service.assert_deep_inspection_allowed()  # must not raise

    # The verdict survives a service restart.
    reopened = _service(tmp_path, adapter=_FakeAdapter())
    status = asyncio.run(reopened.status())
    assert status.compatibility_status == "verified"
    assert status.deep_inspection_enabled is True


def test_compatibility_test_disables_deep_inspection_on_failure(tmp_path: Path) -> None:
    service = _service(
        tmp_path,
        adapter=_FakeAdapter(),
        compatibility=_FakeCompatibility(CompatibilityResult(status="failed")),
    )
    result = asyncio.run(service.compatibility_test())
    assert result.status == "failed"
    assert service._state["compatibility_status"] == "failed"
    assert service._state["deep_inspection_enabled"] is False
    with pytest.raises(InspectorCompatibilityError):
        service.assert_deep_inspection_allowed()


def test_status_auto_invalidates_verdict_on_version_change(tmp_path: Path) -> None:
    service = _service(tmp_path, adapter=_FakeAdapter(version="0.8.0"))
    service._state["compatibility_status"] = "verified"
    service._state["deep_inspection_enabled"] = True
    service._state["verified_opencode_version"] = "0.9.0"

    status = asyncio.run(service.status())
    assert status.compatibility_status == "unverified"
    assert status.deep_inspection_enabled is False


# -- connectivity -----------------------------------------------------------


def test_connectivity_test_rejects_model_without_provider_slash(tmp_path: Path) -> None:
    service = _service(tmp_path, adapter=_FakeAdapter())
    result = asyncio.run(
        service.connectivity_test("deepseek", "", "v4", "sk-x")
    )
    assert result.status == "failed"
    assert result.error is not None and "provider/model" in result.error
    # Config and credential are still saved before validation.
    assert service.get_config().provider == "deepseek"
    assert service.get_config().model == "v4"
    assert service.credential_configured("deepseek") is True


def test_connectivity_test_requires_credential(tmp_path: Path) -> None:
    service = _service(tmp_path, adapter=_FakeAdapter())
    result = asyncio.run(
        service.connectivity_test("deepseek", "", "deepseek/v4", "")
    )
    assert result.status == "failed"
    assert result.error is not None and "credential" in result.error


# -- control-channel commands ------------------------------------------------


def test_control_inspector_status_command(tmp_path: Path) -> None:
    service = _service(tmp_path, adapter=_FakeAdapter())
    result = asyncio.run(_control(service, "inspector.status", {}))
    assert result["opencode_available"] is True
    assert result["credential_configured"] is False
    assert result["compatibility_status"] == "unverified"


def test_control_inspector_config_update_and_get(tmp_path: Path) -> None:
    service = _service(tmp_path, adapter=_FakeAdapter())
    updated = asyncio.run(
        _control(
            service,
            "inspector.config.update",
            {"provider": "deepseek", "base_url": "https://api.example.com/v1", "model": "deepseek/v4"},
        )
    )
    assert updated["model"] == "deepseek/v4"
    fetched = asyncio.run(_control(service, "inspector.config.get", {}))
    assert fetched["provider"] == "deepseek"
    assert fetched["base_url"] == "https://api.example.com/v1"


def test_control_inspector_credential_set_and_delete(tmp_path: Path) -> None:
    service = _service(tmp_path, adapter=_FakeAdapter())
    set_result = asyncio.run(
        _control(service, "inspector.credential.set", {"provider": "deepseek", "api_key": "sk-secret"})
    )
    assert set_result == {"configured": True}
    assert service.credential_configured("deepseek") is True

    with pytest.raises(ValueError):
        asyncio.run(_control(service, "inspector.credential.set", {}))

    deleted = asyncio.run(
        _control(service, "inspector.credential.delete", {"provider": "deepseek"})
    )
    assert deleted == {"configured": False}
    assert service.credential_configured("deepseek") is False


def test_control_inspector_connectivity_and_compatibility(tmp_path: Path) -> None:
    service = _service(
        tmp_path,
        adapter=_FakeAdapter(),
        compatibility=_FakeCompatibility(CompatibilityResult(status="verified")),
    )
    connectivity = asyncio.run(
        _control(
            service,
            "inspector.connectivity.test",
            {"provider": "deepseek", "base_url": "", "model": "v4", "api_key": ""},
        )
    )
    assert connectivity["status"] == "failed"
    assert "provider/model" in (connectivity["error"] or "")

    compatibility = asyncio.run(_control(service, "inspector.compatibility.test", {}))
    assert compatibility["status"] == "verified"
    status = asyncio.run(_control(service, "inspector.status", {}))
    assert status["deep_inspection_enabled"] is True


# -- compatibility probe evidence --------------------------------------------


def test_compatibility_fixture_contains_decoy_files(tmp_path: Path) -> None:
    service = CompatibilityService(executable="opencode", config_dir=tmp_path / "cfg")
    fixture = tmp_path / "fixture"
    service._create_fixture(fixture)
    for name in ("README.md", "src/marker.py", "AGENTS.md", "opencode.json", ".env", "secret.key"):
        assert (fixture / name).is_file(), name
    config_source = (fixture / "src" / "config.py").read_text(encoding="utf-8")
    assert _SECRET_SENTINEL in config_source


def test_compatibility_snapshot_excludes_control_and_secret_files(tmp_path: Path) -> None:
    from idlerdream.models import FactBaseline, Project

    service = CompatibilityService(executable="opencode", config_dir=tmp_path / "cfg")
    fixture = tmp_path / "fixture"
    service._create_fixture(fixture)

    project = Project(name="compat-fixture", path=str(fixture))
    baseline = FactBaseline(
        project_id=project.id,
        workspace_path=str(fixture),
        workspace_fingerprint="compat-fixture-fp",
        considered_paths=[
            "README.md",
            "src/marker.py",
            "src/config.py",
            "AGENTS.md",
            "opencode.json",
            ".env",
            "secret.key",
        ],
    )
    snapshot = service.snapshot_builder.build(
        job_id="compatibility-test", project=project, baseline=baseline
    )
    manifest = json.loads(
        (
            snapshot.root / ".idlerdream" / "inspection-manifest.json"
        ).read_text(encoding="utf-8")
    )
    copied = set(manifest["copied_files"])
    excluded = {
        item["path"]: item["reason"]
        for item in manifest["excluded_files"]
    }

    # Ordinary source stays readable; control and sensitive files vanish.
    assert "README.md" in copied
    assert "src/marker.py" in copied
    for name in ("AGENTS.md", "opencode.json", ".env", "secret.key"):
        assert name not in copied
    assert excluded.get("src/config.py") == "secret_content"


def test_compatibility_run_reports_clean_failure_without_executable(tmp_path: Path) -> None:
    service = CompatibilityService(
        executable="definitely-missing-opencode-9b41",
        config_dir=tmp_path / "cfg",
    )
    result = asyncio.run(service.run())
    assert result.status == "failed"
    assert result.error is not None and "could not launch OpenCode" in result.error
    assert "OpenCode executable is unavailable" in result.warnings


@pytest.mark.skipif(os.name == "nt", reason="stub probe is a POSIX shell script")
def test_compatibility_run_verifies_with_stub_probe(tmp_path: Path) -> None:
    stub = tmp_path / "opencode-stub.sh"
    stub.write_text(
        "#!/bin/sh\n"
        f"cat <<'EOF'\n"
        f'{{"marker": "{MARKER}", "read_ok": true, "sensitive_visible": false}}\n'
        "EOF\n"
        "exit 0\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    service = CompatibilityService(
        executable=str(stub),
        model="stub/model",
        config_dir=tmp_path / "cfg",
        timeout_seconds=60,
    )
    result = asyncio.run(service.run())
    assert result.status == "verified"
    assert result.ordinary_source_read is True
    assert result.sensitive_content_absent is True
    assert result.snapshot_unmodified is True
