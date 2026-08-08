# IdlerDream reviewed asset validation

Date: 2026-08-03

## Passed

```text
Python Sidecar tests: 21 passed
Python compilation: passed
Asset verification script: passed
Report Schema JSON parsing: passed
TypeScript/TSX syntax transpilation: 18 files, 0 diagnostics
Residual previous product-name scan: clean
```

Commands:

```powershell
python -m pytest apps/sidecar/tests
python -m compileall -q apps/sidecar/idlerdream
python scripts/verify_assets.py
```

## Implementation milestone validation (2026-08-04)

The first implementation milestone (P1.1 + CR-14/CR-16/CR-17/CR-18) was
completed in a normal internet-connected Windows environment:

```text
Python Sidecar tests: 35 passed (21 baseline + 14 new)
Sidecar control-channel tests: passed (project.add persist/publish, rejects)
Sidecar WebSocket event tests: passed (token rejection, event streaming)
Storage reconcile tests: passed (truncate partial tail, rebuild index)
Project recycle-bin tests: passed (soft delete, restore, purge, expiry, v1→v2 migration)
Asset verification script: passed
TypeScript semantic typecheck: passed (protocol + desktop + electron)
Vite production build + Electron Main compile: passed
electron-builder win-unpacked packaging: passed (unpacked dir generated)
npm package-lock.json: committed
```

Commands:

```powershell
python -m pytest apps/sidecar/tests
python scripts/verify_assets.py
npm install
npm run typecheck
npm run build
```

The `apps/sidecar/dist/idlerdream-sidecar.exe` extraResource is not yet
produced: the Sidecar PyInstaller packaging step is still a release task
(CR-24), so the unpacked Electron app currently starts without the Sidecar
binary when run from the packaged directory.

## Inspection reliability overlay validation (2026-08-06)

