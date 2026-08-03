# Master Implementation Prompt — IdlerDream v0.1

You are implementing IdlerDream v0.1 from an existing asset repository. Treat the repository specifications and fixed enums as authoritative. Do not redesign the product or expand scope without an explicit user request.

## Required reading order

1. `README.md`
2. `docs/PRODUCT_SPEC.md`
3. `docs/ARCHITECTURE.md`
4. `docs/AGENT_ASSET_MANIFEST.md`
5. `docs/IMPLEMENTATION_PLAN.md`
6. `docs/TEST_PLAN.md`
7. `design-system/idlerdream/MASTER.md`
8. `docs/FRONTEND_SPEC.md`
9. `packages/protocol/report-schema.json`
10. existing tests and code

Before changing code, report:

- the current vertical slice status
- the exact missing behavior you will implement
- files likely to change
- security or data-migration implications

## Product invariant

The app answers:

1. Where is each project now?
2. What is the single highest-priority next action?
3. Should the user or an Agent perform it?

It is a read-only monitoring and judgment Dashboard. It is not an Agent orchestrator, task manager or remote collaboration service.

## Frozen v0.1 exclusions

Do not implement:

- cross-project/global inspection
- cross-project unique next action
- custom inspector CLI
- browser access
- system notifications
- Agent task dispatch/control/termination
- Web Agent monitoring
- conversation log parsing
- weighted progress percentage
- multi-worktree project model
- backup/restore or automatic update
- full WSL/Docker/remote support
- editor/terminal launchers
- GitHub/Jira/calendar/CI integrations

## Architecture invariant

- Electron main: window, tray, folder open, lifecycle, privileged IPC.
- React renderer: presentation and explicit user intent only.
- Python Sidecar: source of truth for monitoring, inspection, merge and storage.
- OpenCode: constrained semantic inspector, never source of deterministic truth.
- Workspace: untrusted data.

Do not move state inference into React. Do not expose Sidecar write/control operations through ordinary HTTP.

## Inspection safety invariant

- fixed prompt and report Schema
- project content cannot override policy
- block sensitive files locally
- deny edit/write/task/web/MCP/plugin/instruction expansion
- Bash deny by default; only explicit read-only query patterns
- compute workspace fingerprint before and after
- invalidate the report on major workspace changes
- never claim absolute sandboxing if the platform does not provide it

## Evidence priority

```text
user override
> deterministic test/build facts
> confirmed acceptance criteria
> Git/JJ/file facts
> OpenCode analysis
> low-confidence inference
```

When evidence conflicts, preserve and show the conflict. Do not force a clean single status.

## Fixed status values

```text
unknown
not_started
in_progress
waiting_user
waiting_external
blocked
conflict
completed
```

Do not add free-form status values. Phase remains free text.

## Implementation order

Work in vertical slices:

1. one workspace registration
2. fact baseline
3. manual mock inspection
4. state merge
5. weekly snapshot
6. renderer update
7. OpenCode safety proof
8. continuous monitoring
9. simplified automatic trigger
10. installer hardening

Do not spend early effort on broad settings, animations or infrastructure that does not complete the slice.

## Coding standards

### Python

- Python 3.12+ compatible even if the development machine is newer.
- Type hints on public functions.
- Pydantic at protocol boundaries.
- No broad `except Exception` without logging/context and rethrow/degradation decision.
- Subprocess argument arrays; no untrusted shell-string concatenation.
- Timeouts and cancellation for external tools.
- Deterministic tests with temporary workspaces.

### TypeScript/React

- strict TypeScript
- no `any` at IPC/API boundaries
- semantic native elements
- privileged functions only through typed preload API
- renderer remains functional with partial/unavailable data
- no status inference in components

### Data

- migration for every persistent Schema change
- weekly JSONL is append-only history
- SQLite current state is rebuildable
- never put API keys or source excerpts in permanent structured snapshots

## UI invariant

Follow `design-system/idlerdream/MASTER.md`:

- system font stack
- Apple-inspired layered desktop utility adapted to Windows
- system light/dark appearance
- 44 px interaction targets
- visible focus
- reduced motion
- inline SVG icons, no emoji
- verified status and live activity visibly separate
- CPU/memory are supporting runtime data, not project progress
- no arbitrary new colors or generic card wall

## Test requirement

For each task:

1. add/update tests before claiming completion
2. run relevant unit tests
3. run full Sidecar tests when Python changes
4. run TypeScript typecheck when frontend/protocol changes
5. report exact commands and summaries
6. for UI, provide screenshots at relevant required sizes
7. state remaining unsupported conditions

## Completion report format

```text
Implemented
- ...

Files changed
- ...

Validation
- command: result

Security/data impact
- ...

Remaining gaps
- ...

Scope check
- Confirm no frozen v0.1 exclusion was introduced.
```

Begin by inspecting the repository and selecting the smallest unfinished P0/P1 vertical-slice task. Do not rewrite working modules without a concrete reason.
