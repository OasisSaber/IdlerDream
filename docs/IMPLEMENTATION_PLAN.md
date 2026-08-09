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

## Milestone status — 2026-08-09

Evidence: `docs/VALIDATION_REPORT.md`, `docs/INSPECTION_COMPATIBILITY.md`,
`docs/RELEASE_READINESS.md`, `docs/CODE_REVIEW.md` (status update).

| Milestone | Status | Notes |
|---|---|---|
| M0 repository health | Done | Sidecar tests/typecheck/build/CI all green; Ruff clean (2026-08-08) |
| M1 one-project manual inspection slice | Done | add/list/facts/UI done; real OpenCode inspection works (Gate C) and merges reports |
| M2 read-only policy proof | Done (2026-08-06) | filtered-snapshot isolation + compatibility probe passed on OpenCode 1.18.12; re-verified 2026-08-09 (head 4406176+) |
| M3 continuous local monitoring | Done (CR-20) | process/reconcile/deep schedulers split, bounded concurrency, Watchdog file events, cooldown/dedup covered by tests (2026-08-09) |
| M4 simplified automatic inspection | Done (CR-20) | triggers (agent_exit, test_result_changed), stable window, cooldown, fingerprint dedup, no auto retry — tests added 2026-08-09 |
| M5 data resilience | Done (CR-19) | weekly JSONL + SQLite rebuild + raw encryption + DPAPI + compaction + corrupted-container quarantine; Windows DPAPI tests added 2026-08-09 |
| M6 desktop and installer | Partial | tray/single-instance/restart limits exist; crash-recovery gate unit-tested (CR-24); NSIS clean-VM install/uninstall smoke covered by CI; interactive tray lifecycle pending final clean-VM session |
| M7 UI quality gate | Nearly complete | axe 0 violations light/dark, keyboard walk, component tests, screenshots done; system High Contrast screenshots pending final session |
