from __future__ import annotations

import fnmatch
from pathlib import Path

SENSITIVE_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.pfx",
    "*.p12",
    "id_rsa*",
    "credentials*",
    "secrets*",
    ".npmrc",
    ".pypirc",
    "*auth.json",
    "*credential*.json",
)


def is_sensitive_path(path: str | Path) -> bool:
    candidate = Path(path)
    name = candidate.name.lower()
    normalized = str(candidate).replace("\\", "/").lower()
    if any(part in normalized for part in ("/.aws/", "/.azure/", "/.config/gcloud/")):
        return True
    return any(fnmatch.fnmatch(name, pattern.lower()) for pattern in SENSITIVE_PATTERNS)


def ensure_within_workspace(path: str | Path, workspace: str | Path) -> Path:
    resolved_path = Path(path).resolve(strict=False)
    resolved_workspace = Path(workspace).resolve(strict=False)
    try:
        resolved_path.relative_to(resolved_workspace)
    except ValueError as exc:
        raise PermissionError(f"Path escapes workspace: {resolved_path}") from exc
    return resolved_path
