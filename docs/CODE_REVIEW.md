# IdlerDream v0.1 Asset Code Review

Review date: 2026-08-03

Scope: the complete implementation asset bundle, including Electron/React, Python Sidecar, OpenCode inspector, protocol, storage, tests, packaging, prompts and design documentation.

## Executive assessment

The package is a credible **development vertical slice**, not a production-ready v0.1 release. The domain model and product boundaries are unusually well specified, the Sidecar tests are useful, and the frontend gives the implementation Agent a concrete target. The original bundle nevertheless had several security and correctness defects that would make a packaged build misleading or unsafe.

This reviewed package fixes the highest-impact issues that can be corrected without redesigning the product. Remaining gaps are explicitly assigned to the implementation Agent.

## Fixed in this reviewed package

### CR-01 — OpenCode Bash permission patterns were unsafe

**Severity:** Critical  
**Original location:** `apps/sidecar/idlerdream/inspection/opencode.py`

The original permission map allowed patterns such as `git diff*` and `git status*`. OpenCode Bash permissions match parsed command strings with wildcards, so an allow pattern with an unrestricted suffix is not a reliable shell-security boundary.

**Resolution:** Bash is now denied completely. Git/JJ/test facts are supplied by the Sidecar baseline. OpenCode uses only `read`, `list`, `glob` and `grep` for semantic inspection.

### CR-02 — Repository instructions could affect the inspector

**Severity:** Critical  
**Original location:** `apps/sidecar/idlerdream/inspection/opencode.py`

Launching OpenCode with the project as `cwd`/`--dir` allowed project-level `AGENTS.md` and `.opencode` configuration to enter the normal OpenCode configuration path. A prompt telling the model to treat these files as untrusted was not sufficient isolation.

**Resolution:** OpenCode now runs from an isolated directory with isolated `HOME`, `USERPROFILE` and XDG directories. The real workspace is exposed only through a constrained external-directory read permission. The adapter still requires a Windows integration test before production release.

### CR-03 — Production UI silently switched to mock project data

**Severity:** Critical  
**Original location:** `apps/desktop/src/lib/api.ts`

A Sidecar startup delay, crash or authentication failure silently enabled mock mode. This could present fabricated project status as real monitoring data.

**Resolution:** Mock mode is explicit and build-time only (`VITE_USE_MOCKS=1`). Normal builds display a clear Sidecar connection error and never synthesize project state.

### CR-04 — Read-only HTTP and WebSocket endpoints had no authentication

**Severity:** High  
**Original location:** `apps/sidecar/idlerdream/api.py`

Binding to localhost does not make project names, paths, deadlines and status summaries non-sensitive. Any local process and some browser-origin attacks could attempt to read the API.

**Resolution:** Electron generates a random read token, injects it into the Sidecar process and supplies it to the isolated renderer through preload. HTTP requests require `X-IdlerDream-Read-Token`; WebSocket connections require the token query parameter.

### CR-05 — Renderer could issue arbitrary control command strings

**Severity:** High  
**Original location:** `apps/desktop/electron/main.ts`

The renderer-to-main IPC accepted any command name and forwarded it to the privileged Sidecar channel.

**Resolution:** Electron Main now enforces a fixed allowlist and validates payload shape before forwarding.

### CR-06 — Sidecar restart loop was unbounded

**Severity:** High  
**Original location:** `apps/desktop/electron/main.ts`

A persistent startup failure could restart the Sidecar indefinitely.

**Resolution:** restart attempts are capped at three per rolling minute. The renderer exposes the connection failure instead of hiding it.

### CR-07 — Electron single-instance lock was requested too late

**Severity:** Medium  
**Original location:** `apps/desktop/electron/main.ts`

The lock was requested only after `whenReady`, leaving a race in which multiple processes could begin startup.

**Resolution:** the lock is now acquired before application initialization.

### CR-08 — Automatic inspection could lose a newer event

**Severity:** High  
**Original location:** `apps/sidecar/idlerdream/services/monitoring.py`

When a stable-window task was already pending, later meaningful changes were discarded. If the fingerprint changed, the original task exited and no replacement was guaranteed.

**Resolution:** pending targets are replaceable. The stable-window task follows the newest reason/fingerprint instead of dropping it.

