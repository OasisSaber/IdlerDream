from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*([^\s,;]+)"),
    re.compile(r"(?i)bearer\s+[a-z0-9._\-]+"),
    re.compile(r"sk-[a-zA-Z0-9_\-]{12,}"),
    re.compile(r"(?i)(https?://[^:/\s]+:)([^@/\s]+)(@)"),
]


def redact_text(value: str) -> str:
    result = value
    for pattern in _SECRET_PATTERNS:
        if pattern.pattern.startswith("(?i)(https"):
            result = pattern.sub(r"\1<redacted>\3", result)
        elif "bearer" in pattern.pattern.lower():
            result = pattern.sub("Bearer <redacted>", result)
        elif pattern.pattern.startswith("sk-"):
            result = pattern.sub("<redacted-key>", result)
        else:
            result = pattern.sub(lambda match: f"{match.group(1)}=<redacted>", result)
    return result


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if any(token in str(key).lower() for token in ("key", "token", "secret", "password")):
                result[str(key)] = "<redacted>"
            else:
                result[str(key)] = redact_value(item)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [redact_value(item) for item in value]
    return value


def redact_report_text_fields(report: Any) -> Any:
    """Defensively redact free-text fields of a parsed inspection report.

    The report model is validated before this runs, so the plain field names
    are guaranteed by the Pydantic schema. This protects stored state from a
    model that echoed a secret it was not supposed to read.
    """
    if report is None:
        return report
    text_fields = (
        "summary",
        "phase",
        "waiting_condition",
        "action",
        "command",
    )
    for field in text_fields:
        current = getattr(report, field, None)
        if isinstance(current, str):
            setattr(report, field, redact_text(current))
    for container in ("facts", "inferences", "uncertainties"):
        items = getattr(report, container, None) or []
        if isinstance(items, list):
            for item in items:
                if hasattr(item, "summary") and isinstance(item.summary, str):
                    item.summary = redact_text(item.summary)
                if hasattr(item, "command") and isinstance(item.command, str):
                    item.command = redact_text(item.command)
    next_action = getattr(report, "next_action", None)
    if next_action is not None:
        if isinstance(getattr(next_action, "action", None), str):
            next_action.action = redact_text(next_action.action)
        if isinstance(getattr(next_action, "waiting_condition", None), str):
            next_action.waiting_condition = redact_text(next_action.waiting_condition)
    return report
