# Implementation Progress — First Milestone

Date: 2026-08-04
Branch: `main` (working tree)

## Scope

This milestone implements the smallest unfinished P0/P1 vertical-slice task
and the first CODE_REVIEW release milestone (CR-14 through CR-18):

1. **P1.1** — real project add from the UI (Onboarding step 4 and Dashboard).
2. **CR-14** — two-stage project removal with a 30-day recycle bin.
3. **CR-16** — renderer consumes the authenticated WebSocket event stream.
4. **CR-17** — `changed_paths` renamed to `considered_paths` everywhere.
5. **CR-18** — snapshot append/index atomicity with startup reconciliation.

## Implemented

### P1.1 — real project add

- `electron/main.ts`: new `idlerdream:pick-directory` IPC (native folder dialog);
  control allowlist extended with `project.restore`/`project.purge`.
- `electron/preload.ts` + `src/vite-env.d.ts`: typed `pickDirectory()` bridge.
- `src/lib/api.ts`: `addProject`, `discoverProjects`, `pickDirectory`,
  `removeProject`, `restoreProject`, `purgeProject`, `fetchProjects(includeRemoved)`.
- `src/pages/OnboardingPage.tsx`: step 4 now adds the workspace through the
  control channel, reports real errors, and queues the first inspection when
  the "执行首次只读巡检" checkbox is selected.
- `src/components/AddWorkspaceDialog.tsx`: new dialog for the Dashboard
  "添加工作区" button (folder picker + add + error surface).
- `src/App.tsx`: `onAdd` opens the dialog; onboarding completion reloads data.
- Tests: `apps/sidecar/tests/test_control.py` (add persists + publishes event,
  rejects missing directory, rejects unknown commands).

### CR-14 — two-stage removal

- `models.py`: `Project.removed_at`.
- `database.py`: `SCHEMA_VERSION = 2`, idempotent `_migrate` (v1 → v2 adds
  `removed_at`), `soft_delete_project`, `restore_project`, `list_projects(include_removed)`.
- `services/projects.py`: `remove` (soft), `restore`, `purge`, `list_removed`,
  `purge_expired(30d)`; `add` rejects a path still in the recycle bin.
- `api.py`: `project.remove` returns the removed project; new `project.restore`
  and `project.purge` commands; read API supports `include_removed`.
- `main.py`: startup `purge_expired()`.
- UI: Project page "移除工作区" (with confirm), Settings → 数据与保留 shows
  the recycle bin with restore / permanent-delete (with confirm).
- Tests: soft delete/restore/purge lifecycle, double-remove rejection,
  expired purge, workspace never deleted, recycle-bin add rejection,
  v1 → v2 migration.

### CR-16 — WebSocket event stream

- `src/lib/api.ts`: `connectEvents()` — authenticated `ws://…/api/v1/events`,
  exponential reconnect (1 s → 15 s cap), disconnect function.
- `src/App.tsx`: consumes `project.added/removed/restored/purged`,
  `inspection.job` (focused reload) and `project.runtime.updated` (in-place
  runtime refresh); polling reduced to 15 s as reconciliation fallback.
- Tests: `apps/sidecar/tests/test_events_api.py` (token rejection with 4401,
  event streaming over WebSocket).

### CR-17 — `considered_paths`

- `models.py`: `FactBaseline.considered_paths` (200-cap validator);
- `collectors/files.py` `WorkspaceDigest.considered_paths`;
- `services/facts.py`, `packages/protocol/src/index.ts` (and `dist`),
  `src/data/mock.ts`, `src/pages/ProjectPage.tsx` (基线关注文件 wording).
- Tests: collector assertion updated; full-tree grep shows no `changed_paths`.

### CR-18 — snapshot atomicity + startup reconciliation

- `database.py`: `snapshot_index_exists`.
- `storage/snapshots.py`: `reconcile()` — truncates incomplete trailing JSONL
  records, rebuilds missing index rows keyed by `snapshot_id`.
- `main.py`: startup `snapshots.reconcile()`.
- Tests: partial-tail truncation, missing-index rebuild.

## Files changed

- `apps/desktop/electron/main.ts`, `electron/preload.ts`, `src/App.tsx`,
  `src/lib/api.ts`, `src/data/mock.ts`, `src/vite-env.d.ts`, `src/styles.css`,
  `src/components/AddWorkspaceDialog.tsx` (new),
  `src/pages/OnboardingPage.tsx`, `src/pages/ProjectPage.tsx`,
  `src/pages/SettingsPage.tsx`, `package.json` (pin electron 37.10.3)
