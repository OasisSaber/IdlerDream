import type { AgentProcess } from "@idlerdream/protocol";
import { useId, useState } from "react";
import { formatBytes } from "../lib/format";
import { Icon } from "../lib/icons";

function Node({ process, depth = 0 }: { process: AgentProcess; depth?: number }) {
  const [open, setOpen] = useState(depth < 1);
  const childrenId = useId();
  const hasChildren = process.children.length > 0;

  return (
    <div className="process-node">
      <div className="process-row" style={{ paddingLeft: 12 + depth * 20 }}>
        <button
          className={`tree-toggle ${hasChildren ? "" : "tree-toggle--empty"}`}
          onClick={() => hasChildren && setOpen(!open)}
          aria-label={hasChildren ? (open ? `折叠 ${process.name} 子进程` : `展开 ${process.name} 子进程`) : `${process.name} 没有子进程`}
          aria-expanded={hasChildren ? open : undefined}
          aria-controls={hasChildren ? childrenId : undefined}
          disabled={!hasChildren}
        >
          {hasChildren && <Icon name="chevron" className={open ? "rotate-90" : ""} />}
        </button>
        <div className="process-icon"><Icon name={depth === 0 ? "terminal" : "cpu"} /></div>
        <div className="process-main">
          <strong>{process.name}</strong>
          <span title={process.command_summary}>PID {process.pid} · {process.command_summary || "命令已脱敏"}</span>
        </div>
        <div className="process-stat">
          <span>CPU</span>
          <strong>{process.cpu_percent.toFixed(1)}%</strong>
        </div>
        <div className="process-stat">
          <span>内存</span>
          <strong>{formatBytes(process.memory_bytes)}</strong>
        </div>
        <span className={`confidence confidence--${process.association_confidence >= 0.8 ? "high" : "mid"}`}>
          {Math.round(process.association_confidence * 100)}% 关联
        </span>
      </div>
      {open && hasChildren && (
        <div id={childrenId} role="group" aria-label={`${process.name} 的子进程`}>
          {process.children.map((child) => (
            <Node key={child.pid} process={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export function ProcessTree({ agents }: { agents: AgentProcess[] }) {
  if (!agents.length) return <div className="empty-inline">当前没有关联 Agent 进程</div>;
  return (
    <div className="process-tree" role="tree" aria-label="关联 Agent 进程树">
      {agents.map((agent) => <Node key={agent.pid} process={agent} />)}
    </div>
  );
}
