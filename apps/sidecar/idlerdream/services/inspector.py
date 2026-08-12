"""Inspector settings, status and validation service (CR-15).

Owns the non-sensitive Inspector configuration and validation state
(``settings.json`` in the data directory), the CredentialStore, and the
connectivity / compatibility test entry points. The API key never touches
``settings.json``, the database, logs or the renderer beyond the input field.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..inspection.compatibility import CompatibilityService
from ..inspection.opencode import OpenCodeAdapter, _resolve_executable
from ..models import (
    CompatibilityResult,
    ConnectivityResult,
    InspectorConfig,
    InspectorStatus,
)
from ..security.credentials import CredentialStore

_STATE_VERSION = 1


class InspectorCompatibilityError(RuntimeError):
    """Raised when a deep inspection is attempted without a verified boundary."""


class InspectorService:
    """Central state source for Onboarding and Settings (no hardcoded UI state)."""

    def __init__(
        self,
        data_dir: Path,
        *,
        executable: str = "opencode",
        model: str | None = None,
        credential_store: CredentialStore | None = None,
        adapter: OpenCodeAdapter | None = None,
        compatibility: CompatibilityService | None = None,
    ) -> None:
        self.data_dir = Path(data_dir).resolve(strict=False)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.data_dir / "settings.json"
        self._executable_default = executable
        self._model_default = model
        self._store = credential_store or CredentialStore(self.data_dir)
        self._adapter = adapter
        self._compatibility = compatibility
        self._state: dict[str, Any] = self._load_state()

    # -- persistence ---------------------------------------------------------

    def _load_state(self) -> dict[str, Any]:
        if not self.settings_path.is_file():
            return {"version": _STATE_VERSION}
        try:
            state = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return state if isinstance(state, dict) else {"version": _STATE_VERSION}
        except (OSError, json.JSONDecodeError):
            return {"version": _STATE_VERSION}

    def _save_state(self) -> None:
        self.settings_path.write_text(
            json.dumps(self._state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # -- config --------------------------------------------------------------

    def get_config(self) -> InspectorConfig:
        config = self._state.get("config", {})
        return InspectorConfig(
            provider=config.get("provider"),
            base_url=config.get("base_url"),
            model=config.get("model"),
            opencode_executable=config.get("opencode_executable"),
        )

    def update_config(self, config: InspectorConfig) -> InspectorConfig:
        """Persist non-sensitive settings; never accepts an API key."""
        previous = self.get_config()
        if (
            config.model != previous.model
            or config.provider != previous.provider
            or config.base_url != previous.base_url
            or config.opencode_executable != previous.opencode_executable
        ):
            # A changed profile invalidates a previous compatibility verdict.
            self._state["compatibility_status"] = "unverified"
            self._state.pop("compatibility_checked_at", None)
            self._state.pop("verified_opencode_version", None)
            self._state.pop("verified_model", None)
            self._state["deep_inspection_enabled"] = False
        self._state["config"] = config.model_dump(exclude_none=True)
        self._save_state()
        return self.get_config()

    # -- credential ----------------------------------------------------------

    def set_credential(self, provider: str, secret: str) -> bool:
        self._store.set(provider, secret)
        self._state.setdefault("config", {})["provider"] = provider
        self._save_state()
        return True

    def delete_credential(self, provider: str) -> bool:
        existed = self._store.delete(provider)
        self._save_state()
        return existed

    def credential_configured(self, provider: str) -> bool:
        return self._store.configured(provider)

    # -- opencode detection --------------------------------------------------

    def _adapter_for(self) -> OpenCodeAdapter:
        if self._adapter is not None:
            return self._adapter
        config = self.get_config()
        return OpenCodeAdapter(
            executable=config.opencode_executable or self._executable_default,
            model=config.model or self._model_default,
            config_dir=self.data_dir / "opencode-inspector",
        )

    async def opencode_detection(self) -> tuple[bool, str | None, str | None]:
        adapter = self._adapter_for()
        available = adapter.available()
        executable = adapter._executable_path() if available else None
        version = await adapter.version() if available else None
        return available, executable, version

    # -- status --------------------------------------------------------------

    async def status(self) -> InspectorStatus:
        config = self.get_config()
        available, executable, version = await self.opencode_detection()
        provider = config.provider
        credential_configured = (
            self._store.configured(provider) if provider else False
        )

        compatibility_status = self._state.get("compatibility_status", "unverified")
        verified_version = self._state.get("verified_opencode_version")
        verified_model = self._state.get("verified_model")
        if (
            compatibility_status == "verified"
            and (
                (version is not None and verified_version not in (None, version))
                or (verified_model not in (None, config.model))
            )
        ):
            # OpenCode or the model profile changed since the last verdict.
            compatibility_status = "unverified"
            self._state["compatibility_status"] = "unverified"
            self._state["deep_inspection_enabled"] = False
            self._state.pop("compatibility_checked_at", None)
            self._save_state()

        warnings: list[str] = []
        if not available:
            warnings.append("OpenCode executable not found")
        elif not config.model:
            warnings.append("Model not configured")
        elif not credential_configured:
            warnings.append("Provider credential missing")

        deep_enabled = bool(
            compatibility_status == "verified"
            and self._state.get("deep_inspection_enabled", False)
        )

        return InspectorStatus(
            opencode_available=available,
            opencode_executable=executable,
            opencode_version=version,
            provider=config.provider,
            base_url=config.base_url,
            model=config.model,
            credential_configured=credential_configured,
            connectivity_status=self._state.get("connectivity_status", "unknown"),
            compatibility_status=compatibility_status,
            connectivity_checked_at=self._parse_ts(
                self._state.get("connectivity_checked_at")
            ),
            compatibility_checked_at=self._parse_ts(
                self._state.get("compatibility_checked_at")
            ),
            deep_inspection_enabled=deep_enabled,
            warnings=warnings,
        )

    @staticmethod
    def _parse_ts(value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    # -- connectivity ----------------------------------------------------------

    async def connectivity_test(
        self, provider: str, base_url: str, model: str, api_key: str
    ) -> ConnectivityResult:
        """Save config + credential, then prove a minimal safe model request."""
        config = InspectorConfig(
            provider=provider,
            base_url=base_url or None,
            model=model,
            opencode_executable=self.get_config().opencode_executable,
        )
        self.update_config(config)
        if api_key:
            self.set_credential(provider, api_key)

        result = ConnectivityResult(status="failed", provider=provider, model=model)
        if not model or "/" not in model:
            result.error = "model must be provider/model"
            return result

        from ..inspection.run_profile import OpenCodeRunProfile

        profile = OpenCodeRunProfile.create(self.data_dir / "opencode-inspector", "connectivity")
        try:
            auth_dir = profile.home / "data" / "opencode"
            auth_dir.mkdir(parents=True, exist_ok=True)
            secret = self._store.get(provider)
            if not secret:
                result.error = "credential is not configured"
                return result
            (auth_dir / "auth.json").write_text(
                json.dumps({provider: {"type": "api", "key": secret}}),
                encoding="utf-8",
            )

            env = {
                "HOME": str(profile.home),
                "USERPROFILE": str(profile.home),
                "XDG_CONFIG_HOME": str(profile.home / "config"),
                "XDG_DATA_HOME": str(profile.home / "data"),
                "XDG_CACHE_HOME": str(profile.home / "cache"),
                "OPENCODE_CONFIG_DIR": str(profile.config_dir),
                "OPENCODE_CONFIG_CONTENT": json.dumps(
                    {
                        "$schema": "https://opencode.ai/config.json",
                        "share": "disabled",
                        "autoupdate": False,
                        "mcp": {},
                        "plugin": [],
                        "permission": {
                            "*": "deny",
                            "read": "allow",
                            "glob": "allow",
                            "list": "allow",
                            "grep": "allow",
                            "bash": "deny",
                            "edit": "deny",
                            "write": "deny",
                            "patch": "deny",
                            "task": "deny",
                            "webfetch": "deny",
                            "websearch": "deny",
                        },
                        "agent": {
                            "idlerdream-inspector": {
                                "description": "IdlerDream connectivity probe",
                                "mode": "primary",
                                "steps": 10,
                            }
                        },
                    }
                ),
                "OPENCODE_DISABLE_CLAUDE_CODE": "1",
                "OPENCODE_DISABLE_DEFAULT_PLUGINS": "1",
                "OPENCODE_DISABLE_LSP_DOWNLOAD": "1",
            }
            import subprocess

            proc = await asyncio.create_subprocess_exec(
                self._adapter_for()._executable_path(),
                "--pure",
                "run",
                "--format",
                "json",
                "--agent",
                "idlerdream-inspector",
                "--model",
                model,
                "Reply with the single word: ok",
                cwd=str(profile.home),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=(
                    0x08000000 if os.name == "nt" else 0
                ),  # CREATE_NO_WINDOW
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=45
                )
            except TimeoutError:
                proc.kill()
                await proc.wait()
                result.status = "timeout"
                result.error = "model request timed out"
                return result
            output = stdout_bytes.decode("utf-8", errors="replace")
            stderr_text = stderr_bytes.decode("utf-8", errors="replace")

            if proc.returncode != 0:
                lowered = (output + stderr_text).lower()
                if "401" in lowered or "unauthorized" in lowered or "invalid api key" in lowered:
                    result.status = "authentication_error"
                    result.error = "the provider rejected the credential"
                elif "model not found" in lowered or "404" in lowered:
                    result.status = "model_not_found"
                    result.error = "the model id was not found"
                else:
                    result.status = "provider_error"
                    result.error = stderr_text[-300:] or "provider request failed"
                return result
            result.status = "passed"
        finally:
            profile.cleanup()

        if result.status == "passed":
            self._state["connectivity_status"] = "passed"
            self._state["connectivity_checked_at"] = datetime.now(UTC).isoformat()
        else:
            self._state["connectivity_status"] = "failed"
            self._state["connectivity_checked_at"] = datetime.now(UTC).isoformat()
        self._save_state()
        return result

    # -- compatibility ----------------------------------------------------------

    async def compatibility_test(self) -> CompatibilityResult:
        """Run the real read-only probe; PASS enables deep inspection."""
        service = self._compatibility or CompatibilityService(
            executable=self._adapter_for()._executable_path(),
            model=self.get_config().model,
            config_dir=self.data_dir / "opencode-inspector",
            timeout_seconds=240,
        )
        result = await service.run()
        if result.status == "verified":
            self._state["compatibility_status"] = "verified"
            self._state["deep_inspection_enabled"] = True
            status = await self.status()
            self._state["verified_opencode_version"] = status.opencode_version
            self._state["verified_model"] = self.get_config().model
        else:
            self._state["compatibility_status"] = "failed"
            self._state["deep_inspection_enabled"] = False
        self._state["compatibility_checked_at"] = datetime.now(UTC).isoformat()
        self._save_state()
        return result

    # -- deep inspection gate ---------------------------------------------------

    def assert_deep_inspection_allowed(self) -> None:
        """Gate: production deep inspection requires a verified boundary."""
        status_holder = self._state
        if status_holder.get("compatibility_status") != "verified":
            raise InspectorCompatibilityError(
                "Deep inspection requires a verified read-only boundary "
                "(compatibility status is not 'verified')."
            )
        if not status_holder.get("deep_inspection_enabled", False):
            raise InspectorCompatibilityError(
                "Deep inspection is disabled until the compatibility test passes."
            )
