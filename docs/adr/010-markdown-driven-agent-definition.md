# ADR 010: Markdown-Driven Agent Definition

**Status:** Accepted
**Date:** 2025-10-02
**Implemented:** 2025-10-02
**Deciders:** Project Team
**Tags:** architecture, agents, configuration, extensibility, medium-priority

---

## Context

ADH CLI currently has an inconsistency in how agents are defined:

### Current State

1. **Main Orchestrator Agent**: System prompt hardcoded in `PolicyAwareLlmAgent._get_system_instruction()`
   ```python
   def _get_system_instruction(self) -> str:
       return """You are a helpful AI assistant..."""  # 23 lines of hardcoded text
   ```

2. **Sub-Agents** (code_reviewer, researcher): Defined in markdown files with YAML frontmatter
   ```markdown
   ---
   name: code_reviewer
   description: Reviews code for quality
   model: gemini-flash-latest
   temperature: 0.3
   tools: [shell]
   ---
   # System Prompt
   You are an expert code reviewer...
   ```

### Problems

1. **Inconsistency**: Two different ways to define agents (hardcoded vs. markdown)
2. **Limited Customization**: Users can't modify orchestrator behavior without code changes
3. **Incomplete Feature**: `AgentLoader` exists but isn't used for main orchestrator
4. **Variable Injection Missing**: Hardcoded prompt doesn't support `{{variables}}`
5. **Testing Difficulty**: Can't easily test different orchestrator configurations
6. **Documentation Mismatch**: Sub-agent documentation doesn't apply to orchestrator

### Forces at Play

**User Customization Need**:
- Users want to customize AI behavior without modifying code
- Different use cases need different orchestrator personalities
- Advanced users want full control over system prompts

**Consistency Benefits**:
- Single pattern for all agents makes codebase easier to understand
- Documentation applies to all agents uniformly
- Testing infrastructure works for all agents

**Multi-Agent Vision**:
- Future: Multiple agents with different specializations
- Orchestrator is just one type of agent
- Need foundation for agent-to-agent communication

## Decision

**Make the main orchestration agent a loaded agent defined in markdown**, identical to how sub-agents are defined.

### Architecture

```
adh_cli/agents/
├── orchestrator/
│   └── agent.md          # Main orchestrator definition
├── code_reviewer/
│   └── agent.md         # Code review agent
├── researcher/
│   └── agent.md         # Research agent
└── README.md            # Agent format documentation
```

### Configuration

Add `orchestrator_agent` field to config.json:

```json
{
  "api_key": "...",
  "model": "gemini-flash-latest",
  "orchestrator_agent": "orchestrator",  // NEW
  "temperature": 0.7,
  ...
}
```

### Agent Loading Flow

```python
# In PolicyAwareLlmAgent.__init__:
1. Load config.json to get orchestrator_agent name (default: "orchestrator")
2. Use AgentLoader to load agent definition
3. Extract system prompt, model params, tool list from agent metadata
4. Use agent.render_system_prompt() with dynamic variables
5. Initialize LlmAgent with loaded configuration
```

### Variable Injection

Support dynamic variables in system prompts:

```markdown
# System Prompt

You are {{agent_role}}.

Available tools:
{{tool_descriptions}}

Current date: {{current_date}}
Project: {{project_name}}
```

Variables provided by system:
- `tool_descriptions` - Auto-generated from registered tools
- `current_date` - Current timestamp
- `agent_role` - From agent metadata

Variables from config/context:
- `project_name` - From project config
- `user_name` - From system
- Custom variables via API

## Consequences

### Positive

1. **Unified Architecture**: Single pattern for all agents
2. **User Customization**: Users can create custom orchestrators without code
3. **Better Testing**: Easy to test different configurations
4. **Multi-Agent Foundation**: Framework for future agent specializations
5. **Variable Support**: Dynamic prompt injection for context
6. **Validated AgentLoader**: Production use validates planned feature
7. **Documentation Consistency**: One set of docs for all agents
8. **Easier Onboarding**: New contributors see consistent patterns

### Negative

1. **Additional Indirection**: Load agent instead of using hardcoded prompt
2. **Startup Overhead**: Agent loading adds ~10-50ms to startup
3. **Error Handling**: File loading can fail (missing file, invalid YAML)
4. **Migration Complexity**: Need to move hardcoded prompt to markdown

### Risks

