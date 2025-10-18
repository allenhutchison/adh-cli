"""Data models and utilities for tool execution tracking and display."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, List
from adh_cli.policies.policy_types import PolicyDecision


class ToolExecutionState(Enum):
    """State of tool execution for UI display."""

    PENDING = "pending"  # Waiting for confirmation or policy check
    CONFIRMING = "confirming"  # Waiting for user confirmation
    EXECUTING = "executing"  # Currently executing
    SUCCESS = "success"  # Completed successfully
    FAILED = "failed"  # Failed with error
    BLOCKED = "blocked"  # Blocked by policy
    CANCELLED = "cancelled"  # User cancelled


@dataclass
class ToolExecutionInfo:
    """Information about a tool execution for display and tracking."""

    # Identity
    id: str  # Unique execution ID
    tool_name: str
    timestamp: datetime = field(default_factory=datetime.now)
    agent_name: Optional[str] = None  # Name of agent executing (for delegated agents)

    # Parameters
    parameters: Dict[str, Any] = field(default_factory=dict)

    # State
    state: ToolExecutionState = ToolExecutionState.PENDING

    # Policy & Safety
    policy_decision: Optional[PolicyDecision] = None
    requires_confirmation: bool = False
    confirmed: Optional[bool] = None

    # Execution timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Results
    result: Optional[Any] = None
    error: Optional[str] = None
    error_type: Optional[str] = None

    @property
    def duration(self) -> Optional[float]:
        """Calculate execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_terminal(self) -> bool:
        """Check if execution is in a terminal state."""
        return self.state in (
            ToolExecutionState.SUCCESS,
            ToolExecutionState.FAILED,
            ToolExecutionState.BLOCKED,
            ToolExecutionState.CANCELLED,
        )

    @property
    def status_icon(self) -> str:
        """Get icon for current state."""
        icons = {
            ToolExecutionState.PENDING: "⏳",
            ToolExecutionState.CONFIRMING: "⚠️",
            ToolExecutionState.EXECUTING: "🔧",
            ToolExecutionState.SUCCESS: "✅",
            ToolExecutionState.FAILED: "❌",
            ToolExecutionState.BLOCKED: "🚫",
            ToolExecutionState.CANCELLED: "⊗",
        }
        return icons.get(self.state, "")

    @property
    def status_text(self) -> str:
        """Get human-readable status text."""
        if self.state == ToolExecutionState.EXECUTING:
            return "Executing..."
        elif self.state == ToolExecutionState.CONFIRMING:
            return "Awaiting Confirmation"
        elif self.state == ToolExecutionState.SUCCESS:
            if self.duration:
                return f"Completed ({self.duration:.2f}s)"
            return "Completed"
        elif self.state == ToolExecutionState.FAILED:
            return "Failed"
        elif self.state == ToolExecutionState.BLOCKED:
            return "Blocked by Policy"
        elif self.state == ToolExecutionState.CANCELLED:
            return "Cancelled"
        return "Pending"


def truncate_value(value: Any, max_length: int = 50) -> tuple[str, int]:
    """Truncate a parameter value for display.

    Args:
        value: The value to truncate
        max_length: Maximum length for string representation

    Returns:
        Tuple of (display_string, original_length)
    """
    # Handle None
    if value is None:
        return "null", 4

    # Handle strings
    if isinstance(value, str):
        original_length = len(value)
        if original_length <= max_length:
            return f'"{value}"', original_length
        return f'"{value[: max_length - 4]}..."', original_length

    # Handle bytes/binary
    if isinstance(value, bytes):
        size_kb = len(value) / 1024
        if size_kb < 1:
            return f"<binary, {len(value)}B>", len(value)
        elif size_kb < 1024:
            return f"<binary, {size_kb:.1f}KB>", len(value)
        else:
            size_mb = size_kb / 1024
            return f"<binary, {size_mb:.1f}MB>", len(value)

    # Handle lists
    if isinstance(value, (list, tuple)):
        original_length = len(value)
        if original_length == 0:
            return "[]", 0
        elif original_length <= 3:
            # Show all items if few
            items_str = ", ".join(str(v) for v in value)
            if len(items_str) <= max_length:
                return f"[{items_str}]", original_length
        # Show first item and count
        first_item = str(value[0])
        if len(first_item) > 20:
            first_item = first_item[:20] + "..."
        return f"[{first_item}, ... {original_length - 1} more]", original_length

    # Handle dicts
    if isinstance(value, dict):
        original_length = len(value)
        if original_length == 0:
            return "{}", 0
        elif original_length <= 2:
            # Show all keys if few
            items_str = ", ".join(f"{k}: {v}" for k, v in value.items())
            if len(items_str) <= max_length:
                return f"{{{items_str}}}", original_length
        # Show first key and count
        first_key = list(value.keys())[0]
        first_val = value[first_key]
        pair_str = f"{first_key}: {first_val}"
        if len(pair_str) > 30:
            pair_str = pair_str[:30] + "..."
        return f"{{{pair_str}, ... {original_length - 1} more}}", original_length

    # Handle booleans
    if isinstance(value, bool):
        return str(value).lower(), len(str(value))

    # Handle numbers
    if isinstance(value, (int, float)):
        str_val = str(value)
        return str_val, len(str_val)

    # Default: convert to string and truncate
    str_val = str(value)
    original_length = len(str_val)
    if original_length <= max_length:
        return str_val, original_length
    return str_val[: max_length - 3] + "...", original_length


