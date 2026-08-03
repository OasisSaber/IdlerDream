from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

import psutil

from ..models import FactBaseline, InspectionReport, Project
from ..security.redaction import redact_report_text_fields, redact_text, redact_value
from .prompt import build_inspection_prompt
from .report_parser import extract_strings, parse_report_text

ProgressCallback = Callable[[str, dict], Awaitable[None]]

# Sensitive filename patterns that the inspector may never read, even inside an
# allowed workspace. Expanded relative to the workspace root so the deny rules
# are more specific than the workspace allow rule.
SENSITIVE_READ_DENY_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.pfx",
    "*.p12",
    "id_rsa*",
    "credentials*",
    "secrets*",
    ".npmrc",
    ".pypirc",
    "*auth.json",
    "*credential*.json",
)


@dataclass(slots=True)
class InspectionOutcome:
    report: InspectionReport | None
    raw_events: list[dict] = field(default_factory=list)
    stderr_tail: str = ""
    exit_code: int | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


class OpenCodeAdapter:
    """Constrained OpenCode adapter.

    OpenCode is launched outside the target repository with an isolated HOME and
    no Bash permission. The project path is available only through the explicit
    external-directory permission. This prevents project AGENTS.md/.opencode
    configuration from becoming inspector instructions.
    """

    def __init__(
        self,
        executable: str = "opencode",
        *,
        model: str | None = None,
        timeout_seconds: int = 600,
        config_dir: Path | None = None,
    ) -> None:
        self.executable = executable
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.config_dir = (config_dir or Path.home() / ".idlerdream" / "opencode-inspector").resolve(strict=False)
        self.run_root = self.config_dir / "run-root"
        self.isolated_home = self.config_dir / "isolated-home"
        for directory in (self.config_dir, self.run_root, self.isolated_home):
            directory.mkdir(parents=True, exist_ok=True)
        self._running: dict[str, asyncio.subprocess.Process] = {}

    def available(self) -> bool:
        return shutil.which(self.executable) is not None

    async def version(self) -> str | None:
        if not self.available():
            return None
        process = await asyncio.create_subprocess_exec(
            self.executable, "--version", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        return stdout.decode("utf-8", errors="replace").strip() or None

    async def inspect(
        self,
        job_id: str,
        project: Project,
        baseline: FactBaseline,
        on_progress: ProgressCallback | None = None,
    ) -> InspectionOutcome:
        if not self.available():
            return InspectionOutcome(report=None, error="OpenCode executable not found")
        if project.inspection_permission.value == "local_only":
            return InspectionOutcome(report=None, error="Project is configured for local-only monitoring")

        prompt = build_inspection_prompt(project, baseline)
        command = [
            self.executable,
            "--pure",
            "run",
            "--format", "json",
            "--agent", "idlerdream-inspector",
            "--dir", str(self.run_root),
        ]
        if self.model:
            command.extend(["--model", self.model])
        command.append(prompt)

        environment = os.environ.copy()
        environment.update(self._isolated_environment(project))
        creation_flags = 0
        if os.name == "nt":
            creation_flags = getattr(asyncio.subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(self.run_root),
            env=environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=creation_flags,
        )
        self._running[job_id] = process
        events: list[dict] = []
        text_fragments: list[str] = []
        stderr_lines: list[str] = []

        async def consume_stdout() -> None:
            assert process.stdout is not None
            while line := await process.stdout.readline():
                decoded = line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    continue
                try:
                    event = json.loads(decoded)
                    redacted = redact_value(event)
                    events.append(redacted)
                    # Extract from the redacted event so secrets echoed back by
                    # the model never reach the parsed report text.
                    text_fragments.extend(extract_strings(redacted))
                    if on_progress:
                        await on_progress("opencode_event", _progress_payload(redacted))
                except json.JSONDecodeError:
                    text_fragments.append(decoded)
                    if on_progress:
                        await on_progress("opencode_text", {"summary": redact_text(decoded)[:500]})

        async def consume_stderr() -> None:
            assert process.stderr is not None
            while line := await process.stderr.readline():
                decoded = redact_text(line.decode("utf-8", errors="replace").strip())
                if decoded:
                    stderr_lines.append(decoded)
                    del stderr_lines[:-50]

        try:
            async with asyncio.timeout(self.timeout_seconds):
                await asyncio.gather(consume_stdout(), consume_stderr(), process.wait())
        except TimeoutError:
            await self.cancel(job_id)
            return InspectionOutcome(
                report=None,
                raw_events=events,
                stderr_tail="\n".join(stderr_lines[-20:]),
                error=f"Inspection timed out after {self.timeout_seconds} seconds",
            )
        finally:
            self._running.pop(job_id, None)

        parsed = parse_report_text("\n".join(text_fragments))
        if parsed.report:
            redact_report_text_fields(parsed.report)
        if parsed.report and parsed.report.project_id != project.id:
            parsed.report = None
            parsed.error = "Inspection report project_id does not match the requested project"
        if parsed.report and parsed.report.workspace_fingerprint != baseline.workspace_fingerprint:
            parsed.report = None
            parsed.error = "Inspection report workspace fingerprint does not match the baseline"

        return InspectionOutcome(
            report=parsed.report,
            raw_events=events,
            stderr_tail="\n".join(stderr_lines[-20:]),
            exit_code=process.returncode,
            error=parsed.error if process.returncode == 0 else f"OpenCode exited with {process.returncode}",
            warnings=parsed.warnings,
        )

    async def cancel(self, job_id: str) -> bool:
        process = self._running.get(job_id)
        if not process or process.returncode is not None:
            return False
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
            await asyncio.wait_for(process.wait(), timeout=7)
        except (ProcessLookupError, TimeoutError):
            _terminate_process_tree(process.pid)
        return True

    def _isolated_environment(self, project: Project) -> dict[str, str]:
        workspace = Path(project.path).resolve(strict=False).as_posix()
        workspace_pattern = f"{workspace}/**"
        # Read is scoped to the workspace only. Sensitive patterns are repeated
        # inside the workspace with more specific globs so they take precedence
        # over the workspace allow rule regardless of matcher specificity order.
        read_permission: dict[str, str] = {"*": "deny", workspace_pattern: "allow"}
        for pattern in SENSITIVE_READ_DENY_PATTERNS:
            read_permission[f"{workspace}/{pattern}"] = "deny"
            read_permission[f"{workspace}/**/{pattern}"] = "deny"
        permission = {
            "*": "deny",
            "read": read_permission,
            "glob": {"*": "deny", workspace_pattern: "allow"},
            "grep": {"*": "deny", workspace_pattern: "allow"},
            "list": {"*": "deny", workspace_pattern: "allow"},
            "edit": "deny",
            "task": "deny",
            "external_directory": {"*": "deny", workspace_pattern: "allow"},
            "todowrite": "deny",
            "webfetch": "deny",
            "websearch": "deny",
            "lsp": "deny",
            "skill": "deny",
            "question": "deny",
            "doom_loop": "deny",
            # Sidecar already supplies VCS/test facts. Disabling Bash avoids wildcard
            # command-policy bypasses through shell metacharacters.
            "bash": "deny",
        }
        config = {
            "$schema": "https://opencode.ai/config.json",
            "share": "disabled",
            "autoupdate": False,
            "snapshot": False,
            "subagent_depth": 0,
            "instructions": [],
            "mcp": {},
            "plugin": [],
            "formatter": False,
            "lsp": False,
            "permission": permission,
            "agent": {
                "idlerdream-inspector": {
                    "description": "Read-only project status inspector for IdlerDream",
                    "mode": "primary",
                    "steps": 100,
                    "permission": permission,
                }
            },
        }
        return {
            "OPENCODE_CONFIG_DIR": str(self.config_dir),
            "HOME": str(self.isolated_home),
            "USERPROFILE": str(self.isolated_home),
            "XDG_CONFIG_HOME": str(self.isolated_home / "config"),
            "XDG_DATA_HOME": str(self.isolated_home / "data"),
            "XDG_CACHE_HOME": str(self.isolated_home / "cache"),
            "OPENCODE_CONFIG_CONTENT": json.dumps(config, separators=(",", ":")),
            "OPENCODE_PERMISSION": json.dumps(permission, separators=(",", ":")),
            "OPENCODE_DISABLE_CLAUDE_CODE": "1",
            "OPENCODE_DISABLE_DEFAULT_PLUGINS": "1",
            "OPENCODE_DISABLE_LSP_DOWNLOAD": "1",
            "OPENCODE_DISABLE_AUTOUPDATE": "1",
            "OPENCODE_AUTO_SHARE": "false",
            "OPENCODE_CLIENT": "idlerdream",
        }


class MockInspectorAdapter:
    async def version(self) -> str:
        return "mock-1.0"

    def available(self) -> bool:
        return True

    async def inspect(self, job_id: str, project: Project, baseline: FactBaseline, on_progress: ProgressCallback | None = None) -> InspectionOutcome:
        for stage in ("project_structure", "vcs", "tests", "analysis"):
            if on_progress:
                await on_progress("mock_stage", {"stage": stage})
            await asyncio.sleep(0.12)
        failed = baseline.tests.status == "failed"
        from ..models import CoreStatus, EvidenceKind, EvidenceRef, NextAction, NextActor
        report = InspectionReport(
            project_id=project.id,
            workspace_fingerprint=baseline.workspace_fingerprint,
            core_status=CoreStatus.BLOCKED if failed else CoreStatus.IN_PROGRESS,
            phase="testing" if baseline.tests.status != "not_found" else "development",
            summary="Tests contain deterministic failures that require attention." if failed else "The workspace is active and no deterministic blocker was found.",
            next_action=NextAction(actor=NextActor.AGENT, action="Fix the failing tests shown in the latest test report." if failed else "Continue the current implementation and produce a fresh test result."),
            confidence=0.86 if failed else 0.68,
            facts=baseline.deterministic_evidence,
            inferences=[EvidenceRef(kind=EvidenceKind.MODEL, summary="Mock semantic interpretation for the development vertical slice.", deterministic=False)],
            analysis_version={"adapter": "mock-1.0", "prompt": "idlerdream-v1"},
        )
        return InspectionOutcome(report=report, raw_events=[{"type": "mock.complete"}])

    async def cancel(self, job_id: str) -> bool:
        return True


def _progress_payload(event: dict) -> dict:
    strings = extract_strings(event)
    summary = redact_text(strings[-1])[:500] if strings else "OpenCode event received"
    return {"summary": summary, "event_type": str(event.get("type", "unknown"))}


def _terminate_process_tree(pid: int) -> None:
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except psutil.Error:
                pass
        _, alive = psutil.wait_procs(children, timeout=3)
        for child in alive:
            try:
                child.kill()
            except psutil.Error:
                pass
        try:
            parent.kill()
        except psutil.Error:
            pass
    except psutil.Error:
        return
