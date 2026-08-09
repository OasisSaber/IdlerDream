# OpenCode Inspection Compatibility Matrix

| OpenCode | Windows | Model/profile | Read ordinary files | Secrets absent | Writes denied | 10-run stability | Status |
|---|---|---|---:|---:|---:|---:|---|
| 1.18.12 | Windows 11 (build 26200) | `opencode-go/deepseek-v4-flash` | verified | verified | verified | verified (10/10) | verified |

Evidence: `docs/INSPECTION_COMPATIBILITY.md` (2026-08-06).

## Status definitions

- `verified`: compatibility script and 10-run gate pass
- `unverified`: no current test evidence
- `failed`: any source-read, secret, write, identity or stability gate fails

A new OpenCode version inherits no verification status automatically.
