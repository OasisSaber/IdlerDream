# Security Review Prompt

Review IdlerDream’s read-only inspection boundary. Focus on practical bypasses, not generic advice.

## Review targets

- `apps/sidecar/idlerdream/security/`
- `apps/sidecar/idlerdream/inspection/opencode.py`
- `apps/sidecar/idlerdream/inspection/prompt.py`
- subprocess launch/cancel code
- IPC/control channel
- raw-report storage
- API credential handling

## Threats

- repository prompt injection
- project OpenCode config overriding injected policy
- plugin/MCP/instruction loading
- path traversal or symlink escape
- secret-file reads and secret leakage through logs/errors
- Bash wildcard bypass
- shell injection
- lingering child processes after cancel/quit
- report identity/fingerprint spoofing
- local renderer/web content reaching privileged control
- raw report remaining decryptable after expiry

## Required output

Rank findings as critical/high/medium/low. For each:

- exact file and code path
- attack precondition
- realistic consequence
- minimal patch
- regression test

Do not claim the app has an absolute sandbox. Distinguish policy enforcement, detection and OS isolation.
