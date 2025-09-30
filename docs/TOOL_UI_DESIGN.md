# Tool Execution UI Design

## Overview

Enhanced UI for tool execution notifications and confirmations with two main components:
1. **Inline Notifications** - Quick, non-intrusive notifications in the notification area
2. **Tool History Timeline** - Comprehensive view accessible via command palette

## Design Principles

- **Non-intrusive**: Automatic tools show brief notifications that auto-dismiss
- **Context-aware confirmations**: Low-risk inline, high-risk modal
- **Transparency**: Always show what parameters are being used
- **Discoverability**: Full history available when needed

---

## 1. Enhanced Tool Notification Widget

### States

#### 1.1 Automatic Execution (No Confirmation)
```
┌─ Tool Execution ──────────────────────────────────────┐
│ 🔧 read_file                          [●●● Executing] │
│ file_path: adh_cli/services/adk_ag... | max_lines: 100│
└────────────────────────────────────────────────────────┘
```
- Shows immediately when tool starts
- Parameters shown inline, truncated to fit
- Animated spinner during execution
- Auto-dismisses after 2 seconds when complete

#### 1.2 Low-Risk Confirmation (Inline)
```
┌─ Confirmation Required ───────────────────────────────┐
│ ⚠️  write_file                          Risk: MEDIUM   │
│ file_path: test.txt | content: "Hello worl..." (47ch) │
│                                                        │
│              [✓ Confirm]  [✗ Cancel]  [📋 Details]    │
└────────────────────────────────────────────────────────┘
```
- Stays visible until user responds
- Buttons for confirm/cancel/details
- "Details" expands to show full parameters
- Risk level shown with color coding

#### 1.3 Expanded Details View
```
┌─ Tool Details ────────────────────────────────────────┐
│ ⚠️  write_file                          Risk: MEDIUM   │
│                                                        │
│ Parameters:                                            │
│   • file_path: test.txt                                │
│   • content: "Hello world, this is a test file with   │
│              some content that is longer..."           │
│   • create_dirs: true                                  │
│                                                        │
│ Safety Checks:                                         │
│   ✓ BackupChecker - Will create backup                │
│   ✓ DiskSpaceChecker - 1.2GB available                │
│                                                        │
│              [✓ Confirm]  [✗ Cancel]  [▲ Collapse]    │
└────────────────────────────────────────────────────────┘
```
- Shows full parameter values
- Shows safety check results
- Can collapse back to compact view

#### 1.4 Execution Complete
```
┌─ Tool Execution Complete ─────────────────────────────┐
│ ✅ write_file                            [Completed]   │
│ Wrote 47 bytes to test.txt                             │
└────────────────────────────────────────────────────────┘
```
- Brief success message
- Auto-dismisses after 2 seconds

#### 1.5 Execution Failed
```
┌─ Tool Execution Failed ───────────────────────────────┐
│ ❌ read_file                             [Failed]      │
│ FileNotFoundError: File not found: missing.txt        │
│                                          [View Details]│
└────────────────────────────────────────────────────────┘
```
- Shows error message (truncated)
- Stays visible longer (5 seconds) or until dismissed
- Can view full error in details

### Risk Level Handling

| Risk Level | Supervision Level | UI Treatment |
|-----------|------------------|--------------|
| NONE      | AUTOMATIC        | Brief notification, auto-execute |
| LOW       | AUTOMATIC/NOTIFY | Brief notification, auto-execute |
| LOW       | CONFIRM          | Inline confirmation (compact) |
| MEDIUM    | CONFIRM          | Inline confirmation (expanded by default) |
| HIGH      | CONFIRM/MANUAL   | **Modal dialog** |
| CRITICAL  | MANUAL/DENY      | **Modal dialog** or blocked |

### Parameter Truncation Rules

1. **Inline display** (state 1.1, 1.2):
   - Max 50 chars per parameter value
   - Show char count if truncated: `(123ch)`
   - Multiple params separated by ` | `
   - Max 2-3 params shown inline

2. **Expanded display** (state 1.3):
   - Max 200 chars per parameter value
   - Multi-line for long strings
   - Binary/large data: show type and size
   - Arrays/objects: show count

3. **Truncation indicators**:
   - Text: `"Hello worl..."`
   - Binary: `<binary data, 1.2MB>`
   - Long list: `[item1, item2, ... 15 more]`
   - Object: `{key1: value1, ... 8 more keys}`

---

## 2. Tool History Timeline View

### Access

