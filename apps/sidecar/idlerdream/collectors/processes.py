from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from pathlib import Path

import psutil

from ..models import AgentProcess, Project
from ..security.redaction import redact_text

# Terminal hosts whose child shells commonly launch coding Agents. Recognising
# them lets the association walk through the tree instead of stopping at the
# first process whose own working directory is outside the workspace.
TERMINAL_HOSTS = {
    "windowsterminal.exe",
    "wt.exe",
    "code.exe",
    "code-insiders.exe",
    "conhost.exe",
}

_ATTRIBUTES = ["pid", "name", "exe", "cmdline", "cwd", "status", "create_time", "memory_info"]


class CpuSampler:
    """Tracks per-process CPU baselines so the first sample is meaningful.

    ``psutil.Process.cpu_percent(interval=None)`` returns 0.0 on the first call
    per Process instance. The collector creates fresh instances on every pass,
    so without this sampler every process would report 0.0 indefinitely in
    aggregate. The sampler keeps ``(pid, create_time)`` keyed baselines and
    computes utilisation from the delta of ``cpu_times`` over wall time.
    """

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self._previous: dict[tuple[int, float], tuple[float, float]] = {}

    def sample(self, pid: int, create_time: float, cpu_total: float) -> float:
        """Return CPU percent since the previous sample for this process."""
        now = self._clock()
        key = (pid, create_time)
        previous = self._previous.get(key)
        self._previous[key] = (cpu_total, now)
        if previous is None:
            return 0.0  # first sample establishes the baseline only
        previous_cpu, previous_wall = previous
        wall = now - previous_wall
        if wall <= 0:
            return 0.0
        delta_cpu = max(0.0, cpu_total - previous_cpu)
        cores = os.cpu_count() or 1
        return min(delta_cpu / wall * 100.0, cores * 100.0)


class ProcessCollector:
    def __init__(
        self,
        agent_names: set[str],
        *,
        process_iter=None,
        cpu_sampler: CpuSampler | None = None,
    ) -> None:
        self.agent_names = {name.lower() for name in agent_names}
        self._process_iter = process_iter or psutil.process_iter
        self.cpu = cpu_sampler or CpuSampler()

    def collect_for_project(self, project: Project) -> list[AgentProcess]:
        workspace = Path(project.path).resolve(strict=False)
        agents: list[AgentProcess] = []
        for process in self._process_iter(_ATTRIBUTES):
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

        # Terminal-launched Agents: when the Agent's own CWD is not readable
        # (a common Windows access-denied case) or the Agent is nested under a
        # shell, the workspace association can still be established by walking
        # the parent chain and by recognising the terminal host.
        score += self._ancestor_confidence(process, workspace)
        return min(score, 1.0)

    def _ancestor_confidence(self, process: psutil.Process, workspace: Path) -> float:
        score = 0.0
        current = process
        for _depth in range(4):
            try:
                parent = current.parent()
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                break
            if parent is None:
                break
            try:
                parent_name = (parent.name() or "").lower()
                executable = parent.exe() or ""
                executable_name = Path(executable).name.lower()
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                parent_name = ""
                executable_name = ""
            try:
                cwd = parent.cwd()
                if cwd:
                    cwd_path = Path(cwd).resolve(strict=False)
                    if cwd_path == workspace:
                        score += 0.3
                    elif _is_relative_to(cwd_path, workspace):
                        score += 0.2
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                pass
            if parent_name in TERMINAL_HOSTS or executable_name in TERMINAL_HOSTS:
                # A terminal host is the expected launch context for integrated
                # shells; walking through it confirms rather than confuses.
                score += 0.15
            current = parent
        return min(score, 0.6)

    def _to_model(self, process: psutil.Process, confidence: float, depth: int) -> AgentProcess:
        try:
            with process.oneshot():
                info = process.as_dict(
                    attrs=["pid", "name", "exe", "cmdline", "cwd", "status", "create_time"]
                )
                memory = process.memory_info().rss
                cpu = self._cpu_percent(process, info)
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

    def _cpu_percent(self, process: psutil.Process, info: dict) -> float:
        try:
            cpu_times = process.cpu_times()
            cpu_total = float(cpu_times.user) + float(cpu_times.system)
            return self.cpu.sample(
                int(info.get("pid") or process.pid),
                float(info.get("create_time") or 0.0),
                cpu_total,
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            return 0.0


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
