from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

import psutil

from ..models import FactBaseline, InspectionReport, Project
from ..security.redaction import redact_report_text_fields, redact_text, redact_value
from .prompt import PROMPT_VERSION, build_inspection_prompt
from .report_parser import NORMALIZER_VERSION, extract_strings, parse_report_text
from .run_profile import OpenCodeRunProfile
from .workspace_snapshot import (
    SNAPSHOT_POLICY_VERSION,
    InspectionWorkspaceBuilder,
    SnapshotPolicy,
)

ProgressCallback = Callable[[str, dict], Awaitable[None]]
PERMISSION_POLICY_VERSION = "idlerdream-opencode-snapshot-policy-v2"


def _strip_jsonc_comments(text: str) -> str:
    """Remove // and /* */ comments while leaving string contents intact."""
    out: list[str] = []
    index = 0
    length = len(text)
    in_string = False
    escaped = False
    while index < length:
        char = text[index]
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "/":
            while index < length and text[index] != "\n":
                index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "*":
            index += 2
            while index + 1 < length and not (text[index] == "*" and text[index + 1] == "/"):
                index += 1
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _load_jsonc(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    try:
        data = json.loads(_strip_jsonc_comments(text))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def default_opencode_model(config_dir: Path | None = None) -> str | None:
    """Resolve the user's default OpenCode model from their real config.

    The isolated inspector profile cannot load the user's global OpenCode
    config, so the adapter must read the configured model explicitly and pass
    ``--model``. Config files are checked in OpenCode's load order and a later
    explicit value wins.
    """
    if config_dir is not None:
        directories = [Path(config_dir)]
    else:
        directories = []
        xdg_config = os.getenv("XDG_CONFIG_HOME")
        directories.append(
            Path(xdg_config).resolve(strict=False) / "opencode"
            if xdg_config
            else Path.home() / ".config" / "opencode"
        )
        extra_config = os.getenv("OPENCODE_CONFIG_DIR")
        if extra_config:
            directories.append(Path(extra_config).resolve(strict=False))

    model: str | None = None
    for directory in directories:
        for name in ("config.json", "opencode.json", "opencode.jsonc"):
            data = _load_jsonc(directory / name)
            if data is None:
                continue
            value = data.get("model")
            if isinstance(value, str) and value.strip():
                model = value.strip()
    return model


def real_opencode_auth_path() -> Path:
    data_home = os.getenv("XDG_DATA_HOME")
    base = Path(data_home).resolve(strict=False) if data_home else Path.home() / ".local" / "share"
    return base / "opencode" / "auth.json"


def prepare_provider_auth(
    model: str | None,
    isolated_home: Path,
    real_auth_path: Path,
) -> list[str]:
    """Copy only the selected provider's credential into the isolated profile.

    OpenCode resolves a provider only when its auth entry is visible in the
    isolated ``XDG_DATA_HOME``. To keep exposure minimal, exactly one provider
    entry from the user's real ``auth.json`` is written into the isolated data
    directory; all other providers and project content stay outside.
    """
    warnings: list[str] = []
    if not model or "/" not in model:
        return warnings
    provider = model.split("/", 1)[0]
    auth_path = Path(real_auth_path)
    if not auth_path.is_file():
        warnings.append(
            f"OpenCode auth store not found at {auth_path}; provider {provider!r} may fail."
        )
        return warnings
    try:
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        warnings.append(f"OpenCode auth store could not be parsed: {auth_path}")
        return warnings
    entry = auth.get(provider) if isinstance(auth, dict) else None
    if entry is None:
        warnings.append(f"No stored credential for OpenCode provider {provider!r}.")
        return warnings

    target = Path(isolated_home) / "data" / "opencode" / "auth.json"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps({provider: entry}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        try:
            target.chmod(0o600)
        except OSError:
            pass
    except OSError as exc:
        warnings.append(
            f"OpenCode provider credential could not be staged in the ephemeral profile: {exc}"
        )
    return warnings


def _resolve_executable(name: str) -> str:
    """Resolve a CLI name to a directly spawnable executable.

    On Windows, npm-installed CLIs often expose only ``.cmd``/``.ps1`` shims,
    which ``CreateProcess`` cannot launch directly. Follow the standard npm
    shim to the real ``.exe`` target when one is present.
    """
    found = shutil.which(name)
    if not found:
        return name
    path = Path(found)
    if path.suffix.lower() not in {".cmd", ".bat"}:
        return found
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return found
    match = re.search(r'"([^"]*\\node_modules\\[^"]+\.exe)"', text)
    if not match:
        return found
    target = match.group(1)
    target = (
        target.replace("%~dp0", str(path.parent))
        .replace("%dp0%", str(path.parent))
        .replace("%~dp0%", str(path.parent))
    )
    if "%" in target:
        return found
    resolved = Path(target)
    return str(resolved) if resolved.is_file() else found


def _assistant_text_fragments(event: dict) -> list[str]:
    """Collect only model-generated assistant text for the report parser.

    OpenCode ``tool_use`` events carry rendered file contents (including line
    numbers and minified bundles). Feeding those into the report parser pollutes
    candidate extraction, so only events that represent assistant text are
    collected.
    """
    event_type = str(event.get("type", ""))
    part = event.get("part")
    if event_type in {"text", "message", "message.part"}:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            return [part["text"]]
        if isinstance(event.get("text"), str):
            return [event["text"]]
        if isinstance(event.get("content"), str):
            return [event["content"]]
    if (
        isinstance(part, dict)
        and part.get("type") == "text"
        and isinstance(part.get("text"), str)
    ):
        return [part["text"]]
    return []


@dataclass(slots=True)
class InspectionOutcome:
    report: InspectionReport | None
    raw_events: list[dict] = field(default_factory=list)
    stderr_tail: str = ""
    exit_code: int | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    diagnostics: dict[str, object] = field(default_factory=dict)
    snapshot: dict[str, object] = field(default_factory=dict)


class OpenCodeAdapter:
    """Run OpenCode against a filtered inspection snapshot, never the real repo.

    The snapshot removes sensitive files and agent-control files such as
    ``AGENTS.md`` and ``.opencode``. OpenCode receives read/list/glob/grep access
    only inside that temporary directory. All mutation, shell, network and
    delegation tools remain denied. The Sidecar still fingerprints the real
    workspace before and after inspection.
    """

    def __init__(
        self,
        executable: str = "opencode",
        *,
        model: str | None = None,
        timeout_seconds: int = 600,
        config_dir: Path | None = None,
        snapshot_policy: SnapshotPolicy | None = None,
        user_config_dir: Path | None = None,
        user_auth_path: Path | None = None,
    ) -> None:
        self.executable = executable
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.config_dir = (
            config_dir or Path.home() / ".idlerdream" / "opencode-inspector"
        ).resolve(strict=False)
        self.user_config_dir = (
            Path(user_config_dir).resolve(strict=False) if user_config_dir else None
        )
        self.user_auth_path = (
            Path(user_auth_path).resolve(strict=False) if user_auth_path else None
        )
        self.run_root = self.config_dir / "run-root"
        self.isolated_home = self.config_dir / "isolated-home"
        self.snapshot_builder = InspectionWorkspaceBuilder(
            self.config_dir / "inspection-snapshots", policy=snapshot_policy
        )
        for directory in (self.config_dir, self.run_root, self.isolated_home):
            directory.mkdir(parents=True, exist_ok=True)
        self._running: dict[str, asyncio.subprocess.Process] = {}
        self._version_cache: str | None = None
        self._resolved_executable: str | None = None

    def _executable_path(self) -> str:
        if self._resolved_executable is None:
            self._resolved_executable = _resolve_executable(self.executable)
        return self._resolved_executable

    def resolve_model(self) -> str | None:
        if self.model:
            return self.model
        return default_opencode_model(self.user_config_dir)

    def available(self) -> bool:
        return shutil.which(self.executable) is not None

    async def version(self) -> str | None:
        if self._version_cache:
            return self._version_cache
        if not self.available():
            return None
        process = await asyncio.create_subprocess_exec(
            self._executable_path(),
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        self._version_cache = stdout.decode("utf-8", errors="replace").strip() or None
        return self._version_cache

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
            return InspectionOutcome(
                report=None, error="Project is configured for local-only monitoring"
            )

        run_profile = OpenCodeRunProfile.create(self.config_dir, job_id)
        try:
            model = self.resolve_model()
            auth_warnings = prepare_provider_auth(
                model,
                run_profile.home,
                self.user_auth_path or real_opencode_auth_path(),
            )
            snapshot = self.snapshot_builder.build(
                job_id=job_id,
                project=project,
                baseline=baseline,
            )
        except Exception:
            # Every failure after profile creation must remove the staged
            # credentials and runtime state, not defer to garbage collection.
            run_profile.cleanup()
            raise
        if on_progress:
            await on_progress(
                "snapshot_ready",
                {
                    "stage": "snapshot_ready",
                    "summary": (
                        f"Prepared filtered inspection snapshot: "
                        f"{len(snapshot.copied_files)} files"
                    ),
                },
            )

        prompt = build_inspection_prompt(
            project,
            baseline,
            snapshot_manifest=snapshot.manifest_summary(),
        )
        command = [
            self._executable_path(),
            "--pure",
            "run",
            "--format",
            "json",
            "--agent",
            "idlerdream-inspector",
            "--dir",
            str(snapshot.root),
        ]
        if model:
            command.extend(["--model", model])
        command.append(prompt)

        environment = os.environ.copy()
        environment.update(
            self._isolated_environment(
                isolated_home=run_profile.home,
                profile_config_dir=run_profile.config_dir,
            )
        )
        creation_flags = 0
        if os.name == "nt":
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

        events: list[dict] = []
        text_fragments: list[str] = []
        stderr_lines: list[str] = []
        process: asyncio.subprocess.Process | None = None
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(snapshot.root),
                env=environment,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=creation_flags,
            )
            self._running[job_id] = process

            async def consume_stdout() -> None:
                assert process is not None and process.stdout is not None
                while line := await process.stdout.readline():
                    decoded = line.decode("utf-8", errors="replace").strip()
                    if not decoded:
                        continue
                    try:
                        event = json.loads(decoded)
                        redacted = redact_value(event)
                        events.append(redacted)
                        text_fragments.extend(_assistant_text_fragments(redacted))
                        if on_progress:
                            await on_progress("opencode_event", _progress_payload(redacted))
                    except json.JSONDecodeError:
                        redacted_text = redact_text(decoded)
                        text_fragments.append(redacted_text)
                        if on_progress:
                            await on_progress(
                                "opencode_text", {"summary": redacted_text[:500]}
                            )

            async def consume_stderr() -> None:
                assert process is not None and process.stderr is not None
                while line := await process.stderr.readline():
                    decoded = redact_text(
                        line.decode("utf-8", errors="replace").strip()
                    )
                    if decoded:
                        stderr_lines.append(decoded)
                        del stderr_lines[:-50]

            try:
                async with asyncio.timeout(self.timeout_seconds):
                    await asyncio.gather(
                        consume_stdout(), consume_stderr(), process.wait()
                    )
            except TimeoutError:
                await self.cancel(job_id)
                return InspectionOutcome(
                    report=None,
                    raw_events=events,
                    stderr_tail="\n".join(stderr_lines[-20:]),
                    error=f"Inspection timed out after {self.timeout_seconds} seconds",
                    warnings=[*snapshot.warnings, *auth_warnings],
                    snapshot=snapshot.manifest_summary(),
                )

            parsed = parse_report_text(
                "\n".join(text_fragments),
                expected_project_id=project.id,
                expected_workspace_fingerprint=baseline.workspace_fingerprint,
            )
            report = parsed.report
            if report:
                redact_report_text_fields(report)
                report.analysis_version.update(
                    await self._analysis_version_fingerprint(project, baseline, model=model)
                )

            return InspectionOutcome(
                report=report,
                raw_events=events,
                stderr_tail="\n".join(stderr_lines[-20:]),
                exit_code=process.returncode,
                error=(
                    parsed.error
                    if process.returncode == 0
                    else f"OpenCode exited with {process.returncode}"
                ),
                warnings=list(
                    dict.fromkeys([*snapshot.warnings, *auth_warnings, *parsed.warnings])
                ),
                diagnostics=parsed.diagnostics.model_dump(),
                snapshot=snapshot.manifest_summary(),
            )
        finally:
            self._running.pop(job_id, None)
            if process is not None and process.returncode is None:
                # Exception path (callback/parser failure) must not leak a
                # running OpenCode process: terminate it and wait briefly,
                # falling back to the process-tree kill.
                try:
                    if os.name == "nt":
                        process.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=7)
                except (ProcessLookupError, TimeoutError, OSError):
                    _terminate_process_tree(process.pid)
            snapshot.cleanup()
            run_profile.cleanup()

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
        except (ProcessLookupError, TimeoutError, OSError):
            # CTRL_BREAK can fail when the child did not inherit a console. The
            # Job/process-tree fallback remains the authoritative cancellation.
            _terminate_process_tree(process.pid)
        return True

    def _isolated_environment(
        self,
        project: Project | None = None,
        *,
        isolated_home: Path | None = None,
        profile_config_dir: Path | None = None,
    ) -> dict[str, str]:
        runtime_home = (isolated_home or self.isolated_home).resolve(strict=False)
        runtime_config_dir = (profile_config_dir or self.config_dir).resolve(strict=False)
        for directory in (
            runtime_home,
            runtime_home / "config",
            runtime_home / "data",
            runtime_home / "cache",
            runtime_config_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        permission = {
            # Keep the default deny boundary, but grant the four read-only tools
            # without path globs. The process is physically confined to the
            # filtered snapshot, so the OpenCode 1.18.11 path-shadowing bug is
            # no longer part of the security model.
            "*": "deny",
            "read": "allow",
            "glob": "allow",
            "grep": "allow",
            "list": "allow",
            "external_directory": "deny",
            "edit": "deny",
            "write": "deny",
            "patch": "deny",
            "bash": "deny",
            "task": "deny",
            "todowrite": "deny",
            "webfetch": "deny",
            "websearch": "deny",
            "lsp": "deny",
            "skill": "deny",
            "question": "deny",
            "doom_loop": "deny",
            "share": "deny",
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
            "OPENCODE_CONFIG_DIR": str(runtime_config_dir),
            "HOME": str(runtime_home),
            "USERPROFILE": str(runtime_home),
            "XDG_CONFIG_HOME": str(runtime_home / "config"),
            "XDG_DATA_HOME": str(runtime_home / "data"),
            "XDG_CACHE_HOME": str(runtime_home / "cache"),
            "OPENCODE_CONFIG_CONTENT": json.dumps(config, separators=(",", ":")),
            "OPENCODE_PERMISSION": json.dumps(permission, separators=(",", ":")),
            "OPENCODE_DISABLE_CLAUDE_CODE": "1",
            "OPENCODE_DISABLE_DEFAULT_PLUGINS": "1",
            "OPENCODE_DISABLE_LSP_DOWNLOAD": "1",
            "OPENCODE_DISABLE_AUTOUPDATE": "1",
            "OPENCODE_AUTO_SHARE": "false",
            "OPENCODE_CLIENT": "idlerdream",
        }

    async def _analysis_version_fingerprint(
        self,
        project: Project,
        baseline: FactBaseline,
        *,
        model: str | None = None,
    ) -> dict[str, str]:
        components = {
            "adapter": "opencode-snapshot-v2",
            "opencode": await self.version() or "unknown",
            "model": model or self.model or "configured-default",
            "prompt": PROMPT_VERSION,
            "schema": "1",
            "normalizer": NORMALIZER_VERSION,
            "permission_policy": PERMISSION_POLICY_VERSION,
            "snapshot_policy": SNAPSHOT_POLICY_VERSION,
            "permission_mode": project.inspection_permission.value,
            "workspace_fingerprint": baseline.workspace_fingerprint,
        }
        encoded = json.dumps(components, sort_keys=True, separators=(",", ":")).encode()
        components["fingerprint"] = hashlib.sha256(encoded).hexdigest()
        return components


class MockInspectorAdapter:
    async def version(self) -> str:
        return "mock-2.0"

    def available(self) -> bool:
        return True

    async def inspect(
        self,
        job_id: str,
        project: Project,
        baseline: FactBaseline,
        on_progress: ProgressCallback | None = None,
    ) -> InspectionOutcome:
        for stage in ("project_structure", "vcs", "tests", "analysis"):
            if on_progress:
                await on_progress("mock_stage", {"stage": stage})
            await asyncio.sleep(0.12)
        failed = baseline.tests.status == "failed"
        from ..models import (
            CoreStatus,
            EvidenceKind,
            EvidenceRef,
            NextAction,
            NextActor,
        )

        report = InspectionReport(
            schema_version=1,
            project_id=project.id,
            workspace_fingerprint=baseline.workspace_fingerprint,
            core_status=CoreStatus.BLOCKED if failed else CoreStatus.IN_PROGRESS,
            phase="testing" if baseline.tests.status != "not_found" else "development",
            summary=(
                "Tests contain deterministic failures that require attention."
                if failed
                else "The workspace is active and no deterministic blocker was found."
            ),
            next_action=NextAction(
                actor=NextActor.AGENT,
                action=(
                    "Fix the failing tests shown in the latest test report."
                    if failed
                    else "Continue the current implementation and produce a fresh test result."
                ),
            ),
            confidence=0.86 if failed else 0.68,
            facts=baseline.deterministic_evidence,
            inferences=[
                EvidenceRef(
                    kind=EvidenceKind.MODEL,
                    summary="Mock semantic interpretation for the development vertical slice.",
                    deterministic=False,
                )
            ],
            analysis_version={"adapter": "mock-2.0", "prompt": PROMPT_VERSION},
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
