from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_IGNORE_DIRS = {
    ".git", ".jj", ".idlerdream", "node_modules", ".venv", "venv", "env",
    "dist", "build", "out", ".next", ".turbo", ".cache", "coverage",
    "__pycache__", "target",
}

DEFAULT_AGENT_NAMES = {
    "opencode", "opencode.exe", "codex", "codex.exe", "claude", "claude.exe",
    "claude-code", "claude-code.exe",
}


@dataclass(slots=True)
class Settings:
    profile: str = "default"
    data_dir: Path = field(default_factory=lambda: Settings.default_data_dir())
    api_host: str = "127.0.0.1"
    api_port: int = 38173
    control_host: str = "127.0.0.1"
    control_port: int = 38174
    control_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    read_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    opencode_executable: str = "opencode"
    opencode_model: str | None = None
    opencode_timeout_seconds: int = 600
    inspection_concurrency: int = 4
    mock_inspector: bool = False
    dev_control_http: bool = False
    ignore_dirs: set[str] = field(default_factory=lambda: set(DEFAULT_IGNORE_DIRS))
    agent_names: set[str] = field(default_factory=lambda: set(DEFAULT_AGENT_NAMES))

    @staticmethod
    def default_data_dir() -> Path:
        explicit = os.getenv("IDLERDREAM_DATA_DIR")
        if explicit:
            return Path(explicit).expanduser().resolve(strict=False)
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "IdlerDream"
        return Path.home() / ".local" / "share" / "IdlerDream"

    @classmethod
    def from_env(cls) -> Settings:
        settings = cls()
        settings.profile = os.getenv("IDLERDREAM_PROFILE", settings.profile)
        settings.data_dir = cls.default_data_dir() / settings.profile
        settings.api_host = os.getenv("IDLERDREAM_API_HOST", settings.api_host)
        settings.api_port = int(os.getenv("IDLERDREAM_API_PORT", str(settings.api_port)))
        settings.control_host = os.getenv("IDLERDREAM_CONTROL_HOST", settings.control_host)
        settings.control_port = int(os.getenv("IDLERDREAM_CONTROL_PORT", str(settings.control_port)))
        settings.control_token = os.getenv("IDLERDREAM_CONTROL_TOKEN", settings.control_token)
        settings.read_token = os.getenv("IDLERDREAM_READ_TOKEN", settings.read_token)
        settings.opencode_executable = os.getenv("IDLERDREAM_OPENCODE", settings.opencode_executable)
        settings.opencode_model = os.getenv("IDLERDREAM_OPENCODE_MODEL") or None
        settings.opencode_timeout_seconds = int(
            os.getenv("IDLERDREAM_OPENCODE_TIMEOUT", str(settings.opencode_timeout_seconds))
        )
        settings.inspection_concurrency = max(
            1, int(os.getenv("IDLERDREAM_INSPECTION_CONCURRENCY", "4"))
        )
        settings.mock_inspector = os.getenv("IDLERDREAM_MOCK_INSPECTOR", "0") == "1"
        settings.dev_control_http = os.getenv("IDLERDREAM_DEV_CONTROL_HTTP", "0") == "1"
        return settings

    def ensure_directories(self) -> None:
        for name in ("database", "snapshots", "raw-reports", "logs", "profiles", "temp", "config"):
            (self.data_dir / name).mkdir(parents=True, exist_ok=True)
