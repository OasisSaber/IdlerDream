# v0.1 Implementation Plan

## Principle

Build vertical slices before infrastructure breadth. Do not begin with all collectors, all settings or the installer.

## Milestone 0 — repository health

- install JS/Python dependencies
- run Sidecar unit tests
- run TypeScript typecheck
- validate protocol Schema synchronization
- add CI for test/typecheck only

Exit: clean commands documented and reproducible.

## Milestone 1 — one-project manual inspection slice

- add a workspace through control API
- store and list it
- collect Git/JJ/test/file facts
- show it in the React UI
- run mock inspector first
- merge report, append snapshot and update materialized state
- replace mock inspector with OpenCode after policy tests

Exit: one real workspace produces a visible verified state and next action.

## Milestone 2 — read-only policy proof

- isolated OpenCode config directory
- pure mode and project configuration isolation
- hard blocked sensitive paths
- read-only Bash patterns
- malicious repository fixture
- before/after fingerprint
- cancellation and process tree cleanup

Exit: compatibility test passes on supported OpenCode version.

## Milestone 3 — continuous local monitoring

- file watcher and fallback scanner
- Git/JJ throttling
- test report watcher
- Agent process sampling
- project association confirmation
- resource aggregation and 7-day session retention

Exit: Dashboard updates live without deep inspection.

## Milestone 4 — simplified automatic inspection

- Agent exit trigger
- test result trigger
- stable window
- cooldown and input-hash deduplication
- no automatic retry

Exit: stable event causes one inspection and no duplicate state.

## Milestone 5 — data resilience

- weekly JSONL replay
- SQLite rebuild command
- snapshot deduplication
- raw event encryption with DPAPI
- retention and cryptographic deletion
- corrupted-week isolation

Exit: delete SQLite and rebuild current state from snapshots in a test profile.

## Milestone 6 — desktop and installer

- tray icon/menu
- startup preference
- Sidecar restart policy
- read-only recovery UI
- NSIS per-user installer
- uninstall data choice

Exit: clean Windows VM install and uninstallation pass.

## Milestone 7 — UI quality gate

- replace remaining mock-only controls
- complete onboarding forms
- keyboard and screen-reader labels
- visual regression screenshots
- dark/light/reduced-motion/high-contrast tests

Exit: design-system checklist passes.

## Milestone status — 2026-08-06

Evidence: `docs/VALIDATION_REPORT.md`, `docs/INSPECTION_COMPATIBILITY.md`,
`docs/RELEASE_READINESS.md`, `docs/CODE_REVIEW.md` (status update).

| Milestone | Status | Notes |
|---|---|---|
| M0 repository health | Partial | Sidecar tests/typecheck/build pass; Ruff repository-wide findings remain (baseline style debt) |
| M1 one-project manual inspection slice | Core slice done | add/list/facts/UI done; real OpenCode inspection works (Gate C) and merges reports |
| M2 read-only policy proof | Done (2026-08-06) | filtered-snapshot isolation + compatibility probe passed on OpenCode 1.18.12 |
| M3 continuous local monitoring | Partial | monitoring loop exists; Watchdog split and Windows process association pending |
| M4 simplified automatic inspection | Partial | triggers exist; stability/cooldown tests pending production hardening |
| M5 data resilience | Partial | weekly JSONL + SQLite rebuild + raw encryption exist; DPAPI/compaction pending |
| M6 desktop and installer | Partial | tray/single-instance/restart limits exist; NSIS clean-VM install/uninstall pending (CR-24) |
| M7 UI quality gate | Pending | reliability UI implemented and type-checked; visual regression screenshots pending (Gate F) |
