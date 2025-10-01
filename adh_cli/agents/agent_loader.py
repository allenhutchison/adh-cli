"""Agent loader for markdown-driven agents."""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from ..services.prompt_service import PromptTemplate


@dataclass
class Agent:
    """Represents an AI agent configured from markdown."""

    name: str
    description: str
    model: str = "gemini-flash-latest"
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.95
    top_k: int = 40
    tools: List[str] = field(default_factory=list)
    variables: Set[str] = field(default_factory=set)
    system_prompt: str = ""
    user_prompt_template: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def render_system_prompt(self, variables: Dict[str, Any], tool_descriptions: str = "") -> str:
        """Render the system prompt with variables.

        Args:
            variables: Variables to substitute
            tool_descriptions: Descriptions of available tools

        Returns:
            Rendered system prompt
        """
        # Add tool descriptions to variables
        all_vars = {**variables, "tool_descriptions": tool_descriptions}

        # Simple variable substitution
        prompt = self.system_prompt
        for var_name, var_value in all_vars.items():
            prompt = prompt.replace(f"{{{{{var_name}}}}}", str(var_value))
        return prompt

    def render_user_prompt(self, variables: Dict[str, Any]) -> str:
        """Render the user prompt template with variables.

        Args:
            variables: Variables to substitute

        Returns:
            Rendered user prompt
        """
        prompt = self.user_prompt_template
        for var_name, var_value in variables.items():
            prompt = prompt.replace(f"{{{{{var_name}}}}}", str(var_value))
        return prompt


class AgentLoader:
    """Loads agents from markdown files."""

    def __init__(self, agents_dir: Optional[Path] = None):
        """Initialize the agent loader.

        Args:
            agents_dir: Directory containing agent definitions
        """
        if agents_dir is None:
            # Default to adh_cli/agents directory
            agents_dir = Path(__file__).parent
        self.agents_dir = agents_dir

    def load(self, name: str, variables: Optional[Dict[str, Any]] = None) -> Agent:
        """Load an agent from its markdown definition.

        Args:
            name: Name of the agent
            variables: Initial variables for the agent

        Returns:
            Loaded Agent instance

        Raises:
            FileNotFoundError: If agent file not found
            ValueError: If agent file is invalid
        """
        # Look for agent.md in the agent's directory
        agent_path = self.agents_dir / name / "agent.md"
        if not agent_path.exists():
            raise FileNotFoundError(f"Agent not found: {name}")

        content = agent_path.read_text(encoding="utf-8")

        # Parse YAML frontmatter and content
        metadata = {}
        markdown_content = content

        if content.startswith("---"):
            try:
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    yaml_content = parts[1]
                    metadata = yaml.safe_load(yaml_content) or {}
                    markdown_content = parts[2].strip()
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML frontmatter in {agent_path}: {e}")

        # Parse the markdown content for sections
        system_prompt = ""
        user_prompt_template = ""

        # Split by headers
        sections = {}
        current_section = None
        current_content = []

        for line in markdown_content.split("\n"):
            if line.startswith("# "):
                # Save previous section
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                # Start new section
                current_section = line[2:].strip().lower()
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_section:
            sections[current_section] = "\n".join(current_content).strip()

        # Extract prompts from sections
        system_prompt = sections.get("system prompt", "")
        user_prompt_template = sections.get("user prompt template", sections.get("user prompt", ""))

        # Extract variables from prompts
        all_text = f"{system_prompt}\n{user_prompt_template}"
        import re
        variable_pattern = r'\{\{(\w+)\}\}'
        found_variables = set(re.findall(variable_pattern, all_text))

        # Remove special variables that are provided by the system
        special_vars = {"tool_descriptions"}
        agent_variables = found_variables - special_vars

        # Add explicitly declared variables from metadata
        if "variables" in metadata:
            for var in metadata["variables"]:
                if isinstance(var, str):
                    agent_variables.add(var)

        # Create the agent
        agent = Agent(
            name=metadata.get("name", name),
            description=metadata.get("description", ""),
            model=metadata.get("model", "gemini-flash-latest"),
            temperature=metadata.get("temperature", 0.7),
            max_tokens=metadata.get("max_tokens", 2048),
            top_p=metadata.get("top_p", 0.95),
            top_k=metadata.get("top_k", 40),
            tools=metadata.get("tools", []),
            variables=agent_variables,
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            metadata=metadata
        )

        return agent


def load_agent(name: str, variables: Optional[Dict[str, Any]] = None, agents_dir: Optional[Path] = None) -> Agent:
    """Convenience function to load an agent.

    Args:
        name: Name of the agent
        variables: Initial variables for the agent
        agents_dir: Directory containing agent definitions

    Returns:
        Loaded Agent instance
    """
    loader = AgentLoader(agents_dir)
    return loader.load(name, variables)