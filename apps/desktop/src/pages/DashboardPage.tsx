import type { ProjectEnvelope } from "@idlerdream/protocol";
import { useId, useState } from "react";
import { ProjectCard } from "../components/ProjectCard";
import { Icon } from "../lib/icons";

interface DashboardPageProps {
  projects: ProjectEnvelope[];
  onOpen(id: string): void;
  onInspect(id: string): void;
  onAdd(): void;
}

function needsAttention(item: ProjectEnvelope) {
  return Boolean(
    item.state?.needs_user_attention
      || ["blocked", "conflict", "waiting_user"].includes(item.state?.core_status ?? "unknown"),
  );
}

function sorted(items: ProjectEnvelope[]) {
  return [...items].sort((left, right) => {
    const attentionDelta = Number(needsAttention(right)) - Number(needsAttention(left));
    if (attentionDelta) return attentionDelta;
    const priority = { high: 3, medium: 2, low: 1 };
    const priorityDelta = priority[right.project.priority] - priority[left.project.priority];
    if (priorityDelta) return priorityDelta;
    return Date.parse(right.state?.updated_at ?? right.project.updated_at)
      - Date.parse(left.state?.updated_at ?? left.project.updated_at);
  });
}

function ProjectSection({
  title,
  subtitle,
  items,
  defaultCollapsed = false,
  onOpen,
  onInspect,
}: {
  title: string;
  subtitle: string;
  items: ProjectEnvelope[];
  defaultCollapsed?: boolean;
  onOpen(id: string): void;
  onInspect(id: string): void;
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const contentId = useId();

  if (!items.length) return null;

  return (
    <section className={`project-section ${collapsed ? "project-section--collapsed" : ""}`}>
      <div className="section-heading">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        <button
          className="section-count-button"
          aria-expanded={!collapsed}
          aria-controls={contentId}
          onClick={() => setCollapsed((value) => !value)}
        >
          <span>{items.length}</span>
          <Icon name="chevron" className={collapsed ? "" : "rotate-90"} />
        </button>
      </div>
      {!collapsed && (
        <div className="project-grid" id={contentId}>
          {sorted(items).map((item) => (
            <ProjectCard
              key={item.project.id}
              envelope={item}
              onOpen={() => onOpen(item.project.id)}
              onInspect={() => onInspect(item.project.id)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

export function DashboardPage({ projects, onOpen, onInspect, onAdd }: DashboardPageProps) {
  const attention = projects.filter(needsAttention).length;
  const running = projects.filter((item) => (item.runtime?.agents.length ?? 0) > 0).length;
  const active = projects.filter((item) => item.project.activity_state === "active");
  const pinned = active.filter((item) => item.project.pinned);
  const regular = active.filter(
    (item) => !item.project.pinned && item.state?.core_status !== "completed",
  );
  const inactive = projects.filter(
    (item) => item.project.activity_state === "inactive" && item.state?.core_status !== "completed",
  );
  const completed = projects.filter(
    (item) => item.state?.core_status === "completed" && item.project.activity_state !== "archived",
  );
  const archived = projects.filter((item) => item.project.activity_state === "archived");

  return (
    <div className="page dashboard-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Local workspace overview</span>
          <h1>项目运行总览</h1>
          <p>已验证状态与实时活动分层展示。需要你处理的项目会保持高亮。</p>
        </div>
        <button className="button button--primary" onClick={onAdd}>
          <span aria-hidden="true">＋</span>
          添加工作区
        </button>
      </header>

      <section className="overview-strip" aria-label="项目摘要">
        <div className="overview-primary">
          <span className="overview-signal"><Icon name="activity" /></span>
          <div>
            <span>当前最需要关注</span>
            <strong>
              {attention ? `${attention} 个项目需要你的操作` : "没有需要立即处理的项目"}
            </strong>
            <p>
              {attention
                ? "高亮项目包含等待确认、确定性失败或状态冲突。"
                : "所有项目均可由 Agent 继续推进或处于正常等待。"}
            </p>
          </div>
        </div>
        <div className="overview-metrics">
          <div><span>运行中 Agent</span><strong>{running}</strong></div>
          <div><span>活跃项目</span><strong>{active.length}</strong></div>
          <div>
            <span>状态过期</span>
            <strong>{projects.filter((item) => item.state?.freshness === "expired").length}</strong>
          </div>
        </div>
      </section>

      {!projects.length && (
        <section className="panel dashboard-empty">
          <span className="overview-signal"><Icon name="folder" /></span>
          <h2>还没有符合搜索条件的工作区</h2>
          <p>清除搜索条件，或添加一个本地 Windows 工作区开始监控。</p>
          <button className="button button--primary" onClick={onAdd}>添加工作区</button>
        </section>
      )}

      <ProjectSection
        title="置顶 / 当前主项目"
        subtitle="保持在首页顶部，不受普通排序影响"
        items={pinned}
        onOpen={onOpen}
        onInspect={onInspect}
      />
      <ProjectSection
        title="活跃项目"
        subtitle="正在开发、等待确认或近期有有效活动"
        items={regular}
        onOpen={onOpen}
        onInspect={onInspect}
      />
      <ProjectSection
        title="非活跃项目"
        subtitle="停止深度分析，仍保留低成本活动检测"
        items={inactive}
        defaultCollapsed
        onOpen={onOpen}
        onInspect={onInspect}
      />
      <ProjectSection
        title="已完成"
        subtitle="当前周期已满足验收条件"
        items={completed}
        defaultCollapsed
        onOpen={onOpen}
        onInspect={onInspect}
      />
      <ProjectSection
        title="已归档"
        subtitle="保留历史并仅检测新的重大活动"
        items={archived}
        defaultCollapsed
        onOpen={onOpen}
        onInspect={onInspect}
      />
    </div>
  );
}
