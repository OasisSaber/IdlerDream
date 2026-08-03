# IdlerDream v0.1 — Asset Index

Start here when handing the repository to an implementation Agent.

## 1. Run the visual prototype

Open `preview/apple-dashboard.html` directly in a desktop browser. It is a self-contained, dependency-free preview of the Apple-inspired Dashboard direction.

## 2. Give the Agent this prompt

Use `prompts/MASTER_IMPLEMENTATION_PROMPT.md` as the primary implementation prompt.

For focused work:

- Frontend: `prompts/FRONTEND_IMPLEMENTATION_PROMPT.md`
- Security review: `prompts/SECURITY_REVIEW_PROMPT.md`
- Release review: `prompts/RELEASE_READINESS_PROMPT.md`

## 3. Required reading order

1. `docs/CODE_REVIEW.md`
2. `docs/PRODUCT_SPEC.md`
2. `docs/ARCHITECTURE.md`
3. `docs/AGENT_ASSET_MANIFEST.md`
4. `docs/IMPLEMENTATION_PLAN.md`
5. `docs/TEST_PLAN.md`
6. `design-system/idlerdream/MASTER.md`
7. `docs/FRONTEND_SPEC.md`
8. `packages/protocol/report-schema.json`
9. Existing code and tests

## 4. Reusable implementation assets

### Desktop

- `apps/desktop/src/` — React pages, components, mock-data fallback and adaptive Apple-inspired styling
- `apps/desktop/electron/` — Electron window, tray, preload and privileged boundary
- `apps/desktop/resources/` — application and tray icons

### Sidecar

- `apps/sidecar/idlerdream/collectors/` — file, Git/JJ, test and process collectors
- `apps/sidecar/idlerdream/inspection/` — constrained OpenCode prompt, adapter and report parser
- `apps/sidecar/idlerdream/state/` — evidence-priority state merger
- `apps/sidecar/idlerdream/storage/` — weekly snapshots and encrypted raw-report foundation
- `apps/sidecar/tests/` — executable tests for collectors, security, state and storage

### Protocol

- `packages/protocol/src/index.ts`
- `packages/protocol/report-schema.json`

### Design system

- `design-system/idlerdream/MASTER.md`
- `design-system/idlerdream/tokens.json`
- `design-system/idlerdream/pages/`

## 5. Validation status

See `docs/VALIDATION_REPORT.md` for the exact checks run, passed checks and environment-limited checks.
