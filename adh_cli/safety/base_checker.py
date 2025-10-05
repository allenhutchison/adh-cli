"""Base classes for safety checkers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

from ..policies.policy_types import ToolCall, RiskLevel


class SafetyStatus(Enum):
    """Status of a safety check."""

    PASSED = "passed"  # Check passed, safe to proceed
    WARNING = "warning"  # Check passed with warnings
    FAILED = "failed"  # Check failed, should block execution
    ERROR = "error"  # Error during check execution
    SKIPPED = "skipped"  # Check was skipped


@dataclass
class SafetyResult:
    """Result of a safety check."""

    checker_name: str
    status: SafetyStatus
    message: str
    risk_level: RiskLevel = RiskLevel.MEDIUM
    details: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    can_override: bool = False  # Whether user can override this check

    @property
    def is_blocking(self) -> bool:
        """Check if this result should block execution."""
        return self.status == SafetyStatus.FAILED and not self.can_override

    @property
    def needs_attention(self) -> bool:
        """Check if this result needs user attention."""
        return self.status in [SafetyStatus.WARNING, SafetyStatus.FAILED]


class SafetyChecker(ABC):
    """Abstract base class for all safety checkers."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the safety checker.

        Args:
            config: Configuration for the checker
        """
        self.config = config or {}
        self.name = self.__class__.__name__

    @abstractmethod
    async def check(self, tool_call: ToolCall) -> SafetyResult:
        """Perform the safety check.

        Args:
            tool_call: The tool invocation to check

        Returns:
            SafetyResult with the check outcome
        """
        pass

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a configuration value safely."""
        return self.config.get(key, default)