def format_parameters_inline(
    parameters: Dict[str, Any], max_params: int = 3, max_value_length: int = 50
) -> str:
    """Format parameters for inline display.

    Args:
        parameters: Parameter dictionary
        max_params: Maximum number of parameters to show
        max_value_length: Maximum length for each value

    Returns:
        Formatted parameter string
    """
    if not parameters:
        return ""

    parts = []
    for i, (key, value) in enumerate(parameters.items()):
        if i >= max_params:
            remaining = len(parameters) - max_params
            parts.append(f"... {remaining} more")
            break

        display_val, original_len = truncate_value(value, max_value_length)

        # Add length indicator for truncated strings
        if isinstance(value, str) and original_len > max_value_length:
            parts.append(f"{key}: {display_val} ({original_len}ch)")
        else:
            parts.append(f"{key}: {display_val}")

    return " | ".join(parts)


def format_parameters_expanded(
    parameters: Dict[str, Any], max_value_length: int = 200
) -> List[tuple[str, str, int]]:
    """Format parameters for expanded display.

    Args:
        parameters: Parameter dictionary
        max_value_length: Maximum length for each value

    Returns:
        List of (key, display_value, original_length) tuples
    """
    result = []
    for key, value in parameters.items():
        display_val, original_len = truncate_value(value, max_value_length)
        result.append((key, display_val, original_len))
    return result


# Constants for tool context summary truncation
_MAX_COMMAND_LENGTH = 60
_MAX_PATH_LENGTH = 50
_MAX_TASK_LENGTH = 40


def _truncate_from_end(value: str, max_length: int) -> str:
    """Truncate string from the end with ellipsis.

    Args:
        value: String to truncate
        max_length: Maximum length

    Returns:
        Truncated string with trailing "..."
    """
    if len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."


def _truncate_from_start(value: str, max_length: int) -> str:
    """Truncate string from the start with ellipsis.

    Args:
        value: String to truncate
        max_length: Maximum length

    Returns:
        Truncated string with leading "..."
    """
    if len(value) <= max_length:
        return value
    return "..." + value[-(max_length - 3) :]


def _get_string_param(parameters: Dict[str, Any], key: str) -> Optional[str]:
    """Safely extract a string parameter.

    Args:
        parameters: Parameter dictionary
        key: Parameter key

    Returns:
        String value or None if not found or not a string
    """
    value = parameters.get(key)
    return value if isinstance(value, str) else None


def get_tool_context_summary(
    tool_name: str, parameters: Dict[str, Any]
) -> Optional[str]:
    """Extract contextual summary from tool parameters for display in header.

    This provides quick scanability by showing the most relevant detail for each
    tool type (e.g., command being executed, file being written, agent being called).

    Args:
        tool_name: Name of the tool being executed
        parameters: Tool parameters

    Returns:
        Short contextual string (e.g., "pytest tests/") or None if no context
    """
    if not parameters:
        return None

    # Execute command - show the command
    if tool_name == "execute_command":
        cmd = _get_string_param(parameters, "command")
        if cmd:
            return _truncate_from_end(cmd, _MAX_COMMAND_LENGTH)

    # File operations - show the file path
    if tool_name in ("write_file", "read_file", "delete_file", "get_file_info"):
        file_path = _get_string_param(parameters, "file_path")
        if file_path:
            return _truncate_from_start(file_path, _MAX_PATH_LENGTH)

    # Directory operations - show the directory
    if tool_name in ("list_directory", "create_directory"):
        directory = _get_string_param(parameters, "directory")
        if directory and (tool_name != "list_directory" or directory != "."):
            return _truncate_from_start(directory, _MAX_PATH_LENGTH)

    # URL fetch - show the URL
    if tool_name == "fetch_url":
        url = _get_string_param(parameters, "url")
        if url:
            return _truncate_from_end(url, _MAX_COMMAND_LENGTH)

    # Google search - show the query
    if tool_name == "google_search":
        query = _get_string_param(parameters, "query")
        if query:
            return _truncate_from_end(query, _MAX_COMMAND_LENGTH)

    # Agent delegation - show target agent and task preview
    if tool_name == "delegate_to_agent":
        agent = _get_string_param(parameters, "agent")
        if not agent:
            return None

        result = f"→ {agent}"

        task = _get_string_param(parameters, "task")
        if task:
            # Show first line only for multiline tasks
            first_line = task.split("\n")[0] if "\n" in task else task
            task_preview = _truncate_from_end(first_line, _MAX_TASK_LENGTH)
            result += f": {task_preview}"

        return result

    return None
