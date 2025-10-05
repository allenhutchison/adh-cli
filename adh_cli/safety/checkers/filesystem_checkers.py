"""Filesystem-related safety checkers."""

import os
import shutil
from pathlib import Path

from ..base_checker import SafetyChecker, SafetyResult, SafetyStatus
from ...policies.policy_types import ToolCall, RiskLevel
from ...core.config_paths import ConfigPaths


class BackupChecker(SafetyChecker):
    """Ensures backups are created before destructive operations."""

    async def check(self, tool_call: ToolCall) -> SafetyResult:
        """Check if backup is needed and create if necessary."""
        # Check if this is a write/delete operation
        tool_name = tool_call.tool_name.lower()
        if not any(op in tool_name for op in ["write", "delete", "remove", "modify"]):
            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.SKIPPED,
                message="Backup not needed for read operation",
                risk_level=RiskLevel.NONE,
            )

        # Get file path from parameters
        file_path = tool_call.get_parameter("path") or tool_call.get_parameter(
            "file_path"
        )
        if not file_path:
            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.WARNING,
                message="No file path found in parameters",
                risk_level=RiskLevel.MEDIUM,
            )

        path = Path(file_path)
        if not path.exists():
            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.PASSED,
                message="File doesn't exist, no backup needed",
                risk_level=RiskLevel.LOW,
            )

        # Create backup
        backup_dir = ConfigPaths.get_backups_dir()

        backup_path = backup_dir / f"{path.name}.backup"
        try:
            shutil.copy2(path, backup_path)
            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.PASSED,
                message=f"Backup created at {backup_path}",
                risk_level=RiskLevel.NONE,
                details={"backup_path": str(backup_path)},
            )
        except Exception as e:
            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.FAILED,
                message=f"Failed to create backup: {e}",
                risk_level=RiskLevel.HIGH,
                can_override=True,
            )


class DiskSpaceChecker(SafetyChecker):
    """Checks available disk space before write operations."""

    async def check(self, tool_call: ToolCall) -> SafetyResult:
        """Check if there's enough disk space."""
        # Check for write operations
        tool_name = tool_call.tool_name.lower()
        if "write" not in tool_name and "create" not in tool_name:
            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.SKIPPED,
                message="Not a write operation",
                risk_level=RiskLevel.NONE,
            )

        # Get required space (estimate or from parameters)
        required_bytes = tool_call.get_parameter("size", 1024 * 1024)  # Default 1MB

        # Check available space
        stat = shutil.disk_usage("/")
        available_mb = stat.free / (1024 * 1024)
        required_mb = required_bytes / (1024 * 1024)

        if available_mb < required_mb + 100:  # Keep 100MB buffer
            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.FAILED,
                message=f"Insufficient disk space: {available_mb:.1f}MB available",
                risk_level=RiskLevel.HIGH,
                details={"available_mb": available_mb, "required_mb": required_mb},
            )

        return SafetyResult(
            checker_name=self.name,
            status=SafetyStatus.PASSED,
            message=f"Sufficient disk space: {available_mb:.1f}MB available",
            risk_level=RiskLevel.NONE,
        )


class PermissionChecker(SafetyChecker):
    """Checks file permissions before operations."""

    async def check(self, tool_call: ToolCall) -> SafetyResult:
        """Check if we have necessary permissions."""
        file_path = tool_call.get_parameter("path") or tool_call.get_parameter(
            "file_path"
        )
        if not file_path:
            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.PASSED,
                message="No file path to check",
                risk_level=RiskLevel.LOW,
            )

        path = Path(file_path)

        # Check parent directory for new files
        if not path.exists():
            parent = path.parent
            if not parent.exists():
                return SafetyResult(
                    checker_name=self.name,
                    status=SafetyStatus.FAILED,
                    message=f"Parent directory doesn't exist: {parent}",
                    risk_level=RiskLevel.MEDIUM,
                )

            if not os.access(parent, os.W_OK):
                return SafetyResult(
                    checker_name=self.name,
                    status=SafetyStatus.FAILED,
                    message=f"No write permission in directory: {parent}",
                    risk_level=RiskLevel.HIGH,
                )
        else:
            # Check file permissions
            tool_name = tool_call.tool_name.lower()
            if "read" in tool_name and not os.access(path, os.R_OK):
                return SafetyResult(
                    checker_name=self.name,
                    status=SafetyStatus.FAILED,
                    message=f"No read permission: {path}",
                    risk_level=RiskLevel.MEDIUM,
                )

            if any(op in tool_name for op in ["write", "modify", "delete"]):
                if not os.access(path, os.W_OK):
                    return SafetyResult(
                        checker_name=self.name,
                        status=SafetyStatus.FAILED,
                        message=f"No write permission: {path}",
                        risk_level=RiskLevel.HIGH,
                    )

        return SafetyResult(
            checker_name=self.name,
            status=SafetyStatus.PASSED,
            message="Permissions check passed",
            risk_level=RiskLevel.NONE,
        )


class SizeLimitChecker(SafetyChecker):
    """Checks file size limits."""

    async def check(self, tool_call: ToolCall) -> SafetyResult:
        """Check if file size is within limits."""
        file_path = tool_call.get_parameter("path") or tool_call.get_parameter(
            "file_path"
        )
        if not file_path:
            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.PASSED,
                message="No file to check",
                risk_level=RiskLevel.NONE,
            )

        path = Path(file_path)
        if not path.exists():
            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.PASSED,
                message="File doesn't exist yet",
                risk_level=RiskLevel.LOW,
            )

        # Get size limit from config
        max_size = self.get_config_value("max_bytes", 10 * 1024 * 1024)  # Default 10MB

        file_size = path.stat().st_size
        if file_size > max_size:
            return SafetyResult(
                checker_name=self.name,
                status=SafetyStatus.WARNING,
                message=f"File exceeds size limit: {file_size / (1024 * 1024):.1f}MB",
                risk_level=RiskLevel.MEDIUM,
                can_override=True,
                suggestions=["Consider processing file in chunks"],
            )

        return SafetyResult(
            checker_name=self.name,
            status=SafetyStatus.PASSED,
            message=f"File size OK: {file_size / 1024:.1f}KB",
            risk_level=RiskLevel.NONE,
        )
