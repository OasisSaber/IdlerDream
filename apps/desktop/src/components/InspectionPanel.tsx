import type { InspectionJob } from "@idlerdream/protocol";
import { Icon } from "../lib/icons";

interface InspectionPanelProps {
  job: InspectionJob;
  projectName: string;
  onCancel(): void;
}

export function InspectionPanel({ job, projectName, onCancel }: InspectionPanelProps) {
  const stages = ["生成事实基线", "读取项目结构", "检查版本状态", "读取相关源码", "归并状态报告"];
  const current = Math.max(
    0,
    stages.findIndex((stage) => job.stage.includes(stage.replace("生成", ""))),
  );

  return (
    <aside
      className="inspection-panel"
      aria-label={`${projectName} 的只读巡检进度`}
      aria-live="polite"
    >
      <div className="inspection-panel__head">
        <div>
          <span className="eyebrow">Read-only inspection</span>
          <h2>正在巡检</h2>
          <p>{projectName}</p>
        </div>
        <span className="pulse-chip"><i /> LIVE</span>
      </div>

      <div className="inspection-orbit" aria-hidden="true">
        <div className="inspection-orbit__core"><Icon name="shield" /></div>
        <span className="orbit orbit--one" />
        <span className="orbit orbit--two" />
      </div>

      <div className="inspection-stage">
        <span>当前阶段</span>
        <strong>{job.stage}</strong>
        <p>{job.last_activity}</p>
      </div>

      <div className="stage-list">
        {stages.map((stage, index) => (
          <div
            key={stage}
            className={`stage-item ${index < current ? "done" : index === current ? "current" : ""}`}
          >
            <span>{index < current ? <Icon name="check" /> : index + 1}</span>
            <div>
              <strong>{stage}</strong>
              <small>{index < current ? "已完成" : index === current ? "进行中" : "等待"}</small>
            </div>
          </div>
        ))}
      </div>

      <div className="budget-card">
        <div><span>已运行</span><strong>{Math.max(1, Math.round(job.elapsed_seconds / 60))} 分钟</strong></div>
        <div><span>文件预算</span><strong>12 / 40</strong></div>
        <div><span>工具调用</span><strong>28 / 100</strong></div>
      </div>

      <button className="button button--danger button--full" onClick={onCancel}>
        <Icon name="close" />
        取消巡检
      </button>
    </aside>
  );
}
