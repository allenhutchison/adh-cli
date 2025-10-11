# ADR 021: Agent Tool Configuration Strategy

**Status:** Proposed
**Date:** 2025-10-09
**Deciders:** Allen Hutchison
**Tags:** architecture, agents, tools, configuration, medium-priority

---

## Context

Following the implementation of ADR-010 (Markdown-Driven Agent Definition) and ADR-016 (Multi-Agent Orchestration), we have agent definitions with YAML frontmatter that includes a `tools:` field:

```yaml
---
name: researcher
tools:
  - read_file
  - list_directory
  - get_file_info
  - execute_command
---
```

However, actual tool registration happens imperatively in `AgentDelegator._register_agent_tools()`:

```python
def _register_agent_tools(self, agent: PolicyAwareLlmAgent, agent_name: str):
    # Hardcoded logic based on agent name
    if agent_name == "researcher":
        agent.register_tool(name="execute_command", ...)
        self._register_google_search_tools(agent)  # Not in frontmatter!
```

### The Disconnect

1. **Declarative (Frontmatter)**: Lists tools in YAML - appears to be configuration
2. **Imperative (Code)**: Hardcoded if/else logic actually registers tools
3. **Reality**: The `tools:` field in frontmatter is **never read** for tool registration
4. **Documentation Drift**: Researcher gets `google_search` and `google_url_context` but these aren't listed in frontmatter

### Current Problems

1. **Two Sources of Truth**: Frontmatter documents intent, code controls behavior
2. **Maintenance Burden**: Must update both frontmatter and code when changing tools
3. **False Expectations**: Developers editing frontmatter expect it to change behavior
4. **Inconsistency Risk**: Frontmatter and actual tools can drift out of sync
5. **Discovery Difficulty**: To know what tools an agent has, must read code, not config
6. **Testing Complexity**: Tests must validate both frontmatter and actual registration match

### Forces at Play

**Configuration as Code**:
- YAML frontmatter suggests declarative, data-driven configuration
- "Markdown-driven" implies definition should control behavior
- Users expect editing YAML to change agent capabilities
- Follows industry patterns (Docker Compose, K8s, GitHub Actions)

**Tool Registry Integration** (ADR-014):
- `ToolSpec` and `ToolRegistry` already provide metadata abstraction
- Native tools require factory functions
- Registry can include both function-based and ADK native tools
- Provides single place to define tool capabilities

**Agent Ecosystem Growth**:
- More agents coming (tester, researcher enhancements, future specialists)
- Each new agent requires tool configuration
- Pattern should scale to dozens of agents
- Need to balance simplicity and power

## Decision

**Make the YAML frontmatter `tools:` field the single source of truth for agent tool configuration. All tools must be explicitly listed in the agent definition.**

### Core Principles

1. **YAML is Truth**: The `tools:` list in frontmatter is the complete, authoritative list of what tools an agent has
2. **No Hidden Tools**: Code cannot add tools not declared in frontmatter
3. **Registry as Backend**: Tool names map to `ToolSpec` entries in the registry
4. **Fail Fast**: Error immediately if frontmatter lists a tool not in registry
5. **What You See Is What You Get**: Reading the YAML tells you exactly what the agent can do

### Architecture

```
Agent Definition (agent.md)
  └── Frontmatter (YAML)
      └── tools: [read_file, execute_command, google_search, ...]
          ↓
AgentDelegator._register_agent_tools()
  ↓
  For each tool name in agent_definition.tools:
    ├── Look up ToolSpec in registry
    ├── If not found → ERROR (fail fast)
    ├── If native tool → register_native_tool()
    └── If function tool → register_tool()
```

### Implementation Pattern