The reviewed inspection-reliability overlay (issues #19/#20) was integrated on
branch `fix/inspection-real-machine-reliability` and validated in this Windows
environment:

```text
python -m pytest apps/sidecar/tests                      -> 63 passed
python -m pytest <5 focused reliability test files>      -> 34 passed
python -m compileall -q apps/sidecar/idlerdream          -> passed
python scripts/verify_assets.py                          -> passed
python scripts/verify_asset_pack.py                      -> 43 files, 13 Python parsed
npm run typecheck                                        -> passed (protocol + desktop + electron)
npm run build                                            -> vite + electron-builder win-unpacked passed
```

Packaged Sidecar (2026-08-06, local Windows):

```text
python scripts/build-sidecar.ps1 (PyInstaller 6.21, onefile via launcher.py)
  -> apps/sidecar/dist/idlerdream-sidecar.exe (37 MB)
smoke test: /health 200 (opencode_available=true, version 1.18.12,
            database schema_version=2), /api/v1/projects 200 [], no-token 401
electron-builder win-unpacked now includes resources/sidecar/idlerdream-sidecar.exe
```

The packaged exe uses `launcher.py` as the PyInstaller entry point because
running `idlerdream/main.py` as `__main__` breaks relative imports at runtime.

NSIS installer (2026-08-06, local Windows):

```text
npm run dist -w @idlerdream/desktop
  -> apps/desktop/dist/IdlerDream Setup 0.1.0-dev.exe (231 MB; no Authenticode
     certificate configured — the previous "signed with signtool" claim was
     removed in the CR21-08 doc sync)
```

Clean-VM install/uninstall smoke remains an external CR-24 task.

Application state screenshots (1440×900, light/dark, dashboard + full/partial/
failed reliability card): `output/playwright/ui-app-*`.

Accessibility audit (Gate F, 2026-08-06) — axe-core 4, wcag2a/2aa/21aa +
best-practice:

```text
preview/inspection-reliability.html  light: 0 violations (21 passes)
preview/inspection-reliability.html  dark:  0 violations (21 passes)
desktop mock renderer (dashboard)    light: 0 violations (31 passes)
desktop mock renderer (dashboard)    dark:  0 violations (31 passes)
keyboard walk: all primary controls reachable via Tab in a stable cycle
component tests (vitest + Testing Library): 9 passed
  (reliability card full/partial/failed, six-warning cap, long Chinese warning;
   inspection panel stage mapping, budget ceilings, warning status, cancel)
```

Fixes made to pass the audit: light `--text-tertiary` alpha 0.58→0.74 and dark
0.55→0.62; `.actor--agent` and `.button--primary` small-text colors made
theme-aware (`#0060df`/`#48a9ff` actor, `#0060df`/`#0071e3` primary button);
preview mirror tokens and favicon 404. Token deviations are listed in
`docs/acceptance/INSPECTION_ACCEPTANCE_2026-08-06.md`. Real Windows High
Contrast screenshots still require a system High Contrast session.

Acceptance artifact: `artifacts/acceptance/opencode-policy.txt` (raw redacted
probe event stream from the passing Gate C run).

The 63-test suite includes the first-milestone baseline plus new regression
coverage for filtered snapshots, sensitive/control-file exclusion, OpenCode
dangerous-tool denial, deterministic report normalization, identity mismatch
rejection, partial-report confidence capping and failed-report state
preservation, provider-auth isolation, default-model resolution, npm-shim
executable resolution, JSON5-style report repair and assistant-text event
filtering.

Ruff: not clean repository-wide. The repository carries 54 baseline style
findings (E501/I001/UP042, mostly in files outside this overlay). The overlay
introduced one finding (unused import in `workspace_snapshot.py`) which was
fixed during integration. Ruff cleanliness remains part of Gate B, not a pass
claim in this report.

### Real-machine OpenCode compatibility probe (Gates C/D/E) — verified

Environment: OpenCode 1.18.12, model `opencode-go/deepseek-v4-flash`,
Windows 11 (build 26200). PowerShell 7 is not installed, so the pack's
`test-opencode-readonly-policy.ps1` was executed through an equivalent Python
probe (same snapshot, config, permission map, environment variables and
assertions, plus the adapter's auth-injection mirror).

```text
Gate C probe:   ExitCode = 0, OrdinarySourceRead = True,
                SensitiveContentAbsent = True, SnapshotUnmodified = True,
                PolicyPassed = True
Gate D:         10/10 valid or partial reports, identity/fingerprint correct,
                workspace unchanged
Gate E:         5/5 matrix cases (small Git, medium repo, hostile, spaces +
                Chinese paths, non-Git) valid, no secret leak
```

Real-machine validation found and fixed three adapter defects plus one parser
gap, all recorded in `docs/INSPECTION_COMPATIBILITY.md`:

1. The isolated profile lost the provider auth entry, so OpenCode could not
   resolve `opencode-go` (`ProviderModelNotFoundError`). Fix: copy exactly one
   provider entry into the isolated `data/opencode/auth.json`.
2. The configured default model was not resolved under isolation, so the
   inspector silently used OpenCode's built-in default. Fix: resolve the user's
   config `model` and pass `--model`.
3. `opencode` resolves to an npm `.cmd` shim that `CreateProcess` cannot
   launch. Fix: follow the shim to the real `.exe`.
4. Tool outputs (rendered file contents) polluted report-candidate extraction
   and JSON5-style variance could fail parsing. Fixes: collect only assistant
   text events; deterministically repair JSON5 formatting with a `partial`
   warning.

Per the pack's stop conditions, issues #19/#20 now have passing real-machine
evidence. Closing the issues and opening the PR remains an external action
requiring user authorization. No binary release should be published until
Gate F and CR-24 packaging gates pass.

## Environment-limited

`npm install --ignore-scripts` could not complete in the asset-generation environment because its internal npm mirror returned HTTP 404 for `@types/node`. Consequently, the following were not claimed as passed:

- full TypeScript semantic typecheck;
- Vite production build;
- Electron Main compilation against installed Electron types;
- electron-builder/NSIS packaging;
- clean Windows installation test.

The TypeScript compiler API was still used to syntax-transpile all 18 `.ts`/`.tsx` source files, producing zero syntax diagnostics.

## Windows-only validation still required

- Named Pipe current-user ACL and negative authorization tests;
- Windows Credential Manager integration;
- DPAPI encrypt/decrypt and key-destruction tests;
- Windows Job Object process-tree cancellation;
- OpenCode read-only inducement test against the selected installed version;
- Agent process association in Windows Terminal and VS Code;
- NSIS install, tray lifecycle, uninstall and data-preservation behavior.

See `docs/CODE_REVIEW.md` for unresolved production findings.

## CodeReview follow-up validation (2026-08-08)

PR #21 CodeReview fixes (CR21-01 … CR21-10) applied on branch
`fix/inspection-real-machine-reliability` head `590fa5b`; full automated gates
re-run in this Windows environment:

```text
python -m pytest apps/sidecar/tests                      -> 97 passed, 1 skipped
python -m ruff check apps/sidecar/idlerdream
  apps/sidecar/tests apps/sidecar/launcher.py            -> All checks passed
python -m compileall -q apps/sidecar/idlerdream          -> passed
python scripts/verify_assets.py                          -> asset verification passed
npm run test:ui                                          -> 9 passed
npm run typecheck                                        -> passed (protocol + desktop + electron)
npm run build                                            -> vite + electron-builder win-unpacked, exit 0
```

New regression coverage (8 tests in `tests/test_codereview_regressions.py`):
opencode.json(c) exclusion, 40-file default budget, required schema_version,
schemaVersion alias, model-facts demotion, per-inspection Run Profile
isolation + cleanup, high-confidence secret-content exclusion, Restricted-mode
source-body exclusion.

OpenCode 1.18.12 remains installed in this environment. Post-fix real-machine
revalidation was executed on 2026-08-08 (Windows, Python-equivalent probe,
real providers):

```text
read-only policy probe (opencode 1.18.12 + opencode-go/deepseek-v4-flash)
  exit code 0, marker read, sensitive content absent, snapshot hash stable  -> PASS
stability: 10/10 valid or partial reports, identity/fingerprint correct      -> PASS
  (9 full, 1 partial); run profiles + snapshots cleaned after every run
concurrency: opencode-go + deepseek concurrently, two distinct profiles,
  each auth.json holds exactly one provider, no cross-contamination,
  both reports valid, all profiles removed after completion                 -> PASS
cancel: CTRL_BREAK delivered (exit 0xC000013A STATUS_CONTROL_C_EXIT),
  running map empty, profile + snapshot cleaned                             -> PASS
timeout (2 s): error reported, profile + snapshot cleaned                   -> PASS
```
