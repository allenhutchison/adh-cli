# ADR 001: Policy-Aware Architecture for AI Agent Safety

**Status:** Accepted
**Date:** 2025-09-30 (Retroactive documentation)
**Deciders:** Project Team
**Tags:** architecture, security, safety, core

---

## Context

The application integrates with AI models (Google Gemini) that can execute arbitrary tools and commands through function calling. Without proper safeguards, this capability presents serious risks:

- **Unintended file modifications or deletions**: AI might misinterpret requests
- **Exposure of sensitive data**: AI might read or transmit secrets
- **Execution of dangerous system commands**: AI could run destructive operations
- **Loss of audit trail**: No record of what actions were taken
- **Compliance issues**: Inability to demonstrate due diligence

### Forces at Play

**Technical Constraints:**
- Need to support Google ADK's function calling mechanism
- Must maintain async Python architecture
- Performance overhead should be minimal (<500ms per operation)
- Must work with both ADK LlmAgent and manual function calling

**User Needs:**
- Confidence that AI won't damage their system
- Ability to review what operations will be performed
- Flexibility to adjust safety levels based on trust/context
- Clear understanding of why operations are blocked

**Business Requirements:**
- Production-ready safety for real-world use
- Compliance-friendly audit logging
- Extensible for future safety requirements

## Decision

Implement a **dual-mode architecture** with an optional policy-aware layer:

### Architecture Components

1. **Classic Mode** (`PolicyAwareAgent`)
   - Original behavior without policy enforcement
   - Manual function calling with google.genai.Client
   - Kept for backward compatibility and testing

2. **Policy-Aware Mode** (Default - `PolicyAwareLlmAgent`)
   - Full safety system integrated with Google ADK
   - Components:
     - **PolicyEngine**: Rule-based evaluation of tool calls
     - **SafetyPipeline**: Pre-execution safety checks
     - **ToolExecutionManager**: Lifecycle and UI tracking
     - **PolicyAwareFunctionTool**: Wraps ADK FunctionTool

### Key Design Principles

**Separation of Concerns:**
- Policy evaluation ≠ Safety checking ≠ Tool execution
- Each layer has clear responsibility
- Can be tested independently

**Event-Driven Architecture:**
- Tools emit execution events
- UI subscribes via callbacks
- Loose coupling between layers

**Configuration over Code:**
- Policies defined in YAML files
- User preferences override defaults
- Easy to customize without code changes

### Policy Evaluation Flow

```
User Request
    ↓
AI Function Call
    ↓
PolicyEngine.evaluate_tool_call()
    ↓
    ├─ Blocked? → Raise PermissionError
    ↓
SafetyPipeline.run_checks()
    ↓
    ├─ Failed? → Raise SafetyError
    ├─ Modifications? → Update parameters
    ↓
User Confirmation (if required)
    ↓
    ├─ Denied? → Cancel execution
    ↓
Execute Tool Function
    ↓
Audit Logging
```

### Supervision Levels

- **automatic**: Execute immediately
- **notify**: Execute but show notification
- **confirm**: Ask user before executing
- **manual**: Show details, require explicit approval
- **deny**: Block execution entirely

### Risk Levels

- **none**: No risk (read-only operations)
- **low**: Minimal impact (list files)
- **medium**: Moderate impact (write files)
- **high**: Significant impact (delete files)
- **critical**: System-wide impact (format disk)

## Consequences

### Positive

**Security:**
- Prevents accidental destructive operations
- Detects sensitive data before writing
- Creates backups automatically
- Validates permissions and disk space

**Transparency:**
- Users see exactly what will be executed
- Clear rationale for blocks/warnings
- Complete audit trail for compliance

**Flexibility:**
- Users can choose safety level (paranoid/balanced/permissive)
- Policies customizable per-tool or per-pattern
- Easy to add new safety checks

**Education:**
- Users learn about risky operations
- Safety messages explain concerns
- Builds understanding of security best practices

### Negative

**Complexity:**
- ~3,000 LOC added for safety system
- Learning curve for policy configuration
- More files and modules to maintain

**Performance:**
- 100-300ms overhead per tool call
- Policy evaluation: ~1ms
- Safety checks: ~50-200ms
- User confirmation: blocking

**User Friction:**
- Confirmations can interrupt flow
- False positives may frustrate users
- Need to configure preferences

### Risks

**Risk 1: Users Disable Safety**
- **Impact:** High - defeats entire purpose
- **Mitigation:**
  - Make balanced mode very reasonable
  - Show value through clear explanations
  - Make auto-approve easy for trusted patterns

