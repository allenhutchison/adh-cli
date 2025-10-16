# ADR 015: Chat-Integrated Tool Execution with Modal Confirmations

**Status:** Accepted - Implementation Differs from Specification
**Date:** 2025-10-03
**Deciders:** Allen Hutchison
**Tags:** ui, ux, architecture, user-experience

> **Implementation Note (2025-10-14):** The core functionality and intent of this ADR are implemented correctly (tools in chat, modal confirmations, unified view), but the implementation details differ from this document. The actual implementation uses custom `ToolMessage` widgets from `chat_widgets.py` instead of Rich panels, with in-place updates rather than append-only panels. The `ToolExecutionWidget` file still exists (12,514 bytes) but appears unused. The implementation is arguably better than originally planned, but this ADR should be updated to reflect the actual architecture.

---

## Context

After implementing the tool execution UI tracking system (ADR-002) and UI-based tool confirmation (ADR-012), we have a functional but suboptimal user experience:

### Current Implementation

**Tool Execution Display:**
- Tool executions appear in `#notification-area`, a separate scrollable container above the chat input
- Uses `ToolExecutionWidget` with inline confirmation buttons (Confirm/Cancel/Details)
- Auto-removes successful executions after 3 seconds
- Failed/blocked executions stay until manually dismissed
- History is lost when widgets are removed

**Chat Log:**
- Shows user messages and AI responses only
- Uses `RichLog` widget for rendering markdown and rich content
- No indication of tool executions that occurred
- Conversation history incomplete without tool context

**Confirmation Flow:**
- Inline buttons within ToolExecutionWidget
- Uses asyncio.Future to block execution (secure, per ADR-012)
- Buttons become visible/invisible based on confirmation state
- Multiple pending confirmations can stack in notification area

### Problems Identified

**1. Fragmented Conversation View:**
- User must look in two places: chat log for messages, notification area for tools
- Context is split - hard to understand which tools relate to which messages
- Tool history disappears, can't review what happened earlier in session

**2. Visual Clutter:**
- Notification area takes valuable screen real estate
- Inline confirmation buttons add bulk to each widget
- Multiple pending tools create a crowded notification area
- Hard to focus on the conversation flow

**3. UX Inconsistency with Modern AI Chats:**
- ChatGPT, Claude, and other AI chat interfaces show tool calls inline with conversation
- Users expect to see tool executions as part of the chat history
- Our separate notification area is unfamiliar and confusing

**4. History Loss:**
- Auto-removal means users can't scroll back to see what tools executed
- Debugging requires checking audit logs instead of chat history
- Can't easily share or export conversation including tool calls

**5. Confirmation UX Issues:**
- Inline buttons discovered to be invisible (recently fixed in ce49129)
- Hard to make buttons visually prominent without disrupting chat flow
- Details button adds complexity for a rare use case
- Tabbing through multiple buttons to find the right one

### User Feedback

> "I want to see tool calls in the chat so I can understand the full conversation flow"

> "The confirmation buttons are hard to see, I had to tab to find them"

> "Can we make this more like ChatGPT where everything is in one timeline?"

> "I lost track of what tools ran earlier - wish I could scroll back and see"

## Decision

Redesign tool execution UX to integrate tool calls directly into the chat log with modal confirmations:

### Architecture Changes

#### 1. Chat-Integrated Tool Display

**Tool executions appear as Rich panels in the chat log:**

```
┌─ Chat Log ─────────────────────────────────────┐
│ You: Read the file config.json                │
│                                                │
│ ┌─ 🔧 Tool: read_file ────────────────────┐   │
│ │ ⏳ Executing...                          │   │
│ │ • file_path: "config.json"               │   │
│ └──────────────────────────────────────────┘   │
│                                                │
│ [Tool completes, panel updates:]              │
│                                                │
│ ┌─ 🔧 Tool: read_file ────────────────────┐   │
│ │ ✅ Completed (0.15s)                     │   │
│ │ • file_path: "config.json"               │   │
│ │ • result: {...}                          │   │
│ └──────────────────────────────────────────┘   │
│                                                │
│ AI: The config file contains...               │
└────────────────────────────────────────────────┘
```

