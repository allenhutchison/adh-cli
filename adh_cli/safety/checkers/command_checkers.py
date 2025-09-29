"""Command execution safety checkers."""

import os
import shlex
from pathlib import Path
from typing import List, Set

from ..base_checker import SafetyChecker, SafetyResult, SafetyStatus
from ...policies.policy_types import ToolCall, RiskLevel


class CommandValidator(SafetyChecker):
    """Validates shell commands for safety."""

    def __init__(self, config=None):
        super().__init__(config)
        self.dangerous_commands = self._get_dangerous_commands()
        self.safe_commands = self._get_safe_commands()

    def _get_dangerous_commands(self) -> Set[str]:
        """Get list of dangerous commands."""
        return {
            "rm", "rmdir", "del", "format", "mkfs", "dd",
            "fdisk", "parted", "wipefs", "shred",
            "shutdown", "reboot", "halt", "poweroff",
            "kill", "killall", "pkill",
            "chmod", "chown", "chgrp",
            "useradd", "userdel", "usermod",
            "systemctl", "service",
            "iptables", "firewall-cmd",
        }

    def _get_safe_commands(self) -> Set[str]:
        """Get list of safe commands."""
        return {
            "ls", "dir", "pwd", "cd", "echo", "cat", "less", "more",
            "grep", "find", "which", "whereis", "whoami", "id",
            "date", "time", "cal", "df", "du", "free",
            "ps", "top", "htop", "jobs", "history",
            "head", "tail", "wc", "sort", "uniq",
            "diff", "comm", "cmp",
        }

    async def check(self, tool_call: ToolCall) -> SafetyResult:
        """Validate command safety."""
        command = tool_call.get_parameter("command")
        if not command:
            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.PASSED,
                message="No command to validate",
                risk_level=RiskLevel.NONE,
            )

        try:
            # Parse command
            parts = shlex.split(command)
            if not parts:
                return SafetyResult(
                    checker_name=self.name,
                    status=SafetyStatus.WARNING,
                    message="Empty command",
                    risk_level=RiskLevel.LOW,
                )

            cmd = parts[0].lower()
            base_cmd = os.path.basename(cmd)

            # Check if it's a dangerous command
            if base_cmd in self.dangerous_commands:
                # Check for especially dangerous patterns
                if base_cmd == "rm" and any(arg in parts for arg in ["-rf", "-r", "-f", "/*", "~/*"]):
                    return SafetyResult(
                        checker_name=self.name,
                        status=SafetyStatus.FAILED,
                        message=f"Dangerous command blocked: {base_cmd} with risky flags",
                        risk_level=RiskLevel.CRITICAL,
                        suggestions=["Use a safer alternative", "Be more specific with paths"],
                    )

                return SafetyResult(
                    checker_name=self.name,
                    status=SafetyStatus.WARNING,
                    message=f"Potentially dangerous command: {base_cmd}",
                    risk_level=RiskLevel.HIGH,
                    can_override=True,
                    suggestions=["Review command carefully", "Consider safer alternatives"],
                )

            # Check if it's a safe command
            if base_cmd in self.safe_commands:
                return SafetyResult(
                    checker_name=self.name,
                    status=SafetyStatus.PASSED,
                    message=f"Safe command: {base_cmd}",
                    risk_level=RiskLevel.LOW,
                )

            # Unknown command - moderate risk
            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.WARNING,
                message=f"Unknown command: {base_cmd}",
                risk_level=RiskLevel.MEDIUM,
                can_override=True,
            )

        except Exception as e:
            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.ERROR,
                message=f"Failed to parse command: {e}",
                risk_level=RiskLevel.MEDIUM,
            )


class SandboxChecker(SafetyChecker):
    """Ensures operations stay within sandbox boundaries."""

    def __init__(self, config=None):
        super().__init__(config)
        self.sandbox_root = self._get_sandbox_root()
        self.protected_paths = self._get_protected_paths()

    def _get_sandbox_root(self) -> Path:
        """Get the sandbox root directory."""
        return Path(self.get_config_value("sandbox_root", Path.cwd()))

    def _get_protected_paths(self) -> List[Path]:
        """Get list of protected system paths."""
        return [
            Path("/etc"),
            Path("/usr"),
            Path("/bin"),
            Path("/sbin"),
            Path("/boot"),
            Path("/dev"),
            Path("/proc"),
            Path("/sys"),
            Path("/System"),  # macOS
            Path("/Library"),  # macOS
            Path("/Applications"),  # macOS
            Path.home() / ".ssh",
            Path.home() / ".gnupg",
        ]

    async def check(self, tool_call: ToolCall) -> SafetyResult:
        """Check if operation stays within sandbox."""
        # Get path from parameters
        path_param = (
            tool_call.get_parameter("path")
            or tool_call.get_parameter("file_path")
            or tool_call.get_parameter("directory")
        )

        if not path_param:
            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.PASSED,
                message="No path to check",
                risk_level=RiskLevel.LOW,
            )

        try:
            path = Path(path_param).resolve()

            # Check if path is in protected area
            for protected in self.protected_paths:
                try:
                    # Resolve both paths to handle symlinks
                    resolved_protected = protected.resolve() if protected.exists() else protected
                    if path == resolved_protected or path.is_relative_to(resolved_protected):
                        return SafetyResult(
                            checker_name=self.name,
                            status=SafetyStatus.FAILED,
                            message=f"Access to protected path denied: {path}",
                            risk_level=RiskLevel.CRITICAL,
                            details={"protected_area": str(protected)},
                        )
                except (ValueError, AttributeError):
                    # is_relative_to not available in Python < 3.9, fall back to old method
                    try:
                        path.relative_to(resolved_protected if protected.exists() else protected)
                        return SafetyResult(
                            checker_name=self.name,
                            status=SafetyStatus.FAILED,
                            message=f"Access to protected path denied: {path}",
                            risk_level=RiskLevel.CRITICAL,
                            details={"protected_area": str(protected)},
                        )
                    except ValueError:
                        pass  # Not relative to this protected path

            # Check if path is within sandbox
            if self.sandbox_root != Path("/"):
                try:
                    # Resolve sandbox root to handle symlinks
                    resolved_sandbox = self.sandbox_root.resolve()
                    # Check if path is within resolved sandbox
                    path.relative_to(resolved_sandbox)
                    return SafetyResult(
                        checker_name=self.name,
                        status=SafetyStatus.PASSED,
                        message="Path is within sandbox",
                        risk_level=RiskLevel.NONE,
                    )
                except ValueError:
                    return SafetyResult(
                        checker_name=self.name,
                        status=SafetyStatus.WARNING,
                        message=f"Path is outside sandbox: {path}",
                        risk_level=RiskLevel.MEDIUM,
                        details={"sandbox_root": str(resolved_sandbox)},
                        can_override=True,
                    )

            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.PASSED,
                message="Sandbox check passed",
                risk_level=RiskLevel.LOW,
            )

        except Exception as e:
            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.ERROR,
                message=f"Failed to check path: {e}",
                risk_level=RiskLevel.MEDIUM,
            )