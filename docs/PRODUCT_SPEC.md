# IdlerDream v0.1 Product Specification

## 1. Product statement

IdlerDream is a Windows local-first desktop dashboard for observing multiple development workspaces and local coding Agents. It continuously collects deterministic local facts and can run a constrained OpenCode inspection to produce a verified project state, current phase, one highest-priority next action, and the responsible actor.

The product is read-only with respect to project work. It does not start, stop, direct, coordinate, or send tasks to Agents.

## 2. Primary user question

When the user opens the Dashboard, each project should answer:

- What stage is this project in?
- What is happening live right now?
- What is the single most important next action?
- Should the user or an Agent perform it?
- How fresh and trustworthy is this judgment?

## 3. Core product loop

```text
Register workspace
→ collect local facts
→ associate running Agent processes
→ run constrained OpenCode inspection
→ validate and merge report
→ show verified state + live activity
→ append meaningful state changes to weekly snapshots
```

## 4. v0.1 functional scope

### 4.1 Workspace registration

- Add a local Windows workspace manually.
- Discover candidate projects under a user-selected root.
- Detect Git, Jujutsu, package manifests and common project files.
- Require confirmation before monitoring discovered candidates.
- Assign a stable project UUID independent of path.
- Open the workspace folder in Windows Explorer.

### 4.2 Local fact collection

- File activity summary with ignore rules and event aggregation.
- Git/JJ branch, head/change ID, changed file count and status summary.
- Common test report discovery and pass/fail extraction.
- Workspace fingerprint before and after an inspection.
- Agent process discovery, process tree, CPU, memory and association confidence.

### 4.3 Verified inspection

- Official v0.1 inspector: OpenCode only.
- Noninteractive JSON event stream.
- Dedicated runtime configuration and read-only permission policy.
- Fixed report Schema.
- Standard, restricted and local-only project permissions.
- 10-minute default budget, 40 files, 2 MB content, 1 MB diff, 100 tool calls.
- Simplified safe progress UI and cancellation.

### 4.4 Status output

Core status is one of:

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

The current state also contains:

- phase
- summary
- one next action
- actor: user, agent or none
- confidence
- facts
- model inferences
- uncertainties
- freshness
- activity state
- risks
- acceptance-criteria progress when configured

### 4.5 Automatic inspection

A simplified automatic inspection may be triggered when:

- a high-confidence associated Agent exits; or
- a deterministic test result changes.

Rules:

- wait for a three-minute stable window;
- do not repeat within 30 minutes for the same project;
- do not run tests or builds automatically;
- do not retry an automatic inspection failure;
- manual inspection remains available.

### 4.6 History

- Meaningful state changes append to one JSONL file per ISO week.
- SQLite stores project configuration, snapshot index and current materialized state.
- Current state can be rebuilt from weekly history.
- Raw inspection events are encrypted and retained for 7 days by default, optionally 15.
- Structured snapshots remain until manually deleted.

## 5. Monitoring modes

### Unstructured monitoring

A project may be monitored without a cycle definition. It can display runtime facts, inferred phase and a next action, but not percentage completion or final completion.

### Structured progress

The user may define:

- current cycle name
- one-sentence goal
- acceptance criteria
- explicit excluded scope
- optional deadline

v0.1 displays completed acceptance criteria as `n / total`. It does not compute weighted percentages.

## 6. Evidence hierarchy

```text
Explicit user override
> deterministic test/build fact
> confirmed acceptance criterion
> Git/JJ and file fact
> OpenCode semantic analysis
> low-confidence inference
```

When evidence cannot be reconciled, the product shows `conflict`. It must not hide disagreement to preserve a clean-looking status.

## 7. Freshness

- `current`: no meaningful change after verification.
- `possibly_stale`: low-weight activity occurred.
- `expired`: major changes occurred; old next action is no longer authoritative.
- `never_inspected`: no successful inspection exists.

Live activity never directly updates phase, progress or next action.

## 8. Activity and archive behavior

- Default inactivity threshold: 3 days; per-project choices: 1, 3, 7, 14 or 30.
- Inactive projects stop deep analysis but retain low-cost monitoring.
- Blocking, waiting and conflict states are not visually replaced by inactivity.
- Archive is manual.
- Archived projects keep low-cost activity detection and do not automatically reactivate.

## 9. Security model

### Hard blocked content

The local tool layer must reject known credential and secret files, including `.env*`, private keys, credential files, package registry authentication and browser/Windows credential locations.

### Remote model permissions

- Standard source inspection: normal source, docs, diff and test results.
- Restricted inspection: project documents, structure, VCS summaries, tests and filenames; no source body by default.
- Local only: no remote model call.

### Read-only boundary

- Project content is untrusted data.
- Repository instructions cannot change inspector permissions.
- Project plugins, MCP and instructions are isolated.
- Edit and write tools are denied.
- Bash is denied except explicit read-only VCS query patterns.
- The workspace fingerprint is compared after inspection.

## 10. Desktop behavior

- Electron window and system tray.
- Closing the window hides to tray.
- “Quit” stops Electron, Sidecar and active inspection processes.
- No Windows service.
- No administrator permission.
- Single application instance and one Sidecar per data profile.
- Windows Explorer is the only workspace launch shortcut.

## 11. v0.1 acceptance criteria

1. NSIS current-user installation works on Windows 10/11.
2. The app remains available from the tray after window close.
3. A workspace can be added manually and discovered in bulk.
4. Git/JJ, files, tests and Agent processes are collected.
5. Agent CPU, memory and process tree are displayed.
6. Live activity and verified status are separate.
7. OpenCode runs in the constrained inspection profile.
8. The report yields status, phase, one next action and actor.
9. Facts, inferences, confidence and freshness are visible.
10. Agent exit/test change can trigger the simplified automatic inspection.
11. Weekly snapshots are appended and current state can be rebuilt.
12. The folder opens in Windows Explorer.
13. API setup and read-only compatibility tests complete.
14. Sensitive files are locally blocked.
15. IdlerDream does not write to the project workspace.
16. IdlerDream does not control or coordinate Agents.

## 12. Explicitly excluded from v0.1

- global cross-project inspection
- global unique next action
- custom inspector CLI
- manual one-time Agent report workflow
- browser UI
- system notifications
- submodules as first-class project units
- multiple workspace instances per project
- weighted milestones and percentage progress
- backup/restore
- automatic updates
- full WSL/Docker/remote support
- Agent control, task dispatch or orchestration
- Agent conversation parsing
- Web Agent monitoring
- stall/high-resource alerts
- editor and terminal launchers
- GitHub/Jira/calendar/CI integrations
