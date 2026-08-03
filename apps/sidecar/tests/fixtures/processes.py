"""Fake psutil process trees for process-association tests (CR-21).

The fixtures mirror the real Windows scenarios the collector must handle:

- an Agent running directly in the workspace (OpenCode);
- an Agent in a subdirectory of the workspace (Codex);
- an Agent nested deeper under the workspace root (Claude Code);
- an Agent launched from Windows Terminal, including the common case where the
  Agent's own CWD is not readable (AccessDenied) and the association must be
  recovered from the terminal host;
- an Agent inside a VS Code integrated terminal (Code -> shell -> Agent).
"""

from __future__ import annotations

from pathlib import Path

import psutil


class FakeMemoryInfo:
    def __init__(self, rss: int = 0) -> None:
        self.rss = rss


class FakeCpuTimes:
    def __init__(self, user: float = 0.0, system: float = 0.0) -> None:
        self.user = user
        self.system = system


class _Oneshot:
    def __init__(self, process: FakeProcess) -> None:
        self.process = process

    def __enter__(self) -> FakeProcess:
        return self.process

    def __exit__(self, *_exc) -> bool:
        return False


class FakeProcess:
    """Mimics the ``psutil.Process`` surface the collector relies on.

    Data is stored on private attributes so that the ``name()`` and ``exe()``
    methods remain callable (the collector calls them on parent processes).
    """

    def __init__(
        self,
        *,
        pid: int,
        name: str,
        exe: str | None = None,
        cmdline: list[str] | None = None,
        cwd: str | None = None,
        status: str = "running",
        create_time: float = 1000.0,
        memory_rss: int = 0,
        cpu_user: float = 0.0,
        cpu_system: float = 0.0,
        children: list[FakeProcess] | None = None,
        parent: FakeProcess | None = None,
        deny_cwd: bool = False,
        deny_cmdline: bool = False,
    ) -> None:
        self.pid = pid
        self._name = name
        self._exe = exe or name
        self._cmdline = list(cmdline or [])
        self._cwd = cwd
        self._status = status
        self._create_time = create_time
        self._memory_rss = memory_rss
        self._cpu_user = cpu_user
        self._cpu_system = cpu_system
        self._children = list(children or [])
        self._parent = parent
        self._deny_cwd = deny_cwd
        self._deny_cmdline = deny_cmdline
        self._cpu_times_calls = 0
        self.info = {
            "pid": pid,
            "name": self._name,
            "exe": self._exe,
            "cmdline": list(self._cmdline),
            "cwd": self._cwd,
            "status": self._status,
            "create_time": self._create_time,
            "memory_info": FakeMemoryInfo(self._memory_rss),
        }

    def name(self) -> str:
        return self._name

    def exe(self) -> str:
        return self._exe

    def cmdline(self) -> list[str]:
        if self._deny_cmdline:
            raise psutil.AccessDenied(self.pid)
        return list(self._cmdline)

    def cwd(self) -> str | None:
        if self._deny_cwd:
            raise psutil.AccessDenied(self.pid)
        return self._cwd

    def parent(self) -> FakeProcess | None:
        return self._parent

    def oneshot(self) -> _Oneshot:
        return _Oneshot(self)

    def as_dict(self, attrs: list[str] | None = None) -> dict:
        return dict(self.info)

    def memory_info(self) -> FakeMemoryInfo:
        return FakeMemoryInfo(self._memory_rss)

    def cpu_times(self) -> FakeCpuTimes:
        # Accumulate CPU time across calls like a real process so the sampler
        # sees a growing delta between collection passes.
        self._cpu_times_calls += 1
        growth = self._cpu_times_calls * 0.1
        return FakeCpuTimes(self._cpu_user + growth, self._cpu_system + growth)

    def children(self, recursive: bool = False) -> list[FakeProcess]:
        return list(self._children)

    def create_time(self) -> float:
        return self._create_time


