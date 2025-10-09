# ADR 020: Session and Transcript Capture

**Status:** Proposed
**Date:** 2025-10-08
**Deciders:** Allen, ADH CLI Maintainers
**Tags:** architecture, observability, privacy, multi-agent

---

## Context

The multi-agent pipeline (ADR-016) now delegates substantive work to specialist agents (planner, code reviewer, tester, researcher). Each delegation generates valuable intermediate outputs—plans, test summaries, research briefs—that are difficult to revisit once the immediate response is delivered. We currently rely on ephemeral chat history and scattered log messages, making it hard to:

- Reference prior findings when follow-up questions arrive minutes or hours later
- Share consistent context across agents during a single task
- Audit how a conclusion was reached when reviewing changes post hoc
- Provide users with a durable record of what the assistant executed (for compliance or knowledge capture)

Existing audit logging (PolicyAwareLlmAgent) focuses on tool authorization and policy decisions rather than synthesised transcripts. We need a first-class session capture mechanism that preserves conversations, tool calls, and delegated agent outputs in a structured, easy-to-query format while respecting privacy expectations.

## Decision

Implement an opt-in **Session Recorder** service that captures complete interaction transcripts for each ADH CLI session and exposes them to agents that need historical context.

Key elements:

1. **Session Lifecycle**
   - Generate a stable `session_id` when the orchestrator starts.
   - Store metadata (start/end timestamps, user id if provided, environment fingerprint).

2. **Transcript Model**
   - Persist every chat turn (user → orchestrator → delegate) with timestamp, role, and rendered text.
   - Persist tool invocations (tool name, parameters, truncated output, success status).
   - Persist delegation summaries (agent name, task, result, success flag).

3. **Storage & Access**
   - Write transcripts to JSONL files under `~/.adh_cli/sessions/<session_id>.jsonl` by default.
   - Provide an abstraction (`SessionArchive`) to query recent transcripts, scoped to the current repository when possible.
   - Integrate with the TUI so users can open the current session log.

4. **Agent Integration**
   - Expose a lightweight API that allows specialist agents (tester, researcher, planner) to request recent transcript snippets for context (e.g., “last tester summary”).
   - Add orchestration hooks so the orchestrator can attach prior findings when prompting follow-up agents.

5. **Privacy & Controls**
   - Off by default unless the user sets `session.capture = true` in configuration or launches with `--capture-session`.
   - Honor `session.redact_patterns` for secrets (reuse existing policy scrubbing).
   - Provide CLI commands to list, view, and delete captured sessions.

## Consequences

### Positive
- Enables richer cross-agent collaboration by reusing prior outputs.
- Simplifies audits and post-task reviews with durable transcripts.
- Creates a foundation for future analytics (e.g., summarising long-term project history).

### Negative
- Introduces storage overhead that must be managed (rotation/cleanup).
- Adds implementation complexity to the orchestration layer.

### Risks
- **Privacy leakage**: transcripts may contain sensitive data if redaction rules miss values.
  - *Mitigation*: reuse policy scrubbers, default to opt-in, document clearly.
- **Performance impact**: synchronous disk writes could slow interactions.
  - *Mitigation*: buffer writes asynchronously with backpressure.

### Neutral
- Requires a new configuration surface (session settings).
- Provides optional UI affordances (session viewer) without affecting CLI workflows when disabled.

## Alternatives Considered

### Alternative 1: Rely on existing audit logs
Audit logs focus on policy decisions and are verbose, not user-friendly. They also omit orchestrator conversation context. Rejected because they do not serve collaboration or review needs.

### Alternative 2: External observability service
Streaming transcripts to an external service (e.g., GCS, BigQuery) could centralise analytics but raises security concerns and complicates offline use. Rejected for now in favour of local, user-controlled storage.

## Implementation Notes

- Extend `ToolExecutionManager` and `AgentDelegator` to emit transcript events.
- Introduce `adh_cli/session/recorder.py` with async buffering and JSONL writer.
- Update configuration schema to include `session.capture`, `session.root_dir`, and `session.retention_days`.
- Add CLI commands (`task session-list`, `task session-clean`) for maintenance.
- Ensure unit tests cover recorder lifecycle, redaction, and retention pruning.

## References

- Related ADRs: ADR-016 (Multi-Agent Orchestration), ADR-015 (Chat-integrated Tool Execution)
- Discussion seeds: planner/tester/researcher integration work (2025-10)
- External inspiration: OpenAI session transcripts, LangChain conversation memory patterns

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-10-08 | Initial decision | Allen |
