"""Core policy engine for evaluating tool execution policies."""

import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

from .policy_types import (
    PolicyDecision,
    PolicyRule,
    PolicyViolation,
    Restriction,
    RestrictionType,
    RiskLevel,
    SafetyCheck,
    SupervisionLevel,
    ToolCall,
)
from ..core.config_paths import ConfigPaths


class PolicyEngine:
    """Main policy engine for evaluating tool execution requests."""

    def __init__(self, policy_dir: Optional[Path] = None):
        """Initialize the policy engine.

        Args:
            policy_dir: Directory containing user policy files (optional)
                       Built-in policies are always loaded first, then user policies
                       can override them if provided.
        """
        # Built-in policy directories
        self.builtin_policy_dir = Path(__file__).parent / "definitions"
        self.default_policy_dir = Path(__file__).parent / "defaults"

        # User policy directory (optional)
        self.user_policy_dir = policy_dir

        self.rules: List[PolicyRule] = []
        self.default_supervision = SupervisionLevel.CONFIRM
        self.violations: List[PolicyViolation] = []
        self.user_preferences: Dict[str, Any] = {}

        # Load policies (built-in first, then user overrides)
        self._load_policies()
        self._load_user_preferences()

    def evaluate_tool_call(self, tool_call: ToolCall) -> PolicyDecision:
        """Evaluate a tool call against all policies.

        Args:
            tool_call: The tool invocation to evaluate

        Returns:
            PolicyDecision with supervision level, restrictions, and safety checks
        """
        # Start with a default allowing decision
        decision = PolicyDecision(
            allowed=True,
            supervision_level=self.default_supervision,
            risk_level=RiskLevel.MEDIUM,
        )

        # Find matching rules
        matching_rules = self._find_matching_rules(tool_call)

        if not matching_rules:
            # No specific rules, use defaults
            decision = self._apply_default_policy(tool_call)
            # Apply user preferences to default policy decision
            self._apply_user_preferences(tool_call, decision)
            return decision

        # Apply rules in priority order
        for rule in sorted(matching_rules, key=lambda r: r.priority, reverse=True):
            self._apply_rule(rule, tool_call, decision)

            # Check if rule denies execution
            if rule.supervision == SupervisionLevel.DENY:
                decision.allowed = False
                decision.reason = f"Tool execution denied by policy: {rule.name}"
                break

        # Apply user preferences
        self._apply_user_preferences(tool_call, decision)

        # Set confirmation requirements
        decision.requires_confirmation = decision.supervision_level in [
            SupervisionLevel.CONFIRM,
            SupervisionLevel.MANUAL,
        ]

        if decision.requires_confirmation:
            decision.confirmation_message = self._generate_confirmation_message(
                tool_call, decision
            )

        return decision

    def _find_matching_rules(self, tool_call: ToolCall) -> List[PolicyRule]:
        """Find all rules that match the given tool name."""
        matching = []
        for rule in self.rules:
            if (
                rule.enabled
                and rule.matches(tool_call.tool_name)
                and self._conditions_match(rule, tool_call)
            ):
                matching.append(rule)
        return matching

    def _conditions_match(self, rule: PolicyRule, tool_call: ToolCall) -> bool:
        """Evaluate optional rule conditions against the tool call."""

        if not rule.conditions:
            return True

        for condition in rule.conditions:
            if not self._condition_matches(condition, tool_call):
                return False

        return True

    def _condition_matches(
        self, condition: Dict[str, Any], tool_call: ToolCall
    ) -> bool:
        """Evaluate a single condition block."""

        if not condition:
            return True

        if "command_matches" in condition or "command_starts_with" in condition:
            command = str(tool_call.parameters.get("command", "")).strip()
            if not command:
                return False

            patterns = condition.get("command_matches", [])
            if patterns:
                if not any(fnmatch.fnmatch(command, pattern) for pattern in patterns):
                    return False

            prefixes = condition.get("command_starts_with", [])
            if prefixes:
                if not any(command.startswith(prefix) for prefix in prefixes):
                    return False

        if "path_matches" in condition:
            paths = self._collect_path_values(tool_call.parameters)
            patterns = condition.get("path_matches", [])
            if not paths or not patterns:
                return False

            if not any(
                fnmatch.fnmatch(path, pattern) for path in paths for pattern in patterns
            ):
                return False

        # Extend with additional condition types as needed; treat unknown keys as non-matching
        recognised_keys = {
            "command_matches",
            "command_starts_with",
            "path_matches",
        }
        unknown_keys = set(condition.keys()) - recognised_keys
        if unknown_keys:
            return False

        return True

    @staticmethod
    def _collect_path_values(parameters: Dict[str, Any]) -> List[str]:
        """Collect relevant path-like parameter values."""

        candidate_keys = [
            "file_path",
            "path",
            "directory",
            "source",
            "destination",
            "target",
        ]
        paths: List[str] = []

        for key in candidate_keys:
            value = parameters.get(key)
            if isinstance(value, str) and value:
                paths.append(value)

        if not paths:
            for value in parameters.values():
                if isinstance(value, str) and value:
                    paths.append(value)

        return paths

    def _apply_rule(
        self, rule: PolicyRule, tool_call: ToolCall, decision: PolicyDecision
    ):
        """Apply a policy rule to the decision."""
        # For the first matching rule (highest priority), use its values directly
        # For subsequent rules, use more restrictive values
        if not hasattr(decision, "_rule_applied"):
            # First rule - use its values
            decision.supervision_level = rule.supervision
            decision.risk_level = rule.risk_level
            decision._rule_applied = True
            decision.metadata["current_priority"] = rule.priority
        else:
            current_priority = decision.metadata.get("current_priority", rule.priority)

            # Subsequent rules - use most restrictive
            if rule.priority >= current_priority and self._is_more_restrictive(
                rule.supervision, decision.supervision_level
            ):
                decision.supervision_level = rule.supervision
                decision.metadata["current_priority"] = rule.priority

            # Update risk level (use highest)
            if rule.priority >= current_priority and self._risk_priority(
                rule.risk_level
            ) > self._risk_priority(decision.risk_level):
                decision.risk_level = rule.risk_level
                decision.metadata["current_priority"] = rule.priority

        # Add restrictions
        for restriction_config in rule.restrictions:
            restriction = self._create_restriction(restriction_config)
            if restriction:
                decision.add_restriction(restriction)

        # Add safety checks
        for check_name in rule.safety_checks:
            check = self._create_safety_check(check_name)
            if check:
                decision.add_safety_check(check)

    def _apply_default_policy(self, tool_call: ToolCall) -> PolicyDecision:
        """Apply default policy when no specific rules match."""
        # Categorize based on tool name patterns
        tool_name = tool_call.tool_name.lower()

        # Read operations are generally safe
        if any(word in tool_name for word in ["read", "list", "get", "show", "view"]):
            return PolicyDecision(
                allowed=True,
                supervision_level=SupervisionLevel.AUTOMATIC,
                risk_level=RiskLevel.LOW,
                safety_checks=[self._create_safety_check("size_limit")],
            )

        # Write operations need confirmation
        if any(word in tool_name for word in ["write", "create", "save", "put"]):
            return PolicyDecision(
                allowed=True,
                supervision_level=SupervisionLevel.CONFIRM,
                risk_level=RiskLevel.MEDIUM,
                safety_checks=[
                    self._create_safety_check("backup"),
                    self._create_safety_check("disk_space"),
                ],
                requires_confirmation=True,
                confirmation_message="This operation will modify files. Continue?",
            )

        # Delete operations are high risk
        if any(word in tool_name for word in ["delete", "remove", "rm", "destroy"]):
            return PolicyDecision(
                allowed=True,
                supervision_level=SupervisionLevel.MANUAL,
                risk_level=RiskLevel.HIGH,
                safety_checks=[
                    self._create_safety_check("backup"),
                    self._create_safety_check("confirmation_double"),
                ],
                requires_confirmation=True,
                confirmation_message="⚠️ This is a destructive operation. Are you sure?",
            )

        # Execute operations need careful handling
        if any(word in tool_name for word in ["execute", "run", "exec", "command"]):
            return PolicyDecision(
                allowed=True,
                supervision_level=SupervisionLevel.CONFIRM,
                risk_level=RiskLevel.HIGH,
                safety_checks=[
                    self._create_safety_check("command_validator"),
                    self._create_safety_check("sandbox_check"),
                ],
            )

        # Default for unknown operations
        return PolicyDecision(
            allowed=True,
            supervision_level=self.default_supervision,
            risk_level=RiskLevel.MEDIUM,
        )

    def _apply_user_preferences(self, tool_call: ToolCall, decision: PolicyDecision):
        """Apply user preferences to the decision."""
        # Check if user has specific preferences for this tool
        tool_prefs = self.user_preferences.get("tools", {}).get(tool_call.tool_name, {})

        if "supervision" in tool_prefs:
            user_supervision = SupervisionLevel(tool_prefs["supervision"])
            # Only apply if more restrictive
            if self._is_more_restrictive(user_supervision, decision.supervision_level):
                decision.supervision_level = user_supervision

        # Check for auto-approve patterns
        auto_approve = self.user_preferences.get("auto_approve", [])
        for pattern in auto_approve:
            if fnmatch.fnmatch(tool_call.tool_name.lower(), pattern.lower()):
                # When user explicitly auto-approves, bypass risk checks
                # (This is used for "toggle safety off" functionality)
                decision.supervision_level = SupervisionLevel.AUTOMATIC

        # Check for never-allow patterns
        never_allow = self.user_preferences.get("never_allow", [])
        for pattern in never_allow:
            if fnmatch.fnmatch(tool_call.tool_name.lower(), pattern.lower()):
                decision.allowed = False
                decision.supervision_level = SupervisionLevel.DENY
                decision.reason = "Blocked by user preferences"

    def _load_policies(self):
        """Load policy definitions from files.

        Loads built-in policies first, then user policies which can override them.
        """

        # Helper to load policy files from a directory
        def load_directory(directory: Path, source: str) -> None:
            if not directory.exists():
                return
            for policy_file in directory.glob("*.yaml"):
                try:
                    with open(policy_file, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        if data:
                            self._parse_policy_file(data)
                except Exception as e:
                    print(f"Error loading {source} policy file {policy_file}: {e}")

        # Load built-in definitions and defaults (always available)
        load_directory(self.builtin_policy_dir, "built-in")
        load_directory(self.default_policy_dir, "default")

        # Load user policies (can override built-in policies)
        if self.user_policy_dir and self.user_policy_dir.exists():
            load_directory(self.user_policy_dir, "user")

    def _load_user_preferences(self):
        """Load user-specific policy preferences."""
        pref_file = ConfigPaths.get_policy_preferences()
        if pref_file.exists():
            try:
                with open(pref_file, "r") as f:
                    self.user_preferences = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Error loading user preferences: {e}")

    def _parse_policy_file(self, data: Dict[str, Any]):
        """Parse a policy definition file."""
        for category, rules in data.items():
            if isinstance(rules, dict):
                for rule_name, rule_config in rules.items():
                    rule = PolicyRule(
                        name=f"{category}.{rule_name}",
                        pattern=rule_config.get("pattern", rule_name),
                        supervision=SupervisionLevel(
                            rule_config.get("supervision", "confirm")
                        ),
                        risk_level=RiskLevel(rule_config.get("risk", "medium")),
                        conditions=rule_config.get("conditions", []),
                        restrictions=rule_config.get("restrictions", []),
                        safety_checks=rule_config.get("safety_checks", []),
                        priority=rule_config.get("priority", 0),
                        enabled=rule_config.get("enabled", True),
                    )
                    self.rules.append(rule)

    def _create_default_policies(self):
        """Create default policy files if they don't exist."""
        # Create default filesystem policy
        filesystem_policy = {
            "filesystem": {
                "read_file": {
                    "pattern": "*read*",
                    "supervision": "automatic",
                    "risk": "low",
                    "restrictions": [
                        {
                            "type": "size_limit",
                            "max_bytes": 10485760,
                        }
                    ],
                    "safety_checks": ["sensitive_data"],
                },
                "write_file": {
                    "pattern": "*write*",
                    "supervision": "confirm",
                    "risk": "medium",
                    "safety_checks": ["backup", "disk_space"],
                },
                "delete_file": {
                    "pattern": "*delete*",
                    "supervision": "manual",
                    "risk": "high",
                    "safety_checks": ["backup", "confirmation"],
                },
            }
        }

        with open(self.policy_dir / "filesystem.yaml", "w") as f:
            yaml.dump(filesystem_policy, f)

        # Create default command policy
        command_policy = {
            "command": {
                "safe_commands": {
                    "pattern": "ls|pwd|cat|grep|find",
                    "supervision": "notify",
                    "risk": "low",
                },
                "dangerous_commands": {
                    "pattern": "rm*|format|dd|mkfs",
                    "supervision": "deny",
                    "risk": "critical",
                },
            }
        }

        with open(self.policy_dir / "commands.yaml", "w") as f:
            yaml.dump(command_policy, f)

    def _create_restriction(self, config: Dict[str, Any]) -> Optional[Restriction]:
        """Create a restriction from configuration."""
        try:
            return Restriction(
                type=RestrictionType(config["type"]),
                config=config,
                reason=config.get("reason"),
            )
        except (KeyError, ValueError):
            return None

    def _create_safety_check(self, name: str) -> Optional[SafetyCheck]:
        """Create a safety check by name."""
        # Map of check names to checker classes
        check_map = {
            "backup": "BackupChecker",
            "disk_space": "DiskSpaceChecker",
            "sensitive_data": "SensitiveDataChecker",
            "size_limit": "SizeLimitChecker",
            "confirmation": "ConfirmationChecker",
            "confirmation_double": "DoubleConfirmationChecker",
            "command_validator": "CommandValidator",
            "sandbox_check": "SandboxChecker",
        }

        if name in check_map:
            return SafetyCheck(
                name=name,
                checker_class=check_map[name],
            )
        return None

    def _is_more_restrictive(
        self, level1: SupervisionLevel, level2: SupervisionLevel
    ) -> bool:
        """Check if level1 is more restrictive than level2."""
        priority = {
            SupervisionLevel.AUTOMATIC: 0,
            SupervisionLevel.NOTIFY: 1,
            SupervisionLevel.CONFIRM: 2,
            SupervisionLevel.MANUAL: 3,
            SupervisionLevel.DENY: 4,
        }
        return priority.get(level1, 0) > priority.get(level2, 0)

    def _risk_priority(self, risk: RiskLevel) -> int:
        """Get priority value for risk level."""
        priority = {
            RiskLevel.NONE: 0,
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4,
        }
        return priority.get(risk, 0)

    def _generate_confirmation_message(
        self, tool_call: ToolCall, decision: PolicyDecision
    ) -> str:
        """Generate a user-friendly confirmation message."""
        risk_emoji = {
            RiskLevel.NONE: "✅",
            RiskLevel.LOW: "ℹ️",
            RiskLevel.MEDIUM: "⚠️",
            RiskLevel.HIGH: "⛔",
            RiskLevel.CRITICAL: "🚨",
        }

        emoji = risk_emoji.get(decision.risk_level, "❓")

        message = f"{emoji} Tool: {tool_call.tool_name}\n"
        message += f"Risk Level: {decision.risk_level.value}\n"

        if tool_call.agent_name:
            message += f"Requested by: {tool_call.agent_name}\n"

        message += "\nParameters:\n"
        for key, value in tool_call.parameters.items():
            message += f"  {key}: {value}\n"

        if decision.reason:
            message += f"\nReason: {decision.reason}\n"

        message += "\nDo you want to proceed?"

        return message

    def record_violation(self, violation: PolicyViolation):
        """Record a policy violation for audit purposes."""
        self.violations.append(violation)

    def get_supervision_level(self, tool_name: str) -> SupervisionLevel:
        """Get the supervision level for a specific tool."""
        decision = self.evaluate_tool_call(ToolCall(tool_name=tool_name, parameters={}))
        return decision.supervision_level

    def requires_confirmation(self, tool_name: str, parameters: Dict[str, Any]) -> bool:
        """Check if a tool call requires user confirmation."""
        decision = self.evaluate_tool_call(
            ToolCall(tool_name=tool_name, parameters=parameters)
        )
        return decision.requires_confirmation
