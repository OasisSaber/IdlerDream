# v0.1 Release Readiness Prompt

Audit IdlerDream against the frozen v0.1 acceptance criteria.

Read `docs/PRODUCT_SPEC.md`, `docs/TEST_PLAN.md` and `docs/AGENT_ASSET_MANIFEST.md`.

Check:

- clean Windows per-user install/uninstall
- tray and full quit lifecycle
- one-project end-to-end inspection slice
- OpenCode compatibility and read-only fixture
- project workspace unchanged
- sensitive files blocked
- deterministic conflict behavior
- snapshot replay and SQLite rebuild
- Sidecar crash/cancel cleanup
- renderer keyboard/accessibility/appearance checks
- no frozen-scope feature added

Return:

1. ship blockers
2. nonblocking risks
3. evidence for each acceptance criterion
4. missing automated tests
5. exact final validation commands
6. go/no-go recommendation
