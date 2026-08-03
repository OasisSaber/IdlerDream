from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

from ..models import TestFacts

REPORT_CANDIDATES = (
    "junit.xml", "pytest-report.xml", "test-results.xml", "coverage.json", "test-results/results.json",
)


def collect_test_facts(workspace: str | Path) -> TestFacts:
    root = Path(workspace)
    candidates = [root / candidate for candidate in REPORT_CANDIDATES]
    candidates.extend(_discover_shallow_reports(root))
    existing = sorted(
        {path.resolve(strict=False) for path in candidates if path.exists() and path.is_file()},
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    if not existing:
        return TestFacts(status="not_found", summary="No supported test report found.")

    parse_errors: list[str] = []
    unknown: TestFacts | None = None
    for path in existing:
        try:
            parsed = _parse_junit(path) if path.suffix.lower() == ".xml" else _parse_json_report(path)
        except (OSError, ValueError, ET.ParseError, json.JSONDecodeError) as exc:
            parse_errors.append(f"{path.name}: {exc}")
            continue
        if parsed.status in {"passed", "failed"}:
            return parsed
        unknown = unknown or parsed

    if unknown:
        if parse_errors:
            unknown.summary = f"{unknown.summary} Other reports failed to parse: {'; '.join(parse_errors[:3])}"
        return unknown
    newest = existing[0]
    return TestFacts(
        status="unknown",
        source_path=str(newest),
        observed_at=_mtime(newest),
        summary=f"No reliable supported counters found. {'; '.join(parse_errors[:3])}",
    )


def _discover_shallow_reports(root: Path) -> list[Path]:
    results: list[Path] = []
    for directory in ("test-results", "reports", "coverage"):
        candidate = root / directory
        if not candidate.exists() or not candidate.is_dir():
            continue
        try:
            results.extend(candidate.glob("*.xml"))
            results.extend(candidate.glob("*.json"))
        except OSError:
            continue
    return results


def _parse_junit(path: Path) -> TestFacts:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall(".//testsuite"))
    tests = sum(int(item.attrib.get("tests", 0)) for item in suites)
    failures = sum(int(item.attrib.get("failures", 0)) for item in suites)
    errors = sum(int(item.attrib.get("errors", 0)) for item in suites)
    skipped = sum(int(item.attrib.get("skipped", 0)) for item in suites)
    failed = failures + errors
    passed = max(0, tests - failed - skipped)
    return TestFacts(
        status="failed" if failed else "passed", passed=passed, failed=failed, skipped=skipped,
        source_path=str(path), observed_at=_mtime(path),
        summary=f"{passed} passed, {failed} failed, {skipped} skipped",
    )


def _parse_json_report(path: Path) -> TestFacts:
    payload = json.loads(path.read_text(encoding="utf-8"))
    failed = _first_int(payload, "numFailedTests", "failed", "failures")
    passed = _first_int(payload, "numPassedTests", "passed", "successes")
    skipped = _first_int(payload, "numPendingTests", "skipped", "pending")
    if failed is None and passed is None:
        return TestFacts(status="unknown", source_path=str(path), observed_at=_mtime(path), summary="JSON report does not expose supported counters.")
    failed, passed, skipped = failed or 0, passed or 0, skipped or 0
    return TestFacts(
        status="failed" if failed else "passed", passed=passed, failed=failed, skipped=skipped,
        source_path=str(path), observed_at=_mtime(path),
        summary=f"{passed} passed, {failed} failed, {skipped} skipped",
    )


def _first_int(payload: dict, *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, int):
            return value
    return None


def _mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
