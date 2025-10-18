# ADR 023: Streaming Output for Long-Running Tool Execution

**Status:** Accepted
**Date:** 2025-10-18
**Deciders:** Allen Hutchison
**Tags:** architecture, ui, ux, tools, performance

---

## Context

After increasing the `execute_command` timeout to 5 minutes to support large build and test operations, users need real-time feedback during long-running commands. The current implementation waits for complete command execution before displaying any output, which creates several UX problems:

### User Pain Points

**Lack of Real-Time Feedback:**
- No way to see progress during long builds (npm install, cargo build, pytest)
- Commands appear frozen - users can't tell if execution is progressing or stuck
- Must wait minutes to see output, even if error occurs early
- Debugging requires waiting for full completion to see logs

**Opaque Execution:**
- No visibility into what's happening during execution
- Can't tell if tests are passing or failing as they run
- Miss important warnings that scroll by in batch output
- Difficult to understand command behavior

**Poor Developer Experience:**
- Unfamiliar compared to terminal usage where output streams live
- Anxiety about whether commands are working
- Inefficient debugging workflow
- Lacks features users expect from modern dev tools (GitHub Actions, Docker, CI/CD)

### Technical Context

**Current Architecture (ADR-002):**
- Tools execute and return complete results
- `ToolExecutionManager` has callback events:
  - `on_execution_start` - fired when tool begins
  - `on_execution_update` - fired for state changes (not currently used for output)
  - `on_execution_complete` - fired when tool finishes
- `ToolMessage` displays static content after execution
- No mechanism for incremental updates during execution

**Timeout Increase Context:**
- Just increased `execute_command` timeout from 30s to 5 minutes
- Makes streaming even more critical - 5 minutes of waiting is unacceptable
- Large test suites, builds, and installations now supported
- Users expect to watch output during these long operations

## Decision

Implement **streaming output support** for long-running tools, starting with `execute_command`, using an asynchronous callback pattern that integrates with our existing tool execution architecture.

### Architecture

**1. Streaming Callback Protocol**

Add optional callback parameter to tools that produce incremental output:

```python
async def execute_command(
    command: str,
    cwd: Optional[str] = None,
    timeout: Optional[int] = 300,
    shell: bool = True,
    on_output: Optional[Callable[[str, str], Awaitable[None]]] = None,
) -> Dict[str, Any]:
    """
    Args:
        on_output: Optional callback(stream_name, data) called for each output chunk
                   stream_name is "stdout" or "stderr"
                   data is the text chunk (typically line-buffered)
    """
```

**2. Output Streaming Implementation**

Read stdout/stderr incrementally during execution:

```python
# Instead of: stdout, stderr = await process.communicate()
# Use line-by-line reading:
while True:
    line = await process.stdout.readline()
    if not line:
        break
    if on_output:
        await on_output("stdout", line.decode())
```

**3. Tool Execution Manager Integration**

Extend `ToolExecutionInfo` to track streaming output:

```python
@dataclass
class ToolExecutionInfo:
    # ... existing fields ...
    streaming_output: List[Tuple[str, str]] = field(default_factory=list)
    # List of (stream_name, data) tuples
```

Wire streaming callback through execution:

```python
# In ToolExecutor or PolicyAwareFunctionTool
async def execute_with_streaming():
    async def stream_callback(stream_name: str, data: str):
        # Update ToolExecutionInfo
        info.streaming_output.append((stream_name, data))
        # Notify UI via existing callback
        if self.on_execution_update:
            await self.on_execution_update(info)

    await handler(**params, on_output=stream_callback)
```

**4. UI Updates (ToolMessage)**

Add method to append streaming output:

```python
class ToolMessage:
    def append_output(self, stream: str, data: str) -> None:
        """Append new output data to the message content.

        Args:
            stream: "stdout" or "stderr"
            data: Text chunk to append
        """
        # Append to content
        self.message_content += data

        # Update the content widget
        content_widget = self.query_one(".message-content", Static)
        content_widget.update(self.message_content)

        # Auto-scroll if expanded (future enhancement)
```

**5. Rate Limiting**

Buffer updates to avoid overwhelming UI during rapid output:

