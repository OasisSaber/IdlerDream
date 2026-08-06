from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from ..models import InspectionReport, ReportQuality

NORMALIZER_VERSION = "idlerdream-report-normalizer-v2"

_STATUS_ALIASES = {
    "unknown": "unknown",
    "not_started": "not_started",
    "notstarted": "not_started",
    "not-started": "not_started",
    "in_progress": "in_progress",
    "inprogress": "in_progress",
    "in-progress": "in_progress",
    "working": "in_progress",
    "waiting_user": "waiting_user",
    "waiting_for_user": "waiting_user",
    "waiting-user": "waiting_user",
    "waiting_external": "waiting_external",
    "waiting_for_external": "waiting_external",
    "waiting-external": "waiting_external",
    "blocked": "blocked",
    "conflict": "conflict",
    "completed": "completed",
    "complete": "completed",
    "done": "completed",
}

_ACTOR_ALIASES = {
    "user": "user",
    "human": "user",
    "owner": "user",
    "agent": "agent",
    "ai": "agent",
    "assistant": "agent",
    "model": "agent",
    "none": "none",
    "no_action": "none",
    "wait": "none",
}

_EVIDENCE_KINDS = {
    "test",
    "build",
    "vcs",
    "file",
    "process",
    "plan",
    "snapshot",
    "model",
}


@dataclass(slots=True)
class ParseDiagnostics:
    normalizer_version: str = NORMALIZER_VERSION
    candidate_count: int = 0
    decoded_candidates: int = 0
    selected_candidate: int | None = None
    normalized_fields: list[str] = field(default_factory=list)
    dropped_items: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    quality: str = "failed"

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ParseResult:
    report: InspectionReport | None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    diagnostics: ParseDiagnostics = field(default_factory=ParseDiagnostics)


