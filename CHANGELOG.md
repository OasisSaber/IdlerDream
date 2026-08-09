# Changelog

All notable changes to IdlerDream are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — inspection reliability (PR #21, branch `fix/inspection-real-machine-reliability`)

- Filtered physical workspace snapshot for inspection: sensitive/control-file
  exclusion, 40-file / 200 KiB / 2 MiB budgets, before/after fingerprint.
- OpenCode real-machine reliability: provider-auth isolation, configured-model
  resolution, npm-shim executable resolution, assistant-text-only report
  extraction (OpenCode 1.18.12 verified, Gates C/D/E).
- Report normalization with `full` / `partial` / `failed` quality, deterministic
  identity checks (project ID, workspace fingerprint, required `schema_version`),
  partial confidence cap and parse diagnostics.
- Per-job isolated OpenCode run profile (HOME/USERPROFILE/XDG/OPENCODE_CONFIG_DIR,
  single-provider `auth.json`) with cleanup on success, failure, cancel and timeout.
- Restricted inspection privacy boundary: only README/root docs/`docs/*.{md,txt,rst}`
  enter the model snapshot; source bodies are never copied.
- Model-supplied facts are always demoted to `kind=model`, `deterministic=false`
  (prompt requires `facts: []`).
- High-confidence hardcoded secret-content guard: matching files are excluded
  from the snapshot before model exposure without recording their content.
- Snapshot file budget aligned to the frozen v0.1 contract (40 files).
- Windows process cancellation correction: `CREATE_NEW_PROCESS_GROUP` +
  CTRL_BREAK with process-tree fallback (`subprocess.CREATE_NEW_PROCESS_GROUP`).
- Reliability UI: full/partial/failed inspection states, honest budget ceilings,
  snapshot-isolation strip, warnings surface.
- UI test suite (`npm run test:ui`, vitest + Testing Library) added to GitHub
  Actions CI (CR21-07).

### Remaining work merged before the v0.1.0 tag is cut

The v0.1.0 release is **not yet tagged**. The following items are required before
the tag and GitHub release can be executed:

- [CR-19] Raw-report storage: weekly compaction and Windows DPAPI end-to-end validation (#6)
- [CR-20] Monitoring architecture that meets the stated 50-project target (#7)
- [CR-21] Windows process association and resource sampling production validation (#8)
- [CR-22] Control-pipe authorization: current-user-only ACLs and negative tests (#9)
- [CR-24 remainder] Clean Windows VM pass: tray lifecycle and Sidecar crash recovery

## [0.1.0] - 2026-08-03 (pending tag)

IdlerDream initial release — a Windows local-first desktop dashboard for observing
multiple development workspaces and local coding Agents. The v0.1 slice covers
manual one-project registration and inspection; the full acceptance checklist and
the remaining code-review findings (CR-19 through CR-24) must pass before the
binary release is executed. See `docs/RELEASE_CHECKLIST.md` for the go/no-go gates.

### Added

- Electron + React + TypeScript desktop shell: dashboard, project detail, onboarding,
  settings, system tray, single instance, hide-to-tray and full quit lifecycle.
- Read-only HTTP API and WebSocket event stream with random per-launch read tokens
  (`X-IdlerDream-Read-Token` header / `token` query parameter).
- Private Windows Named Pipe control channel with an Electron Main command allowlist
  and payload validation; project add/discover/remove/restore/purge and
  inspection start/cancel are supported.
- Two-stage project removal: recycle-bin style `removed_at`, restore and purge
  commands; workspace directories are never deleted (CR-14).
- Functional onboarding and settings flows backed by typed IPC: native directory
  picker, project add, bulk discovery, recycle-bin management (CR-15).
- Sidecar: project registration/discovery, Git/JJ facts, test-report discovery
  (JUnit/pytest, newest-first with supported counters), file fingerprint and
  classification, Windows Agent process tree/resource sampling, workspace fingerprint.
- Evidence-priority state merger (`unknown/not_started/in_progress/waiting_user/
  waiting_external/blocked/conflict/completed`), freshness handling, partial success.
- Constrained OpenCode inspection adapter: isolated HOME/USERPROFILE/XDG and working
  directory, read-only permission policy (no Bash), noninteractive JSON event stream,
  redaction, report validation and project/fingerprint identity checks (CR-01, CR-02,
  CR-12).
- Weekly JSONL snapshot storage with startup reconciliation that rebuilds missing
  SQLite index rows (CR-18); SQLite materialized current state.
- Encrypted raw-report storage interface (Windows DPAPI path pending per CR-19).
- Versioned TypeScript protocol package (`@idlerdream/protocol`) and report JSON Schema.
- Sidecar unit test suite; asset verification script; CI for Sidecar tests, frontend
  typecheck/build, packaged-exe smoke test and NSIS installer smoke test.
- Committed `package-lock.json` for reproducible installs (CR-23).
- PyInstaller launcher (`launcher.py` + committed spec) so the packaged Sidecar exe
  starts correctly (CR-24 progress).
- NSIS per-user installer with install/uninstall smoke test automation
  (`scripts/smoke-installer.ps1`, CR-24 progress).
- Mock mode is explicit and build-time only (`VITE_USE_MOCKS=1`); normal builds never
  fabricate project state (CR-03).

### Fixed

- OpenCode Bash permission patterns removed; inspection uses `read`/`list`/`glob`/`grep`
  only (CR-01).
- Repository instructions can no longer influence the inspector; OpenCode runs from an
  isolated directory with isolated environment (CR-02).
- Read-only HTTP/WebSocket endpoints now require a per-launch random read token (CR-04).
- Renderer could issue arbitrary control command strings; Electron Main now enforces a
  fixed allowlist (CR-05).
- Sidecar restart loop capped at three attempts per rolling minute; connection failures
  surface in the UI (CR-06).
- Single-instance lock acquired before application initialization (CR-07).
- Automatic inspection no longer drops newer events; pending targets are replaceable (CR-08).
- One collector failure no longer aborts the whole fact baseline; collectors degrade
  independently (CR-09).
- Newest unsupported JSON report can no longer hide a valid JUnit report (CR-10).
- Discovery now evaluates the selected root directory itself, not only nested
  candidates (CR-11).
- Inspection report identity is verified against `project_id` and
  `workspace_fingerprint` before merging (CR-12).
- Product naming consistently renamed to **IdlerDream** across packages, env vars,
  pipe name, data directory, design system and docs (CR-13).
- `changed_paths` renamed to `considered_paths` in the protocol and UI wording
  ("关注文件") so it no longer claims recent modification (CR-17).

### Changed

- Electron dependency bumped 37.10.3 → 39.8.5 (#14).
- Protocol and UI wording reflect `considered_paths` instead of `changed_paths` (CR-17).
- CI installs the Sidecar from `apps/sidecar` so the editable install resolves correctly.

### Security

- Read token per launch; control token never exposed to ordinary web content.
- Renderer is context-isolated with sandbox enabled, no Node integration.
- Sensitive file paths and file types hard-blocked; token/credential redaction in logs
  and inspection output.
- Project content is treated as untrusted data; workspace directories are never written
  to by IdlerDream.

## Comparison / release notes

Full release notes for v0.1.0: `docs/RELEASE_NOTES_v0.1.0.md`.

Go/no-go gates and exact release commands: `docs/RELEASE_CHECKLIST.md`.
