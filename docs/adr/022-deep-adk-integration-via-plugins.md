# 022. Deep ADK Integration via Plugin Architecture

Status: Proposed

## Context

The current application (`adh_cli`) implements critical cross-cutting concerns—specifically Policy Enforcement, Safety Filtering, and Custom Generation Configs—by wrapping and extending core ADK classes such as `LlmAgent` and `BaseTool`. This is visible in custom classes like `PolicyAwareLlmAgent` and `PolicyAwareNativeTool`.

While functional, this approach tightly couples the application's unique logic to the ADK's internal implementation details and bypasses the ADK's canonical extension mechanism, the Plugin framework. We have access to the ADK source code at `~/src/adk-python`, allowing us to achieve a deeper, more maintainable integration.

The goal is to simplify the core agent implementation, decouple cross-cutting concerns, and fully leverage the ADK's intended architectural patterns to ensure better future compatibility and clarity.

## Decision

We will refactor all custom cross-cutting logic from Agent and Tool wrappers into the ADK's native **Plugin** framework by implementing three dedicated plugins.

The chosen implementation path is as follows:

1.  **Transition custom logic** from wrapper classes into ADK-native `BasePlugin` subclasses.
2.  **Register these plugins** directly with the `google.adk.runners.Runner` upon application startup.

### Proposed Plugins

| Plugin Name | Responsibility | Replaces/Refactors | ADK Lifecycle Hooks |
| :--- | :--- | :--- | :--- |
| `PolicyEnforcementPlugin` | Executes safety checks and policy decisions (allow, deny, event-driven confirm) on tool calls. Integrates with `ToolExecutionManager` for UI tracking. | `PolicyAwareFunctionTool`, `PolicyAwareNativeTool`, policy wrapper logic. | `before_tool_callback`, `after_tool_callback`, `on_tool_error_callback` |
| `SafetyFilterPlugin` | Intercepts and processes input/output through the safety pipeline. | `SafetyPipeline` wrapper logic in tools. | `before_model_callback` (input filtering), `after_model_callback` (output filtering) |
| `GenerationConfigPlugin` | Injects custom `GenerateContentConfig` parameters (temperature, top_k, top_p, max_output_tokens). **Note**: Does NOT manage `thinking_config` - that remains with `BuiltInPlanner` on agent initialization. | `GenerationConfigTool` (partially - thinking config stays with planner). | `before_model_callback` |

## Event-Driven Confirmation Architecture

### The Challenge

The current confirmation workflow is **synchronous and blocking**: when a tool requires user confirmation, execution pauses via `await ToolExecutionManager.wait_for_confirmation()` until the user clicks Approve/Deny in the UI.

Plugin hooks **cannot block execution** - they can only short-circuit by returning early. This is fundamentally incompatible with blocking confirmation flows.

### The Solution: Event-Based Confirmation

We will refactor to an **event-driven confirmation model**:

1. **Policy Check Phase** (`before_tool_callback`):
   - Plugin evaluates policy
   - If `requires_confirmation`:
     - Emit `ConfirmationRequestedEvent` via `on_event_callback`
     - Return error dict: `{"error": "PENDING_CONFIRMATION", "tool_name": tool.name, "confirmation_id": uuid}`
   - Tool call fails with "pending" status

2. **UI Displays Confirmation Dialog**:
   - Chat screen listens for `ConfirmationRequestedEvent`
   - Shows confirmation dialog with tool details
   - User clicks Approve/Deny

3. **User Decision Phase**:
   - UI sends confirmation result back to agent via new message or state update
   - Agent receives `ConfirmationResolvedEvent`

4. **Tool Retry Phase**:
   - Agent retries the tool call with confirmation metadata
   - Plugin sees confirmation approval in context, allows execution
   - Tool proceeds normally

### Implementation Details

**New Event Types**:
```python
@dataclass
class ConfirmationRequestedEvent(Event):
    confirmation_id: str
    tool_name: str
    tool_args: dict
    policy_decision: PolicyDecision

@dataclass
class ConfirmationResolvedEvent(Event):
    confirmation_id: str
    approved: bool
    user_id: str
```

