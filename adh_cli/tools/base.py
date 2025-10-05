"""Tool spec and registry primitives for ADH CLI tools.

This layer separates tool metadata (name, description, parameters, tags)
from the concrete handler implementation (callable).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from google.adk.tools.base_tool import BaseTool


@dataclass(frozen=True)
class ToolSpec:
    """Specification describing a tool the agent can call.

    - `parameters` follows a JSONSchema-like shape used by the agent/LLM.
    - `tags` provide semantic hints (e.g., "filesystem", "read", "write").
    - `effects` describe side effects for policy/safety (e.g., ["reads_fs"], ["writes_fs"]).
    """

    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Optional[Callable[..., Any]] = None
    tags: List[str] = field(default_factory=list)
    effects: List[str] = field(default_factory=list)
    adk_tool_factory: Optional[Callable[[], BaseTool]] = None

    def __post_init__(self) -> None:
        """Validate mutually exclusive handler/adk_tool_factory configuration."""
        has_handler = self.handler is not None
        has_factory = self.adk_tool_factory is not None
        if has_handler == has_factory:
            raise ValueError(
                "ToolSpec requires exactly one of 'handler' or 'adk_tool_factory'"
            )

    def create_adk_tool(self) -> Optional[BaseTool]:
        """Instantiate the underlying ADK tool, if a factory is defined."""
        if self.adk_tool_factory is None:
            return None
        return self.adk_tool_factory()


class ToolRegistry:
    """In-memory registry of tool specifications."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def all(self) -> List[ToolSpec]:
        return list(self._tools.values())

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)


# Global, simple registry used by the app at startup
registry = ToolRegistry()