**Risk 2: Policy Misconfiguration**
- **Impact:** Medium - blocks legitimate operations
- **Mitigation:**
  - Provide tested default policies
  - Clear error messages
  - Easy policy testing/debugging

**Risk 3: Policy Bypass**
- **Impact:** Critical - security vulnerability
- **Mitigation:**
  - Policy enforcement in wrapper, not bypassable
  - Comprehensive test coverage
  - Security audit of enforcement layer

**Risk 4: Audit Log Growth**
- **Impact:** Low - disk space consumption
- **Mitigation:**
  - TODO: Implement log rotation
  - Keep logs in ~/.adh-cli (user-scoped)
  - Document cleanup procedures

### Neutral

**Testing Requirements:**
- Need comprehensive policy tests
- Safety checker tests for each checker
- Integration tests for full flow

**Documentation:**
- Need to explain policy system to users
- Document safety checker API
- Provide policy configuration guide

## Alternatives Considered

### Alternative 1: Sandboxed Execution (Docker/VM)

Run all AI operations in isolated container.

**Pros:**
- Strong isolation guarantees
- Can't damage host system
- Industry-standard approach

**Cons:**
- Heavy infrastructure requirement
- Limits functionality (can't edit user files)
- Poor performance (startup overhead)
- Difficult setup for users

**Why Rejected:** Too restrictive for a development tool that needs to interact with user's actual workspace.

### Alternative 2: Whitelist-Only Approach

Only allow explicitly approved operations.

**Pros:**
- Maximum safety
- Simple to reason about
- Easy to audit

**Cons:**
- Terrible UX (must pre-approve everything)
- Breaks exploratory workflow
- Doesn't scale to many tools

**Why Rejected:** Makes AI assistant too rigid and frustrating to use.

### Alternative 3: Post-Execution Review

Execute freely, show review afterward.

**Pros:**
- No interruption to workflow
- Can undo operations
- Learn from history

**Cons:**
- Damage already done
- Can't undo all operations (deleted files)
- False sense of safety

**Why Rejected:** Prevention is better than detection.

### Alternative 4: AI-Based Safety Evaluation

Use another AI model to evaluate safety.

**Pros:**
- Could understand context better
- Adaptive to new scenarios
- Natural language explanations

**Cons:**
- Expensive (another API call per operation)
- Slow (adds latency)
- Unpredictable (AI hallucinations)
- Can't guarantee safety properties

**Why Rejected:** Need deterministic, reliable safety guarantees.

## Implementation Notes

### Key Modules

**Policy System:**
- `adh_cli/policies/policy_engine.py` - Core evaluation logic
- `adh_cli/policies/policy_types.py` - Type definitions
- `adh_cli/policies/defaults/*.yaml` - Default policies

**Safety System:**
- `adh_cli/safety/pipeline.py` - Safety check orchestration
- `adh_cli/safety/checkers/*.py` - Individual safety checkers
- `adh_cli/safety/types.py` - Safety result types

**Tool Integration:**
- `adh_cli/core/policy_aware_function_tool.py` - ADK FunctionTool wrapper
- `adh_cli/core/policy_aware_llm_agent.py` - ADK agent integration
- `adh_cli/core/tool_executor.py` - Legacy execution (deprecated)

**UI Tracking:**
- `adh_cli/ui/tool_execution_manager.py` - Execution lifecycle
- `adh_cli/ui/tool_execution_widget.py` - UI display
- `adh_cli/ui/tool_execution.py` - Data models

### Configuration

**Policy Files:**
```
~/.adh-cli/policies/
  ├── filesystem_policies.yaml
  ├── command_policies.yaml
  └── custom_policies.yaml
```

**User Preferences:**
```
~/.adh-cli/policy_preferences.yaml
```

**Audit Log:**
```
~/.adh-cli/audit.log
```

### Testing

**Coverage:**
- Policy Engine: 58 tests
- Safety Checkers: 24 tests
- Core Integration: 50 tests
- UI Components: 67 tests
- **Total: 324 tests passing**

**Test Strategy:**
- Unit tests for each component
- Integration tests for full flow
- End-to-end tests with real tools
- Policy bypass prevention tests

## References

**Related ADRs:**
- ADR-002: Tool Execution UI System
- ADR-003: Google ADK Integration

**Code:**
- Policy Types: `adh_cli/policies/policy_types.py`
- Policy Engine: `adh_cli/policies/policy_engine.py`
- Safety Pipeline: `adh_cli/safety/pipeline.py`

**Documentation:**
- Default Policies: `adh_cli/policies/defaults/`
- Test Coverage: `tests/policies/`, `tests/safety/`

**External References:**
- Google ADK Documentation
- OWASP Secure Coding Practices

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-01-XX | Initial retroactive documentation | Project Team |
