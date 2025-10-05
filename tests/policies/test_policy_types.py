"""Tests for policy type definitions."""

from datetime import datetime
from adh_cli.policies.policy_types import (
    SupervisionLevel,
    RiskLevel,
    RestrictionType,
    Restriction,
    SafetyCheck,
    ToolCall,
    PolicyDecision,
    PolicyRule,
)


class TestSuperVisionLevel:
    """Test SupervisionLevel enum."""

    def test_supervision_levels(self):
        """Test all supervision levels are defined."""
        assert SupervisionLevel.AUTOMATIC.value == "automatic"
        assert SupervisionLevel.NOTIFY.value == "notify"
        assert SupervisionLevel.CONFIRM.value == "confirm"
        assert SupervisionLevel.MANUAL.value == "manual"
        assert SupervisionLevel.DENY.value == "deny"


class TestRiskLevel:
    """Test RiskLevel enum."""

    def test_risk_levels(self):
        """Test all risk levels are defined."""
        assert RiskLevel.NONE.value == "none"
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"


class TestToolCall:
    """Test ToolCall dataclass."""

    def test_tool_call_creation(self):
        """Test creating a ToolCall."""
        tool_call = ToolCall(
            tool_name="read_file",
            parameters={"path": "/tmp/test.txt"},
            context={"user": "test_user"},
            agent_name="test_agent",
        )

        assert tool_call.tool_name == "read_file"
        assert tool_call.parameters["path"] == "/tmp/test.txt"
        assert tool_call.context["user"] == "test_user"
        assert tool_call.agent_name == "test_agent"
        assert isinstance(tool_call.timestamp, datetime)

    def test_get_parameter(self):
        """Test getting parameters safely."""
        tool_call = ToolCall(
            tool_name="test",
            parameters={"key1": "value1", "key2": None},
        )

        assert tool_call.get_parameter("key1") == "value1"
        assert tool_call.get_parameter("key2") is None
        assert tool_call.get_parameter("missing") is None
        assert tool_call.get_parameter("missing", "default") == "default"

    def test_get_context(self):
        """Test getting context values safely."""
        tool_call = ToolCall(
            tool_name="test",
            parameters={},
            context={"user": "alice", "session": "123"},
        )

        assert tool_call.get_context("user") == "alice"
        assert tool_call.get_context("session") == "123"
        assert tool_call.get_context("missing") is None
        assert tool_call.get_context("missing", "default") == "default"


class TestPolicyDecision:
    """Test PolicyDecision dataclass."""

    def test_policy_decision_creation(self):
        """Test creating a PolicyDecision."""
        decision = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.CONFIRM,
            risk_level=RiskLevel.MEDIUM,
        )

        assert decision.allowed is True
        assert decision.supervision_level == SupervisionLevel.CONFIRM
        assert decision.risk_level == RiskLevel.MEDIUM
        assert decision.restrictions == []
        assert decision.safety_checks == []

    def test_needs_user_interaction(self):
        """Test checking if user interaction is needed."""
        # Automatic - no interaction
        decision = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.AUTOMATIC,
            risk_level=RiskLevel.LOW,
        )
        assert not decision.needs_user_interaction

        # Confirm - needs interaction
        decision.supervision_level = SupervisionLevel.CONFIRM
        assert decision.needs_user_interaction

        # Manual - needs interaction
        decision.supervision_level = SupervisionLevel.MANUAL
        assert decision.needs_user_interaction

    def test_should_notify(self):
        """Test checking if user should be notified."""
        # Automatic - no notification
        decision = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.AUTOMATIC,
            risk_level=RiskLevel.LOW,
        )
        assert not decision.should_notify

        # Notify - should notify
        decision.supervision_level = SupervisionLevel.NOTIFY
        assert decision.should_notify

        # Confirm - should notify
        decision.supervision_level = SupervisionLevel.CONFIRM
        assert decision.should_notify

    def test_add_restriction(self):
        """Test adding restrictions."""
        decision = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.AUTOMATIC,
            risk_level=RiskLevel.LOW,
        )

        restriction = Restriction(
            type=RestrictionType.PATH_PATTERN,
            config={"deny": ["*.key"]},
        )

        decision.add_restriction(restriction)
        assert len(decision.restrictions) == 1
        assert decision.restrictions[0] == restriction

    def test_add_safety_check(self):
        """Test adding safety checks."""
        decision = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.AUTOMATIC,
            risk_level=RiskLevel.LOW,
        )

        check = SafetyCheck(
            name="backup",
            checker_class="BackupChecker",
        )

        decision.add_safety_check(check)
        assert len(decision.safety_checks) == 1
        assert decision.safety_checks[0] == check


