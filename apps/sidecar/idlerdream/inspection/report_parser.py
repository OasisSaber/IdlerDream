from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from ..models import InspectionReport


@dataclass(slots=True)
class ParseResult:
    report: InspectionReport | None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def parse_report_text(text: str) -> ParseResult:
    candidates = _json_candidates(text)
    validation_errors: list[str] = []
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            validation_errors.append(f"JSON decode failed: {exc}")
            continue
        if not isinstance(payload, dict):
            continue
        try:
            report = InspectionReport.model_validate(payload)
            warnings = list(report.validation_warnings)
            if report.next_action is None:
                warnings.append("The model did not provide a reliable next action.")
            return ParseResult(report=report, warnings=warnings)
        except ValidationError as exc:
            validation_errors.append(str(exc))
    return ParseResult(
        report=None,
        error="No valid InspectionReport object found.",
        warnings=validation_errors[-3:],
    )


def extract_strings(value: Any) -> list[str]:
    """Collect likely assistant text from unknown OpenCode JSON event shapes."""
    result: list[str] = []
    if isinstance(value, str):
        if value.strip():
            result.append(value)
    elif isinstance(value, dict):
        priority_keys = ("text", "content", "message", "output", "result", "part")
        for key in priority_keys:
            if key in value:
                result.extend(extract_strings(value[key]))
        for key, item in value.items():
            if key not in priority_keys and key not in {"id", "sessionID", "timestamp"}:
                result.extend(extract_strings(item))
    elif isinstance(value, list):
        for item in value:
            result.extend(extract_strings(item))
    return result


def _json_candidates(text: str) -> list[str]:
    stripped = text.strip()
    candidates: list[str] = []
    if stripped:
        candidates.append(stripped)
    for match in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL):
        candidates.append(match.group(1))
    candidates.extend(_balanced_objects(text))
    seen: set[str] = set()
    unique: list[str] = []
    for candidate in reversed(candidates):
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _balanced_objects(text: str) -> list[str]:
    objects: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                objects.append(text[start : index + 1])
                start = None
    return objects
