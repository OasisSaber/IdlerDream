import type { CoreStatus, Freshness } from "@idlerdream/protocol";
import { Icon } from "../lib/icons";

const statusLabels: Record<CoreStatus, string> = {
  unknown: "未知", not_started: "未开始", in_progress: "进行中", waiting_user: "等待用户", waiting_external: "等待外部", blocked: "阻塞", conflict: "状态冲突", completed: "已完成",
};
const freshnessLabels: Record<Freshness, string> = { current: "当前", possibly_stale: "可能过时", expired: "已过期", never_inspected: "未巡检" };

export function StatusBadge({ status }: { status: CoreStatus }) {
  const icon = status === "completed" ? "check" : status === "blocked" || status === "conflict" ? "alert" : status === "waiting_user" || status === "waiting_external" ? "clock" : "activity";
  return <span className={`badge badge--${status}`}><Icon name={icon} />{statusLabels[status]}</span>;
}
export function FreshnessBadge({ freshness }: { freshness: Freshness }) {
  return <span className={`freshness freshness--${freshness}`}>{freshnessLabels[freshness]}</span>;
}
