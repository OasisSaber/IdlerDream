from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class CoreStatus(StrEnum):
    UNKNOWN = "unknown"
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    WAITING_USER = "waiting_user"
    WAITING_EXTERNAL = "waiting_external"
    BLOCKED = "blocked"
    CONFLICT = "conflict"
    COMPLETED = "completed"


class Freshness(StrEnum):
    CURRENT = "current"
    POSSIBLY_STALE = "possibly_stale"
    EXPIRED = "expired"
    NEVER_INSPECTED = "never_inspected"


class ActivityState(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class InspectionPermission(StrEnum):
    STANDARD_SOURCE = "standard_source"
    RESTRICTED = "restricted"
    LOCAL_ONLY = "local_only"


class NextActor(StrEnum):
    USER = "user"
    AGENT = "agent"
    NONE = "none"


class ReportQuality(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    FAILED = "failed"


class EvidenceKind(StrEnum):
    TEST = "test"
    BUILD = "build"
    VCS = "vcs"
    FILE = "file"
    PROCESS = "process"
    PLAN = "plan"
    SNAPSHOT = "snapshot"
    MODEL = "model"


class AcceptanceCriterion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=300)
    method: Literal["automatic", "model", "user"] = "user"
    completed: bool = False
    suspected_complete: bool = False
    blocking: bool = True
    evidence: list[str] = Field(default_factory=list)


class ProjectCycle(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=200)
    goal: str = Field(min_length=1, max_length=2000)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    excluded_scope: list[str] = Field(default_factory=list)
    deadline: datetime | None = None


class Project(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=200)
    path: str
    enabled: bool = True
    pinned: bool = False
    priority: Literal["high", "medium", "low"] = "medium"
    activity_state: ActivityState = ActivityState.ACTIVE
    inactivity_days: int = Field(default=3, ge=1, le=365)
    inspection_permission: InspectionPermission = InspectionPermission.STANDARD_SOURCE
    current_cycle: ProjectCycle | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    removed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        expanded = Path(value).expanduser()
        return str(expanded.resolve(strict=False))


class EvidenceRef(BaseModel):
    kind: EvidenceKind
    summary: str = Field(min_length=1, max_length=1000)
    path: str | None = None
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    command: str | None = None
    content_hash: str | None = None
    observed_at: datetime = Field(default_factory=utc_now)
    deterministic: bool = True


class NextAction(BaseModel):
    actor: NextActor
    action: str = Field(min_length=1, max_length=1000)
    waiting_condition: str | None = Field(default=None, max_length=1000)


class ProgressState(BaseModel):
    mode: Literal["none", "acceptance_count"] = "none"
    completed: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)

    @field_validator("total")
    @classmethod
    def validate_total(cls, value: int | None) -> int | None:
        if value == 0:
            return None
        return value


class VcsFacts(BaseModel):
    kind: Literal["git", "jj", "none"] = "none"
    head: str | None = None
    branch: str | None = None
    changed_files: int = 0
    untracked_files: int = 0
    status_summary: str = ""
    command_error: str | None = None


class TestFacts(BaseModel):
    status: Literal["passed", "failed", "unknown", "not_found"] = "not_found"
    passed: int | None = None
    failed: int | None = None
    skipped: int | None = None
    source_path: str | None = None
    observed_at: datetime | None = None
    summary: str = ""


class AgentProcess(BaseModel):
    pid: int
    name: str
    executable: str | None = None
    cwd: str | None = None
    command_summary: str = ""
    status: str = "unknown"
    cpu_percent: float = 0.0
    memory_bytes: int = 0
    started_at: datetime | None = None
    association_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    children: list[AgentProcess] = Field(default_factory=list)


class AgentSession(BaseModel):
    """Aggregated record of one observed Agent process run (CR-21).

    When an associated Agent process disappears between monitoring passes its
    last known snapshot is recorded here with an exit time so the UI can show
    recent activity instead of forgetting the process entirely.
    """

    session_id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    process_pid: int
    process: AgentProcess
    started_at: datetime = Field(default_factory=utc_now)
    exited_at: datetime | None = None


class FactBaseline(BaseModel):
    project_id: UUID
    workspace_path: str
    workspace_fingerprint: str
    observed_at: datetime = Field(default_factory=utc_now)
    vcs: VcsFacts = Field(default_factory=VcsFacts)
    tests: TestFacts = Field(default_factory=TestFacts)
    considered_paths: list[str] = Field(default_factory=list)
    file_count_considered: int = 0
    agents: list[AgentProcess] = Field(default_factory=list)
    cycle: ProjectCycle | None = None
    deterministic_evidence: list[EvidenceRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class InspectionReport(BaseModel):
    schema_version: Literal[1] = 1
    project_id: UUID
    workspace_fingerprint: str
    core_status: CoreStatus
    phase: str = Field(default="unknown", min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=3000)
    next_action: NextAction | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    facts: list[EvidenceRef] = Field(default_factory=list)
    inferences: list[EvidenceRef] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    progress: ProgressState = Field(default_factory=ProgressState)
    analysis_version: dict[str, str] = Field(default_factory=dict)
    report_quality: ReportQuality = ReportQuality.FULL
    validation_warnings: list[str] = Field(default_factory=list)


class CurrentProjectState(BaseModel):
    project_id: UUID
    core_status: CoreStatus = CoreStatus.UNKNOWN
    phase: str = "unknown"
    summary: str = "No successful inspection yet."
    next_action: NextAction | None = None
    confidence: float = 0.0
    freshness: Freshness = Freshness.NEVER_INSPECTED
    activity_state: ActivityState = ActivityState.ACTIVE
    facts: list[EvidenceRef] = Field(default_factory=list)
    inferences: list[EvidenceRef] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    progress: ProgressState = Field(default_factory=ProgressState)
    workspace_fingerprint: str | None = None
    verified_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)
    needs_user_attention: bool = False
    inspection_error: str | None = None
    inspection_quality: ReportQuality = ReportQuality.FAILED
    inspection_warnings: list[str] = Field(default_factory=list)


class SnapshotEvent(BaseModel):
    snapshot_id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    event_type: Literal[
        "inspection",
        "manual_override",
        "state_invalidated",
        "cycle_changed",
        "analysis_rebaseline",
    ]
    created_at: datetime = Field(default_factory=utc_now)
    state: CurrentProjectState
    baseline_fingerprint: str | None = None
    analysis_version: dict[str, str] = Field(default_factory=dict)


class InspectionJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    source: Literal["manual", "automatic", "scheduled"] = "manual"
    status: Literal[
        "queued", "running", "completed", "failed", "cancelled", "invalidated"
    ] = "queued"
    stage: str = "queued"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    elapsed_seconds: float = 0.0
    last_activity: str = ""
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    budget: dict[str, int] = Field(default_factory=dict)


AgentProcess.model_rebuild()
