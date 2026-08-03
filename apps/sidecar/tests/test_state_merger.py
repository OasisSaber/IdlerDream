from __future__ import annotations

from uuid import uuid4

from idlerdream.models import (
    CoreStatus,
    FactBaseline,
    InspectionReport,
    Project,
    TestFacts as ModelTestFacts,
)
from idlerdream.state.merger import invalidate_for_change, merge_state


def test_model_completion_conflicts_with_failed_tests(tmp_path) -> None:
    project = Project(name="demo", path=str(tmp_path))
    baseline = FactBaseline(
        project_id=project.id,
        workspace_path=project.path,
        workspace_fingerprint="fingerprint",
        tests=ModelTestFacts(status="failed", failed=2, summary="2 failed"),
    )
    report = InspectionReport(
        project_id=project.id,
        workspace_fingerprint="fingerprint",
        core_status=CoreStatus.COMPLETED,
        phase="release",
        summary="Done",
        confidence=0.9,
    )
    state = merge_state(project, baseline, report)
    assert state.core_status == CoreStatus.CONFLICT
    assert state.needs_user_attention is True


def test_major_change_expires_and_removes_next_action(tmp_path) -> None:
    project = Project(name="demo", path=str(tmp_path))
    baseline = FactBaseline(
        project_id=project.id,
        workspace_path=project.path,
        workspace_fingerprint="fingerprint",
    )
    state = merge_state(project, baseline, None)
    expired = invalidate_for_change(state, major=True, reason="new_commit")
    assert expired.freshness.value == "expired"
    assert expired.next_action is None
