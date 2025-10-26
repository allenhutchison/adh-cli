# ADR 024: Headless CLI Mode for One-Shot Tasks

**Status:** Proposed - Not Implemented
**Date:** 2025-10-26
**Deciders:** Project Team
**Tags:** architecture, cli, automation, separation-of-concerns

> **Implementation Status (2025-10-26):** This ADR describes a proposed feature
> that has not yet been implemented. Current state: ADH CLI operates exclusively
> in TUI mode. The proposed architecture for headless mode remains future work.
> See GitHub issue for detailed implementation plan.

---

## Context

ADH CLI currently operates exclusively in TUI (Terminal User Interface) mode via Textual, requiring an interactive terminal session with full screen rendering. While this provides an excellent interactive experience, it prevents several important use cases:

- **Scripting and Automation**: Cannot integrate adh-cli into shell scripts, makefiles, or automated workflows
- **CI/CD Integration**: Cannot run in continuous integration pipelines where interactive TUI is not available
- **Quick One-Shot Tasks**: Simple queries require launching the full TUI application with its ~2-3 second startup overhead
- **Programmatic Access**: No way to use adh-cli as a composable command-line tool in larger toolchains
- **Batch Processing**: Cannot process multiple requests in sequence without manual interaction
- **Remote Execution**: Cannot easily run via SSH or in containers without terminal emulation

### Current Architecture Limitations

The current codebase has coupling between core agent logic and TUI concerns:

**1. Agent Initialization in TUI Layer** (`app.py:141-174`)

```python
class ADHApp(App):
    def _build_agent(self):
        """Build and configure the agent instance."""
        # This is tightly coupled to ADHApp
        # Cannot be reused outside TUI context
        self.agent = PolicyAwareLlmAgent(...)
```

**2. Tool Registration in TUI Layer** (`app.py:197-270`)

```python
class ADHApp(App):
    def _register_default_tools(self):
        """Register default tools from specs registry."""
        # Tool registration happens within TUI app lifecycle
        # No standalone tool registration mechanism
```

**3. CLI Entry Point Forces TUI** (`__main__.py:18-49`)

```python
def main(debug: bool, policy_dir: Path, no_safety: bool) -> None:
    """Launch the ADH CLI TUI application..."""
    app = ADHApp()
    app.run()  # Always launches TUI
```

**4. Confirmation Handlers Assume TUI** (`app.py:271-306`)

```python
async def handle_confirmation(self, tool_call=None, decision=None, **kwargs):
    """Handle confirmation requests from the policy engine."""
    dialog = ConfirmationDialog(...)
    result = await self.push_screen_wait(dialog)  # Requires Textual screen stack
    return result
```

### Forces at Play

**Technical Constraints:**
- Must maintain 100% backward compatibility with TUI mode
- Policy enforcement must work identically in both modes
- Confirmation handlers differ fundamentally (modal dialogs vs stdin prompts)
- Need to avoid TUI dependencies in headless mode (startup performance)
- Same configuration files should work for both modes

**User Needs:**
- Ability to run quick CLI commands without TUI overhead
- Script integration capability with predictable output
- Same safety guarantees and policy enforcement as TUI mode
- Consistent behavior across interactive and non-interactive modes
- Clear, parseable output for automation (JSON, text, markdown)

**Business Requirements:**
- Professional tool suitable for production automation
- CI/CD friendly for enterprise workflows
- Scriptable for team standardization
- API-ready architecture for future integrations

**Architecture Goals:**
- Clean separation between interface and core logic
- Reusable agent factory pattern
- Support multiple interface types (TUI, CLI, future: web API)
- Maintainable with independent testing
- Foundation for future interface additions

## Decision

Implement headless CLI mode via **three-layer architecture** that cleanly separates concerns:

### Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│  INTERFACE LAYER                                            │
│  ┌──────────────────┐         ┌──────────────────┐         │
│  │   TUI Interface  │         │  CLI Interface   │         │
│  │  (Textual App)   │         │  (Headless Mode) │         │
│  │                  │         │                  │         │
│  │ - Screens        │         │ - Argument       │         │
│  │ - Widgets        │         │   parsing        │         │
│  │ - Dialog boxes   │         │ - Stdout output  │         │
│  │ - Status footer  │         │ - Y/n prompts    │         │
│  │ - Tool execution │         │ - Exit codes     │         │
│  │   widgets        │         │ - Format control │         │
│  └──────────────────┘         └──────────────────┘         │
│           │                            │                    │
│           └────────────────┬───────────┘                    │
│                            │                                │
└────────────────────────────┼────────────────────────────────┘
                             │
                    (Both use same factory)
                             │
