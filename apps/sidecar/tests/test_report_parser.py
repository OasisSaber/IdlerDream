from __future__ import annotations

import json
from uuid import UUID, uuid4

from idlerdream.inspection.report_parser import extract_strings, parse_report_text
from idlerdream.models import ReportQuality


def report_payload(project_id: UUID | None = None) -> dict:
    return {
        "schema_version": 1,
        "project_id": str(project_id or uuid4()),
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


def test_missing_inference_kind_becomes_partial_model_evidence() -> None:
    payload = report_payload()
    payload["inferences"] = [{"summary": "The current architecture is probably stable."}]
    result = parse_report_text(json.dumps(payload))
    assert result.report is not None
    assert result.report.report_quality == ReportQuality.PARTIAL
    assert result.report.inferences[0].kind.value == "model"
    assert result.report.inferences[0].deterministic is False
    assert any("kind to model" in warning for warning in result.warnings)


def test_aliases_null_arrays_and_percent_confidence_are_normalized() -> None:
    project_id = uuid4()
    payload = {
        "schemaVersion": 1,
        "projectId": str(project_id),
        "workspaceFingerprint": "abc123",
        "coreStatus": "IN PROGRESS",
        "summary": "Working on tests.",
        "nextAction": {"actor": "AI", "text": "Repair the failing test."},
        "confidence": 82,
        "facts": None,
        "inferences": None,
        "uncertainties": None,
    }
    result = parse_report_text(
        json.dumps(payload),
        expected_project_id=project_id,
        expected_workspace_fingerprint="abc123",
    )
    assert result.report is not None
    assert result.report.core_status.value == "in_progress"
    assert result.report.next_action is not None
    assert result.report.next_action.actor.value == "agent"
    assert result.report.confidence == 0.82
    assert result.report.report_quality == ReportQuality.PARTIAL


def test_unclassified_fact_without_path_moves_to_inferences() -> None:
    payload = report_payload()
    payload["facts"] = [{"summary": "This appears close to release."}]
    result = parse_report_text(json.dumps(payload))
    assert result.report is not None
    assert not result.report.facts
    assert result.report.inferences[0].kind.value == "model"
    assert result.report.inferences[0].deterministic is False


def test_missing_next_action_is_partial_not_fatal() -> None:
    payload = report_payload()
    payload.pop("next_action")
    result = parse_report_text(json.dumps(payload))
    assert result.report is not None
    assert result.report.next_action is None
    assert result.report.report_quality == ReportQuality.PARTIAL


def test_identity_mismatch_rejected_even_when_schema_valid() -> None:
    payload = report_payload()
    result = parse_report_text(
        json.dumps(payload),
        expected_project_id=uuid4(),
        expected_workspace_fingerprint="abc123",
    )
    assert result.report is None
    assert result.error
    assert any("project_id" in item for item in result.diagnostics.validation_errors)


def test_multiple_json_objects_prefers_full_report() -> None:
    partial = report_payload()
    partial.pop("next_action")
    full = report_payload(UUID(partial["project_id"]))
    text = f"{json.dumps(partial)}\nfinal:\n{json.dumps(full)}"
    result = parse_report_text(text)
    assert result.report is not None
    assert result.report.report_quality == ReportQuality.FULL
    assert result.report.next_action is not None


def test_parse_invalid_report() -> None:
    result = parse_report_text('{"schema_version": 1}')
    assert result.report is None
    assert result.error
    assert result.diagnostics.validation_errors


def test_extract_strings_from_unknown_event_shape() -> None:
    event = {"type": "message.part", "part": {"text": "hello"}, "meta": ["world"]}
    assert "hello" in extract_strings(event)
    assert "world" in extract_strings(event)


def test_extract_strings_does_not_duplicate_text() -> None:
    assert extract_strings({"text": "once"}) == ["once"]


def test_json5_style_unquoted_keys_and_single_quotes_are_repaired() -> None:
    project_id = uuid4()
    payload = (
        "{\n"
        f' schema_version: 1,\n project_id: "{project_id}",\n'
        ' workspace_fingerprint: "abc123",\n core_status: "in_progress",\n'
        " phase: 'testing',\n summary: \"ok\",\n confidence: 0.8,\n"
        " facts: [],\n inferences: [],\n uncertainties: [],\n"
        " progress: {mode: 'none'},\n"
        ' next_action: {actor: "agent", action: "do it"},\n'
        "}\n"
    )
    result = parse_report_text(
        payload,
        expected_project_id=project_id,
        expected_workspace_fingerprint="abc123",
    )
    assert result.report is not None
    assert result.report.report_quality == ReportQuality.PARTIAL
    assert result.report.core_status.value == "in_progress"
    assert result.report.phase == "testing"
    assert result.report.next_action is not None
    assert result.report.next_action.action == "do it"
    assert any("JSON5" in warning for warning in result.warnings)
    assert any("repaired_json5_formatting" in item for item in result.diagnostics.normalized_fields)


def test_json5_style_trailing_commas_are_repaired() -> None:
    project_id = uuid4()
    payload = (
        "{\n"
        f'  "schema_version": 1,\n  "project_id": "{project_id}",\n'
        '  "workspace_fingerprint": "abc123",\n  "core_status": "not_started",\n'
        '  "phase": "unknown",\n  "summary": "ok",\n  "confidence": 0.5,\n'
        '  "facts": [],\n  "inferences": [],\n  "uncertainties": [],\n'
        '  "progress": {"mode": "none"},\n  "next_action": null,\n}\n'
    )
    result = parse_report_text(
        payload,
        expected_project_id=project_id,
        expected_workspace_fingerprint="abc123",
    )
    assert result.report is not None
    assert result.report.report_quality == ReportQuality.PARTIAL
    assert result.report.core_status.value == "not_started"


def test_string_values_with_colons_and_braces_survive_repair() -> None:
    project_id = uuid4()
    payload = json.dumps(
        {
            "schema_version": 1,
            "project_id": str(project_id),
            "workspace_fingerprint": "abc123",
            "core_status": "in_progress",
            "phase": "unknown",
            "summary": "note: https://example.com and {braces} stay intact",
            "confidence": 0.7,
            "facts": [],
            "inferences": [],
            "uncertainties": [],
            "progress": {"mode": "none"},
            "next_action": {"actor": "agent", "action": "proceed"},
        }
    )
    result = parse_report_text(
        payload,
        expected_project_id=project_id,
        expected_workspace_fingerprint="abc123",
    )
    assert result.report is not None
    assert result.report.report_quality == ReportQuality.FULL
    assert "https://example.com and {braces} stay intact" in result.report.summary