**Plugin Logic**:
```python
class PolicyEnforcementPlugin(BasePlugin):
    async def before_tool_callback(self, *, tool, tool_args, tool_context):
        decision = self.policy_engine.evaluate_tool_call(...)

        if not decision.allowed:
            return {"error": "blocked_by_policy", "reason": decision.reason}

        if decision.requires_confirmation:
            # Check if confirmation already provided
            confirmation_id = tool_context.metadata.get("confirmation_id")
            if confirmation_id and self._is_confirmed(confirmation_id):
                return None  # Allow execution

            # Request confirmation
            confirmation_id = str(uuid.uuid4())
            self._pending_confirmations[confirmation_id] = {
                "tool": tool.name,
                "args": tool_args,
                "decision": decision,
            }
            # Emit event via invocation_context
            await self._emit_confirmation_request(confirmation_id, tool, tool_args, decision)
            return {"error": "pending_confirmation", "confirmation_id": confirmation_id}
```

**UI Integration** (ChatScreen):
```python
# Listen for confirmation events
def on_confirmation_requested(self, event: ConfirmationRequestedEvent):
    # Show modal dialog
    self.show_confirmation_dialog(
        tool=event.tool_name,
        args=event.tool_args,
        on_confirm=lambda: self._handle_confirmation(event.confirmation_id, True),
        on_deny=lambda: self._handle_confirmation(event.confirmation_id, False),
    )

def _handle_confirmation(self, confirmation_id: str, approved: bool):
    # Send resolution back to agent
    self.agent.submit_confirmation(confirmation_id, approved)
```

### Migration Path

1. **Phase 1**: Implement event infrastructure and confirmation events
2. **Phase 2**: Update `ToolExecutionManager` to track pending confirmations
3. **Phase 3**: Refactor ChatScreen confirmation UI to be event-driven
4. **Phase 4**: Implement plugin confirmation logic
5. **Phase 5**: Remove synchronous `wait_for_confirmation()` logic

## Detailed Plan

### Phase 0: Validation & Proof-of-Concept (1-2 days)

1. **Validate Plugin Architecture**:
   - Create minimal `LoggingPlugin` to confirm plugin registration works
   - Test plugin execution order and context propagation
   - Verify async operations work correctly in plugins

2. **Prototype Event-Driven Confirmation**:
   - Create prototype confirmation event structure
   - Test event emission and handling in ChatScreen
   - Validate non-blocking behavior

### Phase 1: Generation Config Plugin (3-5 days)

**Rationale**: Start with the simplest plugin (no confirmation, no safety checks).

1. **Create `GenerationConfigPlugin`**:
   - File: `adh_cli/plugins/config_plugin.py`
   - Implement `before_model_callback` to inject temperature, top_k, top_p, max_output_tokens
   - **Important**: Do NOT touch `thinking_config` - that stays with `BuiltInPlanner`

2. **Register Plugin**:
   - Update `PolicyAwareLlmAgent._init_adk_components()` to instantiate and pass plugin to Runner
   - Remove `GenerationConfigTool` from tools list

3. **Test Migration**:
   - Verify generation params still apply correctly
   - Ensure thinking mode still works (unchanged)
   - Update ~5 related tests

### Phase 2: Safety Filter Plugin (3-5 days)

1. **Create `SafetyFilterPlugin`**:
   - File: `adh_cli/plugins/safety_plugin.py`
   - Implement `before_model_callback` for input safety filtering
   - Implement `after_model_callback` for output safety filtering

2. **Refactor Safety Pipeline**:
   - Move safety logic from tool wrappers into plugin
   - Ensure async safety checkers work correctly

3. **Test Migration**:
   - Run existing safety checker tests (~24 tests)
   - Verify sensitive data detection still works
   - Test with various LLM inputs/outputs

### Phase 3: Event-Driven Confirmation Infrastructure (1 week)

1. **Create Event Types**:
   - Define `ConfirmationRequestedEvent` and `ConfirmationResolvedEvent`
   - Add event handling to Runner/invocation context

2. **Refactor ToolExecutionManager**:
   - Add event-based confirmation tracking
   - Remove blocking `wait_for_confirmation()` method
   - Add `register_confirmation()` and `resolve_confirmation()` methods

3. **Update ChatScreen**:
   - Refactor confirmation UI to be event-driven
   - Add event listeners for confirmation requests
   - Test confirmation flow end-to-end

4. **Test Migration**:
   - Update ~15 tests that depend on confirmation flow
   - Add new tests for event-driven confirmation