```python
def _register_agent_tools(self, agent: PolicyAwareLlmAgent, agent_name: str):
    """Register tools for agent based on agent definition.

    This is purely data-driven - reads from frontmatter, looks up in registry.
    No agent-specific logic or hidden tool additions.
    """
    from ..tools.base import registry
    from ..tools.specs import register_default_specs

    # Ensure all tool specs are loaded
    register_default_specs()

    # Get agent definition
    agent_def = agent.agent_definition
    if not agent_def:
        raise ValueError(f"Agent '{agent_name}' has no definition - cannot register tools")

    # Get tool list from frontmatter
    tool_names = agent_def.tools or []
    if not tool_names:
        # Agent explicitly has no tools (valid for some agents)
        return

    # Register each tool from the list
    for tool_name in tool_names:
        spec = registry.get(tool_name)
        if spec is None:
            available = ", ".join(sorted(registry.list_tools()))
            raise ValueError(
                f"Tool '{tool_name}' not found in registry for agent '{agent_name}'. "
                f"Available tools: {available}"
            )

        # Register based on tool type
        if spec.adk_tool_factory:
            # Native ADK tool (e.g., google_search)
            agent.register_native_tool(
                name=spec.name,
                description=spec.description,
                parameters=spec.parameters,
                factory=spec.adk_tool_factory,
            )
        else:
            # Function-based tool
            agent.register_tool(
                name=spec.name,
                description=spec.description,
                parameters=spec.parameters,
                handler=spec.handler,
            )
```

### Agent Definition Example

```yaml
---
name: researcher
description: Deep research specialist with web access
model: gemini-flash-latest
temperature: 0.7
tools:
  # Filesystem exploration
  - read_file
  - list_directory
  - get_file_info

  # Command execution for searches
  - execute_command

  # Web research tools (native ADK tools)
  - google_search
  - google_url_context

variables:
  - topic
  - research_depth
  - output_format
---
```

### Tool Registry Updates

Ensure registry has entries for all tools agents might use:

```python
# In tools/specs.py

def register_default_specs():
    """Register all available tool specifications.

    Uses per-tool existence checking for idempotency, making it resilient
    to partial registrations and avoiding reliance on global state.
    """
    def add(spec: ToolSpec):
        """Add spec only if not already registered."""
        if registry.get(spec.name) is None:
            registry.register(spec)

    # Filesystem tools
    add(ToolSpec(
        name="read_file",
        description="Read contents of a text file",
        handler=shell_tools.read_file,
        ...
    ))

    # Command execution
    add(ToolSpec(
        name="execute_command",
        description="Execute a shell command",
        handler=shell_tools.execute_command,
        ...
    ))

    # Native ADK tools
    add(ToolSpec(
        name="google_search",
        description="Search the web using Google Search",
        adk_tool_factory=lambda: GoogleSearch(),  # ADK native tool
        parameters={...},
        tags=["web", "search"],
    ))

    add(ToolSpec(
        name="google_url_context",
        description="Fetch and analyze web page content",
        adk_tool_factory=lambda: GoogleUrlContext(),  # ADK native tool
        parameters={...},
        tags=["web", "fetch"],
    ))
```

## Consequences

### Positive

1. **Single Source of Truth**: YAML completely defines agent capabilities
2. **Discoverability**: Reading agent.md shows exactly what tools are available
3. **Maintainability**: Changing agent tools = editing YAML list only
4. **Validation**: Immediate errors if tool doesn't exist
5. **No Drift**: Impossible for code and docs to disagree
6. **Testability**: Simple assertion that frontmatter = registered tools
7. **Clarity**: No hidden behavior or special cases
8. **Scalability**: Adding new agents is pure configuration
9. **Predictability**: Editing YAML always works as expected

### Negative

1. **Description Customization**: Can't easily customize tool descriptions per agent (same description across all agents)
2. **Complex Setup**: If a tool needs agent-specific initialization, must create variant tool spec
3. **Registry Dependency**: All tools must be registered before agent loading
4. **Migration Work**: Must update all agent definitions to list all tools

### Addressing Tool Customization

If we need agent-specific behavior for tools (e.g., `execute_command` for tester vs. researcher), we have three options:

**Option A: Extended YAML syntax** (future enhancement):
```yaml
tools:
  - read_file
  - name: execute_command
    description: "Run read-only commands for research (e.g. rg, task list)"
  - google_search
```