### CR-09 — One collector failure aborted the entire fact baseline

**Severity:** High  
**Original location:** `apps/sidecar/idlerdream/services/facts.py`

`asyncio.gather` failed as a unit, contradicting the product requirement for partial success.

**Resolution:** VCS, test and process collector failures now degrade independently and emit warnings. Workspace fingerprint failure remains fatal because consistency cannot otherwise be established.

### CR-10 — A newer unsupported JSON report could hide a valid JUnit report

**Severity:** Medium  
**Original location:** `apps/sidecar/idlerdream/collectors/tests.py`

The collector selected the newest candidate before determining whether it contained supported test counters. A new coverage file could mask a slightly older valid JUnit result.

**Resolution:** candidates are tried newest-first until a reliable passed/failed result is found. A regression test was added.

### CR-11 — Discovery skipped the selected root directory

**Severity:** Medium  
**Original location:** `apps/sidecar/idlerdream/services/projects.py`

Selecting a repository root for discovery returned only nested candidates.

**Resolution:** the root itself is now evaluated. A regression test was added.

### CR-12 — Inspection report identity was not verified by the adapter

**Severity:** High  
**Original location:** `apps/sidecar/idlerdream/inspection/opencode.py`

A valid-looking report for a different project or baseline could reach the state merger.

**Resolution:** the adapter rejects mismatched `project_id` and `workspace_fingerprint`.

### CR-13 — Naming was inconsistent after the product decision

**Severity:** Medium

**Resolution:** source package, npm packages, app ID, environment variables, pipe name, data directory, design-system path, prompts, documentation and UI branding are now consistently named **IdlerDream**.

## Remaining findings for the implementation Agent

### CR-14 — Project removal is destructive instead of two-stage

**Severity:** High  
**Location:** `apps/sidecar/idlerdream/services/projects.py`, `database.py`

`project.remove` directly deletes the project and cascades current-state/snapshot index rows. The frozen design requires a 30-day recycle bin and an explicit permanent-delete action.

**Required work:** add `removed_at`, list/restore/purge operations, migration, UI and tests. Never delete the actual workspace.

### CR-15 — Onboarding and settings are visual prototypes, not functional flows

**Severity:** High  
**Location:** `apps/desktop/src/pages/OnboardingPage.tsx`, `SettingsPage.tsx`

OpenCode detection, Credential Manager storage, compatibility testing, directory picker, project creation and settings persistence are currently simulated.

**Required work:** implement typed IPC operations and corresponding Sidecar services. Do not retain API keys in React state longer than needed or write them to logs/localStorage.

### CR-16 — Frontend does not consume the WebSocket event stream

**Severity:** Medium  
**Location:** `apps/desktop/src/App.tsx`, `apps/desktop/src/lib/api.ts`

The renderer polls every five seconds. This works for a prototype but defeats the event-bus architecture and increases state latency.

**Required work:** connect to authenticated `/api/v1/events`, update affected entities incrementally, and retain slow reconciliation polling as a fallback.

### CR-17 — `changed_paths` is semantically incorrect

**Severity:** High  
**Location:** `collectors/files.py`, protocol model and UI

The field currently contains up to 200 candidate files included in the workspace fingerprint, not files that changed since the prior baseline. Treating it as recent activity produces false status descriptions.

**Required work:** rename it to `considered_paths` or implement a true baseline diff. This reviewed package changes the visible wording to “关注文件” to avoid claiming recent modification, but the protocol should still be corrected before release.

### CR-18 — Snapshot file append and SQLite index are not one atomic transaction

**Severity:** High  
**Location:** `storage/snapshots.py`

A crash after the JSONL append but before the SQLite insert leaves an orphan record; the reverse recovery path is also incomplete.

**Required work:** add startup reconciliation using `snapshot_id`, truncate incomplete trailing records, rebuild missing index rows, and test power-loss boundaries.

### CR-19 — Raw-report storage lacks weekly compaction and Windows end-to-end validation

**Severity:** Medium  
**Location:** `storage/raw_reports.py`

Key destruction is implemented, but dead ciphertext remains indefinitely and DPAPI behavior is not exercised in the Linux test environment.

**Required work:** implement idle compaction, corrupted-container quarantine and Windows DPAPI integration tests. The non-Windows development fallback must never be shipped as the Windows production path.