┌────────────────────────────┼────────────────────────────────┐
│  CORE LAYER                │                                │
│                            ▼                                │
│              ┌──────────────────────────┐                   │
│              │     Agent Factory        │                   │
│              │ (agent_factory.py)       │                   │
│              │                          │                   │
│              │ - create_agent()         │                   │
│              │   (includes tool         │                   │
│              │    registration)         │                   │
│              └──────────────────────────┘                   │
│                            │                                │
│                            ▼                                │
│              ┌──────────────────────────┐                   │
│              │  PolicyAwareLlmAgent     │                   │
│              │                          │                   │
│              │  Uses:                   │                   │
│              │  - PolicyEngine          │                   │
│              │  - SafetyPipeline        │                   │
│              │  - ToolExecutor          │                   │
│              │  - Tool Registry         │                   │
│              │  - Audit Logger          │                   │
│              │  - Execution Manager     │                   │
│              └──────────────────────────┘                   │
│                                                              │
│  (This layer is interface-agnostic)                         │
└──────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────┐
│  FOUNDATION LAYER          │                                │
│                            ▼                                │
│    ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│    │ Policy   │  │ Safety   │  │   Tool   │               │
│    │ Engine   │  │ Pipeline │  │ Registry │               │
│    └──────────┘  └──────────┘  └──────────┘               │
│                                                              │
│    ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│    │   ADK    │  │  Config  │  │  Audit   │               │
│    │  (Gemini)│  │ Manager  │  │  Logger  │               │
│    └──────────┘  └──────────┘  └──────────┘               │
└──────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. AgentFactory (`adh_cli/core/agent_factory.py`)

**Purpose**: Extract agent initialization logic from `ADHApp` into a reusable factory that can be used by both TUI and headless modes.

**Responsibilities**:
- Load configuration from files or parameters
- Initialize `PolicyAwareLlmAgent` with proper settings
- Register tools from the tool registry
- Apply user preferences and safety settings
- Configure audit logging
- Support multiple agent types (orchestrator, planner, researcher)

**Interface**:
```python
class AgentFactory:
    @staticmethod
    def create_agent(
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        policy_dir: Optional[Path] = None,
        confirmation_handler: Optional[Callable] = None,
        notification_handler: Optional[Callable] = None,
        audit_log_path: Optional[Path] = None,
        agent_name: str = "orchestrator",
        safety_enabled: bool = True,
        register_tools: bool = True,
        config: Optional[Dict[str, Any]] = None,
    ) -> PolicyAwareLlmAgent:
        """Create and configure a PolicyAwareLlmAgent.

        Args:
            register_tools: If True, automatically register default tools.
                           Set to False only for testing or custom tool sets.

        Returns:
            Fully initialized and ready-to-use PolicyAwareLlmAgent.
        """
```

**Benefits**:
- Single source of truth for agent creation
- Testable in isolation
- Reusable across interfaces
- Configuration centralized

#### 2. HeadlessRunner (`adh_cli/headless/runner.py`)

**Purpose**: Orchestrate agent execution in non-interactive CLI mode.

**Responsibilities**:
- Execute single prompt via agent
- Handle streaming responses
- Format output (text, JSON, markdown)
- Manage exit codes (0=success, 1=error, 2=policy blocked)
- Error handling and reporting
- Optional verbose mode

**Interface**:
```python
class HeadlessRunner:
    def __init__(
        self,
        agent: PolicyAwareLlmAgent,
        output_format: str = "text",
        verbose: bool = False,
    ):
        """Initialize headless runner with configured agent."""

    async def run(
        self,
        prompt: str,
        context: Optional[ExecutionContext] = None
    ) -> int:
        """Execute single prompt and return exit code."""
```

**Benefits**:
- Clear separation from TUI concerns
- Testable with mock agents
- Supports multiple output formats
- Consistent error handling

#### 3. CLI Confirmation Handler (`adh_cli/headless/confirmation.py`)

