# Report Normalization Specification

## Principle

The normalizer repairs only deterministic representation variance. It never invents project identity, workspace identity or core status.

## Hard-invalid fields

A report is rejected when any of the following cannot be validated:

- `project_id`
- `workspace_fingerprint`
- `core_status`
- JSON object structure

Expected identity is supplied to the parser and checked before state merge.

## Safe normalization

Allowed repairs include:

- camelCase aliases to snake_case
- Markdown fenced JSON extraction
- extra prose around a balanced JSON object
- `null` arrays to empty arrays
- confidence percentages to fractions
- actor aliases such as `AI` → `agent`
- inference evidence without `kind` → `kind=model`
- string evidence → evidence object
- missing phase → `unknown`
- missing summary → explicit generic partial-report message
- missing next action → `None` with warning
- JSON5-style formatting (unquoted keys, single-quoted strings, trailing commas) → repaired with a PARTIAL warning

## Evidence handling

- Inferences are always `deterministic=false`.
- An unclassified “fact” with a path becomes `kind=file`.
- An unclassified “fact” without a path is moved to inferences, not accepted as deterministic evidence.
- Invalid evidence without a summary is dropped and recorded.

## Quality

### Full

No normalization warnings.

### Partial

At least one deterministic repair or dropped non-core field. The state merger caps confidence at `0.75` and exposes warnings in the UI.

### Failed

No candidate passes hard identity and Schema checks. Current state is not replaced by a fabricated report.

## Diagnostics

Encrypted raw reports include:

- candidate count
- decoded candidate count
- selected candidate
- normalizations
- dropped items
- validation errors
- normalizer version
- resulting quality