```python
class StreamBuffer:
    """Buffer streaming updates to avoid excessive UI refreshes."""

    def __init__(self, update_interval: float = 0.1):
        self.buffer = []
        self.interval = update_interval
        self.timer = None

    async def add(self, stream: str, data: str):
        self.buffer.append((stream, data))
        if not self.timer:
            self.timer = asyncio.create_task(self._flush_after_delay())

    async def _flush_after_delay(self):
        await asyncio.sleep(self.interval)
        # Flush all buffered updates to UI
        # ...
```

### Scope

**Phase 1 (Initial Implementation):**
- ✅ `execute_command` streaming support
- ✅ Line-buffered output (stdout/stderr combined in order received)
- ✅ Basic UI updates via existing `on_execution_update` callback
- ✅ Append output to `ToolMessage` content
- ✅ Rate limiting (100ms batch updates)

**Phase 2 (Polish - Future):**
- Auto-scroll toggle when expanded
- "Streaming..." indicator
- Handle ANSI color codes
- Separate stdout/stderr display with different colors

**Phase 3 (Advanced - Future):**
- Search/filter in output
- Download output as text file
- Extend to other tools (`fetch_url` for large downloads)

### Tool Selection Criteria

A tool should support streaming if:
- ✅ Execution can take >10 seconds
- ✅ Produces incremental output during execution
- ✅ Users benefit from seeing progress (builds, tests, downloads)
- ✅ Output helps debug issues (logs, error messages)

**Initially: `execute_command` only**
**Future candidates:** `fetch_url` (download progress), long-running API calls

## Consequences

### Positive

**Better User Experience:**
- See command output in real-time as it executes
- Immediate feedback - know if commands are progressing or stuck
- Catch errors early without waiting for full completion
- Familiar terminal-like experience

**Improved Debugging:**
- See exactly where commands hang or fail
- Watch test progression and failures as they happen
- Understand command behavior better with live logs
- More confidence in what's happening

**Reduced Anxiety:**
- No more wondering if long commands are frozen
- Progress indicators (test counts, build steps) visible immediately
- Matches expectations from terminal usage and modern dev tools

**Architectural Benefits:**
- Builds on existing callback architecture (ADR-002)
- Minimal changes to core execution flow
- Optional feature - tools can opt-in
- Clean separation between streaming and display

### Negative

**Increased Complexity:**
- More complex than current "wait then display" approach
- Need to handle buffering, rate limiting
- State management for streaming vs completed
- ~200 LOC added across multiple files

**Performance Considerations:**
- Rapid output (npm install, large logs) could slow UI
- Need rate limiting to avoid excessive updates
- Memory usage for buffering output
- **Mitigation:** Buffer updates, only refresh UI every 100ms

**Edge Cases:**
- Handle ANSI color codes from tools
- Deal with very large outputs (>10MB logs)
- User interactions during streaming (collapse, cancel)
- **Mitigation:** Strip/preserve ANSI configurable, output size limits

### Risks

**Risk 1: UI Performance Degradation**
- **Impact:** Medium - Rapid output could freeze UI
- **Likelihood:** Low with rate limiting
- **Mitigation:**
  - Batch updates every 100ms
  - Drop updates if UI can't keep up
  - Limit total output buffered (10MB max)
  - Test with high-volume output (npm install --verbose)

**Risk 2: Inconsistent Tool Behavior**
- **Impact:** Low - Some tools stream, others don't
- **Likelihood:** Medium - will happen as we add tools
- **Mitigation:**
  - Clear documentation of which tools support streaming
  - Graceful degradation - works same as before if no callback
  - Consistent UI indicator for streaming vs completed

**Risk 3: Line Buffering Issues**
- **Impact:** Low - Some output might not be line-buffered
- **Likelihood:** Medium - some programs buffer differently
- **Mitigation:**
  - Use line buffering where possible
  - Fallback to time-based flushing (100ms)
  - Document limitations in tool descriptions

### Neutral

**Changes:**
- `execute_command` signature adds optional `on_output` parameter (backward compatible)
- `ToolExecutionInfo` adds `streaming_output` field
- `ToolMessage` adds `append_output` method
- New `StreamBuffer` class for rate limiting (~50 LOC)

**Testing:**
- Need tests for streaming callback invocation
- Need tests for rate limiting / buffering
- Need integration tests with real commands
- Manual testing with various command outputs

## Alternatives Considered

### Alternative 1: Polling for Output

Poll command output at intervals instead of streaming:

```python
# Poll every 500ms
while process.running:
    await asyncio.sleep(0.5)
    output = read_partial_output()
    update_ui(output)
```

