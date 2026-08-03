from __future__ import annotations

import json
from uuid import uuid4

from idlerdream.inspection.report_parser import extract_strings, parse_report_text


def report_payload() -> dict:
    project_id = str(uuid4())
    return {
        "schema_version": 1,
        "project_id": project_id,
        "workspace_fingerprint": "abc123",
        "core_status": "in_progress",
        "phase": "testing",
        "summary": "The project is validating its test suite.",
        "next_action": {"actor": "agent", "action": "Fix the remaining failing test."},
        "confidence": 0.82,
        "facts": [],
        "inferences": [],
        "uncertainties": [],
        "progress": {"mode": "none"},
    }


def test_parse_fenced_json() -> None:
    payload = report_payload()
    result = parse_report_text(f"analysis before\n```json\n{json.dumps(payload)}\n```\n")
    assert result.report is not None
    assert result.report.phase == "testing"
    assert result.error is None


def test_parse_invalid_report() -> None:
    result = parse_report_text('{"schema_version": 1}')
    assert result.report is None
    assert result.error


def test_extract_strings_from_unknown_event_shape() -> None:
    event = {"type": "message.part", "part": {"text": "hello"}, "meta": ["world"]}
    assert "hello" in extract_strings(event)
    assert "world" in extract_strings(event)