- **Keybinding**: `Ctrl+H` (tool history)
- **Command Palette**: `/history` or `/tools`
- **Screen**: New `ToolHistoryScreen` modal

### Layout

```
╔═══════════════════════════════════════════════════════════════════════╗
║                      Tool Execution History                           ║
║  [All] [Success] [Failed] [Blocked]          [Clear] [Export] [Close] ║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  15:32:45  ✅ list_directory                             (0.02s)     ║
║    → directory: . | show_hidden: false                               ║
║    ← 7 items found                                                   ║
║                                                                       ║
║  15:32:47  ✅ read_file                                  (0.01s)     ║
║    → file_path: adh_cli/app.py | max_lines: 100                      ║
║    ← 325 lines read                                                  ║
║                                                                       ║
║  15:32:49  ⚠️  write_file                   [CONFIRMED]  (0.03s)     ║
║    → file_path: test.txt | content: "..." (47ch)                     ║
║    ← Success: Wrote 47 bytes                                         ║
║                                                                       ║
║  15:32:52  ❌ read_file                                  (0.01s)     ║
║    → file_path: missing.txt                                          ║
║    ← FileNotFoundError in read_file(file_path='missing.txt'):        ║
║      File not found: missing.txt                                     ║
║                                                                       ║
║  15:32:55  🚫 delete_file                     [BLOCKED]              ║
║    → file_path: important.txt | confirm: true                        ║
║    ← PermissionError: Tool blocked by policy                         ║
║                                                                       ║
║  [Scroll for more...]                                                ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
```

### Features

1. **Timeline entries** show:
   - Timestamp
   - Status icon (✅ success, ❌ error, 🚫 blocked, ⚠️ confirmed)
   - Tool name
   - Confirmation indicator if required
   - Duration
   - Input parameters (→)
   - Output/result (←)

2. **Filtering**:
   - All: Show everything
   - Success: Only completed successfully
   - Failed: Only errors
   - Blocked: Only policy-blocked

3. **Actions**:
   - Click entry to expand full details
   - Clear history
   - Export to file (JSON/CSV)

4. **Entry details** (expanded):
```
╔═══════════════════════════════════════════════════════════════════════╗
║  Tool Execution Details                                        [Close]║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  Tool: read_file                                                      ║
║  Status: ❌ Failed                                                    ║
║  Timestamp: 2024-01-15 15:32:52                                       ║
║  Duration: 0.01s                                                      ║
║                                                                       ║
║  Parameters:                                                          ║
║    file_path: adh_cli/services/missing.txt                            ║
║    max_lines: null                                                    ║
║                                                                       ║
║  Error:                                                               ║
║    FileNotFoundError in read_file(                                    ║
║      file_path='adh_cli/services/missing.txt'                         ║
║    ): File not found: adh_cli/services/missing.txt                    ║
║                                                                       ║
║  Stack Trace:                                                         ║
║    [Show full traceback]                                              ║
║                                                                       ║
║  Policy Decision:                                                     ║
║    Allowed: true                                                      ║
║    Supervision: AUTOMATIC                                             ║
║    Risk: LOW                                                          ║
║                                                                       ║
║  Audit Log Entry:                                                     ║
║    [Copy to clipboard]                                                ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
```

---

## 3. Data Model

### ToolExecutionRecord

```python
@dataclass
class ToolExecutionRecord:
    """Record of a tool execution for history tracking."""

    id: str  # Unique ID
    timestamp: datetime
    tool_name: str
    parameters: Dict[str, Any]

    # Policy & Safety
    policy_decision: PolicyDecision
    requires_confirmation: bool
    confirmed: Optional[bool]  # None if no confirmation needed

    # Execution
    status: Literal["pending", "executing", "success", "failed", "blocked"]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration: Optional[float]  # seconds

    # Results
    result: Optional[Any]
    error: Optional[str]
    error_type: Optional[str]

    # Additional context
    user_id: str
    session_id: str
```

### ToolExecutionHistory

```python
class ToolExecutionHistory:
    """Manages history of tool executions."""

    def __init__(self, max_entries: int = 1000):
        self.entries: List[ToolExecutionRecord] = []
        self.max_entries = max_entries

    def add_execution(self, record: ToolExecutionRecord) -> None:
        """Add execution record to history."""

    def get_recent(self, limit: int = 50) -> List[ToolExecutionRecord]:
        """Get most recent executions."""

    def filter_by_status(self, status: str) -> List[ToolExecutionRecord]:
        """Filter executions by status."""

    def export_to_json(self, path: Path) -> None:
        """Export history to JSON file."""

    def clear(self) -> None:
        """Clear all history."""
```