### CR-20 — Monitoring architecture will not meet the stated 50-project target

**Severity:** High  
**Location:** `services/monitoring.py`, `collectors/files.py`

The current loop fingerprints projects sequentially every 30 seconds. Large repositories can delay every other project.

**Required work:** split process sampling, file events, VCS/test reconciliation and deep fingerprinting into separate bounded schedulers; use Watchdog on Windows and low-frequency recovery scans.

### CR-21 — Windows process association and resource sampling need production validation

**Severity:** High  
**Location:** `collectors/processes.py`

Current association is a useful heuristic, but Windows process CWD access, terminal process trees, first-sample CPU semantics and exited-session aggregation need real-system tests.

**Required work:** add fixtures and Windows integration tests for OpenCode, Codex, Claude Code, Windows Terminal and VS Code integrated terminals.

### CR-22 — Control-pipe authorization relies on token secrecy without explicit Windows ACL tests

**Severity:** High  
**Location:** `control.py`, Electron Main

The named-pipe token is strong, but the production security posture also depends on pipe ACLs and process inheritance behavior.

**Required work:** create the pipe with current-user-only ACLs and add negative tests from another user/session where practical.

### CR-23 — No dependency lockfiles or supply-chain policy

**Severity:** Medium

The package specifies ranges but includes no npm lockfile and no Python lock/constraints file.

**Required work:** generate and commit lockfiles in a normal internet-connected environment; configure Dependabot/Renovate only after the first reproducible build.

### CR-24 — Build and installer are not yet proven

**Severity:** High

The asset environment could not complete npm dependency installation, Electron compilation or NSIS packaging. Python tests and static validation pass, but this is not equivalent to a Windows release test.

**Required work:** run the release checklist on a clean Windows 10/11 VM, including install, first-run, tray lifecycle, uninstall-with-data-preservation and Sidecar crash recovery.

**Progress:** CI now automates the release acceptance baseline on a clean `windows-latest` runner (`.github/workflows/ci.yml` job `windows-installer`): it builds the Sidecar executable with PyInstaller, packages the NSIS per-user installer with electron-builder and runs `scripts/smoke-installer.ps1`, which silently installs, verifies the installed layout (main exe, bundled Sidecar, uninstaller, Start Menu/Desktop shortcuts, HKCU Uninstall key), launches the packaged app and confirms it stays alive (first-run + packaged Sidecar start), then silently uninstalls and verifies removal while preserving user data. A clean-VM tray lifecycle and Sidecar crash-recovery pass are still required before release.

## Validation performed after review

- Python Sidecar unit tests: **21 passed**
- Python compilation: passed
- JSON asset parsing: passed
- Asset presence verification: passed
- Residual old product names: removed from text assets
- Git repository bootstrap assets: added

Frontend dependency installation and packaged Electron/NSIS build remain environment-limited and must be completed by the implementation Agent.

## Release recommendation

**Do not publish a binary release from this asset package.** Use it as the initial private repository baseline. The first implementation milestone should resolve CR-14 through CR-18 and produce a reproducible Windows development build; the second should focus on CR-19 through CR-24 and clean-VM release readiness.

## Status update — 2026-08-06 (inspection reliability)

Implemented and verified on branch `fix/inspection-real-machine-reliability`
(commits `b09a263`, `f2fd883`, `8ce40d9`). Evidence: `docs/VALIDATION_REPORT.md`,
`docs/INSPECTION_COMPATIBILITY.md`, `docs/RELEASE_READINESS.md`.

