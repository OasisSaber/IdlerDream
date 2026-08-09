# IdlerDream v0.1 Release Readiness — live status

Updated: 2026-08-08
Branch: `fix/inspection-real-machine-reliability`

Plan: `docs/RELEASE_READINESS_PLAN.md` (asset-pack gates). Every claim below
points to `docs/VALIDATION_REPORT.md` or `docs/INSPECTION_COMPATIBILITY.md`.

## Gate A — focused automated checks: PASS

```text
python -m pytest apps/sidecar/tests/test_report_parser.py
  apps/sidecar/tests/test_workspace_snapshot.py
  apps/sidecar/tests/test_opencode_policy.py
  apps/sidecar/tests/test_partial_report_state.py
  apps/sidecar/tests/test_security.py      -> 34 passed
python -m compileall -q apps/sidecar/idlerdream  -> ok
npm run typecheck                          -> ok
```

Full suite: `python -m pytest apps/sidecar/tests` → 101 passed, 1 skipped
(off-Windows TCP fallback; head `6d026fe`, 2026-08-08 — prior 97 at `590fa5b`).

## Gate B — full repository CI: PARTIAL

- Sidecar suite: passed (101; 1 skipped — off-Windows TCP fallback).
- Ruff: passed — `apps/sidecar` is clean (all baseline findings fixed).
- TypeScript: passed.
- Electron build: `npm run build` → win-unpacked generated.
- Packaged Sidecar smoke test: passed locally (2026-08-06) — PyInstaller exe
  built via `launcher.py`, `/health` 200, `/api/v1/projects` 200, no-token 401,
  and included in win-unpacked.
- NSIS installer: builds locally (231 MB; no Authenticode certificate
  configured — the previous “signed” claim was removed in the CR21-08 doc
  sync); clean-VM install/uninstall smoke test blocked (CR-24).

## Gate C — OpenCode compatibility: PASS

OpenCode 1.18.12 + `opencode-go/deepseek-v4-flash` on Windows 11:

```text
ExitCode = 0, OrdinarySourceRead = True, SensitiveContentAbsent = True,
SnapshotUnmodified = True, PolicyPassed = True
```

Evidence and adapter changes: `docs/INSPECTION_COMPATIBILITY.md`.

## Gate D — 10-run stability: PASS

10/10 valid or partial reports, identity/fingerprint correct, workspace
unchanged, next action available or explicitly unavailable.

## Gate E — real project matrix: PASS

small Git project / medium repo / hostile fixture / spaces + Chinese paths /
non-Git directory all produced valid reports with no secret leak or workspace
modification.

## Gate F — UI quality: NEARLY COMPLETE

- Preview and desktop mock renderer: axe-core 4 audit with wcag2a/2aa/21aa +
  best-practice → 0 violations in light and dark (21/31 checks pass per page).
- Keyboard-only walk: all primary controls reachable in a stable Tab cycle.
- Component tests (vitest + Testing Library): 9 passed — reliability card
  full/partial/failed, six-warning cap, long Chinese warning, panel stage
  mapping, budget ceilings, warning status and cancel action.
- Screenshots: 4 sizes × light/dark + reduced-motion, and app-level
  dashboard/full/partial/failed states at 1440×900 in light and dark
  (`output/playwright/`).
- Remaining: real Windows High Contrast screenshots and screen-reader spot
  checks require a system High Contrast session.

## Release decision

**Do not create `v0.1.0-rc.1` yet.** Gate F is pending and Gate B is partial
(Sidecar PyInstaller/NSIS are CR-24). Issues #19/#20 now have passing
real-machine evidence, but closing them and opening the PR is an external
action that requires the user's authorization.

## CodeReview follow-up (2026-08-08) — CR21-01 … CR21-10

Applied on branch `fix/inspection-real-machine-reliability` (head `590fa5b`)
via the PR #21 review-fix package. 30 edits across 9 files plus 2 new files
(`inspection/run_profile.py`, `tests/test_codereview_regressions.py`).

| Finding | Status | Evidence |
|---|---|---|
| CR21-01 root `opencode.json(c)` in snapshot | Resolved | excluded, classified `agent_control_file`; regression test |
| CR21-02 concurrent shared OpenCode HOME | Resolved | per-job `OpenCodeRunProfile` (HOME/XDG/config) + cleanup; regression test |
| CR21-03 model-declared deterministic facts | Resolved | prompt requires `facts: []`; parser demotes every model fact to `kind=model`, `deterministic=false`; regression test |
| CR21-04 `schema_version` invented by normalizer | Resolved | now required, `Literal[1]`; only `schemaVersion` alias allowed; regression tests |
| CR21-05 snapshot file budget mismatch | Resolved | `SnapshotPolicy.max_files` 200 → 40; regression test |
| CR21-06 Windows CTRL_BREAK constant | Resolved | `subprocess.CREATE_NEW_PROCESS_GROUP`; `OSError` → process-tree fallback |
| CR21-07 UI tests not in CI | Resolved | `.github/workflows/ci.yml` runs `npm run test:ui` before typecheck |
| CR21-08 docs inaccurate | Resolved (this file + README + VALIDATION_REPORT + IMPLEMENTATION_PROGRESS + INSPECTION_ARCHITECTURE) | stale test counts replaced, “signed” claims removed (no Authenticode certificate configured), 40-file budget documented |
| CR21-09 Restricted mode copied source bodies | Resolved | restricted allowlist (README/root docs/`docs/*.md|txt|rst`); source bodies excluded with `restricted_permission`; regression test |
| CR21-10 hardcoded secrets in ordinary source | Resolved | local high-confidence scan; matching files excluded with `secret_content`; regression test |

Automated gates re-run on 2026-08-08 (Windows, Python 3.14.6 / Node 24.17.0):

```text
python -m pytest apps/sidecar/tests                -> 101 passed, 1 skipped (head 6d026fe; prior 97 at 590fa5b)
python -m ruff check apps/sidecar/...              -> All checks passed
python -m compileall -q apps/sidecar/idlerdream    -> ok
python scripts/verify_assets.py                    -> asset verification passed
npm run test:ui                                    -> 9 passed
npm run typecheck                                  -> ok
npm run build                                      -> exit 0 (win-unpacked)
```

Real-machine revalidation was executed on 2026-08-08 and passed: read-only
policy probe (OpenCode 1.18.12, marker read, no sensitive content, snapshot
unchanged), 10/10 stability, two-provider concurrent isolation (each profile's
`auth.json` holds exactly one provider), CTRL_BREAK cancellation, and 2-second
timeout cleanup — no leftover profiles/snapshots on any path.