**Purpose**: Replace TUI modal dialogs with CLI-based Y/n prompts for policy confirmations.

**Responsibilities**:
- Format confirmation prompts for terminal display
- Read user input from stdin
- Return boolean decision
- Handle Ctrl+C gracefully (deny by default)
- Support auto-approval mode (dangerous, explicit flag)

**Interface**:
```python
async def cli_confirmation_handler(
    tool_call: Optional[ToolCall] = None,
    decision: Optional[PolicyDecision] = None,
    message: Optional[str] = None,
    **kwargs
) -> bool:
    """CLI-based confirmation using stdin/stdout."""

async def cli_notification_handler(
    message: str,
    level: str = "info"
) -> None:
    """CLI-based notification to stderr."""
```

**Example Output**:
```
⚠️  Confirmation Required
============================================================
Tool: write_file
Parameters:
  path: /home/user/important.txt
  content: [3421 bytes]

Policy: confirm (medium risk)
Reason: File modification requires review

Safety Checks:
  ✅ Backup created: /home/user/important.txt.backup
  ✅ Permissions OK
  ⚠️  Sensitive data detected (possible API key on line 42)

============================================================
Proceed? [y/N]: _
```

**Benefits**:
- Consistent with TUI confirmation information
- Non-interactive environments can use --yes flag
- Clear, informative prompts
- Safe defaults (deny on ambiguous input)

#### 4. Updated CLI Entry Point (`adh_cli/__main__.py`)

**Purpose**: Support both TUI and headless modes via Click command groups.

**Interface**:
```bash
# TUI mode (default, backward compatible)
adh-cli                              # Launch TUI
adh-cli --policy-dir ./policies      # TUI with custom policies
adh-cli --debug                      # TUI with debug mode

# Headless mode (NEW)
adh-cli run "your prompt here"                    # Basic headless
adh-cli run "analyze code" --policy strict.yaml   # Custom policy
adh-cli run "quick task" --yes                    # Auto-approve
adh-cli run "generate docs" --output json         # JSON output
adh-cli run "plan feature" --agent planner        # Different agent
```

**Flags for Headless Mode**:
- `--policy <file>`: Single policy file (alternative to --policy-dir)
- `--policy-dir <dir>`: Policy directory (same as TUI)
- `--yes`: Auto-approve all confirmations (DANGEROUS, explicit)
- `--no-safety`: Disable all safety checks (same as TUI)
- `--output <format>`: Output format (text, json, markdown)
- `--verbose`: Show detailed execution info (to stderr)
- `--model <name>`: Override model selection
- `--agent <name>`: Specify agent type (orchestrator, planner, researcher, code_reviewer)
- `--debug`: Enable debug mode

**Benefits**:
- Backward compatible (no subcommand = TUI)
- Discoverable interface (subcommands)
- Consistent flag names across modes
- Standard CLI conventions

### CLI Output Formats

#### Text Format (Default)

```bash
$ adh-cli run "List files in current directory"

Current directory contains 15 files and 3 directories:

Files:
- README.md (2.3 KB)
- setup.py (1.1 KB)
- pyproject.toml (856 B)
...

Directories:
- adh_cli/
- tests/
- docs/
```

#### JSON Format (for scripting)

When using `--output json`, the response field contains structured data suitable for programmatic consumption:

```bash
$ adh-cli run "List files in current directory" --output json
{
  "success": true,
  "response": {
    "summary": "Current directory contains 15 files and 3 directories",
    "files": [
      {"name": "README.md", "size_kb": 2.3, "type": "file"},
      {"name": "setup.py", "size_kb": 1.1, "type": "file"},
      {"name": "pyproject.toml", "size_kb": 0.86, "type": "file"}
    ],
    "directories": [
      {"name": "adh_cli", "type": "directory"},
      {"name": "tests", "type": "directory"},
      {"name": "docs", "type": "directory"}
    ]
  },
  "metadata": {
    "execution_time_ms": 234,
    "tools_used": ["list_directory"],
    "model": "gemini-2.0-flash-exp",
    "agent": "orchestrator"
  }
}
```

**Note**: The structure of the `response` field varies based on the agent's output. For unstructured responses, the field will contain a simple string. Tool outputs that naturally map to structured data (file listings, JSON parsing, etc.) will be represented as objects or arrays for easier consumption.

