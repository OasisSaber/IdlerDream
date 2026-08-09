export type CoreStatus =
  | "unknown"
  | "not_started"
  | "in_progress"
  | "waiting_user"
  | "waiting_external"
  | "blocked"
  | "conflict"
  | "completed";

export type Freshness = "current" | "possibly_stale" | "expired" | "never_inspected";
export type ActivityState = "active" | "inactive" | "archived";
export type InspectionPermission = "standard_source" | "restricted" | "local_only";
export type NextActor = "user" | "agent" | "none";
export type ReportQuality = "full" | "partial" | "failed";

export interface AcceptanceCriterion {
  id: string;
  title: string;
  method: "automatic" | "model" | "user";
  completed: boolean;
  suspected_complete: boolean;
  blocking: boolean;
  evidence: string[];
}

export interface ProjectCycle {
  id: string;
  name: string;
  goal: string;
  acceptance_criteria: AcceptanceCriterion[];
  excluded_scope: string[];
  deadline?: string | null;
}

export interface Project {
  id: string;
  name: string;
  path: string;
  enabled: boolean;
  pinned: boolean;
  priority: "high" | "medium" | "low";
  activity_state: ActivityState;
  inactivity_days: number;
  inspection_permission: InspectionPermission;
  current_cycle?: ProjectCycle | null;
  created_at: string;
  updated_at: string;
  removed_at?: string | null;
  metadata: Record<string, unknown>;
}

export interface EvidenceRef {
  kind: "test" | "build" | "vcs" | "file" | "process" | "plan" | "snapshot" | "model";
  summary: string;
  path?: string | null;
  line_start?: number | null;
  line_end?: number | null;
  command?: string | null;
  content_hash?: string | null;
  observed_at: string;
  deterministic: boolean;
}

export interface NextAction {
  actor: NextActor;
  action: string;
  waiting_condition?: string | null;
}

export interface AgentProcess {
  pid: number;
  name: string;
  executable?: string | null;
  cwd?: string | null;
  command_summary: string;
  status: string;
  cpu_percent: number;
  memory_bytes: number;
  started_at?: string | null;
  association_confidence: number;
  children: AgentProcess[];
}

export interface FactBaseline {
  project_id: string;
  workspace_path: string;
  workspace_fingerprint: string;
  observed_at: string;
  vcs: {
    kind: "git" | "jj" | "none";
    head?: string | null;
    branch?: string | null;
    changed_files: number;
    untracked_files: number;
    status_summary: string;
    command_error?: string | null;
  };
  tests: {
    status: "passed" | "failed" | "unknown" | "not_found";
    passed?: number | null;
    failed?: number | null;
    skipped?: number | null;
    source_path?: string | null;
    observed_at?: string | null;
    summary: string;
  };
  considered_paths: string[];
  file_count_considered: number;
  agents: AgentProcess[];
  warnings: string[];
}

export interface CurrentProjectState {
  project_id: string;
  core_status: CoreStatus;
  phase: string;
  summary: string;
  next_action?: NextAction | null;
  confidence: number;
  freshness: Freshness;
  activity_state: ActivityState;
  facts: EvidenceRef[];
  inferences: EvidenceRef[];
  risks: string[];
  progress: { mode: "none" | "acceptance_count"; completed?: number | null; total?: number | null };
  workspace_fingerprint?: string | null;
  verified_at?: string | null;
  updated_at: string;
  needs_user_attention: boolean;
  inspection_error?: string | null;
  inspection_quality: ReportQuality;
  inspection_warnings: string[];
}

export interface ProjectEnvelope {
  project: Project;
  state: CurrentProjectState | null;
  runtime: FactBaseline | null;
}

export interface InspectionJob {
  id: string;
  project_id: string;
  source: "manual" | "automatic" | "scheduled";
  status: "queued" | "running" | "completed" | "failed" | "cancelled" | "invalidated";
  stage: string;
  started_at?: string | null;
  finished_at?: string | null;
  elapsed_seconds: number;
  last_activity: string;
  error?: string | null;
  warnings: string[];
  budget: Record<string, number>;
}
