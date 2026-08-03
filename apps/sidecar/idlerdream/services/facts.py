from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from ..collectors.files import WorkspaceDigest, collect_workspace_digest
from ..collectors.processes import ProcessCollector
from ..collectors.tests import collect_test_facts
from ..collectors.vcs import collect_vcs_facts
from ..models import (
    AgentProcess,
    EvidenceKind,
    EvidenceRef,
    FactBaseline,
    Project,
    TestFacts,
    VcsFacts,
)


class FactService:
    def __init__(self, process_collector: ProcessCollector, ignore_dirs: set[str]) -> None:
        self.process_collector = process_collector
        self.ignore_dirs = ignore_dirs

    async def collect(self, project: Project) -> FactBaseline:
        """Full deterministic baseline, used by the inspection service.

        Collectors degrade independently: a VCS, test or process failure is
        reported as a warning while the rest of the baseline still assembles.
        A workspace fingerprint failure remains fatal because consistency
        cannot otherwise be established.
        """
        results = await asyncio.gather(
            asyncio.to_thread(self.collect_reconcile_sync, project),
            asyncio.to_thread(self.collect_digest_sync, project),
            asyncio.to_thread(self.collect_processes_sync, project),
            return_exceptions=True,
        )
        reconcile_result, digest_result, agents_result = results
        warnings: list[str] = []

        if isinstance(reconcile_result, BaseException):
            warnings.append(f"VCS/test reconciliation failed: {reconcile_result}")
            vcs = VcsFacts(
                kind="none",
                command_error=str(reconcile_result),
                status_summary="VCS facts unavailable.",
            )
            tests = TestFacts(status="unknown", summary="Test facts unavailable.")
        else:
            vcs, tests = reconcile_result

        if isinstance(digest_result, BaseException):
            raise RuntimeError(  # noqa: TRY004 - gather() returns exception instances
                f"Workspace fingerprint collection failed: {digest_result}"
            ) from digest_result
        digest: WorkspaceDigest = digest_result

        if isinstance(agents_result, BaseException):
            warnings.append(f"Process collector failed: {agents_result}")
            agents: list[AgentProcess] = []
        else:
            agents = agents_result

        return self.assemble_baseline(
            project,
            agents=agents,
            digest=digest,
            vcs=vcs,
            tests=tests,
            warnings=warnings,
        )

    def collect_reconcile_sync(self, project: Project) -> tuple[VcsFacts, TestFacts]:
        """VCS and test report facts for the medium-frequency scheduler."""
        try:
            vcs = collect_vcs_facts(project.path)
        except Exception as exc:  # noqa: BLE001 - degrade independently per CR-09
            vcs = VcsFacts(
                kind="none",
                command_error=str(exc),
                status_summary="VCS facts unavailable.",
            )
        try:
            tests = collect_test_facts(project.path)
        except Exception as exc:  # noqa: BLE001 - degrade independently per CR-09
            tests = TestFacts(status="unknown", summary=f"Test facts unavailable: {exc}")
        return vcs, tests

    def collect_processes_sync(self, project: Project) -> list[AgentProcess]:
        """Agent process sample for the fast scheduler."""
        return self.process_collector.collect_for_project(project)

    def collect_digest_sync(self, project: Project) -> WorkspaceDigest:
        """Deep workspace fingerprint for the slow scheduler."""
        return collect_workspace_digest(project.path, ignore_dirs=self.ignore_dirs)

    def assemble_baseline(
        self,
        project: Project,
        *,
        agents: list[AgentProcess] | None = None,
        digest: WorkspaceDigest,
        vcs: VcsFacts | None = None,
        tests: TestFacts | None = None,
        observed_at: datetime | None = None,
        warnings: list[str] | None = None,
    ) -> FactBaseline:
        """Assemble a FactBaseline from independently collected pieces.

        The monitoring service calls this whenever one of its schedulers
        updates a piece, so the API always sees a coherent baseline instead of
        a half-collected snapshot.
        """
        agents = agents or []
        vcs = vcs or VcsFacts()
        tests = tests or TestFacts(status="not_found")
        warnings = list(warnings or [])
        warnings.extend(digest.warnings)

        evidence = [
            EvidenceRef(
                kind=EvidenceKind.VCS,
                summary=vcs.status_summary or "No VCS changes detected.",
                deterministic=True,
            )
        ]
        if tests.status not in {"not_found", "unknown"}:
            evidence.append(
                EvidenceRef(
                    kind=EvidenceKind.TEST,
                    summary=tests.summary,
                    path=tests.source_path,
                    deterministic=True,
                )
            )
        if agents:
            evidence.append(
                EvidenceRef(
                    kind=EvidenceKind.PROCESS,
                    summary=f"{len(agents)} associated Agent process(es) currently running.",
                    deterministic=True,
                )
            )

        return FactBaseline(
            project_id=project.id,
            workspace_path=str(Path(project.path).resolve(strict=False)),
            workspace_fingerprint=digest.fingerprint,
            vcs=vcs,
            tests=tests,
            considered_paths=digest.considered_paths,
            file_count_considered=digest.considered_files,
            agents=agents,
            cycle=project.current_cycle,
            deterministic_evidence=evidence,
            warnings=warnings,
            observed_at=observed_at,
        )
