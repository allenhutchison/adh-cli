"""Tests for the agent loader."""

import pytest
from adh_cli.agents.agent_loader import Agent, AgentLoader, load_agent
from adh_cli.config.models import ModelRegistry


class TestAgent:
    """Test Agent class."""

    def test_init_defaults(self):
        """Test agent initialization with defaults."""
        agent = Agent(name="test_agent", description="Test agent")

        assert agent.name == "test_agent"
        assert agent.description == "Test agent"
        assert agent.model == ModelRegistry.DEFAULT.id
        assert agent.model_config.id == ModelRegistry.DEFAULT.id
        assert agent.temperature == 0.7
        assert agent.max_tokens == 2048
        assert agent.tools == []
        assert agent.variables == set()

    def test_init_custom(self):
        """Test agent initialization with custom values."""
        agent = Agent(
            name="custom",
            description="Custom agent",
            model="gemini-pro",
            temperature=0.3,
            max_tokens=4096,
            tools=["shell", "web"],
            variables={"var1", "var2"},
        )

        assert agent.model == "gemini-pro"
        assert agent.model_config.id == ModelRegistry.PRO_25.id
        assert agent.temperature == 0.3
        assert agent.max_tokens == 4096
        assert agent.tools == ["shell", "web"]
        assert agent.variables == {"var1", "var2"}

    def test_render_system_prompt_simple(self):
        """Test rendering system prompt."""
        agent = Agent(
            name="test",
            description="Test",
            system_prompt="You are a {{role}} assistant.",
        )

        result = agent.render_system_prompt({"role": "helpful"})
        assert result == "You are a helpful assistant."

    def test_render_system_prompt_with_tools(self):
        """Test rendering system prompt with tool descriptions."""
        agent = Agent(
            name="test",
            description="Test",
            system_prompt="You are an assistant.\n\nTools:\n{{tool_descriptions}}",
        )

        result = agent.render_system_prompt({}, "Tool 1\nTool 2")
        assert result == "You are an assistant.\n\nTools:\nTool 1\nTool 2"

    def test_render_user_prompt(self):
        """Test rendering user prompt."""
        agent = Agent(
            name="test",
            description="Test",
            user_prompt_template="Please {{action}} the {{target}}.",
        )

        result = agent.render_user_prompt({"action": "review", "target": "code"})
        assert result == "Please review the code."


class TestAgentLoader:
    """Test AgentLoader class."""

    def test_init_default(self):
        """Test default initialization."""
        loader = AgentLoader()
        assert loader.agents_dir.name == "agents"

    def test_init_custom_dir(self, tmp_path):
        """Test initialization with custom directory."""
        loader = AgentLoader(agents_dir=tmp_path)
        assert loader.agents_dir == tmp_path

    def test_load_simple_agent(self, tmp_path):
        """Test loading a simple agent."""
        # Create agent directory and file
        agent_dir = tmp_path / "simple"
        agent_dir.mkdir()
        agent_file = agent_dir / "agent.md"
        agent_file.write_text("""---
name: simple
description: Simple test agent
---

# System Prompt

You are a helpful assistant.

# User Prompt Template

Please help with: {{task}}""")

        loader = AgentLoader(agents_dir=tmp_path)
        agent = loader.load("simple")

        assert agent.name == "simple"
        assert agent.description == "Simple test agent"
        assert agent.system_prompt == "You are a helpful assistant."
        assert agent.user_prompt_template == "Please help with: {{task}}"
        assert agent.variables == {"task"}

    def test_load_agent_with_tools(self, tmp_path):
        """Test loading agent with tools configuration."""
        agent_dir = tmp_path / "tooled"
        agent_dir.mkdir()
        agent_file = agent_dir / "agent.md"
        agent_file.write_text("""---
name: tooled
description: Agent with tools
tools:
  - shell
  - web_search
---

# System Prompt

You have access to tools.

{{tool_descriptions}}""")

        loader = AgentLoader(agents_dir=tmp_path)
        agent = loader.load("tooled")

        assert agent.tools == ["shell", "web_search"]
        assert "tool_descriptions" not in agent.variables  # Special variable

    def test_load_agent_with_custom_config(self, tmp_path):
        """Test loading agent with custom configuration."""
        agent_dir = tmp_path / "custom"
        agent_dir.mkdir()
        agent_file = agent_dir / "agent.md"
        agent_file.write_text("""---
name: custom
description: Custom configured agent
model: gemini-pro
temperature: 0.3
max_tokens: 4096
top_p: 0.9
top_k: 30
---

# System Prompt

Custom agent prompt.""")

        loader = AgentLoader(agents_dir=tmp_path)
        agent = loader.load("custom")

        assert agent.model == ModelRegistry.PRO_25.id
        assert agent.model_config.id == ModelRegistry.PRO_25.id
        assert agent.temperature == 0.3
        assert agent.max_tokens == 4096
        assert agent.top_p == 0.9
        assert agent.top_k == 30

    def test_load_agent_with_explicit_variables(self, tmp_path):
        """Test loading agent with explicitly declared variables."""
        agent_dir = tmp_path / "explicit"
        agent_dir.mkdir()
        agent_file = agent_dir / "agent.md"
        agent_file.write_text("""---
name: explicit
description: Agent with explicit variables
variables:
  - language
  - framework
  - extra_var
---

# System Prompt

You work with {{language}} and {{framework}}.""")

        loader = AgentLoader(agents_dir=tmp_path)
        agent = loader.load("explicit")

        # Should include both detected and explicit variables
        assert agent.variables == {"language", "framework", "extra_var"}

    def test_load_agent_not_found(self, tmp_path):
        """Test error when agent not found."""
        loader = AgentLoader(agents_dir=tmp_path)

        with pytest.raises(FileNotFoundError, match="Agent not found: nonexistent"):
            loader.load("nonexistent")

    def test_load_agent_invalid_yaml(self, tmp_path):
        """Test error with invalid YAML frontmatter."""
        agent_dir = tmp_path / "invalid"
        agent_dir.mkdir()
        agent_file = agent_dir / "agent.md"
        agent_file.write_text("""---
invalid: yaml: syntax:
---

# System Prompt""")

        loader = AgentLoader(agents_dir=tmp_path)

        with pytest.raises(ValueError, match="Invalid YAML frontmatter"):
            loader.load("invalid")

    def test_load_agent_no_frontmatter(self, tmp_path):
        """Test loading agent without frontmatter."""
        agent_dir = tmp_path / "plain"
        agent_dir.mkdir()
        agent_file = agent_dir / "agent.md"
        agent_file.write_text("""# System Prompt

You are a helpful assistant.

# User Prompt Template

Help with {{task}}""")

        loader = AgentLoader(agents_dir=tmp_path)
        agent = loader.load("plain")

        assert agent.name == "plain"  # Uses directory name
        assert agent.description == ""
        assert agent.system_prompt == "You are a helpful assistant."
        assert agent.user_prompt_template == "Help with {{task}}"


def test_load_agent_function(tmp_path):
    """Test the convenience load_agent function."""
    # Create agent
    agent_dir = tmp_path / "test"
    agent_dir.mkdir()
    agent_file = agent_dir / "agent.md"
    agent_file.write_text("""---
name: test
description: Test agent
---

# System Prompt

Test prompt with {{var}}""")

    agent = load_agent("test", agents_dir=tmp_path)

    assert agent.name == "test"
    assert agent.variables == {"var"}
