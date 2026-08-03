# Development Agent Asset Manifest

This document tells the implementation Agent what is already usable and what still requires production work.

## 1. Assets ready to reuse

### Shared protocol

- `packages/protocol/src/index.ts`
- `packages/protocol/report-schema.json`

Use these as the TypeScript public contract. Keep values aligned with Python Pydantic models.

### Python data models and merge logic

- `apps/sidecar/idlerdream/models.py`
- `apps/sidecar/idlerdream/state/merger.py`
- tests in `apps/sidecar/tests/`

Do not replace the fixed core status enum with free-form model output.

### Deterministic collectors

- `collectors/vcs.py`
- `collectors/tests.py`
- `collectors/files.py`
- `collectors/processes.py`

These are implementation-grade starting points, but Windows process working-directory detection and true watcher scheduling still need hardening.

### Inspector adapter

- `inspection/opencode.py`
- `inspection/prompt.py`
- `inspection/report_parser.py`

The adapter already builds an isolated configuration, streams JSON events, redacts output and parses the report. It must be verified against the exact installed OpenCode version and Windows Job Object behavior.

### Storage

- `database.py`
- `storage/snapshots.py`
- `storage/raw_reports.py`

Weekly JSONL and indexes are implemented as a foundation. Production encrypted raw-report storage needs Windows DPAPI integration and per-report key deletion.

### Desktop frontend

- `apps/desktop/src/`
- `apps/desktop/electron/`
- `apps/desktop/src/styles.css`
- `preview/apple-dashboard.html`

The React UI is a high-fidelity functional shell with mock-data fallback. Replace placeholders with real control commands; keep the design system and accessibility rules.

### Design and specifications

- `design-system/idlerdream/MASTER.md`
- `docs/PRODUCT_SPEC.md`
- `docs/ARCHITECTURE.md`
- `docs/FRONTEND_SPEC.md`
- `docs/TEST_PLAN.md`
- `docs/IMPLEMENTATION_PLAN.md`

## 2. Production gaps by priority

### P0 — validate dangerous assumptions

1. Verify OpenCode noninteractive JSON output on Windows.
2. Verify project config/plugins/instructions cannot override the injected read-only policy.
3. Implement and test Windows Job Object cancellation for the full child process tree.
4. Confirm workspace before/after fingerprint invalidation.
5. Implement real Windows Credential Manager and DPAPI paths.

### P1 — complete the first vertical slice

1. Real project add command from UI.
2. Persist project and display through the read API.
3. Collect facts for one workspace.
4. Run a manual OpenCode inspection.
5. Merge one report.
6. Append one snapshot.
7. Render the updated state in the Dashboard.

### P2 — monitoring loop

1. Watchdog-based file events on Windows.
2. Debounce and aggregate.
3. VCS status throttling.
4. Test report change detection.
5. Agent exit detection.
6. Three-minute stability window and 30-minute automatic cooldown.

### P3 — desktop hardening

1. Real tray icon and application icon.
2. Sidecar startup retry limits and health UX.
3. Protocol mismatch handling.
4. Single-instance and stale-lock recovery tests.
5. NSIS clean install/uninstall tests.

### P4 — accessibility and visual QA

1. Add automated axe tests.
2. Add component tests.
3. Verify keyboard flows.
4. Capture required screenshot sizes.
5. Verify light, dark, reduced motion and forced colors.

## 3. Code that is intentionally not included

Do not add these to v0.1:

- global inspection and cross-project prioritization
- custom inspector CLI
- browser access
- notifications
- Agent task sending or control
- Web Agent or conversation-log parsing
- weighted progress percentages
- multi-worktree project model
- backup/restore and auto-update

## 4. Agent completion evidence

Every implementation task must provide:

- changed files
- test command and output summary
- screenshots for UI changes
- security implications
- remaining limitations
- no-scope-expansion statement