**Display States:**
- **Pending/Executing:** Show spinner icon, tool name, parameters
- **Awaiting Confirmation:** Show ⚠️ icon, "Awaiting confirmation..." text
- **Success:** Show ✅ icon, execution time, result summary
- **Failed:** Show ❌ icon, error message
- **Blocked:** Show 🚫 icon, policy reason
- **Cancelled:** Show ⊗ icon, "Cancelled by user"

**Styling:**
- Use Rich Panel with distinct border color (orange/yellow vs cyan for AI)
- Leverage design system (ADR-013): `$execution-running`, `$execution-success`, etc.
- Compact by default, can add expand/collapse later
- Parameters truncated to 3 items max (like current implementation)

#### 2. Modal Confirmations

**Replace inline buttons with modal dialog:**

```python
# When confirmation required:
async def on_confirmation_required(self, info, decision):
    # Show modal dialog
    dialog = ConfirmationDialog(
        tool_name=info.tool_name,
        parameters=info.parameters,
        decision=decision
    )

    # Block until user responds
    confirmed = await self.app.push_screen_wait(dialog)

    # Resolve execution
    if confirmed:
        self.agent.execution_manager.confirm_execution(info.id)
    else:
        self.agent.execution_manager.cancel_execution(info.id)
```

**Modal Dialog (reuse existing ConfirmationDialog):**
- Already implemented in `adh_cli/ui/confirmation_dialog.py`
- Shows risk level badge, parameters, safety checks, restrictions
- Clear Confirm/Cancel buttons
- Can add keyboard shortcuts: Ctrl+Enter=confirm, Esc=cancel
- Focuses user attention on decision

**Benefits over inline buttons:**
- Modal forces clear decision point
- More space to show details
- Can't miss the confirmation request
- Familiar UI pattern (modals for important decisions)
- Removes visual clutter from chat

#### 3. Remove Notification Area

**Simplify ChatScreen layout:**

```python
# Old layout:
# - chat-container (RichLog)
# - notification-area (ToolExecutionWidgets)
# - chat-input

# New layout:
# - chat-container (RichLog + tool panels)
# - chat-input
```

- Remove `#notification-area` container entirely
- Remove `ToolExecutionWidget` (no longer needed)
- All content in unified chat log
- More screen space for conversation

#### 4. Update Callbacks

**Modify execution manager callbacks:**

```python
# ChatScreen
def on_execution_start(self, info):
    """Add tool panel to chat log (pending state)"""
    self._add_tool_message(info)
    # Track for later updates
    self.tool_messages[info.id] = info

def on_execution_update(self, info):
    """Update tool panel in chat log"""
    # RichLog is append-only, so append updated panel
    # Or use markers to identify and update
    self._update_tool_message(info)

def on_execution_complete(self, info):
    """Update tool panel to show result"""
    self._update_tool_message(info)
    # No auto-removal - permanent in chat log

async def on_confirmation_required(self, info, decision):
    """Show modal confirmation dialog"""
    dialog = ConfirmationDialog(
        tool_name=info.tool_name,
        parameters=info.parameters,
        decision=decision
    )
    confirmed = await self.app.push_screen_wait(dialog)

    if confirmed:
        self.agent.execution_manager.confirm_execution(info.id)
    else:
        self.agent.execution_manager.cancel_execution(info.id)
```

### Data Flow

```
Tool Execution Start
    ↓
PolicyAwareFunctionTool
    ↓
ToolExecutionManager.create_execution()
    ↓
emit: on_execution_start(info)
    ↓
ChatScreen.on_execution_start()
    ↓
Add tool panel to chat log (⏳ Executing...)
    ↓
Policy Requires Confirmation?
    ├─ Yes ↓
    │   emit: on_confirmation_required(info, decision)
    │       ↓
    │   ChatScreen.on_confirmation_required()
    │       ↓
    │   Show ConfirmationDialog modal
    │       ↓
    │   User confirms/cancels
    │       ↓
    │   Manager resolves Future
    │       ↓
    └─ No/After Confirmation ↓
        Tool executes
            ↓
        emit: on_execution_complete(info)
            ↓
        ChatScreen.on_execution_complete()
            ↓
        Update tool panel in chat (✅ Completed)
```