class TestPolicyRule:
    """Test PolicyRule dataclass."""

    def test_policy_rule_creation(self):
        """Test creating a PolicyRule."""
        rule = PolicyRule(
            name="test_rule",
            pattern="read_*",
            supervision=SupervisionLevel.AUTOMATIC,
            risk_level=RiskLevel.LOW,
        )

        assert rule.name == "test_rule"
        assert rule.pattern == "read_*"
        assert rule.supervision == SupervisionLevel.AUTOMATIC
        assert rule.risk_level == RiskLevel.LOW
        assert rule.enabled is True
        assert rule.priority == 0

    def test_matches_exact(self):
        """Test exact pattern matching."""
        rule = PolicyRule(
            name="test",
            pattern="read_file",
            supervision=SupervisionLevel.AUTOMATIC,
            risk_level=RiskLevel.LOW,
        )

        assert rule.matches("read_file")
        assert not rule.matches("write_file")
        assert not rule.matches("read_files")

    def test_matches_wildcard(self):
        """Test wildcard pattern matching."""
        rule = PolicyRule(
            name="test",
            pattern="read_*",
            supervision=SupervisionLevel.AUTOMATIC,
            risk_level=RiskLevel.LOW,
        )

        assert rule.matches("read_file")
        assert rule.matches("read_directory")
        assert not rule.matches("write_file")
        assert not rule.matches("readfile")  # No underscore

    def test_matches_case_insensitive(self):
        """Test case-insensitive matching."""
        rule = PolicyRule(
            name="test",
            pattern="READ_FILE",
            supervision=SupervisionLevel.AUTOMATIC,
            risk_level=RiskLevel.LOW,
        )

        assert rule.matches("read_file")
        assert rule.matches("READ_FILE")
        assert rule.matches("Read_File")


class TestRestriction:
    """Test Restriction dataclass."""

    def test_restriction_creation(self):
        """Test creating a Restriction."""
        restriction = Restriction(
            type=RestrictionType.SIZE_LIMIT,
            config={"max_bytes": 1024},
            reason="File too large",
        )

        assert restriction.type == RestrictionType.SIZE_LIMIT
        assert restriction.config["max_bytes"] == 1024
        assert restriction.reason == "File too large"

    def test_applies_to(self):
        """Test checking if restriction applies."""
        restriction = Restriction(
            type=RestrictionType.PATH_PATTERN,
            config={"pattern": "*.txt"},
        )

        tool_call = ToolCall(
            tool_name="read_file",
            parameters={"path": "test.txt"},
        )

        # Currently returns True by default (to be implemented)
        assert restriction.applies_to(tool_call)


class TestSafetyCheck:
    """Test SafetyCheck dataclass."""

    def test_safety_check_creation(self):
        """Test creating a SafetyCheck."""
        check = SafetyCheck(
            name="backup",
            checker_class="BackupChecker",
            config={"backup_dir": "/tmp/backups"},
            required=True,
            timeout=10.0,
        )

        assert check.name == "backup"
        assert check.checker_class == "BackupChecker"
        assert check.config["backup_dir"] == "/tmp/backups"
        assert check.required is True
        assert check.timeout == 10.0

    def test_safety_check_defaults(self):
        """Test SafetyCheck default values."""
        check = SafetyCheck(
            name="test",
            checker_class="TestChecker",
        )

        assert check.config == {}
        assert check.required is True
        assert check.timeout == 5.0
