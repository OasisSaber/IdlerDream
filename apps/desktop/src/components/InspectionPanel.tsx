import type { InspectionJob } from "@idlerdream/protocol";
import { Icon } from "../lib/icons";
import "./InspectionPanel.css";

interface InspectionPanelProps {
  job: InspectionJob;
  projectName: string;
  onCancel(): void;
}

const STAGES = [
  { key: "collecting_baseline", label: "生成事实基线" },
  { key: "snapshot_ready", label: "建立隔离快照" },
  { key: "semantic_inspection", label: "只读语义巡检" },
  { key: "completed", label: "校验并归并报告" },
];

function stageIndex(stage: string) {
  if (stage === "completed") return STAGES.length - 1;
  const index = STAGES.findIndex((item) => stage.includes(item.key));
  return index < 0 ? 0 : index;
}

function budgetValue(job: InspectionJob, key: string, fallback: string) {
  const value = job.budget?.[key];
  return typeof value === "number" ? String(value) : fallback;
}

export function InspectionPanel({ job, projectName, onCancel }: InspectionPanelProps) {
  const current = stageIndex(job.stage);
  const minutes = Math.max(0, Math.floor(job.elapsed_seconds / 60));
  const seconds = Math.max(0, Math.round(job.elapsed_seconds % 60));

  return (
    <aside
      className="inspection-panel inspection-panel--reliable"
      aria-label={`${projectName} 的只读巡检进度`}
      aria-live="polite"
    >
      <div className="inspection-panel__head">
        <div>
          <span className="eyebrow">Filtered read-only inspection</span>
          <h2>正在巡检</h2>
          <p>{projectName}</p>
        </div>
        <span className="pulse-chip"><i /> LIVE</span>
      </div>

      <div className="inspection-security-strip">
        <Icon name="shield" />
        <div>
          <strong>真实工作区保持隔离</strong>
          <span>OpenCode 仅读取经过过滤的临时快照</span>
        </div>
      </div>

      <div className="inspection-stage">
        <span>当前阶段</span>
        <strong>{STAGES[current]?.label ?? job.stage}</strong>
        <p>{job.last_activity || "正在等待安全的巡检事件。"}</p>
      </div>

      <div className="stage-list">
        {STAGES.map((stage, index) => (
          <div
            key={stage.key}
            className={`stage-item ${index < current ? "done" : index === current ? "current" : ""}`}
          >
            <span>{index < current ? <Icon name="check" /> : index + 1}</span>
            <div>
              <strong>{stage.label}</strong>
              <small>{index < current ? "已完成" : index === current ? "进行中" : "等待"}</small>
            </div>
          </div>
        ))}
      </div>

      {job.warnings?.length > 0 && (
        <div className="inspection-warning" role="status">
          <Icon name="activity" />
          <span>{job.warnings[job.warnings.length - 1]}</span>
        </div>
      )}

      <div className="budget-card">
        <div><span>已运行</span><strong>{minutes}:{seconds.toString().padStart(2, "0")}</strong></div>
        <div><span>文件上限</span><strong>{budgetValue(job, "max_files", "40")}</strong></div>
        <div><span>总内容预算</span><strong>{budgetValue(job, "max_content_mb", "2 MB")}</strong></div>
      </div>

      <button className="button button--danger button--full" onClick={onCancel}>
        <Icon name="close" />
        取消巡检
      </button>
    </aside>
  );
}
