import type { ProjectEnvelope } from "@idlerdream/protocol";
import { useId } from "react";
import { formatBytes, relativeTime } from "../lib/format";
import { Icon } from "../lib/icons";
import { FreshnessBadge, StatusBadge } from "./StatusBadge";

function actorLabel(actor?: string) {
  if (actor === "user") return "由你执行";
  if (actor === "agent") return "由 Agent 执行";
  return "当前无动作";
}

export function ProjectCard({
  envelope,
  onOpen,
  onInspect,
}: {
  envelope: ProjectEnvelope;
  onOpen(): void;
  onInspect(): void;
}) {
  const descriptionId = useId();
  const { project, state, runtime } = envelope;
  const agents = runtime?.agents ?? [];
  const cpu = agents.reduce((sum, item) => sum + item.cpu_percent, 0);
  const memory = agents.reduce((sum, item) => sum + item.memory_bytes, 0);
  const done = project.current_cycle?.acceptance_criteria.filter((item) => item.completed).length ?? 0;
  const total = project.current_cycle?.acceptance_criteria.length ?? 0;
  const attention = Boolean(
    state?.needs_user_attention
      || ["blocked", "conflict", "waiting_user"].includes(state?.core_status ?? "unknown")
      || state?.risks.includes("workspace_missing"),
  );
  const actionIsExpired = state?.freshness === "expired";
  const currentAction = actionIsExpired ? null : state?.next_action;
  const nextActionText = actionIsExpired
    ? "状态已过期，需要重新巡检后判断下一步"
    : currentAction?.action ?? "需要首次巡检后判断";

  return (
    <article className={`project-card ${attention ? "project-card--attention" : ""}`}>
      <button
        className="project-card__body"
        onClick={onOpen}
        aria-describedby={descriptionId}
      >
        <header className="project-card__header">
          <div className="project-identity">
            <span className="project-monogram">{project.name.slice(0, 2).toUpperCase()}</span>
            <div>
              <div className="project-title-row">
                <h3>{project.name}</h3>
                {project.pinned && <span className="pin">置顶</span>}
              </div>
              <p>
                {project.current_cycle?.name ?? "非结构化监控"}
                {" · "}
                {runtime?.vcs.kind === "none"
                  ? "无版本控制"
                  : `${runtime?.vcs.kind.toUpperCase()} ${runtime?.vcs.branch ?? ""}`}
              </p>
            </div>
          </div>
          <div className="project-badges">
            {state && <StatusBadge status={state.core_status} />}
            {state && <FreshnessBadge freshness={state.freshness} />}
          </div>
        </header>

        <div className="project-card__grid" id={descriptionId}>
          <section className="project-next">
            <span className="section-kicker">最高优先级下一步</span>
            <strong>{nextActionText}</strong>
            <div className="actor-row">
              <span className={`actor actor--${currentAction?.actor ?? "none"}`}>
                {actorLabel(currentAction?.actor)}
              </span>
              <span>
                {state?.confidence && !actionIsExpired
                  ? `置信度 ${Math.round(state.confidence * 100)}%`
                  : actionIsExpired
                    ? "旧结论不再作为当前行动"
                    : "尚无置信度"}
              </span>
            </div>
          </section>

          <section className="project-runtime">
            <div>
              <span>实时活动</span>
              <strong>{agents.length ? `${agents.length} 个 Agent 正在运行` : "当前无 Agent"}</strong>
            </div>
            <div className="resource-pills">
              <span><Icon name="cpu" />{cpu.toFixed(1)}%</span>
              <span><Icon name="memory" />{formatBytes(memory)}</span>
            </div>
          </section>
        </div>

        <footer className="project-card__footer">
          <div className="progress-summary">
            <span>{total ? `验收条件 ${done}/${total}` : `当前阶段 · ${state?.phase ?? "未知"}`}</span>
            {total > 0 && (
              <div className="mini-progress" aria-label={`验收条件完成 ${done}/${total}`}>
                <i style={{ width: `${Math.round((done / total) * 100)}%` }} />
              </div>
            )}
          </div>
          <div className="project-meta">
            <span>{runtime?.vcs.changed_files ?? 0} 个变更文件</span>
            <span>最后验证 {relativeTime(state?.verified_at)}</span>
            <Icon name="chevron" />
          </div>
        </footer>
      </button>

      <button
        className="inspect-button"
        onClick={(event) => {
          event.stopPropagation();
          onInspect();
        }}
        aria-label={`巡检 ${project.name}`}
      >
        <Icon name="refresh" />
        巡检
      </button>
    </article>
  );
}
