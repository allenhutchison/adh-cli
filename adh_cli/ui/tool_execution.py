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
        return f'"{value[:max_length-4]}..."', original_length

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
        return f"[{first_item}, ... {original_length-1} more]", original_length

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
        return f"{{{pair_str}, ... {original_length-1} more}}", original_length

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
    return str_val[:max_length-3] + "...", original_length


def format_parameters_inline(
    parameters: Dict[str, Any],
    max_params: int = 3,
    max_value_length: int = 50
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
    parameters: Dict[str, Any],
    max_value_length: int = 200
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