# ADR 002: Tool Execution UI Tracking System

**Status:** Accepted
**Date:** 2025-09-30
**Deciders:** Project Team
**Tags:** ui, architecture, user-experience

---

## Context

After implementing the policy-aware architecture (ADR-001), we needed a way to display tool execution status and history in the UI. The original implementation used simple pop-up notifications, but users needed:

### User Pain Points

**Lack of Visibility:**
- Pop-up notifications disappeared quickly
- No way to see what tools were running
- Couldn't see parameters being passed to tools
- Lost history after notifications dismissed

**Poor Confirmation UX:**
- Confirmations used modal dialogs
- Interrupted workflow significantly
- Couldn't review multiple pending operations
- No context for why confirmation needed

**Missing History:**
- No record of successful operations
- Couldn't review what was executed
- Difficult to debug policy issues
- No timeline of tool usage

### Technical Requirements

**Integration with Policy System:**
- Must work with PolicyAwareFunctionTool
- Track execution lifecycle (pending → executing → success/failed)
- Support inline confirmations
- Show policy decisions and risk levels

**Performance:**
- Minimal impact on tool execution speed
- Support concurrent tool executions
- Efficient UI updates (don't block main thread)

**Separation of Concerns:**
- Data model independent of UI
- UI independent of execution logic
- Manager layer coordinates between them

## Decision

Implement a **three-layer architecture** for tool execution tracking:

### Architecture Layers

**1. Data Layer** (`ToolExecutionInfo`)
- Pure data models with no UI dependencies
- State machine pattern for execution lifecycle
- Parameter formatting and truncation utilities
- Immutable state tracking

**2. Coordination Layer** (`ToolExecutionManager`)
- Manages execution lifecycle
- Maintains active and historical executions
- Emits events via callbacks
- UI-agnostic (no Textual dependencies)

**3. UI Layer** (`ToolExecutionWidget`)
- Pure UI component (no business logic)
- Receives ToolExecutionInfo for display
- Compact and expanded views
- Action buttons (confirm/cancel/details)

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
Create ToolExecutionWidget
    ↓
Mount in notification area
    ↓
Tool State Changes
    ↓
Manager.update_execution()
    ↓
emit: on_execution_update(info)
    ↓
Widget.update_info()
    ↓
Tool Completes
    ↓
Manager.complete_execution()
    ↓
emit: on_execution_complete(info)
    ↓
Auto-remove after 3s (if success)
```

### State Machine

```
PENDING
    ↓ (policy requires confirmation)
CONFIRMING
    ↓ (user confirms)
EXECUTING
    ↓ (completes)
    ├─ SUCCESS
    ├─ FAILED
    └─ CANCELLED

Or:
PENDING
    ↓ (policy blocks)
BLOCKED
```

### Widget Display Modes

**Compact View (Default):**
- Tool name with status icon
- Risk level badge
- Inline parameters (truncated)
- Action buttons (if confirming)

**Expanded View:**
- All parameters in detail
- Safety checks being run
- Policy decision details
- Full error messages

### Event-Driven Integration

**Manager Callbacks:**
```python
on_execution_start(info: ToolExecutionInfo)
on_execution_update(info: ToolExecutionInfo)
on_execution_complete(info: ToolExecutionInfo)
on_confirmation_required(info: ToolExecutionInfo, decision: PolicyDecision)
```

**Widget Callbacks:**
```python
on_confirm(info: ToolExecutionInfo)
on_cancel(info: ToolExecutionInfo)
on_details(info: ToolExecutionInfo)
```

### History Management

- Keep last 100 executions in memory
- Auto-remove successful executions after 3 seconds
- Keep failed/blocked executions until manually dismissed
- LRU eviction for history overflow

## Consequences

### Positive

**Better User Experience:**
- Always see what's happening
- Review parameters before confirmation
- Understand why operations blocked
- Learn from execution history

**Inline Confirmations:**
- No modal interruptions
- See context while deciding
- Can review multiple pending operations
- Better for low/medium risk operations

**Debugging:**
- Clear execution timeline
- See exact parameters used
- Understand policy decisions
- Trace errors to source

**Separation of Concerns:**
- Data model can be tested without UI
- UI can be tested with mock data
- Manager coordinates without coupling
- Easy to swap UI framework later

**Type Safety:**
- Full type hints throughout
- Dataclasses for data models
- Enums for state machine
- Protocol types for callbacks

### Negative

**Complexity:**
- Three layers instead of one
- More files to maintain (8 new files)
- Learning curve for contributors

**Memory Usage:**
- History kept in memory
- Widget objects not immediately freed
- ~1-2KB per execution tracked

**UI Real Estate:**
- Notification area takes screen space
- Can accumulate many widgets
- Need scrolling for many executions

### Risks

**Risk 1: Widget Leak**
- **Impact:** Medium - memory growth over time
- **Mitigation:**
  - Auto-remove successful executions
  - Max history limit (100)
  - Clear API to remove widgets

**Risk 2: Event Ordering**
- **Impact:** Low - UI updates out of order
- **Mitigation:**
  - Single-threaded event handling
  - State transitions validated
  - Tests cover concurrent executions

**Risk 3: Performance with Many Executions**
- **Impact:** Low - UI slowdown with 100+ widgets
- **Mitigation:**
  - Virtualized scrolling (if needed)
  - Aggressive auto-removal
  - History limit enforcement

### Neutral

**Testing:**
- 67 new tests for UI components
- Data model tests (30)
- Manager tests (22)
- Widget tests (13)
- Integration tests (4)

**Replaced:**
- Simple pop-up notifications
- Modal confirmation dialogs (for low/medium risk)
- Old notification area (static text)

## Alternatives Considered

### Alternative 1: Single ToolExecutionDisplay Class

Combine data, manager, and UI into one class.

**Pros:**
- Simpler architecture
- Fewer files
- Easier to understand initially

**Cons:**
- Tight coupling
- Hard to test
- Can't swap UI framework
- Violates single responsibility

**Why Rejected:** Would make testing and maintenance harder long-term.

### Alternative 2: Keep Modal Dialogs for Confirmations

Continue using modal ConfirmationDialog for all confirmations.

**Pros:**
- Consistent with current UX
- Clear decision point
- Already implemented

**Cons:**
- Interrupts workflow
- Can't review multiple operations
- Poor for frequent operations

**Why Rejected:** User feedback indicated modals were too disruptive for low/medium risk operations.

### Alternative 3: Reactive Properties Instead of Callbacks

Use Textual's reactive properties for state updates.

**Pros:**
- More "Textual-like"
- Automatic UI updates
- Less boilerplate

**Cons:**
- Couples manager to Textual
- Harder to test without UI
- Performance issues found in testing
- Timing issues during mount

**Why Rejected:** Testing revealed timing issues and tight coupling to UI framework.

### Alternative 4: Message Passing Instead of Direct Callbacks

Use message bus pattern for events.

**Pros:**
- Full decoupling
- Can have multiple listeners
- Easier to add new subscribers

**Cons:**
- More complex
- Harder to debug
- Overkill for current needs

**Why Rejected:** Callbacks sufficient for current architecture; can refactor later if needed.

## Implementation Notes

### Key Files

**Data Layer:**
- `adh_cli/ui/tool_execution.py` (150 LOC)
  - `ToolExecutionState` enum
  - `ToolExecutionInfo` dataclass
  - Parameter formatting utilities

**Coordination Layer:**
- `adh_cli/ui/tool_execution_manager.py` (335 LOC)
  - `ToolExecutionManager` class
  - Lifecycle management
  - Event emission
  - History management

**UI Layer:**
- `adh_cli/ui/tool_execution_widget.py` (400 LOC)
  - `ToolExecutionWidget` class
  - Compact/expanded views
  - Action button handling
  - CSS styling

**Integration:**
- `adh_cli/core/policy_aware_function_tool.py` (45 LOC added)
  - Manager integration
  - Execution tracking calls

- `adh_cli/core/policy_aware_llm_agent.py` (60 LOC added)
  - Manager instantiation
  - Callback parameters

- `adh_cli/screens/chat_screen.py` (120 LOC added)
  - Callback implementation
  - Widget mounting
  - Confirm/cancel handling

### Testing

**Tests Added:**
- `tests/ui/test_tool_execution.py` - Data models (30 tests)
- `tests/ui/test_tool_execution_manager.py` - Manager (22 tests)
- `tests/ui/test_tool_execution_widget.py` - Widget (13 tests)
- `tests/integration/test_tool_execution_ui.py` - Integration (4 tests)

**Coverage:**
- Data layer: 100%
- Manager layer: 95%
- Widget layer: 85%
- Integration: Full workflow coverage

### Migration

**Removed:**
- Pop-up notifications from PolicyAwareLlmAgent.chat()
- Notification count tracking
- `test_notification_handler_called` (replaced by widget tests)

**Preserved:**
- Modal dialogs for high/critical risk operations
- Error notifications (still use app.notify)
- Settings screen notifications

### Configuration

**CSS Styling:**
```css
.tool-execution-widget.executing { border: solid blue; }
.tool-execution-widget.success { border: solid green; }
.tool-execution-widget.failed { border: solid red; }
.tool-execution-widget.blocked { border: solid yellow; }
```

**Auto-removal:**
- Successful executions: 3 seconds
- Failed executions: Manual dismissal
- Blocked executions: Manual dismissal

**History Limits:**
- Active executions: Unlimited
- Historical executions: 100 max
- LRU eviction when limit reached

## References

**Related ADRs:**
- ADR-001: Policy-Aware Architecture
- ADR-003: Google ADK Integration (future)

**Design Documents:**
- `docs/TOOL_UI_DESIGN.md` - Original design spec
- Conversation: Tool UI discussion (2025-01-29)

**Code:**
- Tool Execution Data: `adh_cli/ui/tool_execution.py`
- Execution Manager: `adh_cli/ui/tool_execution_manager.py`
- Execution Widget: `adh_cli/ui/tool_execution_widget.py`

**Tests:**
- Data Tests: `tests/ui/test_tool_execution.py`
- Manager Tests: `tests/ui/test_tool_execution_manager.py`
- Widget Tests: `tests/ui/test_tool_execution_widget.py`
- Integration: `tests/integration/test_tool_execution_ui.py`

**Commits:**
- Design ToolExecutionManager: `ceb6e8f`
- Wire up widgets in ChatScreen: `d21e130`
- Add integration tests: `cbe76cb`
- Remove pop-up notifications: `7f717b8`

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-01-30 | Initial decision documentation | Project Team |
