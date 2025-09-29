"""Tests for the policy engine."""

import pytest
import tempfile
import yaml
from pathlib import Path
from adh_cli.policies.policy_engine import PolicyEngine
from adh_cli.policies.policy_types import (
    ToolCall,
    SupervisionLevel,
    RiskLevel,
    PolicyRule,
    RestrictionType,
)


class TestPolicyEngine:
    """Test the PolicyEngine class."""

    @pytest.fixture
    def temp_policy_dir(self):
        """Create a temporary directory for policy files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def engine_with_policies(self, temp_policy_dir):
        """Create a policy engine with test policies."""
        # Create test policy file BEFORE initializing engine
        test_policy = {
            "test_category": {
                "safe_read": {
                    "pattern": "read_*",
                    "supervision": "automatic",
                    "risk": "low",
                    "safety_checks": ["size_limit"],
                },
                "dangerous_delete": {
                    "pattern": "delete_*",
                    "supervision": "manual",
                    "risk": "high",
                    "safety_checks": ["backup", "confirmation"],
                },
                "blocked_format": {
                    "pattern": "format_*",
                    "supervision": "deny",
                    "risk": "critical",
                },
            }
        }

        # Write policy file FIRST to prevent default policies being created
        policy_file = temp_policy_dir / "test_policies.yaml"
        with open(policy_file, "w") as f:
            yaml.dump(test_policy, f)

        return PolicyEngine(policy_dir=temp_policy_dir)

    def test_engine_initialization(self, temp_policy_dir):
        """Test PolicyEngine initialization."""
        engine = PolicyEngine(policy_dir=temp_policy_dir)

        assert engine.policy_dir == temp_policy_dir
        assert engine.default_supervision == SupervisionLevel.CONFIRM
        assert isinstance(engine.rules, list)
        assert isinstance(engine.violations, list)
        assert isinstance(engine.user_preferences, dict)

    def test_default_policies_creation(self):
        """Test that default policies are created if directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            policy_dir = Path(tmpdir) / "policies"
            engine = PolicyEngine(policy_dir=policy_dir)

            # Check that default policy files were created
            assert policy_dir.exists()
            assert (policy_dir / "filesystem.yaml").exists()
            assert (policy_dir / "commands.yaml").exists()

    def test_evaluate_matching_rule(self, engine_with_policies):
        """Test evaluating a tool call with matching rule."""
        tool_call = ToolCall(
            tool_name="read_file",
            parameters={"path": "/tmp/test.txt"},
        )

        decision = engine_with_policies.evaluate_tool_call(tool_call)

        assert decision.allowed is True
        assert decision.supervision_level == SupervisionLevel.AUTOMATIC
        assert decision.risk_level == RiskLevel.LOW
        assert len(decision.safety_checks) > 0
        assert not decision.requires_confirmation

    def test_evaluate_dangerous_operation(self, engine_with_policies):
        """Test evaluating a dangerous operation."""
        tool_call = ToolCall(
            tool_name="delete_file",
            parameters={"path": "/tmp/test.txt"},
        )

        decision = engine_with_policies.evaluate_tool_call(tool_call)

        assert decision.allowed is True
        assert decision.supervision_level == SupervisionLevel.MANUAL
        assert decision.risk_level == RiskLevel.HIGH
        assert decision.requires_confirmation
        assert decision.confirmation_message is not None

    def test_evaluate_denied_operation(self, engine_with_policies):
        """Test evaluating a denied operation."""
        tool_call = ToolCall(
            tool_name="format_disk",
            parameters={"device": "/dev/sda"},
        )

        decision = engine_with_policies.evaluate_tool_call(tool_call)

        assert decision.allowed is False
        assert decision.supervision_level == SupervisionLevel.DENY
        assert decision.risk_level == RiskLevel.CRITICAL
        assert decision.reason is not None

    def test_evaluate_no_matching_rule(self, engine_with_policies):
        """Test evaluating with no matching rules (uses defaults)."""
        tool_call = ToolCall(
            tool_name="unknown_operation",
            parameters={},
        )

        decision = engine_with_policies.evaluate_tool_call(tool_call)

        # Should use default policy
        assert decision.allowed is True
        assert decision.supervision_level == SupervisionLevel.CONFIRM
        assert decision.risk_level == RiskLevel.MEDIUM

    def test_default_policy_for_read_operations(self, temp_policy_dir):
        """Test default policy for read operations."""
        engine = PolicyEngine(policy_dir=temp_policy_dir)

        tool_call = ToolCall(
            tool_name="read_something",
            parameters={},
        )

        decision = engine.evaluate_tool_call(tool_call)

        assert decision.allowed is True
        assert decision.supervision_level == SupervisionLevel.AUTOMATIC
        assert decision.risk_level == RiskLevel.LOW

    def test_default_policy_for_write_operations(self, temp_policy_dir):
        """Test default policy for write operations."""
        engine = PolicyEngine(policy_dir=temp_policy_dir)

        tool_call = ToolCall(
            tool_name="write_file",
            parameters={"path": "/tmp/test.txt"},
        )

        decision = engine.evaluate_tool_call(tool_call)

        assert decision.allowed is True
        assert decision.supervision_level == SupervisionLevel.CONFIRM
        assert decision.risk_level == RiskLevel.MEDIUM
        assert decision.requires_confirmation

    def test_default_policy_for_delete_operations(self, temp_policy_dir):
        """Test default policy for delete operations."""
        engine = PolicyEngine(policy_dir=temp_policy_dir)

        tool_call = ToolCall(
            tool_name="delete_file",
            parameters={"path": "/tmp/test.txt"},
        )

        decision = engine.evaluate_tool_call(tool_call)

        assert decision.allowed is True
        assert decision.supervision_level == SupervisionLevel.MANUAL
        assert decision.risk_level == RiskLevel.HIGH
        assert decision.requires_confirmation

    def test_get_supervision_level(self, engine_with_policies):
        """Test getting supervision level for a tool."""
        assert engine_with_policies.get_supervision_level("read_file") == SupervisionLevel.AUTOMATIC
        assert engine_with_policies.get_supervision_level("delete_file") == SupervisionLevel.MANUAL
        assert engine_with_policies.get_supervision_level("format_disk") == SupervisionLevel.DENY

    def test_requires_confirmation(self, engine_with_policies):
        """Test checking if confirmation is required."""
        assert not engine_with_policies.requires_confirmation("read_file", {})
        assert engine_with_policies.requires_confirmation("delete_file", {"path": "/tmp/test.txt"})
        assert not engine_with_policies.requires_confirmation("format_disk", {})  # Denied, not confirmed

    def test_user_preferences_auto_approve(self, temp_policy_dir):
        """Test user preferences for auto-approval."""
        engine = PolicyEngine(policy_dir=temp_policy_dir)

        # Set user preferences
        engine.user_preferences = {
            "auto_approve": ["read_*", "list_*"],
        }

        tool_call = ToolCall(
            tool_name="read_file",
            parameters={},
        )

        decision = engine.evaluate_tool_call(tool_call)

        # Should be automatic due to user preference
        assert decision.supervision_level == SupervisionLevel.AUTOMATIC

    def test_user_preferences_never_allow(self, temp_policy_dir):
        """Test user preferences for blocking tools."""
        engine = PolicyEngine(policy_dir=temp_policy_dir)

        # Set user preferences
        engine.user_preferences = {
            "never_allow": ["delete_*", "format_*"],
        }

        tool_call = ToolCall(
            tool_name="delete_file",
            parameters={"path": "/tmp/test.txt"},
        )

        decision = engine.evaluate_tool_call(tool_call)

        assert decision.allowed is False
        assert decision.supervision_level == SupervisionLevel.DENY
        assert "user preferences" in decision.reason.lower()

    def test_priority_ordering(self, temp_policy_dir):
        """Test that higher priority rules override lower ones."""
        # Create policies with different priorities
        test_policy = {
            "test": {
                "low_priority": {
                    "pattern": "*_file",
                    "supervision": "automatic",
                    "risk": "low",
                    "priority": 0,
                },
                "high_priority": {
                    "pattern": "delete_*",
                    "supervision": "manual",
                    "risk": "high",
                    "priority": 10,
                },
            }
        }

        policy_file = temp_policy_dir / "priority_test.yaml"
        with open(policy_file, "w") as f:
            yaml.dump(test_policy, f)

        engine = PolicyEngine(policy_dir=temp_policy_dir)

        tool_call = ToolCall(
            tool_name="delete_file",  # Matches both patterns
            parameters={},
        )

        decision = engine.evaluate_tool_call(tool_call)

        # High priority rule should win
        assert decision.supervision_level == SupervisionLevel.MANUAL
        assert decision.risk_level == RiskLevel.HIGH

    def test_confirmation_message_generation(self, engine_with_policies):
        """Test that confirmation messages are properly generated."""
        tool_call = ToolCall(
            tool_name="delete_file",
            parameters={"path": "/tmp/test.txt", "recursive": True},
            agent_name="FileAgent",
        )

        decision = engine_with_policies.evaluate_tool_call(tool_call)

        assert decision.confirmation_message is not None
        assert "delete_file" in decision.confirmation_message
        assert "FileAgent" in decision.confirmation_message
        assert "/tmp/test.txt" in decision.confirmation_message

    def test_add_multiple_restrictions(self, engine_with_policies):
        """Test that multiple restrictions can be added."""
        # Create a policy with multiple restrictions
        test_policy = {
            "test": {
                "restricted_write": {
                    "pattern": "write_*",
                    "supervision": "confirm",
                    "risk": "medium",
                    "restrictions": [
                        {"type": "size_limit", "max_bytes": 1048576},
                        {"type": "path_pattern", "deny": ["*.exe", "*.dll"]},
                    ],
                },
            }
        }

        policy_file = engine_with_policies.policy_dir / "restrictions.yaml"
        with open(policy_file, "w") as f:
            yaml.dump(test_policy, f)

        # Reload engine
        engine = PolicyEngine(policy_dir=engine_with_policies.policy_dir)

        tool_call = ToolCall(
            tool_name="write_file",
            parameters={"path": "/tmp/test.txt"},
        )

        decision = engine.evaluate_tool_call(tool_call)

        # Should have multiple restrictions
        assert len(decision.restrictions) >= 2
        restriction_types = [r.type for r in decision.restrictions]
        assert RestrictionType.SIZE_LIMIT in restriction_types
        assert RestrictionType.PATH_PATTERN in restriction_types