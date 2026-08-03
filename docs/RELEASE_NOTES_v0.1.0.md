# IdlerDream v0.1.0 Release Notes

> **Status: DRAFT — tag and GitHub release are NOT yet executed.**
> These notes describe the release that will be cut after acceptance and the
> remaining code-review findings (CR-19…CR-24) are merged. See
> `docs/RELEASE_CHECKLIST.md` for the go/no-go gates.

- Version: **0.1.0**
- Release type: initial release (first milestone vertical slice)
- Planned tag: `v0.1.0`
- Target platform: **Windows 10/11** (per-user NSIS installer)
- Repository: https://github.com/OasisSaber/IdlerDream

---

## What is IdlerDream

IdlerDream is a Windows **local-first** desktop dashboard for observing multiple
development workspaces and local coding Agents. It continuously collects
deterministic local facts (Git/JJ, files, test reports, Agent processes) and can
run a **constrained, read-only OpenCode inspection** to produce:

- verified project state (stage)
- what is happening live right now
- the single most important next action
- the responsible actor (user / agent / none)
- how fresh and trustworthy the judgment is

IdlerDream is **read-only with respect to project work**: it does not start, stop,
direct, coordinate, or send tasks to Agents, and it never writes into a monitored
workspace.

---

## Highlights

- **First functional vertical slice**: add a workspace through the control API →
  persist and list it → collect Git/JJ/test/file facts → run an inspection → merge
  the verified report → append weekly snapshot → show verified state + next action
  in the React dashboard.
- **Security hardening from code review**: all critical/high review findings
  (CR-01…CR-13) are fixed, including read-token auth, IPC allowlist, build-time-only
  mocks, isolated inspector environment and report identity verification.
- **Two-stage project removal** (recycle bin: remove → restore → purge) with the
  workspace directory never deleted (CR-14).
- **Authenticated live event stream** (WebSocket) with polling fallback (CR-16).
- **Reproducible builds**: committed `package-lock.json` (CR-23), PyInstaller
  launcher so the packaged Sidecar exe starts (CR-24 progress), and a Windows CI
  job that builds the NSIS installer and smoke-tests silent install/first-run/
  uninstall with data preservation (CR-24 progress).

---

## What's in this release

### Desktop application (`apps/desktop`)

- Electron + React + TypeScript shell: Dashboard, project detail, onboarding,
  settings pages.
- System tray with hide-to-tray, single application instance, and full quit
  lifecycle (Quit stops Electron, Sidecar and active inspections).
- Native directory picker, open-in-Explorer, control bridge with a fixed command
  allowlist and payload validation.
- Context-isolated renderer (sandbox, no Node integration); read token delivered
  through preload only.
- Apple-inspired adaptive design system (light/dark, keyboard focus, 44px targets,
  reduced motion, forced colors).
- Mock mode is explicit and build-time only (`VITE_USE_MOCKS=1`).

### Sidecar (`apps/sidecar`, Python)

- Project registration/discovery with stable project UUID; root directory itself is
  evaluated (CR-11).
- Two-stage removal: `removed_at`, restore, purge, list removed (CR-14).
- Collectors: Git/JJ status, test-report discovery (JUnit/pytest, newest-first with
  supported counters), file fingerprint/classification, Windows Agent process tree
  and resource sampling.
- Independent collector degradation: one failed collector no longer aborts the
  baseline (CR-09); workspace fingerprint failure remains fatal.
- Constrained OpenCode inspection adapter: isolated HOME/USERPROFILE/XDG + working
  directory, read/list/glob/grep only (no Bash), noninteractive JSON event stream,
  redaction, report Schema validation, project/fingerprint identity checks.
- Evidence-priority state merger with freshness, partial success and conflict
  handling; deterministic facts always override model claims.
- Storage: weekly JSONL snapshots with startup reconciliation that rebuilds missing
  SQLite index rows (CR-18); SQLite materialized current state; encrypted
  raw-report interface (Windows DPAPI path pending per CR-19).
