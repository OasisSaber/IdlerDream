from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import psutil

from ..models import AgentProcess, Project
from ..security.redaction import redact_text


class ProcessCollector:
    def __init__(self, agent_names: set[str]) -> None:
        self.agent_names = {name.lower() for name in agent_names}

    def collect_for_project(self, project: Project) -> list[AgentProcess]:
        workspace = Path(project.path).resolve(strict=False)
        agents: list[AgentProcess] = []
        for process in psutil.process_iter(
            ["pid", "name", "exe", "cmdline", "cwd", "status", "create_time", "memory_info"]
        ):
            try:
                name = (process.info.get("name") or "").lower()
                executable_name = Path(process.info.get("exe") or name).name.lower()
                if name not in self.agent_names and executable_name not in self.agent_names:
                    continue
                confidence = self._association_confidence(process, workspace)
                if confidence < 0.25:
                    continue
                agents.append(self._to_model(process, confidence, depth=0))
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                continue
        return sorted(agents, key=lambda item: item.association_confidence, reverse=True)

    def _association_confidence(self, process: psutil.Process, workspace: Path) -> float:
        score = 0.0
        try:
            cwd = process.cwd()
            if cwd:
                cwd_path = Path(cwd).resolve(strict=False)
                if cwd_path == workspace:
                    score += 0.65
                elif _is_relative_to(cwd_path, workspace):
                    score += 0.5
                elif _is_relative_to(workspace, cwd_path):
                    score += 0.2
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            pass

        try:
            command = " ".join(process.cmdline()).lower().replace("\\", "/")
            workspace_text = str(workspace).lower().replace("\\", "/")
            if workspace_text in command:
                score += 0.35
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
        return min(score, 1.0)

    def _to_model(self, process: psutil.Process, confidence: float, depth: int) -> AgentProcess:
        try:
            with process.oneshot():
                info = process.as_dict(
                    attrs=["pid", "name", "exe", "cmdline", "cwd", "status", "create_time"]
                )
                memory = process.memory_info().rss
                cpu = process.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            info = {"pid": process.pid, "name": "unknown"}
            memory = 0
            cpu = 0.0

        children: list[AgentProcess] = []
        if depth < 2:
            try:
                for child in process.children(recursive=False)[:50]:
                    children.append(self._to_model(child, confidence, depth + 1))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        command = redact_text(" ".join(info.get("cmdline") or []))[:1000]
        create_time = info.get("create_time")
        return AgentProcess(
            pid=int(info.get("pid") or process.pid),
            name=str(info.get("name") or "unknown"),
            executable=info.get("exe"),
            cwd=info.get("cwd"),
            command_summary=command,
            status=str(info.get("status") or "unknown"),
            cpu_percent=float(cpu),
            memory_bytes=int(memory),
            started_at=(
                datetime.fromtimestamp(float(create_time), tz=UTC) if create_time else None
            ),
            association_confidence=confidence,
            children=children,
        )


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
