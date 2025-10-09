# ADH CLI Agent Definitions

This directory contains agent definitions for ADH CLI. All agents, including the main orchestrator, are defined using markdown files with YAML frontmatter.

## Agent Format

Each agent is defined in its own directory with an `agent.md` file:

```
adh_cli/agents/
├── orchestrator/
│   └── agent.md          # Main orchestration agent
├── code_reviewer/
│   └── agent.md         # Code review specialist
└── researcher/
    └── agent.md         # Research specialist
```

## Agent Definition Structure

An agent definition consists of two parts:

### 1. YAML Frontmatter (Metadata)

```yaml
---
name: agent_name
description: Brief description of the agent
model: gemini-flash-latest
temperature: 0.7
max_tokens: 2048
top_p: 0.95
top_k: 40
tools:
  - tool_name_1
  - tool_name_2
variables:
  - custom_var_1
  - custom_var_2
---
```

**Fields:**
- `name`: Agent identifier (required)
- `description`: Human-readable description (required)
- `model`: Gemini model to use (default: gemini-flash-latest)
- `temperature`: Sampling temperature 0.0-1.0 (default: 0.7)
- `max_tokens`: Maximum output tokens (default: 2048)
- `top_p`: Nucleus sampling parameter (default: 0.95)
- `top_k`: Top-k sampling parameter (default: 40)
- `tools`: List of tool names this agent should have access to (optional)
- `variables`: Additional variables required by this agent (optional)

### 2. Markdown Content (Prompts)

After the frontmatter, define prompt sections using markdown headers:

```markdown
# System Prompt

The main system prompt that defines the agent's behavior, personality, and capabilities.

You can use {{variables}} for dynamic content:
- {{tool_descriptions}} - Automatically generated list of available tools
- {{current_date}} - Current timestamp
- {{agent_role}} - From the description field
- {{custom_variables}} - Any variables you define

## Subsections

You can use subsections to organize the prompt.

# User Prompt Template

Optional template for formatting user messages.

This will be used when the user provides input: {{user_input}}
```

## Variable Substitution

Variables in prompts use `{{variable_name}}` syntax and are substituted at runtime:

### Built-in Variables

These are automatically provided by the system:

- **{{tool_descriptions}}**: List of available tools with descriptions
- **{{current_date}}**: Current date/time in ISO format
- **{{agent_role}}**: The agent's description from frontmatter

### Custom Variables

You can define additional variables in the frontmatter:

```yaml
variables:
  - language
  - framework
```

Then use them in your prompt:

```markdown
You are an expert in {{language}} development using {{framework}}.
```

Custom variables must be provided when the agent is used.

## Example: Code Reviewer Agent

```markdown
---
name: code_reviewer
description: Expert code reviewer with focus on best practices
model: gemini-flash-latest
temperature: 0.3
max_tokens: 4096
tools:
  - read_file
  - list_directory
  - get_file_info
variables:
  - language
  - review_focus
---

# System Prompt

You are an expert code reviewer specializing in {{language}}.

Your role is to:
1. Identify bugs and security vulnerabilities
2. Suggest improvements for code quality
3. Explain the reasoning behind recommendations

Focus areas for this review: {{review_focus}}

## Available Tools

{{tool_descriptions}}

Use these tools to:
- Read source files
- Check for similar patterns
- Verify dependencies
```

## Creating Custom Agents

### 1. Create Agent Directory

```bash
mkdir -p adh_cli/agents/my_agent
```

### 2. Create agent.md File

```bash
nano adh_cli/agents/my_agent/agent.md
```

### 3. Define Agent

Follow the format above with frontmatter and prompt sections.

### 4. Use the Agent

For the orchestrator, set in config.json:

```json
{
  "orchestrator_agent": "my_agent"
}
```

For sub-agents, load programmatically:

```python
from adh_cli.agents.agent_loader import load_agent

agent = load_agent("my_agent", variables={
    "custom_var": "value"
})
```

## Best Practices

### Prompt Design

1. **Be Specific**: Clearly define the agent's role and capabilities
2. **Use Subsections**: Organize complex prompts with markdown headers
3. **Show Examples**: Include examples in the prompt when helpful
4. **Set Expectations**: Tell the agent how to format responses
5. **Use Variables**: Make prompts dynamic and reusable

### Model Configuration

1. **Temperature**: Lower (0.0-0.3) for deterministic tasks, higher (0.7-1.0) for creative tasks
2. **Max Tokens**: Set based on expected response length
3. **Tools**: Only include tools the agent actually needs

### Testing

Always test your agent definitions:

```python
def test_my_agent():
    agent = load_agent("my_agent")
    assert agent.name == "my_agent"
    assert agent.temperature == 0.7
    # Test prompt rendering
    prompt = agent.render_system_prompt({
        "tool_descriptions": "tools here",
        "custom_var": "test"
    })
    assert "{{" not in prompt  # No unsubstituted variables
```

## Troubleshooting

### Agent Not Found

Error: `FileNotFoundError: Agent not found: my_agent`

**Solution**: Ensure `adh_cli/agents/my_agent/agent.md` exists

### Invalid YAML

Error: `ValueError: Invalid YAML frontmatter`

**Solution**: Validate YAML syntax, ensure three dashes before and after

### Unsubstituted Variables

Prompt shows `{{variable_name}}` instead of value

**Solution**: Provide all required variables when rendering prompt

### Missing Tools

Error: `Tool 'tool_name' not found`

**Solution**: Ensure tools are registered before agent initialization

## Architecture

The agent definition system uses:

- **AgentLoader** (`adh_cli/agents/agent_loader.py`): Loads and parses agent.md files
- **Agent** (dataclass): Represents loaded agent definition
- **PromptTemplate** (`adh_cli/services/prompt_service.py`): Handles variable substitution

## See Also

- ADR-010: Markdown-Driven Agent Definition
- ADR-003: Google ADK Integration
- PolicyAwareLlmAgent: Uses agents for orchestration
- Agent Loader Tests: `tests/agents/test_agent_loader.py`
