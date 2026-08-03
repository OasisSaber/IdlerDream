from __future__ import annotations

from datetime import UTC, datetime

from ..models import (
    CoreStatus,
    CurrentProjectState,
    EvidenceKind,
    EvidenceRef,
    FactBaseline,
    Freshness,
    InspectionReport,
    NextAction,
    NextActor,
    ProgressState,
    Project,
)


def merge_state(
    project: Project,
    baseline: FactBaseline,
    report: InspectionReport | None,
    *,
    previous: CurrentProjectState | None = None,
    inspection_error: str | None = None,
) -> CurrentProjectState:
    now = datetime.now(UTC)
    progress = _cycle_progress(project)
    facts = list(baseline.deterministic_evidence)
    risks: list[str] = []

    if baseline.tests.status == "failed":
        risks.append("test_failure")
    if not report:
        return _fallback_state(
            project,
            baseline,
            previous=previous,
            progress=progress,
            risks=risks,
            inspection_error=inspection_error,
            now=now,
        )

    if report.workspace_fingerprint != baseline.workspace_fingerprint:
        return CurrentProjectState(
            project_id=project.id,
            core_status=previous.core_status if previous else CoreStatus.UNKNOWN,
            phase=previous.phase if previous else "unknown",
            summary="Inspection result was invalidated because the workspace fingerprint changed.",
            next_action=None,
            confidence=0.0,
            freshness=Freshness.EXPIRED,
            activity_state=project.activity_state,
            facts=facts,
            inferences=report.inferences,
            risks=risks + ["workspace_changed_during_inspection"],
            progress=progress,
            workspace_fingerprint=baseline.workspace_fingerprint,
            verified_at=previous.verified_at if previous else None,
            updated_at=now,
            needs_user_attention=True,
            inspection_error="Workspace fingerprint mismatch",
        )

    facts.extend(item for item in report.facts if item not in facts)
    core_status = report.core_status
    if baseline.tests.status == "failed" and report.core_status == CoreStatus.COMPLETED:
        core_status = CoreStatus.CONFLICT
        risks.append("deterministic_model_conflict")
        facts.append(
            EvidenceRef(
                kind=EvidenceKind.TEST,
                summary="The model reported completion while deterministic tests are failing.",
                deterministic=True,
            )
        )

    next_action = report.next_action
    if core_status == CoreStatus.CONFLICT and next_action is None:
        next_action = NextAction(
            actor=NextActor.USER,
            action="Review the conflicting deterministic evidence and model conclusion.",
        )

    needs_attention = (
        core_status in {CoreStatus.WAITING_USER, CoreStatus.BLOCKED, CoreStatus.CONFLICT}
        or (next_action is not None and next_action.actor == NextActor.USER)
        or bool(risks)
    )

    return CurrentProjectState(
        project_id=project.id,
        core_status=core_status,
        phase=report.phase,
        summary=report.summary,
        next_action=next_action,
        confidence=report.confidence,
        freshness=Freshness.CURRENT,
        activity_state=project.activity_state,
        facts=facts,
        inferences=report.inferences,
        risks=risks,
        progress=report.progress if report.progress.mode != "none" else progress,
        workspace_fingerprint=baseline.workspace_fingerprint,
        verified_at=now,
        updated_at=now,
        needs_user_attention=needs_attention,
        inspection_error=inspection_error,
    )


def invalidate_for_change(
    state: CurrentProjectState,
    *,
    major: bool,
    reason: str,
) -> CurrentProjectState:
    updated = state.model_copy(deep=True)
    updated.freshness = Freshness.EXPIRED if major else Freshness.POSSIBLY_STALE
    if major:
        updated.next_action = None
    updated.updated_at = datetime.now(UTC)
    updated.risks = list(dict.fromkeys([*updated.risks, reason]))
    return updated


def materially_changed(
    previous: CurrentProjectState | None, current: CurrentProjectState
) -> bool:
    if previous is None:
        return True
    comparable_fields = (
        "core_status",
        "phase",
        "next_action",
        "freshness",
        "progress",
        "risks",
        "needs_user_attention",
    )
    return any(getattr(previous, field) != getattr(current, field) for field in comparable_fields)


def _fallback_state(
    project: Project,
    baseline: FactBaseline,
    *,
    previous: CurrentProjectState | None,
    progress: ProgressState,
    risks: list[str],
    inspection_error: str | None,
    now: datetime,
) -> CurrentProjectState:
    if baseline.tests.status == "failed":
        status = CoreStatus.BLOCKED
        summary = baseline.tests.summary or "Deterministic test failures were detected."
        next_action = NextAction(
            actor=NextActor.AGENT,
            action="Investigate and fix the failing tests in the latest test report.",
        )
        confidence = 0.58
    else:
        status = previous.core_status if previous else CoreStatus.UNKNOWN
        summary = (
            previous.summary
            if previous
            else "Lightweight monitoring is active, but no verified semantic inspection exists."
        )
        next_action = None if not previous else previous.next_action
        confidence = min(previous.confidence, 0.45) if previous else 0.0

    freshness = Freshness.EXPIRED if previous else Freshness.NEVER_INSPECTED
    return CurrentProjectState(
        project_id=project.id,
        core_status=status,
        phase=previous.phase if previous else "unknown",
        summary=summary,
        next_action=next_action if freshness != Freshness.EXPIRED else None,
        confidence=confidence,
        freshness=freshness,
        activity_state=project.activity_state,
        facts=baseline.deterministic_evidence,
        inferences=previous.inferences if previous else [],
        risks=risks,
        progress=progress,
        workspace_fingerprint=baseline.workspace_fingerprint,
        verified_at=previous.verified_at if previous else None,
        updated_at=now,
        needs_user_attention=bool(risks),
        inspection_error=inspection_error,
    )


def _cycle_progress(project: Project) -> ProgressState:
    if not project.current_cycle or not project.current_cycle.acceptance_criteria:
        return ProgressState(mode="none")
    criteria = project.current_cycle.acceptance_criteria
    return ProgressState(
        mode="acceptance_count",
        completed=sum(1 for item in criteria if item.completed),
        total=len(criteria),
    )
