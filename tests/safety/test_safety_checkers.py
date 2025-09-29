"""Tests for safety checkers."""

import pytest
import asyncio
import tempfile
from pathlib import Path
from adh_cli.safety.base_checker import SafetyChecker, SafetyResult, SafetyStatus
from adh_cli.safety.checkers import (
    BackupChecker,
    DiskSpaceChecker,
    PermissionChecker,
    SizeLimitChecker,
    SensitiveDataChecker,
    CommandValidator,
    SandboxChecker,
)
from adh_cli.policies.policy_types import ToolCall, RiskLevel


class TestBackupChecker:
    """Test BackupChecker."""

    @pytest.mark.asyncio
    async def test_skip_read_operations(self):
        """Test that read operations are skipped."""
        checker = BackupChecker()
        tool_call = ToolCall(
            tool_name="read_file",
            parameters={"path": "/tmp/test.txt"},
        )

        result = await checker.check(tool_call)

        assert result.status == SafetyStatus.SKIPPED
        assert result.risk_level == RiskLevel.NONE

    @pytest.mark.asyncio
    async def test_backup_created_for_write(self):
        """Test that backup is created for write operations."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = tmp.name

        try:
            checker = BackupChecker()
            tool_call = ToolCall(
                tool_name="write_file",
                parameters={"path": tmp_path},
            )

            result = await checker.check(tool_call)

            assert result.status == SafetyStatus.PASSED
            assert "backup_path" in result.details

            # Check backup file exists
            backup_path = Path(result.details["backup_path"])
            assert backup_path.exists()

            # Clean up backup
            backup_path.unlink()

        finally:
            Path(tmp_path).unlink()

    @pytest.mark.asyncio
    async def test_no_backup_for_nonexistent_file(self):
        """Test that no backup is needed for nonexistent files."""
        checker = BackupChecker()
        tool_call = ToolCall(
            tool_name="write_file",
            parameters={"path": "/tmp/nonexistent.txt"},
        )

        result = await checker.check(tool_call)

        assert result.status == SafetyStatus.PASSED
        assert "doesn't exist" in result.message.lower()


class TestDiskSpaceChecker:
    """Test DiskSpaceChecker."""

    @pytest.mark.asyncio
    async def test_skip_non_write_operations(self):
        """Test that non-write operations are skipped."""
        checker = DiskSpaceChecker()
        tool_call = ToolCall(
            tool_name="read_file",
            parameters={},
        )

        result = await checker.check(tool_call)

        assert result.status == SafetyStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_sufficient_disk_space(self):
        """Test checking sufficient disk space."""
        checker = DiskSpaceChecker()
        tool_call = ToolCall(
            tool_name="write_file",
            parameters={"size": 1024},  # 1KB
        )

        result = await checker.check(tool_call)

        # Should pass unless system is really out of space
        assert result.status == SafetyStatus.PASSED
        assert result.risk_level == RiskLevel.NONE


class TestPermissionChecker:
    """Test PermissionChecker."""

    @pytest.mark.asyncio
    async def test_no_path_passes(self):
        """Test that missing path passes."""
        checker = PermissionChecker()
        tool_call = ToolCall(
            tool_name="some_operation",
            parameters={},
        )

        result = await checker.check(tool_call)

        assert result.status == SafetyStatus.PASSED

    @pytest.mark.asyncio
    async def test_readable_file_for_read(self):
        """Test checking read permission for existing file."""
        with tempfile.NamedTemporaryFile() as tmp:
            checker = PermissionChecker()
            tool_call = ToolCall(
                tool_name="read_file",
                parameters={"path": tmp.name},
            )

            result = await checker.check(tool_call)

            assert result.status == SafetyStatus.PASSED
            assert result.risk_level == RiskLevel.NONE

    @pytest.mark.asyncio
    async def test_writable_file_for_write(self):
        """Test checking write permission for existing file."""
        with tempfile.NamedTemporaryFile() as tmp:
            checker = PermissionChecker()
            tool_call = ToolCall(
                tool_name="write_file",
                parameters={"path": tmp.name},
            )

            result = await checker.check(tool_call)

            assert result.status == SafetyStatus.PASSED


class TestSizeLimitChecker:
    """Test SizeLimitChecker."""

    @pytest.mark.asyncio
    async def test_no_file_passes(self):
        """Test that missing file passes."""
        checker = SizeLimitChecker()
        tool_call = ToolCall(
            tool_name="read_file",
            parameters={},
        )

        result = await checker.check(tool_call)

        assert result.status == SafetyStatus.PASSED

    @pytest.mark.asyncio
    async def test_small_file_passes(self):
        """Test that small files pass."""
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write(b"small content")
            tmp.flush()

            checker = SizeLimitChecker({"max_bytes": 1024 * 1024})  # 1MB limit
            tool_call = ToolCall(
                tool_name="read_file",
                parameters={"path": tmp.name},
            )

            result = await checker.check(tool_call)

            assert result.status == SafetyStatus.PASSED
            assert result.risk_level == RiskLevel.NONE

    @pytest.mark.asyncio
    async def test_large_file_warning(self):
        """Test that large files trigger warning."""
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write(b"x" * 1024)  # 1KB
            tmp.flush()

            checker = SizeLimitChecker({"max_bytes": 512})  # 512B limit
            tool_call = ToolCall(
                tool_name="read_file",
                parameters={"path": tmp.name},
            )

            result = await checker.check(tool_call)

            assert result.status == SafetyStatus.WARNING
            assert result.risk_level == RiskLevel.MEDIUM
            assert result.can_override


class TestSensitiveDataChecker:
    """Test SensitiveDataChecker."""

    @pytest.mark.asyncio
    async def test_no_sensitive_data(self):
        """Test when no sensitive data is found."""
        checker = SensitiveDataChecker()
        tool_call = ToolCall(
            tool_name="read_file",
            parameters={"content": "This is normal text"},
        )

        result = await checker.check(tool_call)

        assert result.status == SafetyStatus.PASSED
        assert result.risk_level == RiskLevel.NONE

    @pytest.mark.asyncio
    async def test_detect_api_key_in_params(self):
        """Test detecting API key in parameters."""
        checker = SensitiveDataChecker()
        tool_call = ToolCall(
            tool_name="write_file",
            parameters={"content": "api_key=sk-1234567890abcdef"},
        )

        result = await checker.check(tool_call)

        assert result.status == SafetyStatus.WARNING
        assert result.risk_level == RiskLevel.HIGH
        assert "sensitive data" in result.message.lower()
        assert result.can_override

    @pytest.mark.asyncio
    async def test_detect_ssh_key(self):
        """Test detecting SSH private key."""
        checker = SensitiveDataChecker()
        tool_call = ToolCall(
            tool_name="write_file",
            parameters={"content": "-----BEGIN RSA PRIVATE KEY-----"},
        )

        result = await checker.check(tool_call)

        assert result.status == SafetyStatus.WARNING
        assert result.risk_level == RiskLevel.HIGH

    @pytest.mark.asyncio
    async def test_detect_email(self):
        """Test detecting email addresses."""
        checker = SensitiveDataChecker()
        tool_call = ToolCall(
            tool_name="write_file",
            parameters={"content": "Contact me at user@example.com"},
        )

        result = await checker.check(tool_call)

        assert result.status == SafetyStatus.WARNING
        assert len(result.suggestions) > 0


class TestCommandValidator:
    """Test CommandValidator."""

    @pytest.mark.asyncio
    async def test_no_command_passes(self):
        """Test that missing command passes."""
        checker = CommandValidator()
        tool_call = ToolCall(
            tool_name="execute_command",
            parameters={},
        )

        result = await checker.check(tool_call)

        assert result.status == SafetyStatus.PASSED

    @pytest.mark.asyncio
    async def test_safe_command(self):
        """Test that safe commands pass."""
        checker = CommandValidator()
        tool_call = ToolCall(
            tool_name="execute_command",
            parameters={"command": "ls -la"},
        )

        result = await checker.check(tool_call)

        assert result.status == SafetyStatus.PASSED
        assert result.risk_level == RiskLevel.LOW

    @pytest.mark.asyncio
    async def test_dangerous_command_warning(self):
        """Test that dangerous commands trigger warning."""
        checker = CommandValidator()
        tool_call = ToolCall(
            tool_name="execute_command",
            parameters={"command": "rm test.txt"},
        )

        result = await checker.check(tool_call)

        assert result.status == SafetyStatus.WARNING
        assert result.risk_level == RiskLevel.HIGH
        assert result.can_override

    @pytest.mark.asyncio
    async def test_very_dangerous_command_blocked(self):
        """Test that very dangerous commands are blocked."""
        checker = CommandValidator()
        tool_call = ToolCall(
            tool_name="execute_command",
            parameters={"command": "rm -rf /"},
        )

        result = await checker.check(tool_call)

        assert result.status == SafetyStatus.FAILED
        assert result.risk_level == RiskLevel.CRITICAL
        assert "dangerous" in result.message.lower()

    @pytest.mark.asyncio
    async def test_unknown_command(self):
        """Test that unknown commands trigger warning."""
        checker = CommandValidator()
        tool_call = ToolCall(
            tool_name="execute_command",
            parameters={"command": "unknowncommand --arg"},
        )

        result = await checker.check(tool_call)

        assert result.status == SafetyStatus.WARNING
        assert result.risk_level == RiskLevel.MEDIUM
        assert result.can_override


class TestSandboxChecker:
    """Test SandboxChecker."""

    @pytest.mark.asyncio
    async def test_no_path_passes(self):
        """Test that missing path passes."""
        checker = SandboxChecker()
        tool_call = ToolCall(
            tool_name="some_operation",
            parameters={},
        )

        result = await checker.check(tool_call)

        assert result.status == SafetyStatus.PASSED

    @pytest.mark.asyncio
    async def test_protected_path_blocked(self):
        """Test that protected paths are blocked."""
        checker = SandboxChecker()
        tool_call = ToolCall(
            tool_name="write_file",
            parameters={"path": "/etc/passwd"},
        )

        result = await checker.check(tool_call)

        assert result.status == SafetyStatus.FAILED
        assert result.risk_level == RiskLevel.CRITICAL
        assert "protected" in result.message.lower()

    @pytest.mark.asyncio
    async def test_sandbox_path_allowed(self):
        """Test that paths within sandbox are allowed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checker = SandboxChecker({"sandbox_root": tmpdir})
            tool_call = ToolCall(
                tool_name="write_file",
                parameters={"path": f"{tmpdir}/test.txt"},
            )

            result = await checker.check(tool_call)

            assert result.status == SafetyStatus.PASSED
            assert result.risk_level == RiskLevel.NONE

    @pytest.mark.asyncio
    async def test_outside_sandbox_warning(self):
        """Test that paths outside sandbox trigger warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checker = SandboxChecker({"sandbox_root": tmpdir})
            tool_call = ToolCall(
                tool_name="read_file",
                parameters={"path": "/tmp/outside.txt"},
            )

            result = await checker.check(tool_call)

            assert result.status == SafetyStatus.WARNING
            assert result.risk_level == RiskLevel.MEDIUM
            assert result.can_override
            assert "outside sandbox" in result.message.lower()