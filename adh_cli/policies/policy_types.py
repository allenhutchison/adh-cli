"""Policy type definitions for the policy engine."""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime


class SupervisionLevel(Enum):
    """Level of supervision required for tool execution."""

    AUTOMATIC = "automatic"      # No supervision needed, execute immediately
    NOTIFY = "notify"            # Notify user but proceed without waiting
    CONFIRM = "confirm"          # Require user confirmation before execution
    MANUAL = "manual"            # Full manual review and modification allowed
    DENY = "deny"                # Never allow execution


class RiskLevel(Enum):
    """Risk assessment level for operations."""

    NONE = "none"          # No risk
    LOW = "low"            # Minimal risk
    MEDIUM = "medium"      # Moderate risk, reversible
    HIGH = "high"          # High risk, potentially destructive
    CRITICAL = "critical"  # Critical risk, system-level changes


class RestrictionType(Enum):
    """Types of restrictions that can be applied."""

    PATH_PATTERN = "path_pattern"      # File path patterns to allow/deny
    SIZE_LIMIT = "size_limit"          # Maximum size limits
    RATE_LIMIT = "rate_limit"          # Rate limiting for operations
    TIME_WINDOW = "time_window"        # Time-based restrictions
    SCOPE_LIMIT = "scope_limit"        # Limit scope of operations
    PARAMETER_FILTER = "parameter_filter"  # Filter/modify parameters


@dataclass
class Restriction:
    """A restriction to apply to tool execution."""

    type: RestrictionType
    config: Dict[str, Any]
    reason: Optional[str] = None

    def applies_to(self, tool_call: 'ToolCall') -> bool:
        """Check if this restriction applies to the given tool call."""
        # Implementation depends on restriction type
        return True


@dataclass
class SafetyCheck:
    """A safety check to perform before tool execution."""

    name: str
    checker_class: str  # Class name of the safety checker
    config: Dict[str, Any] = field(default_factory=dict)
    required: bool = True  # If True, failing this check blocks execution
    timeout: float = 5.0  # Timeout in seconds


@dataclass
class ToolCall:
    """Represents a tool invocation request."""

    tool_name: str
    parameters: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)
    agent_name: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Safely get a parameter value."""
        return self.parameters.get(key, default)

    def get_context(self, key: str, default: Any = None) -> Any:
        """Safely get a context value."""
        return self.context.get(key, default)


@dataclass
class PolicyDecision:
    """Result of policy evaluation for a tool call."""

    allowed: bool
    supervision_level: SupervisionLevel
    risk_level: RiskLevel
    restrictions: List[Restriction] = field(default_factory=list)
    safety_checks: List[SafetyCheck] = field(default_factory=list)
    reason: Optional[str] = None
    alternative_suggestion: Optional[str] = None
    requires_confirmation: bool = False
    confirmation_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def needs_user_interaction(self) -> bool:
        """Check if this decision requires user interaction."""
        return self.supervision_level in [
            SupervisionLevel.CONFIRM,
            SupervisionLevel.MANUAL
        ]

    @property
    def should_notify(self) -> bool:
        """Check if user should be notified."""
        return self.supervision_level != SupervisionLevel.AUTOMATIC

    def add_restriction(self, restriction: Restriction):
        """Add a restriction to the decision."""
        self.restrictions.append(restriction)

    def add_safety_check(self, check: SafetyCheck):
        """Add a safety check to the decision."""
        self.safety_checks.append(check)


@dataclass
class PolicyRule:
    """A single policy rule definition."""

    name: str
    pattern: str  # Tool name pattern (supports wildcards)
    supervision: SupervisionLevel
    risk_level: RiskLevel
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    restrictions: List[Dict[str, Any]] = field(default_factory=list)
    safety_checks: List[str] = field(default_factory=list)
    priority: int = 0  # Higher priority rules override lower ones
    enabled: bool = True

    def matches(self, tool_name: str) -> bool:
        """Check if this rule matches the given tool name."""
        import fnmatch
        return fnmatch.fnmatch(tool_name.lower(), self.pattern.lower())


@dataclass
class PolicyViolation:
    """Record of a policy violation."""

    tool_call: ToolCall
    rule: PolicyRule
    violation_type: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    severity: RiskLevel = RiskLevel.MEDIUM