| Item | Status | Evidence |
|---|---|---|
| #19 OpenCode cannot read under old policy | Code complete; real-machine Gate C passed | OpenCode 1.18.12 + `opencode-go/deepseek-v4-flash`, read OK, secrets absent, writes denied, snapshot unchanged |
| #20 strict parser fails on model variance | Code complete; real-machine Gates D/E passed | 10/10 stability; 5/5 project matrix; JSON5 repair + assistant-text event filtering |
| CR-14 two-stage project removal | Implemented (2026-08-04) | recycle bin, restore/purge, expiry, migration tests |
| CR-15 onboarding/settings flows | Implemented (2026-08-12) | typed `inspector.*` IPC + Sidecar `InspectorService` (config persistence, Credential Manager, connectivity/compatibility tests, deep-inspection gate); onboarding steps 1–2 and Settings functional; tests added; real-machine Credential Manager/connectivity run pending |
| CR-16 WebSocket event stream | Implemented (2026-08-04) | authenticated `/api/v1/events`, reconnect, tests |
| CR-17 `considered_paths` | Implemented (2026-08-04) | protocol/collectors/UI renamed; tests |
| CR-18 snapshot append/index atomicity | Implemented (2026-08-04) | startup reconciliation + tests |
| CR-19 raw-report compaction/DPAPI Windows tests | Done (2026-08-09) | DPAPI round-trip, wrapped-key non-plaintext, expiry-undecryptable + end-to-end tests; compaction/quarantine already implemented |
| CR-20 monitoring scheduler split | Done (2026-08-09) | three schedulers + Watchdog + bounded concurrency; cooldown/dedup/pending-replacement/restart tests added |
| CR-21 Windows process association validation | Done (2026-08-09) | fixtures + real OpenCode binary (`opencode serve`) association test |
| CR-22 control-pipe ACL tests | Done (2026-08-09) | current-user-only DACL; malformed/non-dict/unknown-command rejection tests; cross-user documented as needing a second logon session |
| CR-23 dependency lockfiles | Partial | npm `package-lock.json` committed; Python lock and Dependabot pending |
| CR-24 build/installer proof | Partial (2026-08-09) | Sidecar PyInstaller exe built and smoke-tested locally; NSIS install/uninstall/first-run smoke green on CI `windows-installer`; crash-recovery restart gate unit-tested; interactive tray lifecycle pending final clean-VM session |

Issues #19/#20 have passing evidence but are not closed: closing and opening the
PR is an external action requiring user authorization.

## Status update — 2026-08-08 (PR #21 CodeReview follow-up)

A merge-before review of PR #21 (`fix/inspection-real-machine-reliability`,
head `590fa5b`) found ten pre-merge defects (CR21-01 … CR21-10). All were
fixed on the branch and verified by the full automated suite
(`103 passed, 1 skipped` at head `d78b9aa`; ruff clean; `test:ui` 9 passed; typecheck and build
pass). Evidence: `docs/VALIDATION_REPORT.md`, `docs/RELEASE_READINESS.md`.

| Finding | Severity | Resolution |
|---|---|---|
| CR21-01 root `opencode.json(c)` enters snapshot | High / Security | excluded + classified `agent_control_file` |
| CR21-02 concurrent inspections share OpenCode HOME/auth | High / Security + Correctness | per-job ephemeral `OpenCodeRunProfile` (HOME/XDG/config), cleanup on all paths |
| CR21-03 model can declare deterministic facts | High / Trust Boundary | prompt requires `facts: []`; parser demotes every model fact to `kind=model`, `deterministic=false` |
| CR21-04 `schema_version` invented by normalizer | Medium | required core field; only `schemaVersion` alias accepted |
| CR21-05 snapshot budget 200 vs frozen 40 | Medium | `SnapshotPolicy.max_files = 40` |
| CR21-06 Windows CTRL_BREAK constant wrong | Medium | `subprocess.CREATE_NEW_PROCESS_GROUP` + `OSError` tree-kill fallback |
| CR21-07 UI tests absent from CI | Medium | `npm run test:ui` added before typecheck |
| CR21-08 release docs inaccurate | Low | stale test counts replaced; “signed” claims removed (no Authenticode certificate configured); 40-file budget documented |
| CR21-09 Restricted mode copies full source | High / Privacy | allowlist: root README/docs + `docs/*.{md,txt,rst}` only; source bodies excluded (`restricted_permission`) |
| CR21-10 hardcoded secrets in ordinary source | High / Security | local high-confidence scan; matching files excluded (`secret_content`) without recording content |

Remaining before merge: the PR description sync (no product scope was
introduced). Real-machine revalidation passed on 2026-08-08: read-only policy
probe (OpenCode 1.18.12), 10/10 stability, two-provider concurrent isolation,
CTRL_BREAK cancellation and timeout cleanup — evidence in
`docs/VALIDATION_REPORT.md` and `docs/RELEASE_READINESS.md`.
