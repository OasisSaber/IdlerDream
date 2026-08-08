from __future__ import annotations

from idlerdream.models import (
    CoreStatus,
    FactBaseline,
    InspectionReport,
    Project,
    ReportQuality,
)
from idlerdream.state.merger import merge_state


def test_partial_report_caps_confidence_and_preserves_warnings(tmp_path) -> None:
    project = Project(name="demo", path=str(tmp_path))
    baseline = FactBaseline(
        project_id=project.id,
        workspace_path=project.path,
        workspace_fingerprint="fingerprint",
    )
    report = InspectionReport(
        schema_version=1,
        project_id=project.id,
        workspace_fingerprint="fingerprint",
        core_status=CoreStatus.IN_PROGRESS,
        phase="testing",
        summary="The core status is valid, but non-core fields were normalized.",
        confidence=0.96,
        report_quality=ReportQuality.PARTIAL,
        validation_warnings=["Normalizer: defaulted inferences[0].kind to model."],
    )
    state = merge_state(project, baseline, report)
    assert state.inspection_quality == ReportQuality.PARTIAL
    assert state.confidence == 0.75
    assert state.inspection_warnings == report.validation_warnings


def test_failed_report_does_not_create_verified_state(tmp_path) -> None:
    project = Project(name="demo", path=str(tmp_path))
    baseline = FactBaseline(
        project_id=project.id,
        workspace_path=project.path,
        workspace_fingerprint="fingerprint",
    )
    state = merge_state(project, baseline, None, inspection_error="invalid identity")
    assert state.inspection_quality == ReportQuality.FAILED
    assert state.verified_at is None
    assert state.inspection_error == "invalid identity"