### Phase 4: Policy Enforcement Plugin (1 week)

1. **Create `PolicyEnforcementPlugin`**:
   - File: `adh_cli/plugins/policy_plugin.py`
   - Implement `before_tool_callback` with event-driven confirmation
   - Implement `after_tool_callback` for audit logging
   - Implement `on_tool_error_callback` for error handling
   - Integrate with `ToolExecutionManager` for UI tracking

2. **Remove Wrapper Classes**:
   - Deprecate `PolicyAwareFunctionTool`
   - Deprecate `PolicyAwareNativeTool`
   - Update tool registration to use plain ADK tools

3. **Test Migration**:
   - Update ~40 policy-related tests
   - Update ~20 integration tests
   - Add dedicated plugin unit tests

### Phase 5: Core Application Simplification (3-5 days)

1. **Simplify PolicyAwareLlmAgent**:
   - Remove wrapper logic, keep only tool registration
   - Consider renaming to `ADHAgent` or similar
   - Clean up initialization code

2. **Update Documentation**:
   - Update CLAUDE.md with new architecture
   - Document plugin configuration
   - Add plugin development guide

3. **Final Testing**:
   - Run full test suite (410 tests)
   - Perform end-to-end testing
   - Test with real Gemini API calls

## Test Migration Estimate

Based on analysis of the current test suite:

- **Generation Config Tests**: ~5 tests need updates
- **Safety Pipeline Tests**: ~24 tests need updates
- **Policy Enforcement Tests**: ~40 tests need updates
- **Confirmation Flow Tests**: ~15 tests need updates
- **Integration Tests**: ~20 tests need updates
- **New Plugin Tests**: ~30 new tests to be written

**Total Estimated Test Updates**: ~134 test changes

**Approach**:
- Start with unit tests for each plugin
- Update integration tests incrementally with each phase
- Maintain test coverage at 80%+ throughout migration
- Use feature flags to run both old and new implementations in parallel during transition

## Risk Mitigation

### Risk 1: Event-Driven Confirmation Complexity
**Severity**: High
**Mitigation**:
- Build confirmation infrastructure in Phase 3 before touching policy plugin
- Create extensive unit tests for event flow
- Implement feature flag to fall back to synchronous confirmation if issues arise
- Consider gradual rollout: start with non-critical tools

### Risk 2: Plugin Performance Overhead
**Severity**: Medium
**Mitigation**:
- Benchmark plugin execution time vs current wrapper approach in Phase 0
- Target <5ms overhead per tool call
- Profile hot paths and optimize if necessary
- Consider caching policy decisions when safe

### Risk 3: ADK Plugin API Changes
**Severity**: Medium
**Mitigation**:
- Pin ADK version during migration
- Document all plugin hook dependencies
- Create adapter layer if ADK plugin API changes in future
- Maintain good test coverage to catch breaking changes early

### Risk 4: Test Migration Scope Underestimated
**Severity**: Medium
**Mitigation**:
- Budget 50% time buffer for test updates
- Prioritize critical path tests (policy enforcement, safety)
- Accept temporary test skips with tracking issues
- Use test generators/fixtures to reduce duplication

### Risk 5: Incomplete Migration State
**Severity**: Low
**Mitigation**:
- Each phase delivers working, shippable code
- Use feature flags to enable/disable plugins
- Maintain wrapper classes as deprecated but functional during transition
- Create rollback plan for each phase

## Rollback Strategy

If the plugin approach proves problematic:

1. **Phase 0-1**: Simply remove plugin, restore `GenerationConfigTool` (low cost)
2. **Phase 2-3**: Keep `SafetyFilterPlugin`, revert confirmation changes (medium cost)
3. **Phase 4+**: Maintain both systems in parallel via feature flag (high cost but feasible)

Each phase is designed to be independently revertible without affecting prior phases.

## Consequences

### Positive
*   **Architectural Alignment**: Uses ADK's intended extension mechanism (plugins) instead of bypassing it with wrappers
*   **Decoupling**: Policy, safety, and configuration logic are cleanly separated from core agent/tool logic
*   **Maintainability**: Simpler core code relying on official extension points makes ADK upgrades less disruptive
*   **Testability**: Plugins can be tested in isolation with clear boundaries
*   **Flexibility**: Plugins can be enabled, disabled, or reordered independently
*   **Scalability**: Adding new cross-cutting concerns (logging, metrics, caching) follows the same plugin pattern
*   **Event-Driven UX**: Non-blocking confirmation flow enables better user experience and eliminates race conditions