#### Markdown Format (for documentation)

```bash
$ adh-cli run "Generate API docs" --output markdown > api.md
```

### Exit Codes

Standard Unix exit codes:

- **0**: Success
- **1**: General error (tool execution failed, API error, etc.)
- **2**: Policy/permission error (operation blocked by policy)
- **130**: User interrupt (Ctrl+C)

### Policy Enforcement in Headless Mode

Policy enforcement works **identically** in both modes:

1. Same `PolicyEngine` evaluates tool calls
2. Same safety checks run (backup, permissions, etc.)
3. Same audit logging
4. Only difference: confirmation UI (modal vs CLI prompt)

**Example with Policy Block**:

```bash
$ adh-cli run "Delete all .pyc files recursively" --policy strict.yaml

⛔ Policy blocked: delete_file

Tool 'delete_file' is not allowed by current policy.

Policy: deny (critical risk)
Reason: Recursive deletion operations are blocked in strict mode
Pattern matched: delete_file with recursive=true

Suggestion: Review policy settings in strict.yaml or use a less restrictive policy.

$ echo $?
2  # Policy error exit code
```

**Example with Confirmation**:

```bash
$ adh-cli run "Update README with new examples"

⚠️  Confirmation Required
============================================================
Tool: write_file
Parameters:
  path: README.md
  content: [8234 bytes]

Policy: confirm (medium risk)
Reason: File modification requires review

Safety Checks:
  ✅ Backup created: README.md.backup
  ✅ Sufficient disk space
  ✅ No sensitive data detected

============================================================
Proceed? [y/N]: y

✅ README.md updated successfully

$ echo $?
0  # Success
```

## Consequences

### Positive

**Better Architecture:**
- ✅ **Clean Separation of Concerns**: Interface layer cleanly separated from core logic
- ✅ **Reusable Components**: `AgentFactory` can be used by TUI, CLI, and future interfaces
- ✅ **Testable in Isolation**: Each layer can be tested independently
- ✅ **Foundation for Future Interfaces**: Easy to add web UI, REST API, etc.
- ✅ **Single Source of Truth**: Agent creation logic not duplicated

**New Capabilities:**
- ✅ **Scripting Support**: Can integrate into shell scripts, makefiles
- ✅ **CI/CD Integration**: Works in automated pipelines
- ✅ **Batch Processing**: Process multiple tasks sequentially
- ✅ **Programmatic Access**: Use as part of larger toolchains
- ✅ **Quick One-Shot Tasks**: Fast startup for simple queries
- ✅ **Remote Execution**: Easy to run via SSH, containers

**Developer Experience:**
- ✅ **Easier Maintenance**: Clear responsibility boundaries
- ✅ **Simpler Testing**: Mock interfaces easily
- ✅ **Better Documentation**: Clear architecture to explain
- ✅ **Easier Onboarding**: Logical code organization

**User Experience:**
- ✅ **Flexibility**: Choose mode based on task
- ✅ **Familiar Interface**: Standard CLI conventions
- ✅ **Automation Friendly**: Predictable output formats
- ✅ **Consistent Behavior**: Same policies in both modes

### Negative

**Added Complexity:**
- ❌ **More Files**: Additional modules for factory, runner, confirmation handlers
- ❌ **Dual Code Paths**: TUI and CLI have different confirmation/notification implementations
- ❌ **CLI Argument Parsing**: Need to handle multiple flags and validation
- ❌ **Mode Selection Logic**: Entry point more complex with subcommands
- ❌ **Documentation Burden**: Need to document both modes thoroughly

**Migration Work:**
- ❌ **Refactor `ADHApp`**: Extract agent creation to factory
- ❌ **Update Tests**: Ensure TUI tests still pass after refactoring
- ❌ **Backward Compatibility**: Must carefully preserve existing behavior
- ❌ **Documentation Updates**: README, CLAUDE.md, examples

**Testing Requirements:**
- ❌ **More Test Coverage Needed**: Factory, runner, confirmation handlers
- ❌ **Integration Tests**: Both modes with real policy enforcement
- ❌ **CLI Argument Tests**: Validate all flag combinations
- ❌ **Output Format Tests**: Verify text, JSON, markdown formatting