**Pros:**
- Per-agent customization in YAML
- No code or prompt changes needed
- Single tool spec in registry

**Cons:**
- Requires new YAML parsing logic
- More complex agent definition format
- Description only, can't change other behavior

---

**Option B: Variant tool specs in registry**:
```python
# Register variants in tool registry
registry.register(ToolSpec(
    name="execute_command_tester",
    description="Run build/test commands (prefer `task` shortcuts)",
    handler=shell_tools.execute_command,
    ...
))

registry.register(ToolSpec(
    name="execute_command_researcher",
    description="Run read-only commands for research",
    handler=shell_tools.execute_command,
    ...
))
```

```yaml
# In tester/agent.md
tools:
  - execute_command_tester

# In researcher/agent.md
tools:
  - execute_command_researcher
```

**Pros:**
- Works with existing YAML format
- Clear distinction between variants
- No code changes to registration logic

**Cons:**
- Registry bloat (many similar specs)
- Maintenance burden (update all variants)
- Names become awkward (`execute_command_researcher`)

---

**Option C: Agent-specific instructions in system prompt** (recommended):

Registry has generic tool specs:
```python
registry.register(ToolSpec(
    name="execute_command",
    description="Execute a shell command in the repository",
    handler=shell_tools.execute_command,
    ...
))
```

YAML lists generic tool names:
```yaml
---
name: researcher
tools:
  - read_file
  - execute_command  # Generic tool
  - google_search
---

# System Prompt

You are a deep research agent...

## Tool Usage Guidelines

**execute_command**: Use for read-only exploration:
- `rg "pattern" path/` - Search file contents
- `find . -name "*.py"` - Find files
- `task list` - Show available tasks
- Do NOT use for destructive operations (policy will block them)

**google_search** and **google_url_context**: Use when repository
materials are insufficient. Always cite external sources.
```

Meanwhile, the tester agent has different instructions:
```yaml
---
name: tester
tools:
  - execute_command  # Same tool
---

# System Prompt

You validate builds and tests...

## Tool Usage Guidelines

**execute_command**: Run validation commands:
- `task lint` - Run linting
- `task test` - Run test suite
- `task build` - Build the project
- Prefer `task` shortcuts over direct commands
```

**Pros:**
- No registry bloat - one spec serves all agents
- No new YAML syntax required
- Instructions live with the agent that uses them
- LLM gets both generic spec + contextual guidance
- Can include examples, warnings, best practices
- Easier to maintain - update agent prompt, not registry
- Most flexible - can describe nuanced usage patterns

**Cons:**
- Customization split between registry and prompt
- Longer agent prompts
- Must read agent definition to see full tool behavior

**Decision**: Use **Option C (prompt-based customization)** as the primary pattern. It provides the best balance of simplicity, flexibility, and maintainability. Registry provides generic tool specifications, agent prompts provide contextual usage guidance.

### Risks

**Risk 1: Tool Name Typos**
- **Impact**: Agent fails to load
- **Mitigation**: Clear error with list of available tools, validation in CI/tests

**Risk 2: Registry Completeness**
- **Impact**: Can't use tool if not in registry
- **Mitigation**: Comprehensive registry, documentation on adding tools, clear errors

**Risk 3: Prompt Instructions Ignored**
- **Impact**: LLM may ignore agent-specific tool instructions in prompt
- **Mitigation**: Place tool guidelines prominently in system prompt, use clear formatting, reinforce in examples, test agent behavior with different tools

### Neutral

1. **Prompt Length**: Agent prompts are longer with tool usage guidelines
2. **Agent Definition Length**: YAML lists may be longer (but more explicit)
3. **Split Responsibility**: Tool definition in registry, usage guidance in prompt

## Alternatives Considered

### Alternative 1: Hybrid (Code Extensions Allowed)

Allow code to add tools not in frontmatter for "special cases":

```python
# Read from frontmatter
for tool_name in agent_def.tools:
    register_tool(tool_name)

# Also allow code extensions
if agent_name == "researcher":
    register_tool("secret_special_tool")
```

**Pros:**
- Maximum flexibility
- Easy to add one-off tools

