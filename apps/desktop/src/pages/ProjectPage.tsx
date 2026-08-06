import type { ProjectEnvelope } from "@idlerdream/protocol";
import { InspectionReliabilityCard } from "../components/InspectionReliabilityCard";
import { ProcessTree } from "../components/ProcessTree";
import { FreshnessBadge, StatusBadge } from "../components/StatusBadge";
import { formatBytes, relativeTime } from "../lib/format";
import { Icon } from "../lib/icons";

interface ProjectPageProps {
  envelope: ProjectEnvelope;
  onBack(): void;
  onInspect(): void;
  onOpenFolder(): void;
  onRemove(): void;
}

function actorLabel(actor?: string) {
  if (actor === "user") return "由你执行";
  if (actor === "agent") return "由 Agent 执行";
  return "当前无动作";
}

export function ProjectPage({
  envelope,
  onBack,
  onInspect,
  onOpenFolder,
  onRemove,
}: ProjectPageProps) {
  const { project, state, runtime } = envelope;
  const agents = runtime?.agents ?? [];
  const cpu = agents.reduce((sum, item) => sum + item.cpu_percent, 0);
  const memory = agents.reduce((sum, item) => sum + item.memory_bytes, 0);
  const actionIsExpired = state?.freshness === "expired";
  const currentAction = actionIsExpired ? null : state?.next_action;

  return (
    <div className="page project-page">
      <header className="project-page__header">
        <button className="icon-button" onClick={onBack} aria-label="返回项目总览">
          <Icon name="back" />
        </button>
        <div className="project-page__identity">
          <span className="project-monogram project-monogram--large">
            {project.name.slice(0, 2)}
          </span>
          <div>
            <span className="eyebrow">Project detail</span>
            <h1>{project.name}</h1>
            <p title={project.path}>{project.path}</p>
          </div>
        </div>
        <div className="project-page__actions">
          <button className="button button--secondary" onClick={onOpenFolder}>
            <Icon name="folder" />
            打开文件夹
          </button>
          <button className="button button--primary" onClick={onInspect}>
            <Icon name="refresh" />
            立即巡检
          </button>
          <button className="button button--danger" onClick={onRemove}>
            <Icon name="trash" />
            移除项目
          </button>
        </div>
      </header>

      <div className="detail-hero">
        <section className="verified-state" aria-labelledby="verified-state-title">
          <div className="verified-state__title">
            <div>
              <span className="eyebrow">Verified state</span>
              <h2 id="verified-state-title">已验证状态</h2>
            </div>
            <div>
              {state && <StatusBadge status={state.core_status} />}
              {state && <FreshnessBadge freshness={state.freshness} />}
            </div>
          </div>
          <p className="state-summary">{state?.summary ?? "尚未完成首次巡检。"}</p>
          <div className="next-action-large">
            <span>最高优先级下一步</span>
            <strong>
              {actionIsExpired
                ? "状态已过期，需要重新巡检后判断下一步"
                : currentAction?.action ?? "执行首次深度巡检"}
            </strong>
            <div>
              <b>{actorLabel(currentAction?.actor)}</b>
              <span>置信度 {Math.round((state?.confidence ?? 0) * 100)}%</span>
              <span>验证于 {relativeTime(state?.verified_at)}</span>
            </div>
          </div>
        </section>

        <aside className="runtime-summary" aria-labelledby="runtime-title">
          <span className="eyebrow">Live runtime</span>
          <h2 id="runtime-title">实时活动</h2>
          <div className="runtime-big">
            <strong>{agents.length}</strong>
            <span>关联 Agent</span>
          </div>
          <div className="runtime-resources">
            <div>
              <Icon name="cpu" />
              <span>总 CPU</span>
              <strong>{cpu.toFixed(1)}%</strong>
            </div>
            <div>
              <Icon name="memory" />
              <span>总内存</span>
              <strong>{formatBytes(memory)}</strong>
            </div>
          </div>
          <p>
            {runtime?.considered_paths[0]
              ? `参与基线 ${runtime.considered_paths[0]}`
              : "暂无文件参与基线"}
          </p>
        </aside>
      </div>

      <div className="detail-grid-layout">
        <main className="detail-main">
          <section className="panel" aria-labelledby="evidence-title">
            <div className="panel-title">
              <div>
                <span className="eyebrow">Evidence</span>
                <h2 id="evidence-title">事实与推断</h2>
              </div>
            </div>
            <div className="evidence-columns">
              <div>
                <h3><span className="evidence-dot evidence-dot--fact" />确定事实</h3>
                {(state?.facts ?? []).map((fact, index) => (
                  <article className="evidence-item" key={`${fact.kind}-${fact.observed_at}-${index}`}>
                    <Icon name="check" />
                    <div>
                      <strong>{fact.summary}</strong>
                      <span>{fact.path ?? fact.kind} · {relativeTime(fact.observed_at)}</span>
                    </div>
                  </article>
                ))}
                {!state?.facts.length && <div className="empty-inline">暂无确定事实</div>}
              </div>
              <div>
                <h3><span className="evidence-dot evidence-dot--inference" />模型推断</h3>
                {(state?.inferences ?? []).map((fact, index) => (
                  <article
                    className="evidence-item evidence-item--inference"
                    key={`${fact.kind}-${fact.observed_at}-${index}`}
                  >
                    <Icon name="activity" />
                    <div>
                      <strong>{fact.summary}</strong>
                      <span>语义判断 · 可由巡检更新</span>
                    </div>
                  </article>
                ))}
                {!state?.inferences.length && <div className="empty-inline">暂无模型推断</div>}
              </div>
            </div>
          </section>

          <section className="panel" aria-labelledby="process-title">
            <div className="panel-title">
              <div>
                <span className="eyebrow">Processes</span>
                <h2 id="process-title">Agent 进程树</h2>
              </div>
              <span className="panel-meta">后台 10 秒 / 详情 2 秒采样</span>
            </div>
            <ProcessTree agents={agents} />
          </section>

          <section className="panel" aria-labelledby="workspace-facts-title">
            <div className="panel-title">
              <div>
                <span className="eyebrow">Repository</span>
                <h2 id="workspace-facts-title">工作区事实</h2>
              </div>
            </div>
            <div className="fact-cards">
              <div>
                <span>版本控制</span>
                <strong>{runtime?.vcs.kind.toUpperCase() ?? "NONE"}</strong>
                <p>{runtime?.vcs.status_summary ?? "无状态"}</p>
              </div>
              <div>
                <span>测试结果</span>
                <strong>
                  {runtime?.tests.status === "passed"
                    ? "通过"
                    : runtime?.tests.status === "failed"
                      ? "失败"
                      : "未知"}
                </strong>
                <p>{runtime?.tests.summary ?? "未发现报告"}</p>
              </div>
              <div>
                <span>工作区指纹</span>
                <strong>{runtime?.workspace_fingerprint.slice(0, 10) ?? "—"}</strong>
                <p>{runtime?.file_count_considered ?? 0} 个文件参与基线</p>
              </div>
            </div>
          </section>
        </main>

        <aside className="detail-side">
          <InspectionReliabilityCard
            state={state}
            permission={project.inspection_permission}
          />

          <section className="panel compact-panel">
            <span className="eyebrow">Cycle</span>
            <h2>{project.current_cycle?.name ?? "非结构化监控"}</h2>
            <p>
              {project.current_cycle?.goal
                ?? "当前未配置目标和验收条件，系统只展示阶段和下一步。"}
            </p>
            {project.current_cycle && (
              <div className="criteria-list">
                {project.current_cycle.acceptance_criteria.map((item) => (
                  <div key={item.id}>
                    <span className={item.completed ? "criterion-check done" : "criterion-check"}>
                      {item.completed ? <Icon name="check" /> : ""}
                    </span>
                    <span>{item.title}</span>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="panel compact-panel">
            <span className="eyebrow">Inspection permission</span>
            <h2>
              {project.inspection_permission === "standard_source"
                ? "标准源码巡检"
                : project.inspection_permission === "restricted"
                  ? "受限巡检"
                  : "仅本地监控"}
            </h2>
            <p>敏感文件与 Agent 控制文件始终由本地快照构建器拒绝复制。</p>
            <div className="security-row">
              <Icon name="shield" />
              <span>OpenCode 仅访问过滤后的临时快照</span>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
