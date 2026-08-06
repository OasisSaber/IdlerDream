# IdlerDream v0.1 Release Readiness — live status

Updated: 2026-08-06
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

Full suite: `python -m pytest apps/sidecar/tests` → 63 passed.

## Gate B — full repository CI: PARTIAL

- Sidecar suite: passed (63).
- Ruff: passed — `apps/sidecar` is clean (all baseline findings fixed).
- TypeScript: passed.
- Electron build: `npm run build` → win-unpacked generated.
- Packaged Sidecar smoke test: passed locally (2026-08-06) — PyInstaller exe
  built via `launcher.py`, `/health` 200, `/api/v1/projects` 200, no-token 401,
  and included in win-unpacked.
- NSIS installer: builds locally (231 MB, signed); clean-VM install/uninstall
  smoke test blocked (CR-24).

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
