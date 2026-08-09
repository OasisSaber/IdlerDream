import type { CurrentProjectState, InspectionPermission } from "@idlerdream/protocol";
import { Icon } from "../lib/icons";
import "./InspectionReliabilityCard.css";

interface InspectionReliabilityCardProps {
  state: CurrentProjectState | null;
  permission: InspectionPermission;
}

const qualityCopy = {
  full: {
    title: "完整巡检结果",
    detail: "结构化报告无需修复即可通过身份、指纹和 Schema 校验。",
    icon: "check" as const,
  },
  partial: {
    title: "部分有效巡检",
    detail: "核心状态有效；非核心格式偏差已由确定性标准化器修复。",
    icon: "activity" as const,
  },
  failed: {
    title: "巡检尚未验证",
    detail: "当前仅展示本地事实或上一次有效状态，不会用失败结果覆盖项目判断。",
    icon: "alert" as const,
  },
};

export function InspectionReliabilityCard({ state, permission }: InspectionReliabilityCardProps) {
  const quality = state?.inspection_quality ?? "failed";
  const copy = qualityCopy[quality];
  const warnings = state?.inspection_warnings ?? [];

  return (
    <section
      className={`reliability-card reliability-card--${quality}`}
      aria-labelledby="inspection-reliability-title"
    >
      <div className="reliability-card__header">
        <span className="reliability-card__symbol" aria-hidden="true">
          <Icon name={copy.icon} />
        </span>
        <div>
          <span className="eyebrow">Inspection integrity</span>
          <h2 id="inspection-reliability-title">{copy.title}</h2>
        </div>
        <span className="reliability-card__badge">
          {quality === "full" ? "FULL" : quality === "partial" ? "PARTIAL" : "UNVERIFIED"}
        </span>
      </div>

      <p className="reliability-card__description">{copy.detail}</p>

      <div className="reliability-card__facts" aria-label="巡检安全边界">
        <div>
          <Icon name="shield" />
          <span>
            <strong>隔离快照</strong>
            <small>模型不接触真实工作区路径</small>
          </span>
        </div>
        <div>
          <Icon name="folder" />
          <span>
            <strong>
              {permission === "standard_source"
                ? "标准源码"
                : permission === "restricted"
                  ? "受限读取"
                  : "仅本地"}
            </strong>
            <small>敏感与 Agent 控制文件本地过滤</small>
          </span>
        </div>
      </div>

      {warnings.length > 0 && (
        <details className="reliability-card__warnings">
          <summary>
            <span>{warnings.length} 项标准化说明</span>
            <small>不会静默修改项目身份或核心状态</small>
          </summary>
          <ul>
            {warnings.slice(0, 6).map((warning, index) => (
              <li key={`${warning}-${index}`}>{warning}</li>
            ))}
          </ul>
        </details>
      )}

      {state?.inspection_error && (
        <div className="reliability-card__error" role="status">
          <Icon name="alert" />
          <span>{state.inspection_error}</span>
        </div>
      )}
    </section>
  );
}
