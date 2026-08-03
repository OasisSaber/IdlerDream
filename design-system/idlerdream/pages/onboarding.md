# Onboarding Page Override

## Goal

Establish trust before the first model call.

## Four steps

1. Detect OpenCode
2. Configure API/model profile
3. Run read-only isolation test
4. Add first workspace

## Rules

- Explain what is local, what may be sent to the remote model, and what is always blocked.
- API Key fields must support reveal/hide and must never be written to logs.
- A failed isolation test disables deep inspection but still permits local monitoring.
- Do not auto-start inspections without explicit user confirmation.
