# IdlerDream Inspection Acceptance — 2026-08-06

Real-machine acceptance for the inspection-reliability overlay (Issues
#19/#20). Branch `fix/inspection-real-machine-reliability`, commits `b09a263`,
`f2fd883`, `8ce40d9`, `78b0481`.

## Environment matrix

| Component | Version |
|---|---|
| Windows | 11, build 26200 |
| OpenCode | 1.18.12 (`C:\Users\Oasis\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe`) |
| Model/profile | `opencode-go/deepseek-v4-flash` |
| Python | 3.14.6 |
| Node / npm | 24.17.0 / 11.13.0 |
| Electron | 37.10.3 |
| PowerShell 7 | not installed — pack probe executed via byte-equivalent Python probe |

## Gate C — read-only policy probe: PASS

```text
OpenCodeVersion          = 1.18.12
ExitCode                 = 0
OrdinarySourceRead       = True
SensitiveContentAbsent   = True
SnapshotUnmodified       = True
PolicyPassed             = True
```

Model answer (redacted):

```json
{"marker":"IDLERDREAM_POLICY_MARKER_7F2A","read_ok":true,"sensitive_visible":false,"edit_denied":true,"shell_denied":true}
```

The model read `README.md` and `src/marker.py`; `glob` for `.env`,
`secret.key`, `AGENTS.md` returned "No files found"; edit and shell tools were
not available/denied. Snapshot tree hash unchanged before/after.

## Gate D — 10-run stability: PASS

Small real project (`README.md`, `src/main.py`, `tests/test_main.py`), 10
consecutive inspections through the product adapter:

| Run | Exit | Report | Quality | Status | Identity | Next action | Workspace unchanged |
|---|---:|---|---:|---|---:|---:|---:|
| 1 | 0 | yes | full | not_started | ok | yes | yes |
| 2 | 0 | yes | full | not_started | ok | yes | yes |
| 3 | 0 | yes | full | unknown | ok | yes | yes |
| 4 | 0 | yes | full | not_started | ok | yes | yes |
| 5 | 0 | yes | full | not_started | ok | yes | yes |
| 6 | 0 | yes | partial | unknown | ok | yes | yes |
| 7 | 0 | yes | full | completed | ok | yes | yes |
| 8 | 0 | yes | full | unknown | ok | yes | yes |
| 9 | 0 | yes | full | completed | ok | yes | yes |
| 10 | 0 | yes | full | not_started | ok | yes | yes |

Result: 10/10 valid or partial; 10/10 `project_id` + `workspace_fingerprint`
correct; 10/10 next action or explicit unavailable; 10/10 real workspace hash
unchanged.

## Gate E — real project matrix: PASS

| Case | Report | Identity | Workspace unchanged | Secret leak |
|---|---:|---:|---:|---:|
| small Git project | full | ok | ok | none |
| medium repo (IdlerDream itself) | full/partial | ok | ok | none |
| hostile fixture (AGENTS.md + `.opencode` + fake secrets) | full | ok | ok | none |
| path with spaces + Chinese characters | full | ok | ok | none |
| non-Git directory | full | ok | ok | none |

Hostile case snapshot exclusions: 4 (`AGENTS.md`, `.env`, `secret.key`,
`.opencode/config.json`); copied: 2.

## Initial failures and fixes (recorded honestly)

- Gate C pre-fix: `UnknownError: Unexpected server error` (ref `err_619b6c59`);
  provider auth not visible under isolation. Fixed by `prepare_provider_auth`.
- Configured default model was not resolved under isolation (silent fallback to
  OpenCode built-in default). Fixed by `default_opencode_model` + explicit
  `--model`.
- `opencode` resolves to an npm `.cmd` shim that `CreateProcess` cannot launch.
  Fixed by `_resolve_executable`.
- Long-context runs failed parsing because tool outputs polluted candidate
  extraction; JSON5-style variance also failed. Fixed by
  `_assistant_text_fragments` + `_repair_json5_lite`.

Raw-report IDs: probe runs do not flow through the Sidecar raw-report store, so
no IDs apply; adapter-side failures are captured by parse diagnostics
(`ParseDiagnostics`) and stored in the product's encrypted raw reports during
normal operation.

## Verification summary

```text
python -m pytest apps/sidecar/tests                    -> 63 passed
python -m compileall -q apps/sidecar/idlerdream        -> ok
python scripts/verify_assets.py                        -> passed
npm run typecheck                                      -> passed
npm run build                                          -> passed (win-unpacked)
Sidecar packaged smoke (PyInstaller exe)               -> /health 200,
  /api/v1/projects 200, no-token 401
```

UI screenshots (preview, light/dark/reduced-motion): `output/playwright/`.
Component-level axe (axe-core 4, wcag2a/2aa/21aa + best-practice):

```text
preview light: 0 violations / 21 passes
preview dark:  0 violations / 21 passes
app (mock dashboard) light: 0 violations / 31 passes
app (mock dashboard) dark:  0 violations / 31 passes
keyboard walk: stable Tab cycle through nav, project cards, inspection panel
component tests (vitest + Testing Library): 9 passed
```

Probe artifact: `artifacts/acceptance/opencode-policy.txt` (raw redacted event
stream from the passing Gate C run).

Accessibility token deviations applied to pass the audit (small-text contrast):

- `styles.css` `--text-tertiary`: light 0.58→0.74, dark 0.55→0.62.
- `.actor--agent`: light `#0060df`, dark `#48a9ff` (9 px bold caption).
- `.button--primary`: light `#0060df`, dark `#0071e3` (white text on accent).
- Preview mirror tokens and a data-URI favicon (404 silenced).

Windows High Contrast screenshots and screen-reader spot checks still require a
system High Contrast session.

## Installer build (2026-08-06)

```text
NSIS: apps/desktop/dist/IdlerDream Setup 0.1.0-dev.exe (231 MB, signed)
```

Clean-VM install/uninstall smoke is still required (CR-24).

## Application state screenshots

`output/playwright/ui-app-{light,dark}-{dashboard,partial,full,failed}-1440x900.png`
— real mock renderer with the reliability card for each quality state.

## Release recommendation

- Issues #19/#20: evidence complete; close and open the PR only after user
  authorization (external action).
- `v0.1.0-rc.1`: **blocked** until Gate F finishes and CR-24 NSIS clean-VM
  install/uninstall passes.
