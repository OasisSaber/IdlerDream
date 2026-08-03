from __future__ import annotations

from uuid import uuid4

from idlerdream.inspection.prompt import build_inspection_prompt
from idlerdream.models import FactBaseline, InspectionPermission, Project, VcsFacts


def test_prompt_contains_security_authority_and_baseline(tmp_path) -> None:
    project = Project(
        name="Demo",
        path=str(tmp_path),
        inspection_permission=InspectionPermission.STANDARD_SOURCE,
    )
    baseline = FactBaseline(
        project_id=project.id,
        workspace_path=project.path,
        workspace_fingerprint="fingerprint-123",
        vcs=VcsFacts(kind="git", branch="main", changed_files=2),
    )

    prompt = build_inspection_prompt(project, baseline)
    assert "untrusted project data" in prompt
    assert "Do not edit, create, rename, or delete" in prompt
    assert "deterministic fact baseline" in prompt
    assert "fingerprint-123" in prompt
    assert str(project.id) in prompt
    assert '"schema_version": 1' in prompt
    assert "one highest-priority next action" in prompt


def test_restricted_prompt_disallows_full_source_bodies(tmp_path) -> None:
    project = Project(
        name="Restricted",
        path=str(tmp_path),
        inspection_permission=InspectionPermission.RESTRICTED,
    )
    baseline = FactBaseline(
        project_id=project.id,
        workspace_path=project.path,
        workspace_fingerprint=uuid4().hex,
    )
    prompt = build_inspection_prompt(project, baseline)
    assert "Do not read full source bodies" in prompt
