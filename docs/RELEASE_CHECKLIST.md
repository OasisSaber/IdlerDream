# IdlerDream v0.1.0 Release Checklist (发布清单)

> **Status: PREPARED — NOT executed.** The tag/release steps below must only be run
> after acceptance and after the remaining code-review findings are merged.
> This document is the go/no-go gate referenced by `docs/RELEASE_NOTES_v0.1.0.md`.

- Release version: **0.1.0**
- Tag: `v0.1.0`
- Target platform: Windows 10/11 x64, per-user NSIS installer
- Planned execution window: after v0.1 acceptance + CR-19…CR-24 merge

---

## 0. Definitions

| Term | Meaning |
|------|---------|
| Blocker | Must be green before the tag is cut |
| Gate | Must be green before the GitHub release is published |
| Post | Can be done after publishing; documented as follow-up |

---

## 1. Code-review findings (Blockers)

Tracked as GitHub issues; merge before release. Status as of 2026-08-09:

| ID | Issue | Gate | Status |
|----|-------|------|--------|
| CR-19 | Raw-report weekly compaction + Windows DPAPI end-to-end | #6, Blocker | **Done** — DPAPI + compaction + quarantine implemented (#18); Windows DPAPI/expiry tests added 2026-08-09 |
| CR-20 | Monitoring architecture for 50-project target | #7, Blocker | **Done** — three schedulers + Watchdog + cooldown/dedup; tests added 2026-08-09 |
| CR-21 | Windows process association production validation | #8, Blocker | **Done** — fixtures + real OpenCode binary association test added 2026-08-09 |
| CR-22 | Control-pipe current-user ACLs + negative tests | #9, Blocker | **Done** — DACL current-user-only + malformed/non-dict/unknown-command rejection tests (2026-08-09) |
| CR-24 | Clean Windows VM: tray lifecycle + Sidecar crash recovery | Blocker | **Partial** — NSIS install/uninstall/first-run smoke green on CI; crash-recovery restart gate unit-tested; interactive tray lifecycle pending final clean-VM session |

After each merge, update `docs/CODE_REVIEW.md` progress notes and re-run the full
verification set in §4.

## 2. v0.1 acceptance criteria (Gates)

From `docs/PRODUCT_SPEC.md` §11, checked against `prompts/RELEASE_READINESS_PROMPT.md`:

- [ ] 1. NSIS current-user installation works on Windows 10/11.
- [ ] 2. App remains available from the tray after window close.
- [ ] 3. A workspace can be added manually and discovered in bulk.
- [ ] 4. Git/JJ, files, tests and Agent processes are collected.
- [ ] 5. Agent CPU, memory and process tree are displayed.
- [ ] 6. Live activity and verified status are separate.
- [ ] 7. OpenCode runs in the constrained inspection profile.
- [ ] 8. Report yields status, phase, one next action and actor.
- [ ] 9. Facts, inferences, confidence and freshness are visible.
- [ ] 10. Agent exit / test change can trigger the simplified automatic inspection.
- [ ] 11. Weekly snapshots are appended and current state can be rebuilt.
- [ ] 12. The folder opens in Windows Explorer.
- [ ] 13. API setup and read-only compatibility tests complete.
- [ ] 14. Sensitive files are locally blocked.
- [ ] 15. IdlerDream does not write to the project workspace.
- [ ] 16. IdlerDream does not control or coordinate Agents (frozen boundary intact).

Evidence for each criterion is recorded in the release-notes "Verification summary"
and in the final acceptance report.

## 3. Version bump (Gate, only at release execution time)

Current versions at drafting time (2026-08-03):

| File | Current | Target |
|------|---------|--------|
| `package.json` (root) | `0.1.0-dev` | `0.1.0` |
| `apps/desktop/package.json` | `0.1.0-dev` | `0.1.0` |
| `package-lock.json` (root + workspaces) | `0.1.0-dev` | `0.1.0` |
| `packages/protocol/package.json` | `0.1.0` | unchanged |
| `apps/sidecar/pyproject.toml` | `0.1.0` | unchanged |
| `apps/sidecar/idlerdream/__init__.py` | `0.1.0` | unchanged |
| `apps/sidecar/idlerdream/api.py` (FastAPI `version=`) | `0.1.0` | unchanged |

