# IdlerDream v0.1 Architecture

## 1. System topology

```text
┌───────────────────────────────────────────────────────────────┐
│ Electron main                                                 │
│ window · tray · single instance · folder open · sidecar host  │
└───────────────┬───────────────────────────────┬───────────────┘
                │ preload IPC                   │ private control
                ▼                               ▼
┌─────────────────────────────┐       ┌──────────────────────────┐
│ React renderer              │       │ Python Sidecar           │
│ read-only API consumer      │◄─────►│ control + local facts    │
│ dashboard and settings      │ HTTP  │ inspection + storage     │
└─────────────────────────────┘ / WS  └──────────┬───────────────┘
                                                 │ subprocess
                                                 ▼
                                      ┌──────────────────────────┐
                                      │ OpenCode inspector       │
                                      │ remote model + local read│
                                      └──────────────────────────┘
```

## 2. Trust boundaries

### Renderer

Untrusted relative to the operating system. It has no Node integration. It can read Sidecar data over localhost and request privileged actions only through typed preload IPC.

### Electron main

Owns desktop lifecycle and platform actions. It does not implement project analysis. It forwards control commands to the Sidecar through a private channel and opens folders with Electron `shell.openPath`.

### Sidecar

Source of truth for projects, deterministic facts, inspection scheduling, state merge and persistence. It alone can approve inspection inputs and merge reports into current state.

### OpenCode

Semantically capable but untrusted for deterministic fact ownership and permissions. It receives a fixed system prompt, a Sidecar fact baseline and constrained tools. Its report is validated before use.

### Project workspace

All content is untrusted data. README, comments, prompt files and logs cannot change IdlerDream policy.

## 3. Communication

### Read path

- Renderer → `GET /api/v1/projects`
- Renderer → `GET /api/v1/projects/{id}`
- Renderer → `GET /api/v1/inspections`
- Sidecar → WebSocket event updates

The HTTP surface is read-only in v0.1.

### Control path

```text
Renderer
→ context-isolated preload API
→ Electron main IPC
→ Windows Named Pipe / private control socket
→ Sidecar command handler
```

Commands include project add/remove, inspection start/cancel and configuration changes.

### Authentication

Electron starts the Sidecar with a random control token. The token is not exposed to ordinary web content. Browser access is not offered in v0.1.

## 4. Sidecar modules

```text
idlerdream/
├─ collectors/
│  ├─ files.py          fingerprint and file classification
│  ├─ processes.py      Agent process tree and resources
│  ├─ tests.py          test report discovery
│  └─ vcs.py            Git/JJ facts
├─ inspection/
│  ├─ opencode.py       constrained adapter and event stream
│  ├─ prompt.py         fixed inspector prompt
│  └─ report_parser.py  JSON extraction and validation
├─ security/
│  ├─ paths.py          hard-blocked paths and file types
│  └─ redaction.py      token/credential redaction
├─ services/
│  ├─ facts.py          deterministic baseline
│  ├─ inspections.py    job lifecycle and merge
│  ├─ monitoring.py     periodic runtime observations
│  └─ projects.py       registration and discovery
├─ state/merger.py      evidence priority and freshness
├─ storage/
│  ├─ snapshots.py      weekly JSONL
│  └─ raw_reports.py    encrypted raw events
├─ api.py               read API and app context
├─ control.py           private command transport
├─ database.py          SQLite materialized state/index
├─ models.py            Pydantic contracts
└─ main.py              process entry point
```

## 5. Inspection sequence

```text
1. Queue job
2. Generate deterministic FactBaseline
3. Record start workspace fingerprint
4. Build fixed prompt + structured context
5. Start OpenCode with isolated environment
6. Stream and redact events
7. Parse final report candidate
8. Validate report Schema and project/fingerprint identity
9. Recalculate end fingerprint
10. Invalidate report if major workspace changes occurred
11. Merge report with deterministic baseline
12. Append meaningful SnapshotEvent
13. Update SQLite materialized state
14. Publish renderer event
```

## 6. State merge rules

The merger never accepts a model statement as a replacement for a deterministic failure.

Examples:

- Model says completed + tests failed → `conflict` or `blocked`, depending on acceptance scope.
- Model supplies no next action but status/phase are valid → partial success; state may update without authoritative next action.
- Report fingerprint mismatches the baseline → invalidated; no current state update.
- User override says waiting user → override remains until its configured expiry scope.

## 7. Persistence

### SQLite

Stores:

- project and cycle configuration
- current materialized state
- inspection jobs
- snapshot file index/offsets
- association and override rules
- short-lived resource samples/aggregates

WAL is enabled for read/write coexistence.

### Weekly JSONL

The immutable history source. One file per ISO week. Each line is a `SnapshotEvent`. SQLite can be rebuilt by replaying these events.

### Raw inspection container

Raw OpenCode events, source excerpts and full command output are short-lived. The production implementation should encrypt each report with a random data key protected by Windows DPAPI, then destroy the key at expiry.

## 8. Process lifecycle

- Electron starts Sidecar and checks protocol health.
- Sidecar crashes may be restarted a limited number of times.
- Active inspection subprocesses run under a Windows Job Object in the production implementation.
- Cancel requests first attempt graceful interruption, then kill the full process tree.
- App “Quit” stops all components.
- Closing the main window does not stop monitoring.

## 9. Failure modes and degradation

| Failure | Behavior |
|---|---|
| OpenCode unavailable | local facts remain visible; inspection disabled |
| API/model unavailable | old verified state receives freshness treatment; local facts continue |
| Git/JJ unavailable | corresponding collector disabled; project remains monitored |
| file watcher fails | fall back to periodic incremental scan |
| inspection output invalid | retain raw report; do not update current state |
| workspace changes during inspection | report invalidated |
| SQLite migration fails | enter read-only recovery mode |
| weekly snapshot file damaged | isolate affected file; other weeks continue |

## 10. Protocol versioning

The Electron/Sidecar protocol and inspection report Schema are versioned independently.

A snapshot records:

- inspector adapter/version
- model profile ID/model label
- prompt template version
- report Schema version
- rule engine version
- project context fingerprint
- workspace fingerprint

A change only in analysis version is a re-evaluation, not project progress.