**Risk 1: Agent Loading Failures**
- **Impact**: App won't start if agent.md is missing/invalid
- **Mitigation**:
  - Ship default orchestrator/agent.md in package
  - Validate agent definition on load
  - Fall back to embedded default if load fails
  - Clear error messages with recovery instructions

**Risk 2: Variable Injection Bugs**
- **Impact**: Variables not substituted, broken prompts
- **Mitigation**:
  - Comprehensive tests for variable substitution
  - Validate required variables are provided
  - Warning if unused variables in template
  - Safe defaults for missing variables

**Risk 3: Performance Degradation**
- **Impact**: Slower startup time
- **Mitigation**:
  - Cache loaded agent definitions
  - Lazy load only when needed
  - Profile to ensure <100ms overhead
  - Consider compiled/cached prompt option

### Neutral

1. **File Organization**: More files in agents/ directory
2. **Config Schema Change**: Adds one field to config.json

## Alternatives Considered

### Alternative 1: Keep Hardcoded, Add Override

Keep hardcoded default, allow optional override via config file.

**Pros:**
- Minimal changes to current code
- Backward compatible
- Fast default path

**Cons:**
- Still maintains two patterns
- Override path rarely tested
- Doesn't validate AgentLoader
- Doesn't support variables

**Rejected because:** Doesn't solve the consistency problem.

### Alternative 2: Separate Orchestrator Config Format

Create special config format just for orchestrator (JSON/YAML, not markdown).

**Pros:**
- Could be simpler than markdown
- Structured data easier to validate

**Cons:**
- Yet another format (three total)
- Loses markdown documentation benefits
- Can't reuse AgentLoader

**Rejected because:** Creates more inconsistency, not less.

### Alternative 3: Environment Variable Overrides

Allow setting system prompt via environment variable.

**Pros:**
- Very simple implementation
- Good for testing
- No file management

**Cons:**
- Unwieldy for long prompts
- No variable support
- No metadata (model params, etc.)
- Doesn't address consistency

**Rejected because:** Too limited, doesn't address core issues.

### Alternative 4: Python-Based Agent DSL

Create Python classes for agent definitions instead of markdown.

```python
class OrchestratorAgent(Agent):
    name = "orchestrator"
    system_prompt = """..."""
    temperature = 0.7
```

**Pros:**
- Type checking
- Code completion
- Powerful Python features

**Cons:**
- Requires Python knowledge to customize
- Harder for non-programmers
- Needs code changes and restarts
- Loses markdown documentation benefits

**Rejected because:** Markdown is more accessible and maintainable.

## Implementation Notes

### Phase 1: Create Default Orchestrator Agent

**File:** `adh_cli/agents/orchestrator/agent.md`

Migrate current hardcoded prompt:

```markdown
---
name: orchestrator
description: Main orchestration agent for ADH CLI
model: gemini-flash-latest
temperature: 0.7
max_tokens: 2048
top_p: 0.95
top_k: 40
tools:
  - read_file
  - write_file
  - list_directory
  - execute_command
  - create_directory
  - delete_file
  - get_file_info
---

# System Prompt

You are a helpful AI assistant for development tasks.

You have access to tools for file system operations and command execution.
All tool usage is subject to policy enforcement and safety checks.

## Tool Usage Guidelines

{{tool_descriptions}}

- IMMEDIATELY use tools to accomplish user requests
- When you execute a tool, ALWAYS include results in your response
- Show actual data returned (file contents, directory listings, outputs)
- Format tool results clearly for the user

## Tool Execution Behavior

- If user asks about "this directory" or "current directory", use "." as path
- Execute tools RIGHT AWAY - don't ask clarifying questions unless necessary
- Only wait for confirmation when policy system requires it
- Don't ask "do you want me to..." - just do it and show results
- Be direct and action-oriented

Your goal is to be helpful and efficient - use your tools immediately.
```

### Phase 2: Update PolicyAwareLlmAgent

**File:** `adh_cli/core/policy_aware_llm_agent.py`

Changes needed:

