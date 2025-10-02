# ADR 014: Tool Spec Registry and Separation of Concerns

Status: Accepted
Date: 2025-10-02
Authors: ADH CLI Team

## Context

Tool definitions (names, descriptions, parameters) were embedded alongside implementation functions and registered directly in `ADHApp`. This coupled metadata to code, complicated testing, and made it harder to reason about policy/safety aspects (e.g., side effects, tags), or to introspect the available tools.

## Decision

Introduce a small tools layer with explicit separation:
- `adh_cli/tools/base.py` provides `ToolSpec` and a simple in‑memory `ToolRegistry`.
- `adh_cli/tools/specs.py` contains metadata for built‑in tools and registers them via `register_default_specs()` (idempotent).
- `adh_cli/tools/shell_tools.py` continues to host the actual handlers.
- `ADHApp._register_default_tools()` now loads specs from the registry and registers them with the agent.

Each `ToolSpec` includes:
- `name`, `description`, and `parameters` (JSONSchema‑like shape)
- `handler` (callable reference)
- `tags` (e.g., filesystem/read/write) and `effects` (e.g., reads_fs, writes_fs)

## Consequences

Positive:
- Clear separation of metadata vs. logic; easier to add/update tools.
- Central place to attach policy‑relevant attributes (tags/effects).
- Idempotent registration avoids double‑registration in tests.
- Improves introspection and documentation of available tools.

Negative:
- Small amount of indirection (registry) to learn.

## Notes

- Tests updated implicitly by preserving names and handlers; all tests pass.
- Future: add validation for parameter schemas and generate docs from specs.