**Performance Considerations:**
- ❌ **Import Overhead**: Need lazy imports to keep headless startup fast
- ❌ **Dual Maintenance**: Changes to core must work in both modes
- ❌ **Testing Time**: More test scenarios to cover

### Risks

**Risk 1: Breaking Changes to TUI**
- **Impact:** High - Breaks existing users who rely on TUI
- **Likelihood:** Medium - Refactoring always has risk
- **Mitigation:**
  - Comprehensive test suite before refactoring
  - Default behavior unchanged (no subcommand → TUI)
  - Integration tests for TUI mode continue to pass
  - Careful refactoring with test-driven approach
  - Beta testing period before release

**Risk 2: Policy Inconsistency Between Modes**
- **Impact:** Critical - Security implications if policies differ
- **Likelihood:** Medium - Different code paths could diverge
- **Mitigation:**
  - Use same `PolicyEngine` instance in both modes
  - Shared test cases for policy enforcement
  - Document policy behavior guarantees
  - Integration tests that verify identical policy enforcement
  - Code review focused on policy consistency

**Risk 3: Poor Headless UX**
- **Impact:** Medium - Users avoid headless mode, wasted effort
- **Likelihood:** Low - With careful design
- **Mitigation:**
  - Clear, actionable error messages
  - Good output formatting options (text, JSON, markdown)
  - Sensible defaults (text output, deny on ambiguous input)
  - Comprehensive examples and documentation
  - User testing and feedback incorporation

**Risk 4: Slow Headless Startup**
- **Impact:** Medium - Defeats purpose of quick CLI mode
- **Likelihood:** High - Python import overhead is real
- **Mitigation:**
  - Lazy imports in headless path (avoid Textual)
  - Measure and optimize startup time
  - Target < 1 second for headless startup
  - Profile hot paths and optimize
  - Consider pyinstaller for faster binary

**Risk 5: Maintenance Burden of Dual Paths**
- **Impact:** Medium - Slows down future development
- **Likelihood:** Medium - Two implementations to maintain
- **Mitigation:**
  - Shared core logic via `AgentFactory`
  - Clear abstraction boundaries
  - Comprehensive tests prevent regressions
  - Good documentation of architecture
  - Regular refactoring to reduce duplication

### Neutral

**Testing Requirements:**
- Need tests for `AgentFactory.create_agent()` with and without tool registration
- Need tests for tool registration integration
- Need tests for `HeadlessRunner.run()`
- Need tests for confirmation handlers
- Need CLI integration tests
- Need mode selection tests

**Documentation Updates:**
- ADR-024 (this document)
- README.md (add headless mode section)
- CLAUDE.md (update architecture description)
- Example scripts (shell, CI/CD)
- CLI flag reference

**Configuration:**
- Same config files work for both modes
- No new configuration format needed
- Policy files unchanged

## Alternatives Considered

### Alternative 1: Separate Binary (`adh` CLI tool)

Create a separate `adh` command-line tool alongside `adh-cli` TUI application.

**Pros:**
- Complete separation of concerns
- No risk of breaking TUI mode
- Independent evolution of features
- Can optimize each separately

**Cons:**
- Significant code duplication
- Separate installation and distribution
- Confusing for users (two similar tools)
- Harder to maintain consistency
- Need to sync bug fixes across both
- Policy files would need separate management

**Why Rejected:** Unnecessary duplication; Click subcommands provide sufficient separation while sharing core logic. Modern CLI tools use subcommands (git, docker, kubectl) for different modes rather than separate binaries.

### Alternative 2: Environment Variable Mode Selection

Use `ADH_MODE=headless` environment variable to switch between modes.

**Pros:**
- No CLI interface changes needed
- Very simple implementation
- Easy backward compatibility
- Can be set in shell config

**Cons:**
- Non-obvious and hard to discover
- Not idiomatic CLI design
- Awkward for one-shot commands
- Requires documentation to discover
- Environment pollution
- Hard to combine with other env vars

**Why Rejected:** Environment variables are for configuration, not mode selection. Subcommands are the standard, discoverable way to offer different operating modes in CLI tools.

### Alternative 3: Keep Everything in TUI, Add `--batch` Flag

Add `--batch` flag to existing TUI mode that runs non-interactively.

**Pros:**
- Minimal changes to codebase
- Reuses all existing code
- No refactoring needed
- Single code path