**Cons:**
- Breaks single source of truth
- Hidden behavior returns
- Testing complexity
- Documentation drift risk

**Rejected because:** Defeats the purpose of making YAML authoritative.

### Alternative 2: Pure Code (Remove Frontmatter Tools)

Remove `tools:` field entirely, all registration in code:

```python
def _register_agent_tools(self, agent, agent_name):
    if agent_name == "researcher":
        for tool in ["read_file", "execute_command", "google_search"]:
            register_tool_from_registry(tool)
```

**Pros:**
- Single place (code)
- No ambiguity
- Maximum flexibility

**Cons:**
- Violates markdown-driven philosophy (ADR-010)
- Must read code to understand agents
- Harder to modify for non-developers
- Can't generate agent documentation automatically

**Rejected because:** Goes against ADR-010's core principle of markdown-driven configuration.

### Alternative 3: Full Tool Config in YAML

Put complete tool specifications in each agent's YAML:

```yaml
tools:
  - name: execute_command
    description: "Run commands..."
    handler: shell_tools.execute_command
    parameters:
      command: {type: string}
      timeout: {type: integer, default: 300}
```

**Pros:**
- Ultimate flexibility
- Per-agent customization
- Self-contained agent definitions

**Cons:**
- Massive YAML duplication
- Hard to maintain (update tool = update N agent files)
- Violates DRY
- Can't reference Python handlers easily in YAML
- Loses benefit of tool registry

**Rejected because:** Too much duplication, loses registry benefits, YAML becomes unwieldy.

## Implementation Plan

### Phase 1: Enhance Tool Registry

1. Add all native tools to registry with `adk_tool_factory`:
   - `google_search`
   - `google_url_context`

2. Add helper method to registry:
   ```python
   def list_tools(self) -> list[str]:
       """Return sorted list of all registered tool names."""
       return sorted(self._tools.keys())
   ```

3. Ensure all tool specs have generic, reusable descriptions:
   - `execute_command`: "Execute a shell command in the repository"
   - `google_search`: "Search the web using Google Search"
   - Agent-specific usage guidance will be in agent prompts (Option C)

### Phase 2: Update AgentDelegator

1. Replace `_register_agent_tools()` with pure data-driven implementation
2. Remove all agent-specific if/else logic
3. Remove helper methods (`_register_execute_command_tool`, `_register_google_search_tools`)
4. Add validation and clear error messages

### Phase 3: Update Agent Definitions

Update all agent.md files to list complete tool sets and add tool usage guidelines:

- `orchestrator/agent.md`: Add full tool list + usage guidelines
- `planner/agent.md`: Add tool list + usage guidelines (read-only exploration)
- `code_reviewer/agent.md`: Verify tool list + add usage guidelines
- `researcher/agent.md`: Add `google_search`, `google_url_context` to YAML + add guidelines for web research and read-only commands
- `tester/agent.md`: Add complete tool list + guidelines for build/test commands

Each agent should include a "Tool Usage Guidelines" section in the system prompt explaining how that agent should use each tool (Option C pattern).

### Phase 4: Update Tests

