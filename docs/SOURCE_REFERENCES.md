# External source references

External references are used only for volatile tool behavior; IdlerDream product decisions remain defined by the local product and architecture documents.

## OpenCode

- CLI: `https://opencode.ai/docs/cli/`
  - verifies non-interactive `opencode run`, raw JSON event output through `--format json`, and `--pure` plugin isolation.
- Permissions: `https://opencode.ai/docs/permissions/`
  - documents allow/ask/deny, parsed Bash-command matching, simple wildcards, last-match precedence, agent permission overrides and `external_directory` behavior.
- Rules: `https://opencode.ai/docs/rules/`
  - documents automatic local `AGENTS.md`/`CLAUDE.md` discovery by walking upward from the current directory.
- Configuration: `https://opencode.ai/docs/config/`
  - documents configuration precedence and `OPENCODE_CONFIG_CONTENT` runtime overrides.

These sources motivated the reviewed adapter changes: no Bash wildcard allowlist, isolated working directory and home, explicit external-directory permission, disabled external plugins/Claude compatibility, and runtime-injected permissions.