### Negative
*   **Implementation Overhead**: Significant refactoring effort (~3-4 weeks estimated)
*   **Test Migration**: ~134 tests need updates, plus 30 new tests to write
*   **Confirmation Complexity**: Event-driven confirmation is more complex than synchronous blocking
*   **Learning Curve**: Team needs to understand ADK plugin lifecycle and event system
*   **Debugging Complexity**: Plugin chain execution may be harder to debug than direct method calls
*   **Short-Term Instability**: Migration period will have both old and new systems coexisting

### Tradeoffs Accepted
*   **Immediate Development Cost vs Long-Term Maintainability**: Accept 3-4 weeks of refactoring for cleaner architecture
*   **Event-Driven Complexity vs Non-Blocking UX**: Accept more complex confirmation flow for better UX
*   **ADK Coupling**: Increased dependency on ADK plugin API stability (mitigated by version pinning)

## ToolExecutionManager Integration

The `ToolExecutionManager` tracks tool execution state for UI display. This functionality must be preserved during plugin migration.

**Current Flow** (in `PolicyAwareFunctionTool`):
```python
execution_id = manager.create_execution(tool_name, parameters, decision)
manager.start_execution(execution_id)
result = await tool_handler(**parameters)
manager.complete_execution(execution_id, result=result)
```

**Plugin Flow** (in `PolicyEnforcementPlugin`):
```python
async def before_tool_callback(self, *, tool, tool_args, tool_context):
    decision = self.policy_engine.evaluate(...)

    # Create execution tracking
    execution_id = self.execution_manager.create_execution(
        tool_name=tool.name,
        parameters=tool_args,
        policy_decision=decision,
    )

    # Store in context for after_tool_callback
    tool_context.metadata["execution_id"] = execution_id

    # Start tracking
    self.execution_manager.start_execution(execution_id)

    # ... policy checks ...

async def after_tool_callback(self, *, tool, tool_args, tool_context, result):
    execution_id = tool_context.metadata.get("execution_id")
    if execution_id:
        self.execution_manager.complete_execution(
            execution_id,
            success=True,
            result=result
        )

async def on_tool_error_callback(self, *, tool, tool_args, tool_context, error):
    execution_id = tool_context.metadata.get("execution_id")
    if execution_id:
        self.execution_manager.complete_execution(
            execution_id,
            success=False,
            error=str(error),
            error_type=type(error).__name__
        )
```

**Key Points**:
- Use `tool_context.metadata` to pass execution tracking state between hooks
- All three hooks (`before_tool_callback`, `after_tool_callback`, `on_tool_error_callback`) must coordinate
- UI integration remains unchanged - widgets still listen to manager events

## Alternatives Considered

### Alternative 1: Continue Wrapping/Composition (Status Quo)
**Rejected**: Leads to architectural drift and increased complexity over time. Bypasses ADK's intended extension mechanism.

### Alternative 2: Subclass ADK Runner
**Rejected**: Overly broad for the task. Plugin system is explicitly designed for this type of customization. Subclassing Runner would couple application logic to Runner implementation.

### Alternative 3: Hybrid Approach (Wrappers + Plugins)
**Considered but Rejected**: Use plugins for automatic/deny policies, keep wrappers for confirmation-required tools.

**Pros**: Minimal disruption to confirmation flow
**Cons**:
- Defeats purpose of architectural simplification
- Maintains two parallel systems indefinitely
- Confusion about which tools use which system
- No path to full plugin adoption

**Decision**: Rejected in favor of event-driven confirmation (more work upfront, cleaner long-term)

### Alternative 4: Synchronous Confirmation in Plugin Hook
**Considered but Rejected**: Use `asyncio.wait_for()` with timeout in `before_tool_callback`.

**Pros**: Simpler than event-driven approach
**Cons**:
- Violates plugin design principles (hooks shouldn't block)
- May cause ADK Runner to timeout or hang
- Poor user experience (hard timeouts)
- May conflict with ADK's internal async management

**Decision**: Rejected - event-driven is the right long-term solution