Implement comprehensive testing strategy as detailed in the [Testing Strategy](#testing-strategy) section below:
1. Remove tests validating hardcoded registration logic
2. Add tests for YAML-driven registration
3. Add tests for invalid tool names with clear error messages
4. Add tests for native ADK tool registration
5. Add tests ensuring no hidden tools
6. Add registry completeness tests across all agents

### Phase 5: Documentation

1. Update `adh_cli/agents/README.md`:
   - Explain tools field is authoritative
   - Show how to add new tools
   - Document Option C pattern (prompt-based customization)
   - Provide examples of tool usage guidelines in prompts

2. Update contributing docs:
   - How to add new tool to registry
   - How to add tool to agent YAML
   - How to write tool usage guidelines in agent prompts
   - Best practices for agent-specific instructions

3. Add validation to CI:
   - Ensure all agent tools exist in registry
   - Lint check for tool name typos

## Testing Strategy

```python
# Test 1: YAML drives registration
def test_yaml_tools_are_registered():
    """All tools in YAML frontmatter are registered with agent."""
    delegator = AgentDelegator(api_key="test", policy_dir=None)
    # Researcher lists 6 tools in YAML
    agent = await delegator._create_agent("researcher")

    expected = {"read_file", "list_directory", "get_file_info",
                "execute_command", "google_search", "google_url_context"}
    actual = {tool.name for tool in agent.tools}
    assert actual == expected

# Test 2: Invalid tool fails fast
def test_invalid_tool_name_raises():
    """Tool not in registry causes immediate error."""
    with temp_agent_definition(tools=["read_file", "fake_tool"]):
        with pytest.raises(ValueError) as exc:
            delegator = AgentDelegator(api_key="test", policy_dir=None)
            await delegator._create_agent("bad_agent")

        assert "fake_tool" in str(exc.value)
        assert "not found in registry" in str(exc.value)
        assert "Available tools:" in str(exc.value)

# Test 3: Native tools work
def test_native_adk_tools_registered():
    """Native ADK tools are registered correctly."""
    delegator = AgentDelegator(api_key="test", policy_dir=None)
    agent = await delegator._create_agent("researcher")

    google_tools = [t for t in agent.tools
                    if t.name in ("google_search", "google_url_context")]
    assert len(google_tools) == 2

    # Verify they're native tools (have adk_tool_factory)
    for tool_name in ("google_search", "google_url_context"):
        spec = registry.get(tool_name)
        assert spec.adk_tool_factory is not None

# Test 4: No hidden tools
def test_no_hidden_tools():
    """Agent only has tools declared in frontmatter."""
    delegator = AgentDelegator(api_key="test", policy_dir=None)
    agent = await delegator._create_agent("code_reviewer")

    declared = set(agent.agent_definition.tools)
    registered = {tool.name for tool in agent.tools}

    # No extras
    assert registered == declared
    # No missing
    assert declared == registered

# Test 5: Registry completeness
def test_registry_has_all_tools():
    """Registry includes specs for all tools used by agents."""
    from pathlib import Path
    from adh_cli.agents.agent_loader import load_agent

    agents_dir = Path("adh_cli/agents")
    all_tools = set()

    for agent_dir in agents_dir.iterdir():
        if agent_dir.is_dir() and (agent_dir / "agent.md").exists():
            agent = load_agent(agent_dir.name)
            all_tools.update(agent.tools)

    for tool_name in all_tools:
        assert registry.get(tool_name) is not None, \
            f"Tool '{tool_name}' used by agents but not in registry"
```

## Migration Checklist

- [ ] Add native tools to registry (`google_search`, `google_url_context`)
- [ ] Add `registry.list_tools()` helper method
- [ ] Rewrite `_register_agent_tools()` to be pure data-driven
- [ ] Remove agent-specific registration logic and helper methods
- [ ] Update `researcher/agent.md` to include web tools in YAML
- [ ] Update all other agent definitions with complete tool lists
- [ ] Update tests to validate YAML-driven behavior
- [ ] Add test for invalid tool names
- [ ] Add test for registry completeness
- [ ] Update documentation (README, contributing guide)
- [ ] Add CI validation for agent tool references

## References

- **Related ADRs**:
  - ADR-010: Markdown-Driven Agent Definition (foundation)
  - ADR-014: Tool Spec Registry (tool metadata system)
  - ADR-016: Multi-Agent Orchestration (AgentDelegator context)
- **Code**:
  - `adh_cli/core/agent_delegator.py` - Tool registration
  - `adh_cli/tools/base.py` - ToolSpec and registry
  - `adh_cli/tools/specs.py` - Tool spec definitions
  - `adh_cli/agents/*/agent.md` - Agent definitions

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-10-09 | Initial proposal (pure YAML-driven approach) | Allen Hutchison |
| 2025-10-09 | Added Option C (prompt-based customization) as recommended approach | Allen Hutchison |
| 2025-10-11 | Improved idempotency pattern for register_default_specs(), consolidated testing sections | Allen Hutchison |