**Pros:**
- Simpler implementation
- Natural rate limiting built-in
- Easier to understand

**Cons:**
- Up to 500ms latency for output
- Inefficient - wastes CPU polling
- Less responsive than true streaming
- Still need to read incrementally from process

**Why Rejected:** Streaming with buffering gives better latency and efficiency. Rate limiting achieves same UI protection without artificial delays.

### Alternative 2: Store Complete Output, Display Window

Store all output but only display a "window" in UI:

```python
# Store everything
all_output = []
# Display only last 100 lines
display_output = all_output[-100:]
```

**Pros:**
- Protects UI from huge outputs
- Can scroll through history
- Memory usage bounded

**Cons:**
- Users still don't see progress in real-time during execution
- Doesn't solve core problem of no feedback
- Complex UI for scrolling through historical window
- Could still implement later on top of streaming

**Why Rejected:** Doesn't address real-time feedback need. Could be added later as enhancement to streaming (output size limits).

### Alternative 3: Separate "Output Viewer" Widget

Create dedicated widget for watching command output, separate from tool message:

```python
class OutputViewer(Widget):
    """Dedicated widget for streaming output."""
    # Rich terminal emulation
    # Scrolling, search, etc.
```

**Pros:**
- Full-featured terminal emulator
- Better UX for large outputs
- Could support advanced features (search, filter)

**Cons:**
- Much more complex - entire new widget system
- Fragments tool execution display
- Overhead for simple commands
- Could still build later if needed

**Why Rejected:** Over-engineered for Phase 1. Start simple with in-place streaming, can enhance later.

### Alternative 4: No Streaming, Just Progress Indicator

Show generic "Executing..." with spinner, no actual output:

```python
# Just show: "Executing pytest... ⏳"
# No real output until complete
```

**Pros:**
- Very simple
- No performance concerns
- Minimal code changes

**Cons:**
- Doesn't solve debugging problem
- Still no visibility into what's happening
- Can't see errors or progress
- Poor UX compared to streaming

**Why Rejected:** Doesn't meet user needs. Users want to see actual output, not just "something is happening."

## Implementation Notes

### Files Affected

**Core Streaming:**
- `adh_cli/tools/shell_tools.py` - Add streaming to `execute_command` (~40 LOC)
- `adh_cli/core/tool_executor.py` - Wire streaming callback (~20 LOC)
- `adh_cli/ui/tool_execution.py` - Add `streaming_output` field to `ToolExecutionInfo`

**UI Updates:**
- `adh_cli/ui/chat_widgets.py` - Add `append_output()` to `ToolMessage` (~20 LOC)
- `adh_cli/screens/chat_screen.py` - Handle streaming in `on_execution_update()` (~30 LOC)

**Utilities:**
- `adh_cli/ui/stream_buffer.py` - New file for rate limiting (~50 LOC)

**Tests:**
- `tests/tools/test_shell_tools.py` - Streaming callback tests (~50 LOC)
- `tests/ui/test_chat_widgets.py` - `append_output` tests (~30 LOC)
- `tests/integration/test_streaming_output.py` - New integration tests (~80 LOC)

**Total:** ~320 LOC added

### Backward Compatibility

**Fully backward compatible:**
- `on_output` parameter is optional - defaults to `None`
- If not provided, `execute_command` works exactly as before
- Existing code unaffected
- Tools without streaming support continue to work
- UI gracefully handles tools with/without streaming

### Configuration

No new configuration needed initially. Future enhancements might add:
- `streaming_enabled: bool` - global toggle
- `streaming_update_interval: float` - rate limiting interval (default 100ms)
- `max_streaming_output_size: int` - max buffered output (default 10MB)
- `ansi_codes: "strip" | "preserve"` - ANSI handling (Phase 2)

### Testing Approach

**Unit Tests:**
- Test `execute_command` calls callback with output chunks
- Test rate limiting / buffering logic
- Test `ToolMessage.append_output()` updates content

**Integration Tests:**
- Run real command with streaming (`echo` multiple lines)
- Verify UI updates during execution
- Test error handling (command fails mid-stream)
- Test timeout during streaming

**Manual Testing:**
- `pytest tests/` - watch test output stream
- `npm install` - rapid output, rate limiting
- `sleep 5 && echo done` - delayed output
- Long-running command with timeout
- Cancel command during streaming

