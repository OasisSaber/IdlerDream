from __future__ import annotations

import asyncio
from pathlib import Path

from ..collectors.files import WorkspaceDigest, collect_workspace_digest
from ..collectors.processes import ProcessCollector
from ..collectors.tests import collect_test_facts
from ..collectors.vcs import collect_vcs_facts
from ..models import AgentProcess, EvidenceKind, EvidenceRef, FactBaseline, Project, TestFacts, VcsFacts


class FactService:
    def __init__(self, process_collector: ProcessCollector, ignore_dirs: set[str]) -> None:
        self.process_collector = process_collector
        self.ignore_dirs = ignore_dirs

    async def collect(self, project: Project) -> FactBaseline:
        results = await asyncio.gather(
            asyncio.to_thread(collect_vcs_facts, project.path),
            asyncio.to_thread(collect_workspace_digest, project.path, ignore_dirs=self.ignore_dirs),
            asyncio.to_thread(collect_test_facts, project.path),
            asyncio.to_thread(self.process_collector.collect_for_project, project),
            return_exceptions=True,
        )
        warnings: list[str] = []

        vcs_result, digest_result, tests_result, agents_result = results
        if isinstance(vcs_result, BaseException):
            warnings.append(f"VCS collector failed: {vcs_result}")
            vcs = VcsFacts(kind="none", command_error=str(vcs_result), status_summary="VCS facts unavailable.")
        else:
            vcs = vcs_result

        if isinstance(digest_result, BaseException):
            raise RuntimeError(f"Workspace fingerprint collection failed: {digest_result}") from digest_result
        digest: WorkspaceDigest = digest_result
        warnings.extend(digest.warnings)

        if isinstance(tests_result, BaseException):
            warnings.append(f"Test collector failed: {tests_result}")
            tests = TestFacts(status="unknown", summary="Test facts unavailable.")
        else:
            tests = tests_result

        if isinstance(agents_result, BaseException):
            warnings.append(f"Process collector failed: {agents_result}")
            agents: list[AgentProcess] = []
        else:
            agents = agents_result

        evidence = [
            EvidenceRef(
                kind=EvidenceKind.VCS,
                summary=vcs.status_summary or "No VCS changes detected.",
                deterministic=True,
            )
        ]
        if tests.status not in {"not_found", "unknown"}:
            evidence.append(EvidenceRef(kind=EvidenceKind.TEST, summary=tests.summary, path=tests.source_path, deterministic=True))
        if agents:
            evidence.append(EvidenceRef(kind=EvidenceKind.PROCESS, summary=f"{len(agents)} associated Agent process(es) currently running.", deterministic=True))

        return FactBaseline(
            project_id=project.id,
            workspace_path=str(Path(project.path).resolve(strict=False)),
            workspace_fingerprint=digest.fingerprint,
            vcs=vcs,
            tests=tests,
            changed_paths=digest.changed_paths,
            file_count_considered=digest.considered_files,
            agents=agents,
            cycle=project.current_cycle,
            deterministic_evidence=evidence,
            warnings=warnings,
        )
