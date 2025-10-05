"""Tool specifications for built-in tools.

This file defines the metadata (name, description, parameters, tags, effects)
for each tool, separate from the implementation handlers.
"""

from __future__ import annotations

from .base import ToolSpec, registry
from . import shell_tools, web_tools


def register_default_specs() -> None:
    """Register the built-in tool specs in the global registry.

    This function is idempotent: calling it multiple times will not
    duplicate registrations.
    """

    def add(spec: ToolSpec) -> None:
        if registry.get(spec.name) is None:
            registry.register(spec)

    add(
        ToolSpec(
            name="read_file",
            description="Read contents of a text file",
            parameters={
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read",
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Optional max lines to read",
                    "nullable": True,
                },
            },
            handler=shell_tools.read_file,
            tags=["filesystem", "read"],
            effects=["reads_fs"],
        )
    )

    add(
        ToolSpec(
            name="write_file",
            description="Write content to a file",
            parameters={
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to write",
                },
                "content": {"type": "string", "description": "Content to write"},
                "create_dirs": {
                    "type": "boolean",
                    "description": "Create parent dirs if missing",
                    "default": True,
                },
            },
            handler=shell_tools.write_file,
            tags=["filesystem", "write"],
            effects=["writes_fs"],
        )
    )

    add(
        ToolSpec(
            name="list_directory",
            description="List contents of a directory",
            parameters={
                "directory": {
                    "type": "string",
                    "description": "Directory path",
                    "default": ".",
                },
                "show_hidden": {
                    "type": "boolean",
                    "description": "Include dotfiles",
                    "default": False,
                },
            },
            handler=shell_tools.list_directory,
            tags=["filesystem", "read"],
            effects=["reads_fs"],
        )
    )

    add(
        ToolSpec(
            name="execute_command",
            description="Execute a shell command",
            parameters={
                "command": {"type": "string", "description": "Command to execute"},
                "cwd": {
                    "type": "string",
                    "description": "Working directory",
                    "nullable": True,
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout seconds",
                    "default": 30,
                },
                "shell": {
                    "type": "boolean",
                    "description": "Use shell execution",
                    "default": True,
                },
            },
            handler=shell_tools.execute_command,
            tags=["process", "shell"],
            effects=["executes_process"],
        )
    )

    add(
        ToolSpec(
            name="create_directory",
            description="Create a new directory",
            parameters={
                "directory": {
                    "type": "string",
                    "description": "Directory path to create",
                },
                "parents": {
                    "type": "boolean",
                    "description": "Create parent dirs",
                    "default": True,
                },
            },
            handler=shell_tools.create_directory,
            tags=["filesystem", "write"],
            effects=["writes_fs"],
        )
    )

    add(
        ToolSpec(
            name="delete_file",
            description="Delete a file (requires confirmation)",
            parameters={
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to delete",
                },
                "confirm": {"type": "boolean", "description": "Must be true to delete"},
            },
            handler=shell_tools.delete_file,
            tags=["filesystem", "write", "destructive"],
            effects=["writes_fs", "deletes_fs"],
        )
    )

    add(
        ToolSpec(
            name="get_file_info",
            description="Get information about a file or directory",
            parameters={
                "file_path": {
                    "type": "string",
                    "description": "Path to the file or directory",
                },
            },
            handler=shell_tools.get_file_info,
            tags=["filesystem", "read"],
            effects=["reads_fs"],
        )
    )

    # Networking tools
    add(
        ToolSpec(
            name="fetch_url",
            description="Fetch content from a URL (GET) with size/time limits",
            parameters={
                "url": {"type": "string", "description": "HTTP/HTTPS URL to fetch"},
                "timeout": {
                    "type": "integer",
                    "description": "Timeout seconds",
                    "default": 20,
                },
                "max_bytes": {
                    "type": "integer",
                    "description": "Max bytes to read",
                    "default": 500000,
                },
                "as_text": {
                    "type": "boolean",
                    "description": "Decode text instead of base64",
                    "default": True,
                },
                "encoding": {
                    "type": "string",
                    "description": "Text encoding override",
                    "nullable": True,
                },
                "headers": {
                    "type": "object",
                    "description": "Optional request headers",
                    "nullable": True,
                },
            },
            handler=web_tools.fetch_url,
            tags=["network", "http", "fetch"],
            effects=["network_read"],
        )
    )


def get_registered_specs():
    """Helper for callers that need the current spec list."""
    return registry.all()