### Implementation Approach

**Phase 1: Parallel Implementation (No Breaking Changes)**
1. Add `_add_tool_message()` method to format tool panels
2. Add tool panels to chat log in `on_execution_start()`
3. Add tool updates in `on_execution_complete()`
4. Keep notification area working
5. Test and refine formatting

**Phase 2: Modal Confirmations**
1. Update `on_confirmation_required()` to show modal
2. Wire modal buttons to execution manager
3. Test confirmation flow (confirm, cancel, timeout)
4. Keep inline buttons as fallback

**Phase 3: Cleanup**
1. Remove notification area container from CSS
2. Remove ToolExecutionWidget (or repurpose for other uses)
3. Remove inline button handling
4. Update all tests

**Phase 4: Polish**
1. Add keyboard shortcuts to modal (Ctrl+Enter, Esc)
2. Improve panel formatting (colors, spacing)
3. Add expand/collapse for tool details (optional)
4. User preferences for tool display verbosity

### Handling RichLog Append-Only Nature

RichLog is append-only, so we have two options for updating tool panels:

**Option A: Append Updated Panels**
- On update/complete, append new panel with updated state
- Show progression: Executing → Completed
- Advantage: Simple, no widget tracking
- Disadvantage: Multiple panels for same tool (but shows timeline)

**Option B: Use Unique Markers**
- Track tool panel positions/markers
- On update, find and replace panel content
- Advantage: Single panel per tool
- Disadvantage: More complex, requires RichLog internals

**Decision: Start with Option A (append updates)**
- Simpler implementation
- Shows execution timeline naturally
- Can optimize to Option B later if needed
- Users can see state transitions

## Consequences

### Positive

**1. Unified Conversation View:**
- Everything in one place: messages, AI responses, tool calls
- Natural reading flow, easy to follow
- Complete conversation history including tools

**2. Better Context:**
- See exactly which tools relate to which messages
- Understand the full story of a conversation
- Easier debugging - scroll back to see what happened

**3. Permanent History:**
- Tool executions preserved in chat
- Can review any past execution
- Share/export full conversation including tools

**4. Less Visual Clutter:**
- Remove notification area entirely
- More screen space for chat
- Simpler, cleaner UI

**5. Familiar UX:**
- Matches ChatGPT, Claude, and other AI chat interfaces
- Users already know this mental model
- Reduced learning curve