def parse_report_text(
    text: str,
    *,
    expected_project_id: UUID | str | None = None,
    expected_workspace_fingerprint: str | None = None,
) -> ParseResult:
    """Parse and deterministically normalize a model-produced report.

    Only non-authoritative formatting variance is repaired. Project identity,
    workspace identity and core status are never guessed. A report that loses
    non-core fields can still be returned as ``partial`` with explicit warnings.
    """

    candidates = _json_candidates(text)
    diagnostics = ParseDiagnostics(candidate_count=len(candidates))
    valid_results: list[tuple[int, InspectionReport, list[str], ParseDiagnostics]] = []

    for index, candidate in enumerate(candidates):
        pre_warnings: list[str] = []
        repaired_json5 = False
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            try:
                payload = json.loads(_repair_json5_lite(candidate))
            except json.JSONDecodeError as exc2:
                diagnostics.validation_errors.append(f"candidate[{index}] JSON: {exc2}")
                continue
            repaired_json5 = True
            diagnostics.normalized_fields.append("repaired_json5_formatting")
            pre_warnings.append(
                "Normalizer: repaired JSON5-style formatting "
                "(unquoted keys, single-quoted strings or trailing commas)."
            )
        diagnostics.decoded_candidates += 1
        if not isinstance(payload, dict):
            diagnostics.dropped_items.append(f"candidate[{index}] is not an object")
            continue

        normalized, warnings, candidate_diagnostics = _normalize_payload(payload)
        if repaired_json5:
            candidate_diagnostics.normalized_fields.insert(0, "repaired_json5_formatting")
        candidate_diagnostics.candidate_count = len(candidates)
        candidate_diagnostics.decoded_candidates = diagnostics.decoded_candidates
        candidate_diagnostics.selected_candidate = index

        try:
            report = InspectionReport.model_validate(normalized)
        except ValidationError as exc:
            summary = _validation_summary(exc)
            diagnostics.validation_errors.append(f"candidate[{index}] schema: {summary}")
            continue

        if expected_project_id is not None and str(report.project_id) != str(expected_project_id):
            diagnostics.validation_errors.append(
                f"candidate[{index}] project_id does not match the requested project"
            )
            continue
        if (
            expected_workspace_fingerprint is not None
            and report.workspace_fingerprint != expected_workspace_fingerprint
        ):
            diagnostics.validation_errors.append(
                f"candidate[{index}] workspace_fingerprint does not match the baseline"
            )
            continue

        warnings = _deduplicate([*pre_warnings, *warnings, *report.validation_warnings])
        report.validation_warnings = warnings
        report.report_quality = (
            ReportQuality.PARTIAL if warnings else ReportQuality.FULL
        )
        candidate_diagnostics.quality = report.report_quality.value
        candidate_diagnostics.normalized_fields = _deduplicate(
            candidate_diagnostics.normalized_fields
        )
        candidate_diagnostics.dropped_items = _deduplicate(candidate_diagnostics.dropped_items)
        valid_results.append((index, report, warnings, candidate_diagnostics))

    if valid_results:
        # Prefer a full report, then one with a next action and more evidence.
        _, report, warnings, selected = max(
            valid_results,
            key=lambda item: (
                item[1].report_quality == ReportQuality.FULL,
                item[1].next_action is not None,
                len(item[1].facts) + len(item[1].inferences),
                item[0],
            ),
        )
        selected.validation_errors = diagnostics.validation_errors[-6:]
        selected.decoded_candidates = diagnostics.decoded_candidates
        return ParseResult(report=report, warnings=warnings, diagnostics=selected)

    diagnostics.validation_errors = diagnostics.validation_errors[-8:]
    return ParseResult(
        report=None,
        error="No valid InspectionReport object found.",
        warnings=diagnostics.validation_errors[-3:],
        diagnostics=diagnostics,
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


def _normalize_payload(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[str], ParseDiagnostics]:
    normalized = dict(payload)
    warnings: list[str] = []
    diagnostics = ParseDiagnostics()

    aliases = {
        "projectId": "project_id",
        "workspaceFingerprint": "workspace_fingerprint",
        "coreStatus": "core_status",
        "nextAction": "next_action",
        "analysisVersion": "analysis_version",
        "validationWarnings": "validation_warnings",
    }
    for source, target in aliases.items():
        if target not in normalized and source in normalized:
            normalized[target] = normalized.pop(source)
            _record_normalization(diagnostics, warnings, f"renamed {source} to {target}")

    if "schema_version" not in normalized:
        normalized["schema_version"] = 1
        _record_normalization(diagnostics, warnings, "defaulted schema_version to 1")

    if "core_status" in normalized:
        status_key = _canonical_token(normalized["core_status"])
        if status_key in _STATUS_ALIASES:
            canonical = _STATUS_ALIASES[status_key]
            if normalized["core_status"] != canonical:
                _record_normalization(
                    diagnostics, warnings, f"normalized core_status to {canonical}"
                )
            normalized["core_status"] = canonical

    if not _nonempty_string(normalized.get("phase")):
        normalized["phase"] = "unknown"
        _record_normalization(diagnostics, warnings, "defaulted missing phase to unknown")

    if not _nonempty_string(normalized.get("summary")):
        normalized["summary"] = (
            "The model returned a partial report. Review the attached facts "
            "and validation warnings."
        )
        _record_normalization(diagnostics, warnings, "defaulted missing summary")

    normalized["confidence"] = _normalize_confidence(
        normalized.get("confidence"), diagnostics, warnings
    )

    facts, inferred_from_facts = _normalize_evidence_list(
        normalized.get("facts"),
        collection="facts",
        diagnostics=diagnostics,
        warnings=warnings,
    )
    inferences, _ = _normalize_evidence_list(
        normalized.get("inferences"),
        collection="inferences",
        diagnostics=diagnostics,
        warnings=warnings,
    )
    normalized["facts"] = facts
    normalized["inferences"] = [*inferences, *inferred_from_facts]

    normalized["uncertainties"] = _normalize_string_list(
        normalized.get("uncertainties"),
        field_name="uncertainties",
        diagnostics=diagnostics,
        warnings=warnings,
    )
    normalized["validation_warnings"] = _normalize_string_list(
        normalized.get("validation_warnings"),
        field_name="validation_warnings",
        diagnostics=diagnostics,
        warnings=warnings,
    )

    normalized["next_action"] = _normalize_next_action(
        normalized.get("next_action"), diagnostics, warnings
    )
    normalized["progress"] = _normalize_progress(
        normalized.get("progress"), diagnostics, warnings
    )
    normalized["analysis_version"] = _normalize_analysis_version(
        normalized.get("analysis_version"), diagnostics, warnings
    )

    return normalized, _deduplicate(warnings), diagnostics


def _normalize_evidence_list(
    value: Any,
    *,
    collection: str,
    diagnostics: ParseDiagnostics,
    warnings: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if value is None:
        return [], []
    if isinstance(value, (str, dict)):
        value = [value]
        _record_normalization(diagnostics, warnings, f"wrapped {collection} in an array")
    if not isinstance(value, list):
        diagnostics.dropped_items.append(f"discarded invalid {collection}")
        warnings.append(f"Invalid {collection} field was discarded.")
        return [], []

    result: list[dict[str, Any]] = []
    moved_to_inferences: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            item = {"summary": item}
            _record_normalization(
                diagnostics, warnings, f"converted {collection}[{index}] string to evidence"
            )
        if not isinstance(item, dict):
            diagnostics.dropped_items.append(f"discarded {collection}[{index}]")
            continue

        evidence = dict(item)
        summary = evidence.get("summary") or evidence.get("description") or evidence.get("text")
        if not _nonempty_string(summary):
            diagnostics.dropped_items.append(f"discarded {collection}[{index}] without summary")
            warnings.append(f"An item in {collection} without a summary was discarded.")
            continue
        evidence["summary"] = str(summary).strip()[:1000]

        kind = _canonical_token(evidence.get("kind"))
        if collection == "inferences":
            if kind not in _EVIDENCE_KINDS:
                evidence["kind"] = "model"
                _record_normalization(
                    diagnostics, warnings, f"defaulted {collection}[{index}].kind to model"
                )
            else:
                evidence["kind"] = kind
            evidence["deterministic"] = False
            result.append(evidence)
            continue

        if kind not in _EVIDENCE_KINDS:
            if _nonempty_string(evidence.get("path")):
                evidence["kind"] = "file"
                _record_normalization(
                    diagnostics, warnings, f"defaulted facts[{index}].kind to file"
                )
            else:
                evidence["kind"] = "model"
                evidence["deterministic"] = False
                moved_to_inferences.append(evidence)
                _record_normalization(
                    diagnostics,
                    warnings,
                    f"moved unclassified facts[{index}] to inferences",
                )
                continue
        else:
            evidence["kind"] = kind
        evidence["deterministic"] = bool(evidence.get("deterministic", True))
        if not evidence["deterministic"]:
            evidence["kind"] = "model"
            moved_to_inferences.append(evidence)
            _record_normalization(
                diagnostics, warnings, f"moved nondeterministic facts[{index}] to inferences"
            )
            continue
        result.append(evidence)

    return result, moved_to_inferences


def _normalize_next_action(
    value: Any, diagnostics: ParseDiagnostics, warnings: list[str]
) -> dict[str, Any] | None:
    if value is None:
        warnings.append("The model did not provide a reliable next action.")
        return None
    if isinstance(value, str):
        value = {"actor": "agent", "action": value}
        _record_normalization(diagnostics, warnings, "converted next_action string to object")
    if not isinstance(value, dict):
        warnings.append("Invalid next_action was discarded.")
        diagnostics.dropped_items.append("discarded invalid next_action")
        return None

    action = value.get("action") or value.get("text") or value.get("description")
    if not _nonempty_string(action):
        warnings.append("The model did not provide a reliable next action.")
        diagnostics.dropped_items.append("discarded next_action without action text")
        return None
    actor_key = _canonical_token(value.get("actor"))
    actor = _ACTOR_ALIASES.get(actor_key)
    if actor is None:
        actor = "none"
        _record_normalization(diagnostics, warnings, "defaulted unknown next_action.actor to none")
    elif value.get("actor") != actor:
        _record_normalization(diagnostics, warnings, f"normalized next_action.actor to {actor}")
    return {
        "actor": actor,
        "action": str(action).strip()[:1000],
        "waiting_condition": value.get("waiting_condition") or value.get("waitingCondition"),
    }


def _normalize_progress(
    value: Any, diagnostics: ParseDiagnostics, warnings: list[str]
) -> dict[str, Any]:
    if not isinstance(value, dict):
        if value is not None:
            _record_normalization(diagnostics, warnings, "defaulted invalid progress to none")
        return {"mode": "none", "completed": None, "total": None}
    mode = _canonical_token(value.get("mode"))
    if mode not in {"none", "acceptance_count"}:
        mode = "none"
        _record_normalization(diagnostics, warnings, "normalized progress.mode to none")
    completed = _safe_nonnegative_int(value.get("completed"))
    total = _safe_nonnegative_int(value.get("total"))
    if mode == "acceptance_count" and (total is None or completed is None or completed > total):
        mode = "none"
        completed = None
        total = None
        _record_normalization(
            diagnostics, warnings, "discarded inconsistent acceptance_count progress"
        )
    return {"mode": mode, "completed": completed, "total": total}


def _normalize_analysis_version(
    value: Any, diagnostics: ParseDiagnostics, warnings: list[str]
) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        _record_normalization(diagnostics, warnings, "discarded invalid analysis_version")
        return {}
    return {str(key): str(item) for key, item in value.items() if item is not None}


def _normalize_confidence(
    value: Any, diagnostics: ParseDiagnostics, warnings: list[str]
) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        _record_normalization(diagnostics, warnings, "defaulted missing confidence to 0.5")
        return 0.5
    if 1 < confidence <= 100:
        confidence /= 100
        _record_normalization(diagnostics, warnings, "converted confidence percent to fraction")
    if confidence < 0 or confidence > 1:
        confidence = min(1.0, max(0.0, confidence))
        _record_normalization(diagnostics, warnings, "clamped confidence to [0, 1]")
    return confidence


def _normalize_string_list(
    value: Any,
    *,
    field_name: str,
    diagnostics: ParseDiagnostics,
    warnings: list[str],
) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        _record_normalization(diagnostics, warnings, f"wrapped {field_name} in an array")
        return [value]
    if not isinstance(value, list):
        diagnostics.dropped_items.append(f"discarded invalid {field_name}")
        return []
    return [str(item)[:1000] for item in value if item is not None and str(item).strip()]


def _json_candidates(text: str) -> list[str]:
    stripped = text.strip()
    candidates: list[str] = []
    if stripped:
        candidates.append(stripped)
    for match in re.finditer(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        candidates.append(match.group(1))
    candidates.extend(_balanced_objects(text))
    seen: set[str] = set()
    unique: list[str] = []
    # Later objects are usually the final model answer.
    for candidate in reversed(candidates):
        candidate = candidate.strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _repair_json5_lite(text: str) -> str:
    """Repair common JSON5-style variance without interpreting content.

    Only deterministic formatting repairs are applied: unquoted object keys,
    single-quoted strings and trailing commas. String values are preserved
    character-for-character (single-quoted strings are re-quoted, so inner
    double quotes and backslashes are escaped). Any other syntax error is left
    untouched and will fail the subsequent ``json.loads``.
    """
    out: list[str] = []
    index = 0
    length = len(text)
    in_double = False
    in_single = False
    escaped = False
    while index < length:
        char = text[index]
        if in_double:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_double = False
            index += 1
            continue
        if in_single:
            if char == "\\" and index + 1 < length:
                nxt = text[index + 1]
                if nxt == "'":
                    out.append("'")
                elif nxt == '"':
                    out.append('\\"')
                else:
                    out.append("\\" + nxt)
                index += 2
                continue
            if char == "'":
                out.append('"')
                in_single = False
            elif char == '"':
                out.append('\\"')
            else:
                out.append(char)
            index += 1
            continue
        if char == '"':
            in_double = True
            out.append(char)
            index += 1
            continue
        if char == "'":
            in_single = True
            out.append('"')
            index += 1
            continue
        if char == ",":
            lookahead = index + 1
            while lookahead < length and text[lookahead] in " \t\r\n":
                lookahead += 1
            if lookahead < length and text[lookahead] in "}]":
                index = lookahead
                continue
            out.append(char)
            index += 1
            continue
        if char.isalpha() or char in "_$":
            end = index
            while end < length and (text[end].isalnum() or text[end] in "_$"):
                end += 1
            lookahead = end
            while lookahead < length and text[lookahead] in " \t\r\n":
                lookahead += 1
            if (
                lookahead < length
                and text[lookahead] == ":"
                and not (lookahead + 1 < length and text[lookahead + 1] == "/")
            ):
                out.append('"')
                out.append(text[index:end])
                out.append('"')
                index = end
                continue
            out.append(text[index:end])
            index = end
            continue
        out.append(char)
        index += 1
    return "".join(out)


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


def _record_normalization(
    diagnostics: ParseDiagnostics, warnings: list[str], message: str
) -> None:
    diagnostics.normalized_fields.append(message)
    warnings.append(f"Normalizer: {message}.")


def _canonical_token(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace(" ", "_")


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _safe_nonnegative_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _validation_summary(exc: ValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors()[:6]:
        location = ".".join(str(item) for item in error.get("loc", ())) or "report"
        parts.append(f"{location}: {error.get('msg', 'invalid value')}")
    return "; ".join(parts)


def _deduplicate(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))
