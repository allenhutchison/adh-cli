"""Tool registration and discovery system."""

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from ..services.prompt_service import PromptTemplate


@dataclass
class Tool:
    """Represents a registered tool with its functions and metadata."""

    name: str
    path: Path
    functions: Dict[str, Callable]
    prompt: Optional[PromptTemplate]
    metadata: Dict[str, Any]


class ToolRegistry:
    """Registry for discovering and managing tools."""

    def __init__(self, tools_dir: Optional[Path] = None):
        """Initialize the tool registry.

        Args:
            tools_dir: Directory containing tool packages
        """
        if tools_dir is None:
            # Default to adh_cli/tools directory
            tools_dir = Path(__file__).parent
        self.tools_dir = tools_dir
        self._tools: Dict[str, Tool] = {}
        self._discover_tools()

    def _discover_tools(self):
        """Discover all tools in the tools directory."""
        # Look for subdirectories in tools_dir
        for item in self.tools_dir.iterdir():
            if item.is_dir() and not item.name.startswith('_'):
                # Skip __pycache__ and private directories
                if item.name == '__pycache__':
                    continue

                # Check if it has a tool.py file
                tool_module_path = item / "tool.py"
                if tool_module_path.exists():
                    self._load_tool(item.name, item)

    def _load_tool(self, name: str, path: Path):
        """Load a tool from its directory.

        Args:
            name: Name of the tool
            path: Path to the tool directory
        """
        try:
            # Load the tool module
            module_name = f"adh_cli.tools.{name}.tool"
            spec = importlib.util.spec_from_file_location(
                module_name,
                path / "tool.py"
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Extract functions from the module
                functions = {}
                for item_name in dir(module):
                    item = getattr(module, item_name)
                    if callable(item) and not item_name.startswith('_'):
                        # Only include actual functions defined in the module
                        if inspect.isfunction(item):
                            functions[item_name] = item

                # Load prompt if it exists
                prompt = None
                prompt_path = path / "prompt.md"
                if prompt_path.exists():
                    prompt = PromptTemplate.from_file(prompt_path)

                # Extract metadata from prompt or module
                metadata = {}
                if prompt and prompt.metadata:
                    metadata = prompt.metadata
                elif hasattr(module, '__metadata__'):
                    metadata = module.__metadata__

                # Create and register the tool
                tool = Tool(
                    name=name,
                    path=path,
                    functions=functions,
                    prompt=prompt,
                    metadata=metadata
                )
                self._tools[name] = tool

        except Exception as e:
            print(f"Error loading tool {name}: {e}")

    def register_tool(self, name: str, tool: Tool):
        """Manually register a tool.

        Args:
            name: Name to register the tool under
            tool: Tool instance to register
        """
        self._tools[name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name.

        Args:
            name: Name of the tool

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def get_functions(self, tool_names: List[str]) -> List[Callable]:
        """Get all functions from specified tools.

        Args:
            tool_names: List of tool names to get functions from

        Returns:
            List of callable functions
        """
        functions = []
        for tool_name in tool_names:
            tool = self.get_tool(tool_name)
            if tool:
                functions.extend(tool.functions.values())
        return functions

    def get_tool_descriptions(self, tool_names: List[str]) -> str:
        """Get formatted descriptions of specified tools.

        Args:
            tool_names: List of tool names to describe

        Returns:
            Formatted string with tool descriptions
        """
        descriptions = []
        for tool_name in tool_names:
            tool = self.get_tool(tool_name)
            if tool and tool.prompt:
                # Use the prompt content as description
                descriptions.append(f"## {tool.name}\n{tool.prompt.content}")
            elif tool:
                # Fall back to function docstrings
                desc_lines = [f"## {tool.name}"]
                for func_name, func in tool.functions.items():
                    if func.__doc__:
                        desc_lines.append(f"\n### {func_name}")
                        desc_lines.append(func.__doc__.strip())
                descriptions.append("\n".join(desc_lines))

        return "\n\n".join(descriptions)

    def list_tools(self) -> List[str]:
        """Get list of all available tool names.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def reload_tool(self, name: str):
        """Reload a tool (useful for development).

        Args:
            name: Name of the tool to reload
        """
        if name in self._tools:
            # Remove the old tool first
            old_tool = self._tools[name]
            path = old_tool.path

            # Remove module from sys.modules to force reload
            module_name = f"adh_cli.tools.{name}.tool"
            if module_name in sys.modules:
                del sys.modules[module_name]

            del self._tools[name]
            # Reload from disk
            self._load_tool(name, path)