### Migration Path

**Phase 1 (Current):**
1. Implement streaming in `execute_command`
2. Wire through tool executor
3. Update UI to handle streaming
4. Add rate limiting
5. Test with various commands
6. Document in user guide

**Phase 2 (Future):**
- Add auto-scroll toggle
- ANSI color code support
- Streaming indicator UI
- stdout/stderr separation

**Phase 3 (Future):**
- Search/filter in output
- Download output
- Extend to other tools

## References

**Related ADRs:**
- ADR-002: Tool Execution UI Tracking System (callback architecture we're extending)
- ADR-015: Chat-Integrated Tool Execution (where tools are displayed)

**Design Inspiration:**
- GitHub Actions logs - streaming build output
- Docker build - layer-by-layer streaming
- Terminal emulators - real-time command output
- CI/CD systems - live log streaming

**Technical References:**
- Python asyncio subprocess streaming: https://docs.python.org/3/library/asyncio-subprocess.html
- Textual widget updating: https://textual.textualize.io/guide/reactivity/

**Implementation:**
- `adh_cli/tools/shell_tools.py` - Tool implementation
- `adh_cli/core/tool_executor.py` - Execution coordination
- `adh_cli/ui/chat_widgets.py` - UI display
- `adh_cli/ui/tool_execution.py` - Data models

---

## Implementation Updates (Post-Development)

After implementing Phase 1, we made the following adjustments from the original design:

### 1. ADK Schema Generation Constraint

**Issue:** ADK's automatic function schema generator tried to parse the `on_output` parameter and include it in the tool schema sent to the LLM, causing a parsing error: `Failed to parse the parameter on_output of function execute_command`.

**Solution:** Hide `on_output` from ADK by accepting it via `**kwargs` instead of as a named parameter:

```python
async def execute_command(
    command: str,
    cwd: Optional[str] = None,
    timeout: Optional[int] = 300,
    shell: bool = True,
    **kwargs,  # Internal: on_output callback for streaming
) -> Dict[str, Any]:
    on_output = kwargs.get('on_output', None)
    # ... implementation
```

**Impact:** No functional change - our wrapper code still passes `on_output` via kwargs. The LLM only sees the intended parameters (command, cwd, timeout, shell).

### 2. Simplified Rate Limiting

**Original Plan:** Create separate `StreamBuffer` utility class (~50 LOC).

**Actual Implementation:** Inline rate limiting using closure variables:

```python
# In PolicyAwareFunctionTool
last_update_time = [0.0]  # Use list for mutation in nested function
pending_update = [False]

async def on_output(stream_name: str, data: str):
    execution_info.streaming_output.append((stream_name, data))

    current_time = time.time()
    if current_time - last_update_time[0] >= 0.1:  # 100ms
        self.execution_manager.update_execution(execution_id)
        last_update_time[0] = current_time
        pending_update[0] = False
    else:
        pending_update[0] = True
```

**Rationale:** Simpler, no extra class needed, same performance characteristics. Final flush ensures no output is lost.

### 3. Actual LOC Count

**Estimated:** ~320 LOC
**Actual:** ~120 LOC

The implementation was leaner due to:
- No separate `StreamBuffer` class (inline rate limiting)
- Leveraging existing `on_execution_update` callback (no new plumbing)
- Simple `append_output()` method (no auto-scroll complexity)

### Files Modified (Actual)

**Core Streaming:**
- `adh_cli/tools/shell_tools.py` - Streaming implementation (~30 LOC)
- `adh_cli/core/policy_aware_function_tool.py` - Callback wiring + rate limiting (~25 LOC)
- `adh_cli/ui/tool_execution.py` - `streaming_output` field (~2 LOC)

**UI Updates:**
- `adh_cli/ui/chat_widgets.py` - `append_output()` method (~15 LOC)
- `adh_cli/screens/chat_screen.py` - Streaming handler (~20 LOC)

**Tests:**
- `tests/tools/test_streaming.py` - New streaming tests (~55 LOC)
- `tests/tools/test_shell_tools.py` - Updated timeout test mock (~8 LOC)

**Total:** ~155 LOC (including tests), ~100 LOC (implementation only)

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-10-18 | Initial decision and design | Allen Hutchison |
| 2025-10-18 | Post-implementation updates (ADK schema fix, simplified rate limiting, actual LOC) | Allen Hutchison |