**Cons:**
- TUI initialization overhead (~2-3s startup)
- Textual dependency even in headless mode
- Awkward confirmation handling (can't use dialogs)
- Slow startup defeats purpose
- Hard to output clean text (TUI rendering)
- Terminal size requirements

**Why Rejected:** TUI overhead is wasteful for CLI usage. Loading Textual just to print text output violates separation of concerns and kills performance for quick tasks.

### Alternative 4: HTTP API + CLI Client

Expose an HTTP API server, create CLI client that calls it.

**Pros:**
- Very clean separation
- API useful for other integrations (web UI, IDE plugins)
- Well-understood client/server pattern
- Could support multiple concurrent sessions

**Cons:**
- **Massive complexity increase**: server, client, API design
- Server management (start, stop, restart)
- Network overhead for local calls
- Authentication/authorization needed
- Process lifecycle management
- State synchronization issues
- Over-engineering for current need

**Why Rejected:** Way too complex for the current requirement of running simple CLI commands. Can add HTTP API later if demand emerges, but headless CLI mode solves 90% of automation needs with 10% of the complexity.

### Alternative 5: Interactive Prompts in TUI Mode

Add a "headless prompt" screen to TUI that reads commands from stdin.

**Pros:**
- Reuses TUI infrastructure
- Can switch to visual mode if needed
- Single codebase

**Cons:**
- Still requires TUI initialization
- Confusing UX (why launch TUI for CLI?)
- Performance overhead
- Doesn't solve scripting use case
- Complex state management

**Why Rejected:** Doesn't address the core need for fast, scriptable CLI mode. This is a hybrid that gets the worst of both worlds.

## Implementation Notes

> **Note**: This ADR serves as the architectural foundation and should be approved **before** implementation begins. The ADR guides the implementation phases below, not the reverse.

### Implementation Phases

**Phase 1: Refactor for Separation of Concerns** (No user-visible changes)
1. Create `AgentFactory` in `adh_cli/core/agent_factory.py`
2. Extract `ADHApp._build_agent()` → `AgentFactory.create_agent()`
3. Integrate tool registration into `create_agent()` (with `register_tools` parameter)
4. Refactor `ADHApp` to use factory
5. Verify all existing tests pass
6. Add tests for factory methods

**Phase 2: Implement Headless Infrastructure** (Headless components added)
7. Create `adh_cli/headless/` package
8. Implement `HeadlessRunner` class
9. Implement `cli_confirmation_handler()`
10. Implement `cli_notification_handler()`
11. Add tests for all headless components

**Phase 3: Update CLI Entry Point** (Feature complete)
12. Convert `__main__.py` to Click group
13. Add `run` subcommand for headless mode
14. Implement argument parsing and validation
15. Wire up headless components
16. Add CLI integration tests

**Phase 4: Documentation & Polish** (Production ready)
17. Update README.md with headless mode docs
18. Update CLAUDE.md with architecture description
19. Create example scripts (shell, CI/CD, batch processing)
20. Performance profiling and optimization
21. Beta testing and feedback incorporation
22. Update ADR-024 status to "Accepted" upon completion

### File Structure

```
adh_cli/
├── core/
│   ├── agent_factory.py              (NEW - Phase 1)
│   ├── policy_aware_llm_agent.py
│   ├── tool_executor.py
│   └── ...
├── headless/                          (NEW - Phase 2)
│   ├── __init__.py
│   ├── runner.py
│   ├── confirmation.py
│   └── output.py
├── app.py                             (MODIFIED - Phase 1)
├── __main__.py                        (MODIFIED - Phase 3)
└── ...

docs/
└── adr/
    └── 024-headless-cli-mode.md       (PREREQUISITE - approved before implementation)

examples/                              (NEW - Phase 4)
└── headless/
    ├── simple_query.sh
    ├── ci_integration.sh
    └── batch_processing.sh

tests/
├── core/
│   └── test_agent_factory.py         (NEW - Phase 1)
├── headless/                          (NEW - Phase 2)
│   ├── test_runner.py
│   ├── test_confirmation.py
│   └── test_output.py
└── integration/
    └── test_cli_modes.py              (NEW - Phase 3)
```

### Testing Strategy

**Unit Tests:**
```python
# tests/core/test_agent_factory.py
def test_create_agent_with_defaults()
def test_create_agent_with_custom_policy_dir()
def test_create_agent_with_custom_model()
def test_create_agent_with_tools_registered()
def test_create_agent_without_tools()
def test_safety_disabled()

# tests/headless/test_runner.py
async def test_run_success()
async def test_run_with_error()
async def test_run_with_policy_block()
async def test_output_formats()

# tests/headless/test_confirmation.py
async def test_cli_confirmation_accepts()
async def test_cli_confirmation_denies()
async def test_cli_confirmation_keyboard_interrupt()
async def test_auto_approve_mode()
```

**Integration Tests:**
```python
# tests/integration/test_cli_modes.py
def test_tui_mode_default()
def test_headless_mode_basic()
def test_headless_with_policy_file()
def test_headless_with_confirmation()
def test_policy_enforcement_consistency()
```

### Performance Targets

- **Headless startup time**: < 1 second (cold start)
- **TUI startup time**: No regression from current ~2-3s
- **Agent factory overhead**: < 100ms
- **Per-execution overhead**: < 50ms vs direct agent usage

### Configuration Compatibility

All configuration files work in both modes:

```
~/.config/adh-cli/
├── config.json              # Model, agent settings (both modes)
├── policies/                # Policy files (both modes)
│   ├── filesystem_policies.yaml
│   ├── command_policies.yaml
│   └── custom_policies.yaml
├── audit.log                # Audit log (both modes)
└── policy_preferences.yaml  # User preferences (both modes)
```

### Example Usage Scenarios

**1. Quick Code Analysis**
```bash
$ adh-cli run "Explain the main function in app.py"
```

**2. CI/CD Security Check**
```bash
#!/bin/bash
# .github/workflows/security-check.sh

adh-cli run "Analyze new dependencies for security issues" \
  --policy .ci/security-policy.yaml \
  --output json \
  > security-report.json

if [ $? -ne 0 ]; then
  echo "Security check failed"
  exit 1
fi
```

**3. Batch Documentation Generation**
```bash
for module in src/*.py; do
  echo "Documenting $module..."
  adh-cli run "Generate API documentation for $module" \
    --output markdown \
    --yes \
    > "docs/$(basename $module .py).md"
done
```

**4. Git Hook Integration**
```bash
#!/bin/bash
# .git/hooks/pre-commit

adh-cli run "Review staged changes for issues" \
  --policy .git/hooks/pre-commit-policy.yaml \
  --yes

if [ $? -eq 2 ]; then
  echo "Policy blocked commit. Review required."
  exit 1
fi
```

### Migration Path for Users

1. **Phase 1-2**: Internal refactoring, no user impact
2. **Phase 3**: New feature available, TUI unchanged
3. **Phase 4**: Documentation and examples published
4. **Future**: Deprecate nothing (both modes supported indefinitely)

Users can adopt headless mode gradually:
- Existing TUI workflows continue unchanged
- Try headless mode for automation tasks
- Migrate scripts when convenient
- No forced migration

## References

**Related ADRs:**
- ADR-001: Policy-Aware Architecture for AI Agent Safety
- ADR-003: Google ADK Integration
- ADR-009: XDG-Compliant Configuration
- ADR-010: Markdown-Driven Agent Definition

**Code References:**
- Current TUI App: `adh_cli/app.py`
- CLI Entry: `adh_cli/__main__.py`
- Policy Engine: `adh_cli/policies/policy_engine.py`
- Tool Executor: `adh_cli/core/tool_executor.py`

**Documentation:**
- README.md (to be updated)
- CLAUDE.md (to be updated)
- GitHub Issue: Headless CLI Mode Feature Request

**External References:**
- Click Documentation: https://click.palletsprojects.com/
- Click Command Groups: https://click.palletsprojects.com/en/8.1.x/commands/
- Google ADK: https://developers.google.com/adk
- Unix Exit Codes: https://tldp.org/LDP/abs/html/exitcodes.html
- CLI Design Best Practices: https://clig.dev/

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-10-26 | Address review feedback: integrate tool registration into AgentFactory.create_agent(), update JSON output to use structured data, clarify ADR as prerequisite (not Phase 4 deliverable) | Project Team |
| 2025-10-26 | Initial proposal | Project Team |