**6. Better Confirmations:**
- Modal dialogs focus attention
- Clear decision point (can't miss it)
- More space for details
- Keyboard shortcuts for power users

**7. Simpler Architecture:**
- Remove ToolExecutionWidget complexity
- Fewer UI components to maintain
- Unified message rendering logic

### Negative

**1. Chat Log Can Grow Large:**
- Tools add content to chat log
- More scrolling to find older messages
- **Mitigation:** Compact display, expand on demand; future: virtualized scrolling

**2. RichLog Update Complexity:**
- Append-only widget makes updates harder
- May show multiple panels per tool
- **Mitigation:** Start with append approach, works naturally as timeline

**3. Modal Interruptions:**
- Modal confirmations interrupt flow
- Must handle modal before continuing
- **Mitigation:** That's the point - important decisions need focus

**4. Migration Effort:**
- Need to update tests
- Remove notification area
- Rewrite display logic
- **Mitigation:** Phased approach, parallel implementation first

### Risks

**Risk 1: Performance with Long Chat History**
- **Impact:** Medium - UI slowdown with 1000+ messages
- **Mitigation:**
  - RichLog handles large content well
  - Can add message limit (keep last 500)
  - Future: Implement virtualization

**Risk 2: Confusing Tool Updates (Multiple Panels)**
- **Impact:** Low - Users might see tool twice (executing, then completed)
- **Mitigation:**
  - Clear state icons (⏳ → ✅)
  - Shows progression naturally
  - Can optimize later if feedback is negative

**Risk 3: Breaking Existing Workflows**
- **Impact:** Low - Internal changes, external API same
- **Mitigation:**
  - Keep execution manager API unchanged
  - Phased rollout
  - Comprehensive testing

### Neutral

**Changes:**
- Remove ToolExecutionWidget (~400 LOC)
- Add tool panel formatting (~100 LOC)
- Update ChatScreen (~50 LOC modified)
- Update tests (~20 tests modified)

**Net Reduction:** ~250 LOC removed (simpler codebase)

## Alternatives Considered

### Alternative 1: Keep Notification Area, Add Chat Log Copy

Show tools in both places - notification area AND chat log.

**Pros:**
- Preserves current UX for users who like it
- Gradual transition
- History in chat log

**Cons:**
- Duplication - same info in two places
- More complex code
- More visual clutter
- Doesn't solve the fragmentation problem

**Rejected because:** Doesn't address core issue of fragmented view.

### Alternative 2: Notification Area with History Panel

Keep notification area, add separate history panel for past tools.

**Pros:**
- Clear separation: active vs historical
- Can review past without scrolling
- Preserve current confirmation UX

**Cons:**
- Still fragmented (3 areas: chat, active, history)
- More UI complexity
- Doesn't match familiar AI chat UX
- More screen real estate

**Rejected because:** Makes fragmentation worse, not better.

### Alternative 3: Hybrid - Chat Log + Sticky Notification

Show tools in chat log, but current pending/executing in sticky notification.

**Pros:**
- See active status prominently
- History in chat
- Best of both worlds?

**Cons:**
- Still fragmented UI
- Duplication again
- Sticky notification can obscure chat
- Complex implementation

**Rejected because:** Complexity doesn't justify marginal benefits.

### Alternative 4: Keep Inline Buttons in Chat

Put tool executions in chat but keep inline buttons (not modal).

**Pros:**
- Unified view
- No modal interruption
- Familiar from current implementation

**Cons:**
- Inline buttons hard to style (as we discovered)
- Clutters chat with buttons
- Can't show full details without disrupting flow
- Accessibility issues (tiny buttons)

**Rejected because:** We already fixed visibility issues, but UX still suboptimal. Modal is cleaner.

## Implementation Notes

### Files Modified

**adh_cli/screens/chat_screen.py** (~100 LOC modified)
- Add `_add_tool_message(info)` method
- Add `_update_tool_message(info)` method
- Update `on_execution_start()` to add chat panels
- Update `on_execution_complete()` to update panels
- Update `on_confirmation_required()` to show modal
- Remove notification area container
- Remove `_remove_execution_widget()` method
- Add `tool_messages: Dict[str, ToolExecutionInfo]` tracking

**adh_cli/ui/confirmation_dialog.py** (minor enhancements)
- Add keyboard shortcuts (Ctrl+Enter=confirm, Esc=cancel)
- Already has all needed functionality

**Tests:**
- `tests/ui/test_chat_screen.py` - Update for new flow
- `tests/integration/test_tool_execution_ui.py` - Update assertions
- Remove ToolExecutionWidget tests (no longer needed)

**Removed:**
- `adh_cli/ui/tool_execution_widget.py` (~400 LOC)
- Notification area from chat_screen.py CSS (~50 LOC)

### Tool Message Formatting

```python
def _add_tool_message(self, info: ToolExecutionInfo) -> None:
    """Add tool execution message to chat log."""
    from rich.panel import Panel
    from rich.text import Text

    # Build content
    content = Text()

    # Status line with icon
    icon = info.status_icon  # ⏳, ✅, ❌, etc.
    content.append(f"{icon} {info.status_text}\n", style="bold")

    # Parameters (compact)
    if info.parameters:
        params_text = format_parameters_inline(
            info.parameters,
            max_params=3,
            max_value_length=60
        )
        content.append(f"• {params_text}\n", style="dim")

    # Result/error (if complete)
    if info.state == ToolExecutionState.SUCCESS and info.result:
        result_preview = str(info.result)[:200]
        content.append(f"→ {result_preview}\n", style="green")
    elif info.state == ToolExecutionState.FAILED and info.error:
        content.append(f"✗ {info.error}\n", style="red")

    # Create panel
    border_style = {
        ToolExecutionState.EXECUTING: "yellow",
        ToolExecutionState.CONFIRMING: "orange",
        ToolExecutionState.SUCCESS: "green",
        ToolExecutionState.FAILED: "red",
        ToolExecutionState.BLOCKED: "red",
        ToolExecutionState.CANCELLED: "dim",
    }.get(info.state, "dim")

    panel = Panel(
        content,
        title=f"[bold]🔧 Tool: {info.tool_name}[/bold]",
        title_align="left",
        border_style=border_style,
        padding=(0, 1),
    )

    # Add to chat log
    self.chat_log.write(panel)

    # Track for updates
    self.tool_messages[info.id] = info
```

### Modal Confirmation

```python
async def on_confirmation_required(
    self,
    info: ToolExecutionInfo,
    decision: PolicyDecision
) -> None:
    """Show modal confirmation dialog."""

    # Update chat log to show "awaiting confirmation"
    self._update_tool_message(info)

    # Show modal
    dialog = ConfirmationDialog(
        tool_name=info.tool_name,
        parameters=info.parameters,
        decision=decision
    )

    # Block until user responds
    confirmed = await self.app.push_screen_wait(dialog)

    # Resolve execution
    if self.agent and hasattr(self.agent, 'execution_manager'):
        if confirmed:
            self.agent.execution_manager.confirm_execution(info.id)
        else:
            self.agent.execution_manager.cancel_execution(info.id)
```

### Testing Approach

**Unit Tests:**
- `_add_tool_message()` formats correctly
- `_update_tool_message()` updates panels
- Modal confirmation flow

**Integration Tests:**
- Full execution flow: start → confirm → complete → chat log
- Tool appearing in chat at correct time
- Modal shows on confirmation required
- Cancellation works correctly

**Manual Testing:**
- Visual appearance of tool panels
- Modal confirmation UX
- Keyboard shortcuts work
- Long chat history performance

### Configuration

No new configuration needed. Uses existing:
- Design system colors (ADR-013)
- Execution manager (ADR-002, ADR-012)
- Policy engine (ADR-001)

### Migration

**For Users:**
- Transparent - no action required
- Tool executions appear in chat now
- Modal confirmations instead of inline
- History preserved automatically

**For Developers:**
- Update any code expecting notification area
- Update tests expecting ToolExecutionWidget
- No API changes to execution manager

## References

**Related ADRs:**
- ADR-001: Policy-Aware Architecture (policy engine)
- ADR-002: Tool Execution UI Tracking (ToolExecutionInfo, manager)
- ADR-012: UI-Based Tool Confirmation (asyncio.Future mechanism)
- ADR-013: UI Design System (colors, themes)

**Design Inspiration:**
- ChatGPT: Shows tool calls inline with conversation
- Claude: Tool use displayed as part of chat
- Cursor IDE: Inline tool execution in chat

**Implementation:**
- `adh_cli/screens/chat_screen.py` - Main changes
- `adh_cli/ui/confirmation_dialog.py` - Modal dialog
- `adh_cli/ui/tool_execution.py` - Data models (unchanged)

**Textual Widgets:**
- RichLog: https://textual.textualize.io/widgets/rich_log/
- ModalScreen: https://textual.textualize.io/api/screen/#textual.screen.ModalScreen
- Rich Panel: https://rich.readthedocs.io/en/latest/panel.html

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-10-03 | Initial decision and design | Allen Hutchison |
