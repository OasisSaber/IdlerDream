# Project Detail Page Override

## Goal

Provide evidence sufficient to audit why IdlerDream recommends the next action.

## Structure

- Header: identity, path, open folder, inspect
- Hero: verified state + runtime summary
- Main: facts/inferences, process tree, Git/JJ/tests
- Side: cycle and acceptance criteria, security permission, relevant history

## Rules

- Facts use green accent; model inference uses purple accent.
- Runtime summary never uses success/failure color unless the underlying fact is deterministic.
- Process tree is virtualized when large.
- Paths and commands are redacted and monospaced.
- Evidence references show file path/hash/test name, not permanently stored source excerpts.
