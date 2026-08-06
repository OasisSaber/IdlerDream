# v0.1.0-rc.1 Release Readiness Plan

## Current gate

The overlay is code-complete for focused review. It is not proof that OpenCode works with the user's provider/model profile.

## Gate A — focused automated checks

```powershell
python -m pytest apps/sidecar/tests/test_report_parser.py `
  apps/sidecar/tests/test_workspace_snapshot.py `
  apps/sidecar/tests/test_opencode_policy.py `
  apps/sidecar/tests/test_partial_report_state.py `
  apps/sidecar/tests/test_security.py
python -m compileall -q apps/sidecar/idlerdream
npm run typecheck
```

## Gate B — full repository CI

- Sidecar suite
- Ruff
- TypeScript
- Electron build
- packaged Sidecar smoke test
- NSIS install/uninstall smoke test

## Gate C — OpenCode compatibility

Run:

```powershell
.\scripts\test-opencode-readonly-policy.ps1 -Model '<provider/model>'
```

Pass conditions:

- source marker read
- secret marker absent
- snapshot unmodified
- OpenCode exit code 0
- no external directory access

## Gate D — 10-run stability

For one small real project:

- 10/10 source-readable
- 10/10 valid or partial diagnostic result
- 10/10 no real workspace modification
- 10/10 project ID and fingerprint correct
- 10/10 status plus phase/unknown plus next action/explicit unavailable

## Gate E — real project matrix

- small Git project
- medium frontend/backend project
- hostile project containing AGENTS.md and `.opencode`
- spaces and Chinese characters in paths
- non-Git directory

## Gate F — UI quality

Capture at:

- 1920×1080
- 1440×900
- 1280×720
- 1100×720

Each in light and dark; at least one reduced-motion and forced-colors pass.

## Release decision

Create `v0.1.0-rc.1` only when Issues #19/#20 are closed and no Critical/High release blocker remains.