Commands (PowerShell, after merging remaining CRs):

```powershell
# Edit the three files above to 0.1.0, then:
npm install   # syncs package-lock.json workspace versions
npm run typecheck
npm run build
```

Commit the version bump separately:

```text
chore: bump version to 0.1.0 for release
```

## 4. Final validation set (Gates)

Run on a clean checkout of `main` at the release commit, Windows 10/11 x64:

```powershell
# Sidecar
python -m pytest apps/sidecar/tests
python scripts/verify_assets.py
ruff check apps/sidecar/idlerdream apps/sidecar/tests apps/sidecar/launcher.py

# Desktop
npm install
npm run typecheck
npm run build

# Packaged Sidecar exe
powershell -File scripts/build-sidecar.ps1
python -m pytest apps/sidecar/tests -k packaged

# NSIS installer smoke test (after `npm run dist`)
$installer = (Get-ChildItem "apps/desktop/dist/*Setup*.exe" | Select-Object -First 1).FullName
powershell -File scripts/smoke-installer.ps1 -InstallerPath $installer -AppIdleSeconds 10
```

Expected (state 2026-08-09): sidecar tests **114 passed, 1 skipped**
(packaged-exe smoke test runs only after `scripts/build-sidecar.ps1`); asset
verification passed; typecheck passed; build passed; UI tests 12 passed; CI all green.

## 5. CI gates (Blocker)

Confirm on `main` before tagging:

- [ ] `sidecar` job (ubuntu): pytest + verify_assets + ruff — green
- [ ] `desktop` job (windows): npm install + typecheck + build — green
- [ ] `sidecar-packaging` job (windows): PyInstaller build + packaged-exe smoke test — green
- [ ] `windows-installer` job (windows): NSIS build + install/uninstall smoke test — green

```powershell
gh run list --repo OasisSaber/IdlerDream --branch main --limit 10
```

## 6. Tag and release (Gate — executes the release)

Only after §1–§5 are green:

```powershell
git checkout main
git pull --ff-only
# confirm the version bump commit is present (see §3)

git tag -a v0.1.0 -m "IdlerDream v0.1.0 — initial release"
git push origin v0.1.0

# Build the installer artifact on CI (windows-installer job) and download it:
gh run download <run-id> --repo OasisSaber/IdlerDream -n idlerdream-setup

# Create the GitHub release with the release notes:
gh release create v0.1.0 "apps/desktop/dist/IdlerDream Setup 0.1.0.exe" ^
  --repo OasisSaber/IdlerDream ^
  --title "IdlerDream v0.1.0" ^
  --notes-file docs/RELEASE_NOTES_v0.1.0.md
```

Release notes body: `docs/RELEASE_NOTES_v0.1.0.md` (copy into the release; do not
include the DRAFT banner).

## 7. Post-release (Post)

- [ ] Mark `## [0.1.0]` in `CHANGELOG.md` as released (remove "pending tag" note).
- [ ] Set repo topics/description per `GITHUB_REPOSITORY_SETUP.md`.
- [ ] Keep the repository private until the threat model and installer are validated.
- [ ] Enable secret scanning and Dependabot alerts; protect `main` (require PRs + CI).
- [ ] Convert remaining open findings into issues if not already tracked.
- [ ] Do not add an open-source license until the intended license is selected.
- [ ] Decide the next milestone against `docs/IMPLEMENTATION_PLAN.md`
      (Milestone 3+ work: watchers, throttling, automatic inspection, resilience).

## 8. Rollback / re-publish

- If the tag or release is wrong: `gh release delete v0.1.0` and
  `git tag -d v0.1.0 && git push origin :v0.1.0` (only before consumers exist).
- Installer artifacts are per-run; re-download from the `windows-installer` job after
  any rebuild.
