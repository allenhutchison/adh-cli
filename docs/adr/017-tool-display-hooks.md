# ADR 017: Tool-Provided Display Hooks for Execution Updates

**Status:** Proposed - Not Implemented
**Date:** 2025-10-05
**Deciders:** Project Team
**Tags:** architecture, ui, developer-experience, observability

> **Implementation Status (2025-10-14):** This ADR describes a proposed enhancement that has not yet been implemented. The `AdhCliBaseTool` class, `ToolDisplayPayload`, `ToolInvocationContext`, and display hook system do not exist. Tools cannot currently provide custom display formatting for confirmations and execution updates. This remains future work to enhance the tool execution UX.

---

## Context

Policies and UI flows defined in ADR-001, ADR-002, ADR-012, and ADR-015 ensure that tool execution is policy-aware, observable, and integrated into the chat timeline. However, the display content shown during these phases is currently produced by generic formatters in `ToolExecutionManager` and `ToolExecutionWidget`. This leads to several issues:

- **Limited context fidelity:** Default formatting only surfaces raw arguments and truncated results. For tools with complex payloads (e.g., structured edits, shell outputs), users cannot review the most relevant information without leaving the UI or waiting for completion.
- **Inconsistent expectations:** ADR-015 integrates tool panels directly in the chat log, but the data shown is still generic. Users have requested richer previews (e.g., diff snippets for edit tools, initial lines for file writes) similar to modern IDE assistants.
- **Tool author constraints:** Tool builders cannot influence what appears in confirmations or completion summaries without modifying shared UI code, increasing coupling and slowing iteration.
- **Safety signals:** ADR-012 requires that confirmations provide enough detail for a human to make an informed decision. Generic parameter dumps may omit meaningful risk indicators (e.g., target file size, HTTP destination).

At the same time, ADR-014 introduced the tool spec registry, emphasizing explicit metadata owned by each tool. Extending that principle to the display layer aligns responsibility with the tool that best understands its domain.

## Decision

Introduce **tool-provided display hooks** that allow each tool to emit tailored preview and completion payloads while preserving a consistent UI contract.

### New Base Tool Interface

Introduce `AdhCliBaseTool(BaseTool)` within `adh_cli/tools/base.py`. This project-owned subclass exposes two optional coroutine hooks while preserving the external ADK contract:

- `async def get_pre_call_display(self, *, invocation: ToolInvocationContext) -> ToolDisplayPayload`: Called immediately after policy approval (and before execution) so the UI can render confirmation and "about to run" panels.
- `async def get_post_call_display(self, *, invocation: ToolInvocationContext, result: ToolResult) -> ToolDisplayPayload`: Called after execution (success, failure, or cancellation) so the UI can present contextual outcomes.

All built-in tools will inherit from `AdhCliBaseTool` (or an adapter subclass) so the new hooks are available without modifying the upstream ADK `BaseTool` directly.

Key points:

- Both hooks return a structured `ToolDisplayPayload` dataclass with fields such as `title`, `summary`, `details`, `content_blocks`, and `safety_highlights`. This structure extends the formatting guidance from ADR-013 and ensures widgets can render consistent layouts.
- Default implementations in `AdhCliBaseTool` fall back to the current generic formatting to maintain backward compatibility for tools we have not customized yet.
- `ToolDisplayPayload` supports lightweight rich content (markdown text, table rows, diff hunks, truncated text blobs) but intentionally avoids arbitrary Textual widgets to keep tools UI-agnostic.
- For third-party ADK tools that cannot change their inheritance tree, we provide thin adapter subclasses of `AdhCliBaseTool` to delegate execution while supplying display hooks.

### Invocation Flow Integration

- `PolicyAwareFunctionTool` (ADR-001, ADR-012) invokes `get_pre_call_display` once the policy engine authorizes execution. Its payload feeds the confirmation dialog (when required) and the inline chat panel (per ADR-015).
- `ToolExecutionManager` stores both payloads on `ToolExecutionInfo` so UI components can access snapshots for history timelines (ADR-002) and chat rendering.
- Upon completion, `ToolExecutionManager` resolves the execution with the tool's `result` (success, error, or cancellation metadata) and then awaits `get_post_call_display` to update the chat panel and history entry.
- For streaming tools, the hooks may be called multiple times (e.g., intermediate updates). The contract will initially require a single invocation per phase, with future ADRs extending for streaming scenarios if needed.

