# ADR 020: Session and Transcript Capture

**Status:** Accepted - Implemented (Phase 1)
**Date:** 2025-10-08
**Updated:** 2025-10-18
**Deciders:** Allen, ADH CLI Maintainers
**Tags:** architecture, observability, privacy, multi-agent

> **Implementation Status (2025-10-18):** Phase 1 (MVP) implemented. `SessionRecorder` service captures chat turns and tool invocations to JSONL files in `~/.adh-cli/sessions/`. Export to markdown supported. Chat screen integration complete with Ctrl+E export shortcut. Automatic session lifecycle management (new session on chat clear). All features tested with 10 new test cases. Future phases (configuration, retention, advanced querying) remain as described below.

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

## Implementation Details (Phase 1)

### Files Created

**Core Session Module** (`adh_cli/session/`):
- `__init__.py` - Module exports
- `models.py` - Data models (`SessionMetadata`, `ChatTurn`, `ToolInvocation`)
- `recorder.py` - `SessionRecorder` service with JSONL writer

**Integration**:
- `adh_cli/screens/chat_screen.py` - Session recording integrated:
  - Records all chat turns (user/AI messages)
  - Records tool invocations on completion
  - Export action (`Ctrl+E`) to save markdown + JSONL
  - Auto-restart session on chat clear

**Tests** (`tests/session/`):
- `test_session_recorder.py` - 10 comprehensive tests covering:
  - Session initialization
  - Chat turn recording
  - Tool invocation recording
  - Buffering and flushing
  - Markdown export
  - Result truncation
  - Delegated agent tracking
  - Session loading

### Features Implemented

✅ **Session Lifecycle**:
- Auto-generated session IDs (UUID)
- Session metadata (start time, agent name)
- Automatic session creation on chat screen init
- Session close and restart on clear

✅ **Transcript Recording**:
- Chat turns (user and AI messages)
- Tool invocations (parameters, results, errors)
- Agent delegation tracking (future-ready)
- Buffered writes (configurable buffer size, default 10)

✅ **Storage**:
- JSONL format in `~/.adh-cli/sessions/`
- One line per entry for easy streaming/parsing
- Metadata at start and end of session file

✅ **Export**:
- Markdown export with formatted timestamps
- Tool executions with parameters and results
- Success/failure indicators
- Exports saved to `~/.adh-cli/exports/`
- Clipboard copy for convenience

✅ **UI Integration**:
- `Ctrl+E` keyboard shortcut
- Notifications with file paths
- Seamless integration with existing chat flow

### Features Deferred (Future Phases)

⏳ **Configuration** (Phase 2):
- Opt-in/opt-out setting
- Custom session directory
- Retention policies
- Redaction patterns

⏳ **Query API** (Phase 3):
- Load recent sessions
- Search transcripts
- Agent context retrieval
- Session viewer UI

⏳ **Maintenance** (Phase 3):
- Automatic cleanup of old sessions
- Session size limits
- Compression for archived sessions

### Test Coverage

**10 new tests** added (100% pass rate):
1. Session initialization and metadata
2. Chat turn recording
3. Tool invocation recording
4. Buffering behavior
5. Flush on close
6. Markdown export format
7. Long result truncation
8. Delegated agent tracking
9. Session loading
10. Error handling

**Total test suite**: 461 tests passing

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-10-08 | Initial decision | Allen |
| 2025-10-18 | Phase 1 implementation completed | Allen |