def fake_process_iter(*processes: FakeProcess):
    def _iter(attrs: list[str] | None = None):
        return list(processes)

    return _iter


def opencode_direct(workspace: Path) -> FakeProcess:
    return FakeProcess(
        pid=101,
        name="opencode.exe",
        exe="opencode.exe",
        cmdline=["opencode"],
        cwd=str(workspace),
        create_time=1700000000.0,
        cpu_user=4.0,
        cpu_system=1.0,
        memory_rss=120_000_000,
    )


def codex_in_subdirectory(workspace: Path) -> FakeProcess:
    return FakeProcess(
        pid=201,
        name="codex.exe",
        exe="codex.exe",
        cmdline=["codex", "exec"],
        cwd=str(workspace / "src"),
        create_time=1700000100.0,
    )


def claude_nested(workspace: Path) -> FakeProcess:
    return FakeProcess(
        pid=301,
        name="claude.exe",
        exe="claude.exe",
        cmdline=["claude"],
        cwd=str(workspace / "packages" / "web"),
        create_time=1700000200.0,
    )


def windows_terminal_agent(workspace: Path) -> FakeProcess:
    """Agent with a readable CWD launched from Windows Terminal."""
    terminal = FakeProcess(
        pid=401,
        name="WindowsTerminal.exe",
        exe="WindowsTerminal.exe",
        cmdline=["WindowsTerminal.exe"],
        cwd=str(Path.home()),
        create_time=1700000000.0,
    )
    agent = FakeProcess(
        pid=402,
        name="opencode.exe",
        exe="opencode.exe",
        cmdline=["opencode"],
        cwd=str(workspace),
        create_time=1700000300.0,
        deny_cmdline=True,
        parent=terminal,
    )
    terminal._children = [agent]
    return agent


def windows_terminal_denied_cwd(workspace: Path) -> FakeProcess:
    """Agent launched from Windows Terminal whose own CWD raises AccessDenied."""
    terminal = FakeProcess(
        pid=404,
        name="WindowsTerminal.exe",
        exe="WindowsTerminal.exe",
        cmdline=["WindowsTerminal.exe"],
        cwd=str(workspace),
        create_time=1700000000.0,
    )
    agent = FakeProcess(
        pid=403,
        name="opencode.exe",
        exe="opencode.exe",
        cmdline=["opencode"],
        cwd=str(workspace),
        create_time=1700000400.0,
        deny_cwd=True,
        deny_cmdline=True,
        parent=terminal,
    )
    terminal._children = [agent]
    return agent


def vscode_integrated_terminal_agent(workspace: Path) -> FakeProcess:
    """Agent inside a VS Code integrated terminal: Code -> powershell -> claude."""
    editor = FakeProcess(
        pid=501,
        name="Code.exe",
        exe="Code.exe",
        cmdline=["Code.exe", "C:\\Program Files\\Microsoft VS Code"],
        cwd="C:\\Users\\someone\\AppData\\Local\\Programs\\Microsoft VS Code",
        create_time=1700000000.0,
    )
    shell = FakeProcess(
        pid=502,
        name="powershell.exe",
        exe="powershell.exe",
        cmdline=["powershell.exe", "-NoExit"],
        cwd=str(workspace),
        create_time=1700000000.0,
        parent=editor,
    )
    agent = FakeProcess(
        pid=503,
        name="claude.exe",
        exe="claude.exe",
        cmdline=["claude"],
        cwd=str(workspace),
        create_time=1700000500.0,
        parent=shell,
    )
    editor._children = [shell]
    shell._children = [agent]
    return agent


def unrelated_agent() -> FakeProcess:
    """An Agent-named process running somewhere else entirely (negative case)."""
    return FakeProcess(
        pid=601,
        name="opencode.exe",
        exe="opencode.exe",
        cmdline=["opencode"],
        cwd="C:\\Windows\\System32",
        create_time=1700000600.0,
    )