- Read-only HTTP API (`/api/v1/projects`, `/api/v1/inspections`, `/health`) and
  private control channel, both token-authenticated.

### Protocol & packaging

- Versioned TypeScript protocol package (`@idlerdream/protocol` 0.1.0) and report
  JSON Schema.
- PyInstaller launcher + committed spec so the packaged Sidecar exe starts (CR-24).
- NSIS per-user installer (electron-builder) with install/uninstall smoke test
  automation on a clean `windows-latest` runner.

---

## Security model (v0.1)

- Read token (HTTP header) + control token (private pipe) per launch; tokens never
  exposed to ordinary web content.
- Hard-blocked sensitive paths/file types (`.env*`, private keys, credentials).
- Log/redaction of tokens and credentials.
- Project content is untrusted data; repository instructions cannot change
  inspector permissions; edit/write tools denied; Bash denied; workspace
  fingerprint compared after inspection.
- IdlerDream never writes into monitored workspaces.

---

## Known limitations / not in v0.1

These are explicitly excluded from v0.1 by the frozen product boundary and must
**not** be added: Agent control/task dispatch, Web-Agent monitoring, team
collaboration, cloud sync, project-management board, browser UI, notifications,
auto-update, backup/restore, weighted progress percentages.

Known functional limitations (accepted for v0.1 slice):

- Frontend live activity is consumed via WebSocket with a polling fallback; deep
  event-driven incremental reconciliation is a later milestone.
- Onboarding OpenCode detection, Credential Manager storage and compatibility
  testing remain simplified flows, not the full production implementations.
- Raw-report encryption uses the storage interface; Windows DPAPI key management is
  pending (CR-19).
- Monitoring loop fingerprints sequentially (target of 50 projects not yet proven,
  CR-20).
- Windows process association is a useful heuristic that still needs real-system
  validation (CR-21).
- Named-pipe authorization relies on token secrecy; ACL tests pending (CR-22).

---

## Remaining work before the binary release (blockers)

Per `docs/CODE_REVIEW.md` and open issues:

| ID | Issue | Severity | Status |
|----|-------|----------|--------|
| CR-19 | Raw-report weekly compaction + Windows DPAPI end-to-end | Medium | Open (#6) |
| CR-20 | Monitoring architecture for 50-project target | High | Open (#7) |
| CR-21 | Windows process association production validation | High | Open (#8) |
| CR-22 | Control-pipe current-user ACLs + negative tests | High | Open (#9) |
| CR-24 | Clean Windows VM tray lifecycle + Sidecar crash recovery | High | CI baseline automated; clean-VM pass pending |

Release is gated on these items and on the v0.1 acceptance checklist
(`docs/RELEASE_CHECKLIST.md`).

---

## Verification summary (at drafting time)

Local (2026-08-03, on `main` @ `80db2de`):

- `python -m pytest apps/sidecar/tests`: **30 passed, 1 skipped** (packaged-exe
  smoke test skips when the exe is absent locally)
- `python scripts/verify_assets.py`: **passed**
- `npm install`: clean (0 vulnerabilities)
- `npm run typecheck`: **passed**
- `npm run build`: **passed** (`win-unpacked` produced)

CI on `main` (all green): Sidecar tests + ruff, frontend typecheck/build,
packaged-exe smoke test, NSIS installer smoke test (`windows-installer` job).

> These numbers are the state at drafting time; re-run the exact commands in
> `docs/RELEASE_CHECKLIST.md` and confirm the final CI run before executing the
> release.

---

## Related documents

- `CHANGELOG.md` — full change log
- `docs/RELEASE_CHECKLIST.md` — go/no-go gates and exact release commands
- `docs/CODE_REVIEW.md` — code review findings and fixes
- `docs/PRODUCT_SPEC.md` — frozen v0.1 product specification
- `docs/ARCHITECTURE.md` — system architecture
- `docs/TEST_PLAN.md` — test plan
- `prompts/RELEASE_READINESS_PROMPT.md` — release readiness audit prompt
