"""Prompt template service for loading and rendering markdown prompts with variable substitution."""

import re
from pathlib import Path
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass
import yaml


@dataclass
class PromptTemplate:
    """A prompt template that supports variable substitution."""

    content: str
    variables: Set[str]
    metadata: Dict[str, Any]

    @classmethod
    def from_string(cls, content: str, metadata: Optional[Dict[str, Any]] = None) -> "PromptTemplate":
        """Create a prompt template from a string.

        Args:
            content: The prompt content with {{variable}} placeholders
            metadata: Optional metadata for the prompt

        Returns:
            PromptTemplate instance
        """
        variables = cls._extract_variables(content)
        return cls(content=content, variables=variables, metadata=metadata or {})

    @classmethod
    def from_file(cls, file_path: Path) -> "PromptTemplate":
        """Load a prompt template from a markdown file.

        Args:
            file_path: Path to the markdown file

        Returns:
            PromptTemplate instance

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file format is invalid
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")

        # Check for YAML frontmatter
        metadata = {}
        if content.startswith("---"):
            try:
                # Split on the closing ---
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    yaml_content = parts[1]
                    metadata = yaml.safe_load(yaml_content) or {}
                    # Remove frontmatter from content
                    content = parts[2].strip()
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML frontmatter in {file_path}: {e}")

        variables = cls._extract_variables(content)
        return cls(content=content, variables=variables, metadata=metadata)

    @staticmethod
    def _extract_variables(content: str) -> Set[str]:
        """Extract variable names from template content.

        Args:
            content: Template content with {{variable}} placeholders

        Returns:
            Set of variable names found in the template
        """
        # Find all {{variable_name}} patterns
        pattern = r'\{\{(\w+)\}\}'
        matches = re.findall(pattern, content)
        return set(matches)

    def render(self, variables: Dict[str, Any]) -> str:
        """Render the template with provided variables.

        Args:
            variables: Dictionary of variable values

        Returns:
            Rendered template with variables substituted

        Raises:
            ValueError: If required variables are missing
        """
        # Check for missing required variables
        provided = set(variables.keys())
        required = self.variables
        missing = required - provided

        if missing:
            raise ValueError(f"Missing required variables: {missing}")

        # Perform substitution
        rendered = self.content
        for var_name, var_value in variables.items():
            pattern = f"{{{{{var_name}}}}}"
            rendered = rendered.replace(pattern, str(var_value))

        return rendered

    def validate(self, variables: Dict[str, Any]) -> bool:
        """Check if all required variables are provided.

        Args:
            variables: Dictionary of variable values

        Returns:
            True if all required variables are present
        """
        provided = set(variables.keys())
        required = self.variables
        return required.issubset(provided)


class PromptService:
    """Service for managing and loading prompt templates."""

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize the prompt service.

        Args:
            base_path: Base directory for loading prompts
        """
        self.base_path = base_path or Path.cwd()
        self._cache: Dict[str, PromptTemplate] = {}

    def load_prompt(self, name: str, use_cache: bool = True) -> PromptTemplate:
        """Load a prompt template by name.

        Args:
            name: Name of the prompt (relative path without .md extension)
            use_cache: Whether to use cached prompts

        Returns:
            Loaded PromptTemplate

        Raises:
            FileNotFoundError: If the prompt file doesn't exist
        """
        if use_cache and name in self._cache:
            return self._cache[name]

        # Try different file paths
        possible_paths = [
            self.base_path / f"{name}.md",
            self.base_path / f"{name}.prompt.md",
            self.base_path / name / "prompt.md",
        ]

        for path in possible_paths:
            if path.exists():
                prompt = PromptTemplate.from_file(path)
                if use_cache:
                    self._cache[name] = prompt
                return prompt

        raise FileNotFoundError(f"Prompt not found: {name}")

    def clear_cache(self):
        """Clear the prompt cache."""
        self._cache.clear()

    def render_prompt(self, name: str, variables: Dict[str, Any]) -> str:
        """Load and render a prompt template.

        Args:
            name: Name of the prompt
            variables: Variables to substitute

        Returns:
            Rendered prompt text
        """
        prompt = self.load_prompt(name)
        return prompt.render(variables)