---

## 4. Implementation Plan

### Phase 1: Enhanced Notifications (Core)

1. **Create `ToolExecutionWidget`** (replaces `PolicyNotification`)
   - States: pending, executing, confirming, complete, failed
   - Inline confirmation buttons for low/medium risk
   - Parameter display with truncation
   - Expandable details view

2. **Update `PolicyAwareFunctionTool`**
   - Add notification callbacks for each state
   - Pass tool execution context (parameters, decision)

3. **Update notification flow**
   - `PolicyAwareLlmAgent.chat()` creates widget on tool call
   - Updates widget state through execution
   - Auto-dismiss on completion

### Phase 2: Tool History Tracking

1. **Create `ToolExecutionRecord` and `ToolExecutionHistory`**
   - Add to app state
   - Track all executions

2. **Update `PolicyAwareFunctionTool`**
   - Create record on tool start
   - Update record through execution
   - Store in history

### Phase 3: History Timeline View

1. **Create `ToolHistoryScreen`**
   - Timeline display of all executions
   - Filtering and search
   - Expandable details

2. **Add command palette integration**
   - Register `/history` command
   - Add `Ctrl+H` keybinding

### Phase 4: Polish

1. **Parameter formatting**
   - Implement truncation rules
   - Smart formatting for different types

2. **Export functionality**
   - JSON export
   - CSV export for analysis

3. **Performance**
   - Limit history size
   - Lazy loading for large histories

---

## 5. Questions & Decisions

### Decided:
✅ Low-risk confirmations: inline in notification area
✅ Parameter values: truncate long values
✅ History view: accessible via command palette
✅ Notification persistence: dismiss quickly, history preserves all
✅ Layout: Option 1 (enhanced notifications in existing area)

### To Decide:
- [ ] Max notification height when expanded?
- [ ] Should history persist across app restarts?
- [ ] Export format preferences?
- [ ] Should we show parallel tool executions side-by-side?

---

## 6. Example User Flows

### Flow 1: Automatic Tool (read_file)
1. User asks: "What's in app.py?"
2. Agent calls `read_file`
3. Notification appears: `🔧 read_file | file_path: app.py`
4. Completes in 0.01s
5. Shows: `✅ read_file [Completed]`
6. Auto-dismisses after 2s
7. Agent shows file contents in chat

### Flow 2: Low-Risk Confirmation (write_file)
1. User asks: "Create test.txt with hello world"
2. Agent calls `write_file` (MEDIUM risk)
3. Notification appears with inline confirm:
   ```
   ⚠️  write_file                    Risk: MEDIUM
   file_path: test.txt | content: "..." (11ch)

           [✓ Confirm]  [✗ Cancel]  [📋 Details]
   ```
4. User clicks "Details" to see full content
5. User clicks "Confirm"
6. Executes and shows: `✅ write_file [Completed]`
7. Auto-dismisses after 2s

### Flow 3: High-Risk Modal (execute_command)
1. User asks: "Run npm install"
2. Agent calls `execute_command` (HIGH risk)
3. **Modal dialog** appears (not inline):
   - Full screen overlay
   - Detailed view of command
   - Safety warnings
   - Confirm/Cancel buttons
4. User confirms in modal
5. Modal closes
6. Brief notification during execution
7. Shows result in chat

### Flow 4: Reviewing History
1. User presses `Ctrl+H`
2. Tool History screen opens
3. Shows timeline of all tool executions
4. User clicks on failed `read_file`
5. Expands to show full error details
6. User clicks "Copy to clipboard"
7. User closes history screen

---

## 7. Visual Mockup Summary

**Compact inline (automatic):**
`🔧 read_file | file_path: app.py [●●● Executing]`

**Inline confirmation (low/medium risk):**
Expandable widget with confirm/cancel/details buttons

**Modal confirmation (high/critical risk):**
Full-screen modal dialog (existing ConfirmationDialog)

**History timeline:**
Scrollable list with timestamp, tool, params, result, duration

---

This design provides:
- ✅ Quick, non-intrusive notifications for common tools
- ✅ Inline confirmations for low-risk operations
- ✅ Modal dialogs for high-risk operations
- ✅ Full transparency of parameters
- ✅ Complete audit trail via history view
- ✅ Fast auto-dismissal with persistent history