- `apps/sidecar/idlerdream/{api,main,database,models}.py`,
  `services/{projects,facts}.py`, `collectors/files.py`, `storage/snapshots.py`
- `apps/sidecar/tests/{test_control.py (new), test_events_api.py (new),
  test_projects.py, test_storage.py, test_collectors.py}`
- `packages/protocol/src/index.ts`
- `package-lock.json` (new), `.gitignore` (dist-electron),
  `docs/VALIDATION_REPORT.md`

## Validation

```text
python -m pytest apps/sidecar/tests        → 35 passed
python scripts/verify_assets.py            → asset verification passed
npm install                                → ok (lockfile committed)
npm run typecheck                          → passed (protocol/desktop/electron)
npm run build                              → vite + tsc + electron-builder win-unpacked ok
```

## Security / data impact

- Control channel: no new privileges; commands remain allowlisted in Electron
  Main; all new commands (`project.restore`, `project.purge`) require the
  named-pipe token.
- `project.purge` permanently deletes the project row (cascades
  current-state/index rows); weekly JSONL history files are intentionally
  left untouched.
- The workspace directory is never written to or deleted.
- Schema migration is additive (`removed_at` column), idempotent, and covered
  by a v1→v2 migration test.

## Remaining gaps (unchanged)

- P0 Windows validation: OpenCode noninteractive JSON output, Job Object
  process-tree cancellation, Credential Manager/DPAPI integration, read-only
  policy inducement test — require the packaged Windows environment.
- CR-15 (full onboarding/settings flows): steps 0–2 of onboarding remain
  visual prototypes (OpenCode detection, model credentials, isolation test).
- CR-19–CR-24: raw-report compaction/DPAPI tests, monitoring scheduler
  split, control-pipe ACL tests, dependency policy, Sidecar PyInstaller
  packaging + NSIS clean-VM test.
- UI screenshots at required sizes were not captured (no GUI session);
  visual QA belongs to Milestone 7.

## Scope check

No frozen v0.1 exclusion was introduced: no Agent task dispatch/control,
no cross-project inspection, no browser access, no notifications, no
backup/restore, no weighted progress percentages.

---

# Implementation Progress — Inspection Reliability Overlay (#19/#20)

Date: 2026-08-06
Branch: `fix/inspection-real-machine-reliability`

## Scope

Integrated the reviewed `IdlerDream-inspection-reliability-assets` pack
(`C:\Users\Oasis\Downloads\IdlerDream-inspection-reliability-assets.zip`) as an
overlay on top of the first-milestone baseline (commit `b09a263`). The pack
targets release blockers:

- **#19** — OpenCode is isolated but cannot read the workspace under the old
  path-scoped deny/allow policy.
- **#20** — Model output variance can cause a useful report to fail strict
  parsing.

## Applied (20 replacement files)

Sidecar:

- `inspection/workspace_snapshot.py` (new) — filtered physical snapshot,
  sensitive/control-file exclusion, 40-file / 200 KiB / 2 MiB budgets.
- `inspection/opencode.py` — OpenCode runs only inside the snapshot with
  read/list/glob/grep allow and all mutation/delegation tools denied.
- `inspection/prompt.py` — snapshot-aware prompt, workspace paths removed.
- `inspection/report_parser.py` — deterministic normalization, identity checks,
  parse diagnostics, full/partial/failed quality.
- `models.py`, `state/merger.py`, `services/inspections.py`, `security/redaction.py`
  — quality fields, partial confidence cap (0.75), raw-report diagnostics and
  report text redaction.

Frontend/protocol:

- `InspectionReliabilityCard.tsx/.css` (new), `InspectionPanel.tsx/.css` (new),
  `ProjectPage.tsx`, `data/mock.ts`, `packages/protocol/src/index.ts` —
  full/partial/failed reliability UI, honest budget ceilings, snapshot-isolation
  strip, quality/warnings/budget protocol fields.

Tests: `test_report_parser.py`, `test_security.py` replaced; `test_opencode_policy.py`,
`test_workspace_snapshot.py`, `test_partial_report_state.py` added.

Review notes:

- Replacements already contained the first-milestone changes (`removed_at`,
  `considered_paths`), so no milestone work was lost.
- One lint fix was made to the pack code: removed an unused
  `InspectionPermission` import in `workspace_snapshot.py`.
- `packages/protocol/dist` was rebuilt so the desktop typecheck consumes the new
  `inspection_quality`/`warnings`/`budget` types.
