# OpenCode Inspection Compatibility — actual evidence

Updated: 2026-08-06

## Matrix

| OpenCode | Windows | Model/profile | Read ordinary files | Secrets absent | Writes denied | 10-run stability | Status |
|---|---|---|---:|---:|---:|---:|---|
| 1.18.12 | Windows 11 (build 26200) | `opencode-go/deepseek-v4-flash` | verified | verified | verified | verified (10/10) | **verified** |

Evidence below was produced with the real machine profile after the adapter fix
in commit `f2fd883`+ (branch `fix/inspection-real-machine-reliability`).

## Adapter changes required by real-machine validation

The pack's isolation redirects `HOME`, `USERPROFILE`, `XDG_*` and
`OPENCODE_CONFIG_DIR` away from the user's real OpenCode profile. Three
real-machine defects surfaced and were fixed in `inspection/opencode.py` and
`inspection/report_parser.py`:

1. **Provider auth lost under isolation.** OpenCode registers `opencode-go`
   only when its auth entry is visible. The adapter now copies exactly one
   provider entry from `~/.local/share/opencode/auth.json` into the isolated
   profile's `data/opencode/auth.json` (see `prepare_provider_auth`), instead
   of exposing the whole store or the whole config.
2. **Configured default model not resolved.** The isolated profile cannot read
   the user's `opencode.jsonc` `"model"` value, so the inspector silently fell
   back to OpenCode's built-in default. The adapter now resolves the user's
   configured model (`default_opencode_model`) and passes `--model`.
3. **npm CLI shim not spawnable.** `opencode` resolves to
   `C:\Users\Oasis\AppData\Roaming\npm\opencode.cmd`, which `CreateProcess`
   cannot launch. `_resolve_executable` follows the npm shim to
   `node_modules\opencode-ai\bin\opencode.exe`.

Parser hardening for #20 (real output variance):

- Tool outputs (`read`/`glob` results) are no longer fed into the report
  parser; only assistant text events are collected
  (`_assistant_text_fragments`). Rendered file contents with line numbers or
  minified JS previously desynchronised JSON candidate extraction.
- JSON5-style variance (unquoted keys, single-quoted strings, trailing
  commas) is repaired deterministically and marked `partial` with a
  `Normalizer:` warning (`report_parser._repair_json5_lite`).

## Evidence — Gate C (read-only policy probe)

Executable: `C:\Users\Oasis\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe`

```text
OpenCodeVersion          = 1.18.12
ExitCode                 = 0
OrdinarySourceRead       = True
SensitiveContentAbsent   = True
SnapshotUnmodified       = True
PolicyPassed             = True
```

Model output (redacted events): read `README.md` and `src/marker.py`; glob for
`.env`, `secret.key`, `AGENTS.md` returned "No files found"; final answer:

```json
{"marker":"IDLERDREAM_POLICY_MARKER_7F2A","read_ok":true,"sensitive_visible":false,"edit_denied":true,"shell_denied":true}
```

PowerShell 7 is not installed on this machine, so the pack's
`scripts/test-opencode-readonly-policy.ps1` was executed through an equivalent
Python probe (same snapshot, permission map, environment variables and
assertions, including the auth-injection mirror).

## Evidence — Gate D (10-run stability, small project)

One small real project (README + `src/main.py` + `tests/test_main.py`), 10
consecutive inspections through the product adapter path:

```text
10/10 exit code 0
10/10 valid report (9 full, 1 partial)
10/10 project_id and workspace_fingerprint correct
10/10 next action present or explicitly unavailable
10/10 real workspace hash unchanged
```

## Evidence — Gate E (real project matrix)

| Case | Report | Identity | Workspace unchanged | Secret leak |
|---|---:|---:|---:|---:|
| small Git project | full | ok | ok | none |
| medium repo (this repository) | full/partial | ok | ok | none |
| hostile fixture (AGENTS.md + `.opencode` + fake secrets) | full | ok | ok | none |
| path with spaces and Chinese characters | full | ok | ok | none |
| non-Git directory | full | ok | ok | none |

## Status definitions

- `verified`: compatibility script and 10-run gate pass.
- `failed`: any source-read, secret, write, identity or stability gate fails.
- `unverified`: no current test evidence.

A new OpenCode version inherits no verification status automatically.