### Tool Responsibilities

- Each tool module (e.g., `adh_cli/tools/shell_tools.py`, `adh_cli/tools/agent_tools.py`) overrides the hooks to format domain-specific previews:
  - `write_file` can summarize target path, diff preview, byte counts, and a snippet of new content (first N lines).
  - Edit tools can show unified diffs against the current file state.
  - `web_search` can display the query string, provider, and top suggested snippets.
  - Shell execution tools can surface the command and intended working directory before execution, then stream or summarize stdout/stderr afterward.
- Tool authors may reuse shared helpers (e.g., diff generation utilities) to keep payloads concise and consistent.

### API Surface

- Add `ToolDisplayPayload` and `ToolInvocationContext` dataclasses under `adh_cli/tools/models.py` (or similar) to encapsulate the data passed into the hooks.
- Extend the `ToolSpec` schema with a nested `ToolDisplayContract` dataclass (e.g., fields `supports_pre_call_display: bool`, `supports_post_call_display: bool`, `requires_confirmation_preview: bool`). The registry asserts that an `adk_tool_factory` returns an `AdhCliBaseTool` subclass whose hooks satisfy the declared contract, enabling automated validation.

## Consequences

### Positive
- **Richer confirmations:** Humans see the exact context they need to approve or cancel actions, reinforcing ADR-012's safety goals.
- **Improved UX parity:** Aligns ADH CLI with industry-leading assistants that display tool-specific previews, supporting ADR-015's chat-integrated design.
- **Tool autonomy:** Tool maintainers control their presentation logic without editing shared UI code, promoting modularity per ADR-001.
- **Extensible history:** The same payloads populate execution history views (ADR-002), yielding more useful audit trails.

### Negative
- **Increased tool complexity:** Tool implementations must now handle display formatting, adding development overhead.
- **Async hook latency:** Poorly optimized hooks could slow perceived responsiveness before execution starts.

### Risks
- **Inconsistent visuals across tools:** Without guardrails, payloads may diverge stylistically. *Mitigation:* provide shared helper utilities and validate payloads against ADR-013's design tokens.
- **Missing payloads causing regressions:** Legacy or third-party tools might not override hooks. *Mitigation:* default base implementations plus linting to flag uncustomized high-risk tools.

### Neutral
- **Event sequencing:** Execution lifecycle remains the same; only display data sources change.
- **Telemetry volume:** Additional payload data stored for history is expected but manageable.

## Alternatives Considered

### Alternative 1: Centralized Formatter Registry
Maintain a registry that maps tool names to formatter functions within the UI layer.

**Rejected because** it recreates tight coupling between UI and tool logic, duplicates knowledge already present in tool modules, and complicates packaging of external tools.

### Alternative 2: Prompt-Only Display Instructions
Embed display hints in tool descriptions and rely on the LLM to narrate relevant information.

**Rejected because** this contradicts ADR-012's requirement for enforceable confirmations and yields inconsistent, non-deterministic outputs.

### Alternative 3: Expanded Policy Metadata
Have the policy engine enrich `PolicyDecision` objects with display data.

**Rejected because** policy evaluation focuses on safety and access control, not UX formatting. Mixing concerns would bloat the policy layer and still require tool authors to contribute data indirectly.

## Implementation Notes

- Update `adh_cli/tools/base.py` to expose `AdhCliBaseTool` with the new hook signatures and default implementations.
- Introduce `adh_cli/tools/display_payload.py` (or similar) for shared dataclasses and helper utilities (diff formatting, truncation, ANSI stripping).
- Modify `adh_cli/core/policy_aware_function_tool.py` to request pre/post payloads and attach them to `ToolExecutionInfo` records.
- Ensure `ToolExecutionManager` and chat rendering components respect the new payload structure while maintaining backward compatibility.
- Add unit tests covering default payload generation, tool-specific overrides, and failure fallbacks.
- Document hook usage in `docs/TOOL_UI_DESIGN.md` and `docs/TOOLS.md` for tool developers.

## References

- Related ADRs: ADR-001, ADR-002, ADR-012, ADR-013, ADR-014, ADR-015
- Design documents: `docs/TOOL_UI_DESIGN.md`
- External resources: Textual Rich content guidelines – https://textual.textualize.io/guide/widgets/

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-10-05 | Initial decision | Project Team |