- Pack support assets were copied into the repository: `scripts/test-opencode-readonly-policy.ps1`,
  `fixtures/opencode-policy/`, `docs/INSPECTION_ARCHITECTURE.md`,
  `docs/REPORT_NORMALIZATION_SPEC.md`, `docs/UI_UX_PRO_MAX_RELIABILITY_SPEC.md`,
  `docs/RELEASE_READINESS_PLAN.md`, `docs/COMPATIBILITY_MATRIX.md`,
  `preview/inspection-reliability.html`.
  The fixture `.env` is not committed (repository `.gitignore` ignores `.env`);
  the probe script regenerates the fake credential marker at runtime.

## Validation (Gate A)

```text
python -m pytest apps/sidecar/tests                    -> 63 passed
python -m pytest <5 focused reliability test files>    -> 34 passed
python -m compileall -q apps/sidecar/idlerdream        -> ok
python scripts/verify_assets.py                        -> asset verification passed
python scripts/verify_asset_pack.py                    -> 43 files verified, 13 Python parsed
npm run typecheck                                      -> passed (protocol + desktop + electron)
npm run build                                          -> vite + electron-builder win-unpacked ok
```

Ruff: the overlay files are clean after the import fix. The repository still
has baseline-wide style findings (54: E501 line length, I001 import sorting,
UP042 str-enum pattern). This was not a pack gate; `docs/VALIDATION_REPORT.md`
records it explicitly.

## Real-machine OpenCode probe (Gates C/D/E) — verified after adapter fixes

Initially run on 2026-08-06 with:

- OpenCode 1.18.12 (`C:\Users\Oasis\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe`)
- model `opencode-go/deepseek-v4-flash`
- equivalent of `scripts/test-opencode-readonly-policy.ps1` (PowerShell 7 not
  installed; a byte-equivalent Python probe was used)

First result (before fixes):

```text
ExitCode                  = 1
OrdinarySourceRead        = False
SensitiveContentAbsent    = True
SnapshotUnmodified        = True
PolicyPassed              = False
error                     = UnknownError: Unexpected server error (ref err_619b6c59)
```

Diagnosis and fixes (all implemented in this branch):

1. `ProviderModelNotFoundError: opencode-go/deepseek-v4-flash` under isolation —
   the provider auth entry was not visible. `prepare_provider_auth` now copies
   exactly one provider entry into the isolated profile.
2. Configured default model was not resolved under isolation (silent fallback
   to OpenCode's built-in `big-pickle`). `default_opencode_model` now reads the
   user's config and `--model` is passed explicitly.
3. `opencode` resolved to an npm `.cmd` shim that `CreateProcess` cannot
   launch. `_resolve_executable` follows the shim to the real `.exe`.
4. Report parsing failed on long-context runs because tool outputs (rendered
   file contents, minified bundles) polluted candidate extraction, and JSON5
   variance (unquoted keys / single quotes / trailing commas) could fail.
   `_assistant_text_fragments` collects only assistant text and
   `_repair_json5_lite` deterministically repairs JSON5 formatting as
   `partial`.

Final evidence:

```text
Gate C:  ExitCode = 0, OrdinarySourceRead = True, SensitiveContentAbsent = True,
         SnapshotUnmodified = True, PolicyPassed = True
Gate D:  10/10 valid or partial reports, identity/fingerprint correct,
         workspace unchanged
Gate E:  5/5 matrix cases valid, no secret leak, workspace unchanged
```

Full detail: `docs/INSPECTION_COMPATIBILITY.md`.

## Status

- Code integration: complete.
- Gate A: passed.
- Gate B: partial (Ruff debt remains; packaged Sidecar smoke passed locally;
  NSIS clean-VM install/uninstall remains CR-24).
- Gate C: **passed** (OpenCode 1.18.12 + `opencode-go/deepseek-v4-flash`).
- Gate D: **passed** (10/10).
- Gate E: **passed** (5/5 matrix).
- Gate F: nearly complete (preview + app axe 0 violations in light/dark,
  keyboard walk passed, screenshots captured; system High Contrast session
  still pending).
- Issues #19/#20: evidence complete; closing the issues and opening the PR is
  an external action that requires user authorization.
- CR21-01 … CR21-10 (PR #21 CodeReview follow-up, 2026-08-08): resolved in
  code — root `opencode.json(c)` excluded, 40-file budget, Restricted-mode
  doc allowlist, secret-content guard, per-inspection Run Profile, model-facts
  demotion, required `schema_version`, Windows process-group fix, `test:ui` in
  CI. Suite now `103 passed, 1 skipped` (head d78b9aa); real-machine revalidation passed
  (probe, 10/10 stability, two-provider concurrency, cancel/timeout cleanup).

## Scope check

No frozen v0.1 exclusion was introduced: no Agent task dispatch/control, no
cross-project inspection, no browser access, no notifications, no backup/restore,
no weighted progress percentages.