```python
class PolicyAwareLlmAgent:
    def __init__(
        self,
        model_name: str = None,  # Make optional, load from agent
        agent_name: str = None,  # NEW: Agent to load
        api_key: Optional[str] = None,
        ...
    ):
        # Load agent definition
        agent_name = agent_name or self._get_orchestrator_name_from_config()
        self.agent_def = self._load_agent_definition(agent_name)

        # Use agent metadata
        self.model_name = model_name or self.agent_def.model
        self.temperature = self.agent_def.temperature
        self.max_tokens = self.agent_def.max_tokens

        # Rest of init...

    def _get_orchestrator_name_from_config(self) -> str:
        """Get orchestrator agent name from config."""
        config_file = ConfigPaths.get_config_file()
        if config_file.exists():
            with open(config_file) as f:
                config = json.load(f)
                return config.get("orchestrator_agent", "orchestrator")
        return "orchestrator"

    def _load_agent_definition(self, agent_name: str) -> Agent:
        """Load agent definition from markdown."""
        from ..agents.agent_loader import load_agent

        try:
            return load_agent(agent_name)
        except FileNotFoundError:
            # Fall back to embedded default
            return self._get_default_agent()

    def _get_system_instruction(self) -> str:
        """Get system instruction from loaded agent."""
        # Generate tool descriptions
        tool_descriptions = self._generate_tool_descriptions()

        # Render with variables
        variables = {
            "tool_descriptions": tool_descriptions,
            "current_date": datetime.now().isoformat(),
            "agent_role": self.agent_def.description,
        }

        return self.agent_def.render_system_prompt(variables)

    def _generate_tool_descriptions(self) -> str:
        """Generate descriptions of registered tools."""
        if not self.tools:
            return "No tools currently registered."

        descriptions = []
        for tool in self.tools:
            # Extract tool metadata
            name = getattr(tool, 'tool_name', 'unknown')
            # Generate description from tool
            descriptions.append(f"- {name}: ...")

        return "\n".join(descriptions)
```

### Phase 3: Update Settings UI

**File:** `adh_cli/screens/settings_modal.py`

Add orchestrator selector:

```python
def compose(self) -> ComposeResult:
    with Container():
        # ... existing fields ...

        yield Label("\nAgent Configuration")

        # Discover available agents
        agents_dir = Path(__file__).parent.parent / "agents"
        available_agents = [
            d.name for d in agents_dir.iterdir()
            if d.is_dir() and (d / "agent.md").exists()
        ]

        yield Label("Orchestrator Agent:")
        yield Select.from_values(
            available_agents,
            value="orchestrator",
            id="orchestrator-select"
        )
```

### Phase 4: Testing Strategy

**Unit Tests:**
```python
def test_load_orchestrator_from_markdown():
    """Test loading orchestrator agent from markdown."""
    agent = PolicyAwareLlmAgent(agent_name="orchestrator")
    assert agent.agent_def.name == "orchestrator"
    assert "helpful AI assistant" in agent._get_system_instruction()

def test_variable_injection_in_prompt():
    """Test variables are injected into system prompt."""
    agent = PolicyAwareLlmAgent(agent_name="orchestrator")
    instruction = agent._get_system_instruction()
    assert "{{" not in instruction  # No unsubstituted variables
    assert "tool_descriptions" not in instruction  # Variable was replaced

def test_custom_orchestrator():
    """Test loading a custom orchestrator."""
    # Create temp agent.md
    with temp_agent_file() as agent_path:
        agent = PolicyAwareLlmAgent(agent_name="custom")
        assert agent.temperature == 0.5  # From custom config

def test_fallback_on_missing_agent():
    """Test fallback when agent file missing."""
    agent = PolicyAwareLlmAgent(agent_name="nonexistent")
    assert agent.agent_def is not None  # Used fallback
```

**Integration Tests:**
```python
async def test_orchestrator_with_tools():
    """Test orchestrator loads tools from agent definition."""
    agent = PolicyAwareLlmAgent(agent_name="orchestrator")
    # Register tools
    agent.register_tool(...)
    # Verify tool descriptions in prompt
    instruction = agent._get_system_instruction()
    assert "read_file" in instruction

async def test_config_orchestrator_selection():
    """Test config.json orchestrator selection."""
    # Set config to use custom orchestrator
    config = {"orchestrator_agent": "researcher"}
    # Initialize app
    app = ADHApp()
    assert app.agent.agent_def.name == "researcher"
```

### Phase 5: Migration Path

1. **Default Behavior**: Ship with orchestrator/agent.md in package
2. **Backward Compatible**: If config doesn't have `orchestrator_agent`, use "orchestrator"
3. **User Communication**: Add to CHANGELOG
4. **Documentation**: Update README with customization guide

### Configuration Schema

Updated config.json schema:

