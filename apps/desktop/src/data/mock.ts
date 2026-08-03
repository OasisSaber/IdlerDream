import type { InspectionJob, ProjectEnvelope } from "@idlerdream/protocol";

const now = Date.now();
const iso = (minutesAgo: number) => new Date(now - minutesAgo * 60_000).toISOString();

export const mockProjects: ProjectEnvelope[] = [
  {
    project: {
      id: "1e903e08-4480-43d8-a51e-5aab96d11101", name: "IdlerDream", path: "D:/Projects/idlerdream", enabled: true, pinned: true,
      priority: "high", activity_state: "active", inactivity_days: 3, inspection_permission: "standard_source", created_at: iso(9000), updated_at: iso(2), metadata: {},
      current_cycle: { id: "cycle-01", name: "v0.1 核心闭环", goal: "完成本地工作区监控与 OpenCode 只读巡检闭环", excluded_scope: ["全局巡检", "浏览器访问"], deadline: null,
        acceptance_criteria: [
          { id: "a1", title: "工作区与 Agent 轻量监控", method: "automatic", completed: true, suspected_complete: false, blocking: true, evidence: [] },
          { id: "a2", title: "OpenCode 只读巡检", method: "automatic", completed: false, suspected_complete: true, blocking: true, evidence: [] },
          { id: "a3", title: "周级快照存储", method: "automatic", completed: true, suspected_complete: false, blocking: true, evidence: [] },
          { id: "a4", title: "NSIS 安装验证", method: "user", completed: false, suspected_complete: false, blocking: true, evidence: [] },
        ] },
    },
    state: {
      project_id: "1e903e08-4480-43d8-a51e-5aab96d11101", core_status: "in_progress", phase: "只读巡检适配", summary: "Sidecar 已形成事实基线，正在验证 OpenCode 隔离配置。",
      next_action: { actor: "agent", action: "完成 OpenCode 事件流解析测试并验证工作区指纹未变化" }, confidence: .91, freshness: "current", activity_state: "active",
      facts: [{ kind: "test", summary: "Sidecar 单元测试 21 项通过", observed_at: iso(4), deterministic: true }],
      inferences: [{ kind: "model", summary: "当前最大风险位于 OpenCode 只读隔离兼容性", observed_at: iso(3), deterministic: false }],
      risks: [], progress: { mode: "acceptance_count", completed: 2, total: 4 }, workspace_fingerprint: "demo-1", verified_at: iso(3), updated_at: iso(1), needs_user_attention: false, inspection_error: null,
    },
    runtime: {
      project_id: "1e903e08-4480-43d8-a51e-5aab96d11101", workspace_path: "D:/Projects/idlerdream", workspace_fingerprint: "demo-1", observed_at: iso(0),
      vcs: { kind: "git", head: "a91f2d7", branch: "main", changed_files: 14, untracked_files: 3, status_summary: "14 modified, 3 untracked" },
      tests: { status: "passed", passed: 21, failed: 0, skipped: 0, summary: "21 passed" }, considered_paths: ["apps/desktop/src/App.tsx", "apps/sidecar/idlerdream/api.py"], file_count_considered: 118,
      agents: [{ pid: 18320, name: "opencode.exe", cwd: "D:/Projects/idlerdream", command_summary: "opencode run …", status: "running", cpu_percent: 18.4, memory_bytes: 644874240, started_at: iso(38), association_confidence: .98,
        children: [{ pid: 19344, name: "python.exe", cwd: "D:/Projects/idlerdream", command_summary: "python -m pytest", status: "sleeping", cpu_percent: 2.7, memory_bytes: 123731968, started_at: iso(10), association_confidence: 1, children: [] }] }], warnings: [],
    },
  },
  {
    project: { id: "2e903e08-4480-43d8-a51e-5aab96d11102", name: "智能座舱毕业设计", path: "D:/Projects/smart-cockpit", enabled: true, pinned: true, priority: "high", activity_state: "active", inactivity_days: 3, inspection_permission: "standard_source", current_cycle: null, created_at: iso(12000), updated_at: iso(8), metadata: {} },
    state: { project_id: "2e903e08-4480-43d8-a51e-5aab96d11102", core_status: "waiting_user", phase: "HMI 联调", summary: "视觉风险事件已接入，当前等待确认仪表盘告警层级。", next_action: { actor: "user", action: "确认高风险事件应采用全屏红色告警还是局部警示条" }, confidence: .87, freshness: "current", activity_state: "active", facts: [{ kind: "test", summary: "风险事件接口测试 22/22 通过", observed_at: iso(12), deterministic: true }], inferences: [{ kind: "model", summary: "剩余阻塞属于设计决策而非代码问题", observed_at: iso(11), deterministic: false }], risks: [], progress: { mode: "none", completed: null, total: null }, workspace_fingerprint: "demo-2", verified_at: iso(11), updated_at: iso(8), needs_user_attention: true, inspection_error: null },
    runtime: { project_id: "2e903e08-4480-43d8-a51e-5aab96d11102", workspace_path: "D:/Projects/smart-cockpit", workspace_fingerprint: "demo-2", observed_at: iso(0), vcs: { kind: "jj", head: "qzvnym", branch: "main", changed_files: 6, untracked_files: 0, status_summary: "6 modified" },       tests: { status: "passed", passed: 22, failed: 0, skipped: 1, summary: "22 passed, 1 skipped" }, considered_paths: ["hmi/src/components/RiskOverlay.tsx"], file_count_considered: 321, agents: [{ pid: 28412, name: "codex.exe", cwd: "D:/Projects/smart-cockpit", command_summary: "codex", status: "running", cpu_percent: 7.1, memory_bytes: 458227712, started_at: iso(72), association_confidence: .94, children: [] }], warnings: [] },
  },
  {
    project: { id: "3e903e08-4480-43d8-a51e-5aab96d11103", name: "Media Harbor Skill", path: "D:/Projects/media-harbor-skill", enabled: true, pinned: false, priority: "medium", activity_state: "active", inactivity_days: 3, inspection_permission: "restricted", current_cycle: null, created_at: iso(6000), updated_at: iso(18), metadata: {} },
    state: { project_id: "3e903e08-4480-43d8-a51e-5aab96d11103", core_status: "blocked", phase: "环境验证", summary: "下载适配器测试失败，ffmpeg 未在 PATH 中。", next_action: { actor: "user", action: "安装 ffmpeg 或将现有可执行文件加入用户 PATH" }, confidence: .99, freshness: "possibly_stale", activity_state: "active", facts: [{ kind: "test", summary: "环境检查返回 ffmpeg executable not found", observed_at: iso(20), deterministic: true }], inferences: [], risks: ["test_failure"], progress: { mode: "none", completed: null, total: null }, workspace_fingerprint: "demo-3", verified_at: iso(20), updated_at: iso(18), needs_user_attention: true, inspection_error: null },
    runtime: { project_id: "3e903e08-4480-43d8-a51e-5aab96d11103", workspace_path: "D:/Projects/media-harbor-skill", workspace_fingerprint: "demo-3b", observed_at: iso(0), vcs: { kind: "git", head: "77bcaf2", branch: "main", changed_files: 1, untracked_files: 0, status_summary: "1 modified" },       tests: { status: "failed", passed: 8, failed: 1, skipped: 0, summary: "8 passed, 1 failed" }, considered_paths: ["tests/test_environment.py"], file_count_considered: 52, agents: [], warnings: [] },
  },
  {
    project: { id: "4e903e08-4480-43d8-a51e-5aab96d11104", name: "邻舍校园交易平台", path: "D:/Projects/linshe-marketplace-miniapp", enabled: true, pinned: false, priority: "low", activity_state: "inactive", inactivity_days: 3, inspection_permission: "local_only", current_cycle: null, created_at: iso(22000), updated_at: iso(5400), metadata: {} },
    state: { project_id: "4e903e08-4480-43d8-a51e-5aab96d11104", core_status: "in_progress", phase: "UI 重构", summary: "最近一次验证停留在首页卡片组件重构。", next_action: { actor: "agent", action: "继续完成商品详情页组件迁移" }, confidence: .61, freshness: "expired", activity_state: "inactive", facts: [], inferences: [], risks: [], progress: { mode: "none", completed: null, total: null }, workspace_fingerprint: "demo-4", verified_at: iso(5600), updated_at: iso(5400), needs_user_attention: false, inspection_error: null },
    runtime: { project_id: "4e903e08-4480-43d8-a51e-5aab96d11104", workspace_path: "D:/Projects/linshe-marketplace-miniapp", workspace_fingerprint: "demo-4", observed_at: iso(0), vcs: { kind: "git", head: "a4d7741", branch: "ui-refresh", changed_files: 0, untracked_files: 0, status_summary: "clean" },       tests: { status: "not_found", summary: "No test report found" }, considered_paths: [], file_count_considered: 89, agents: [], warnings: [] },
  },
];

export const mockJobs: InspectionJob[] = [{ id: "job-001", project_id: mockProjects[0].project.id, source: "manual", status: "running", stage: "读取相关源码", started_at: iso(2), finished_at: null, elapsed_seconds: 128, last_activity: "正在读取 apps/sidecar/idlerdream/inspection/opencode.py", error: null }];
