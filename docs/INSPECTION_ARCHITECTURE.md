# Filtered Snapshot Inspection Architecture

## Decision

IdlerDream no longer treats OpenCode path-matching rules as the primary boundary between the model and the real workspace.

The primary boundary is now **physical data minimization**:

```text
Real workspace
  → Sidecar candidate list
  → path containment check
  → sensitive/control-file exclusion
  → file/total budget enforcement
  → UTF-8 normalized temporary snapshot
  → isolated OpenCode HOME/config
  → read/list/glob/grep only
  → report normalizer
  → identity + fingerprint validation
  → state merger
```

## Why this fixes Issue #19

The previous policy nested a workspace path allow rule under `*: deny`. OpenCode 1.18.11 treated the blanket deny as dominant, leaving the inspector secure but blind.

The new policy grants read tools without path globs because the process working directory contains only a filtered snapshot. `external_directory` remains denied, so read tools cannot reach the original workspace or unrelated user files. The prompt context also removes the real workspace path, Agent CWD/executable/command line and arbitrary project metadata; evidence paths are converted to workspace-relative paths.

## Snapshot exclusions

Hard excluded:

- `.env*`
- key/certificate formats
- npm/PyPI credential files
- cloud credential roots already covered by `is_sensitive_path`
- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`
- `.opencode`, `.claude`, `.codex`, `.cursor`, `.windsurf`
- Copilot instruction files
- symlinks and non-regular files
- binaries and oversized files

The manifest records paths and exclusion reasons, never sensitive content.

## Budgets

Default snapshot limits:

```text
40 candidate files
200 KiB per file
2 MiB total content
```

OpenCode still has its own step/time budget. Snapshot budgets are the hard data-transfer ceiling.

## Residual risks

- OpenCode may introduce new tool names in future versions. Compatibility testing remains mandatory.
- Project source can contain prompt injection, but it cannot expand permissions. The prompt and physical snapshot boundary must both remain.
- The snapshot is writable by the OpenCode process at the filesystem level. Tool permissions deny writes, and the compatibility probe hashes it before/after. The real workspace remains physically separate.
- A project may require files beyond the snapshot budget. The report must state uncertainty rather than invent content.

## Rejected alternative

Copying the entire workspace or exposing it as an external directory with permissive reads was rejected because it reintroduces secret exposure and project-instruction loading risk.