```json
{
  "api_key": "string (optional)",
  "model": "string (optional, overrides agent default)",
  "orchestrator_agent": "string (default: 'orchestrator')",
  "temperature": "float (optional, overrides agent default)",
  "max_tokens": "int (optional, overrides agent default)",
  "top_p": "float (optional)",
  "top_k": "int (optional)"
}
```

Precedence for model parameters:
1. Config.json explicit overrides (if set)
2. Agent definition metadata
3. System defaults

### Future Enhancements

1. **Hot Reload**: Reload agent without restart when agent.md changes
2. **Agent Marketplace**: Share orchestrator configurations
3. **Agent Composition**: Combine multiple agent definitions
4. **Agent Templates**: Create new agents from templates
5. **Agent Metrics**: Track performance by agent configuration
6. **Multi-Agent Orchestration**: Route requests to specialized agents

## References

- Related ADRs: ADR-003 (Google ADK Integration), ADR-009 (XDG Configuration)
- Agent Definitions: `adh_cli/agents/*/agent.md`
- Agent Loader: `adh_cli/agents/agent_loader.py`
- Prompt Service: `adh_cli/services/prompt_service.py`

---

## Implementation Notes

### Completed (2025-10-02)

All planned features have been successfully implemented:

#### 1. PolicyAwareLlmAgent Enhancement
- Added `agent_name` parameter to `__init__` (default: "orchestrator")
- Integrated `AgentLoader` to load agent definitions from markdown
- Agent configuration (model, temperature, max_tokens) loaded from agent.md
- Fallback to passed parameters if agent loading fails
- File: `adh_cli/core/policy_aware_llm_agent.py`

#### 2. Tool Description Generation
- New `_generate_tool_descriptions()` method creates formatted tool documentation
- Extracts descriptions from tool function docstrings
- Returns "No tools currently available" when no tools registered
- File: `adh_cli/core/policy_aware_llm_agent.py:184-206`

#### 3. System Prompt Rendering
- Updated `_get_system_instruction()` to use agent definition
- Calls `agent.render_system_prompt()` with generated tool descriptions
- Variable substitution for `{{tool_descriptions}}` and custom variables
- Maintains fallback to hardcoded prompt if agent loading fails
- File: `adh_cli/core/policy_aware_llm_agent.py:146-182`

#### 4. Application Configuration
- Added `_load_config()` method to read config.json
- `_initialize_agent()` reads `orchestrator_agent` from config
- Defaults to "orchestrator" if not specified
- All model settings from config passed to agent (overridden by agent.md)
- File: `adh_cli/app.py:78-141`

#### 5. Settings UI Enhancement
- Added `_discover_agents()` method to find available agents
- New "Orchestrator Agent" selector in settings modal
- Dropdown populated with agents from `agents/` directory
- `orchestrator_agent` saved to config.json
- Notification warns "Restart required for agent change"
- File: `adh_cli/screens/settings_modal.py:18-39, 96-102, 149, 177, 218-223`

#### 6. Test Coverage
Added 8 new tests (303 total, up from 295):
- `test_agent_loading_default_orchestrator`: Verify orchestrator loads successfully
- `test_agent_loading_nonexistent_agent`: Test fallback behavior
- `test_generate_tool_descriptions_empty`: Test with no tools
- `test_generate_tool_descriptions_with_tools`: Test with registered tools
- `test_system_prompt_with_agent_definition`: Verify prompt uses agent.md
- `test_system_prompt_fallback_without_agent_definition`: Test fallback prompt
- `test_load_config_with_orchestrator_agent`: Verify config reading
- `test_load_config_defaults`: Test default behavior

All 303 tests passing.

### Architecture Summary

```
User → Settings UI → config.json (orchestrator_agent: "orchestrator")
                          ↓
                     ADHApp._initialize_agent()
                          ↓
                  PolicyAwareLlmAgent(agent_name="orchestrator")
                          ↓
                   AgentLoader.load("orchestrator")
                          ↓
              agents/orchestrator/agent.md (YAML + Markdown)
                          ↓
            Agent Definition (model, temp, tools, prompt)
                          ↓
            agent.render_system_prompt(tool_descriptions)
                          ↓
                 LlmAgent (ADK) with rendered prompt
```

### Backward Compatibility

- Existing configs without `orchestrator_agent` default to "orchestrator"
- If agent loading fails, falls back to hardcoded defaults
- All existing functionality preserved
- No breaking changes to API or behavior

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-10-02 | Initial decision | Allen Hutchison |
| 2025-10-02 | Implementation completed | Allen Hutchison |
