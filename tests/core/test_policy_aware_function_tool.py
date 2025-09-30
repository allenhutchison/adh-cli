"""Tests for PolicyAwareFunctionTool."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from adh_cli.core.policy_aware_function_tool import PolicyAwareFunctionTool, SafetyError
from adh_cli.policies.policy_engine import PolicyEngine
from adh_cli.policies.policy_types import (
    PolicyDecision,
    SupervisionLevel,
    RiskLevel,
    SafetyCheck,
)
from adh_cli.safety.pipeline import SafetyPipeline, SafetyResult, SafetyStatus


class TestPolicyAwareFunctionTool:
    """Test PolicyAwareFunctionTool class."""

    @pytest.fixture
    def mock_policy_engine(self):
        """Create mock policy engine."""
        engine = Mock(spec=PolicyEngine)
        engine.evaluate_tool_call.return_value = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.AUTOMATIC,
            risk_level=RiskLevel.LOW,
        )
        return engine

    @pytest.fixture
    def mock_safety_pipeline(self):
        """Create mock safety pipeline."""
        pipeline = Mock(spec=SafetyPipeline)
        pipeline.checkers = {}
        pipeline.run_checks = AsyncMock(
            return_value=Mock(
                results=[
                    SafetyResult(
                        checker_name="TestChecker",
                        status=SafetyStatus.PASSED,
                        message="Check passed",
                        risk_level=RiskLevel.LOW,
                    )
                ]
            )
        )
        return pipeline

    @pytest.fixture
    def mock_audit_logger(self):
        """Create mock audit logger."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_tool_execution_with_automatic_policy(
        self, mock_policy_engine, mock_safety_pipeline, mock_audit_logger
    ):
        """Test tool executes successfully with automatic policy."""

        async def test_func(arg1: str, arg2: int):
            return f"Result: {arg1}-{arg2}"

        tool = PolicyAwareFunctionTool(
            func=test_func,
            tool_name="test_tool",
            policy_engine=mock_policy_engine,
            safety_pipeline=mock_safety_pipeline,
            audit_logger=mock_audit_logger,
        )

        # Execute the wrapped function
        result = await tool.func(arg1="test", arg2=42)

        assert result == "Result: test-42"
        mock_policy_engine.evaluate_tool_call.assert_called_once()
        mock_audit_logger.assert_called()

    @pytest.mark.asyncio
    async def test_tool_blocked_by_policy(
        self, mock_policy_engine, mock_safety_pipeline
    ):
        """Test tool execution blocked by policy."""
        # Configure policy to block
        mock_policy_engine.evaluate_tool_call.return_value = PolicyDecision(
            allowed=False,
            supervision_level=SupervisionLevel.DENY,
            risk_level=RiskLevel.CRITICAL,
            reason="Dangerous operation",
        )

        async def test_func():
            return "Should not execute"

        tool = PolicyAwareFunctionTool(
            func=test_func,
            tool_name="dangerous_tool",
            policy_engine=mock_policy_engine,
            safety_pipeline=mock_safety_pipeline,
        )

        # Should raise PermissionError
        with pytest.raises(PermissionError) as exc_info:
            await tool.func()

        assert "blocked by policy" in str(exc_info.value)
        assert "Dangerous operation" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_confirmation_required_detection(
        self, mock_policy_engine, mock_safety_pipeline
    ):
        """Test that confirmation requirement is detected."""
        # Configure policy to require confirmation
        mock_policy_engine.evaluate_tool_call.return_value = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.CONFIRM,
            risk_level=RiskLevel.MEDIUM,
            requires_confirmation=True,  # Explicitly set
        )

        async def test_func():
            return "Result"

        tool = PolicyAwareFunctionTool(
            func=test_func,
            tool_name="confirm_tool",
            policy_engine=mock_policy_engine,
            safety_pipeline=mock_safety_pipeline,
        )

        # Check if confirmation is required (this is called by ADK with tool params)
        # Access the internal confirmation checker with sample parameters
        requires_confirmation = tool._require_confirmation(param1="test")

        assert requires_confirmation is True

    @pytest.mark.asyncio
    async def test_no_confirmation_for_automatic(
        self, mock_policy_engine, mock_safety_pipeline
    ):
        """Test that automatic operations don't require confirmation."""
        # Configure policy for automatic execution
        mock_policy_engine.evaluate_tool_call.return_value = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.AUTOMATIC,
            risk_level=RiskLevel.LOW,
        )

        async def test_func():
            return "Result"

        tool = PolicyAwareFunctionTool(
            func=test_func,
            tool_name="auto_tool",
            policy_engine=mock_policy_engine,
            safety_pipeline=mock_safety_pipeline,
        )

        # Check if confirmation is required (with params)
        requires_confirmation = tool._require_confirmation(param1="test")

        assert requires_confirmation is False

    @pytest.mark.asyncio
    async def test_safety_check_failure(
        self, mock_policy_engine, mock_safety_pipeline
    ):
        """Test that failed safety checks block execution."""
        # Configure policy with safety checks
        mock_policy_engine.evaluate_tool_call.return_value = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.AUTOMATIC,
            risk_level=RiskLevel.MEDIUM,
            safety_checks=[
                SafetyCheck(name="test_check", checker_class="TestChecker")
            ],
        )

        # Configure safety pipeline to fail
        mock_safety_pipeline.run_checks.return_value = Mock(
            results=[
                SafetyResult(
                    checker_name="TestChecker",
                    status=SafetyStatus.FAILED,
                    message="Safety check failed",
                    risk_level=RiskLevel.HIGH,
                )
            ]
        )

        async def test_func():
            return "Should not execute"

        tool = PolicyAwareFunctionTool(
            func=test_func,
            tool_name="unsafe_tool",
            policy_engine=mock_policy_engine,
            safety_pipeline=mock_safety_pipeline,
        )

        # Should raise SafetyError
        with pytest.raises(SafetyError) as exc_info:
            await tool.func()

        assert "Safety check failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_parameter_modifications_from_safety_checks(
        self, mock_policy_engine, mock_safety_pipeline, mock_audit_logger
    ):
        """Test that safety checks can modify parameters."""
        # Configure policy with safety checks
        mock_policy_engine.evaluate_tool_call.return_value = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.AUTOMATIC,
            risk_level=RiskLevel.LOW,
            safety_checks=[
                SafetyCheck(name="test_check", checker_class="TestChecker")
            ],
        )

        # Configure safety check to modify parameters
        mock_result = SafetyResult(
            checker_name="TestChecker",
            status=SafetyStatus.PASSED,
            message="Check passed",
            risk_level=RiskLevel.LOW,
        )
        mock_result.parameter_modifications = {"backup_created": True}

        mock_safety_pipeline.run_checks.return_value = Mock(
            results=[mock_result]
        )

        received_params = {}

        async def test_func(**kwargs):
            nonlocal received_params
            received_params = kwargs
            return "Result"

        tool = PolicyAwareFunctionTool(
            func=test_func,
            tool_name="modify_tool",
            policy_engine=mock_policy_engine,
            safety_pipeline=mock_safety_pipeline,
            audit_logger=mock_audit_logger,
        )

        result = await tool.func(original_param="value")

        assert result == "Result"
        assert received_params["original_param"] == "value"
        assert received_params["backup_created"] is True

    @pytest.mark.asyncio
    async def test_audit_logging_on_success(
        self, mock_policy_engine, mock_safety_pipeline, mock_audit_logger
    ):
        """Test audit logging captures successful execution."""

        async def test_func(param: str):
            return f"Success: {param}"

        tool = PolicyAwareFunctionTool(
            func=test_func,
            tool_name="log_tool",
            policy_engine=mock_policy_engine,
            safety_pipeline=mock_safety_pipeline,
            audit_logger=mock_audit_logger,
        )

        result = await tool.func(param="test")

        assert result == "Success: test"

        # Check audit logger was called for pre and post execution
        assert mock_audit_logger.call_count >= 2

        # Check calls contain expected information
        calls = mock_audit_logger.call_args_list
        pre_exec_call = None
        post_exec_call = None

        for call in calls:
            kwargs = call[1] if call[1] else call[0][0] if call[0] else {}
            if kwargs.get("phase") == "pre_execution":
                pre_exec_call = kwargs
            elif kwargs.get("phase") == "post_execution":
                post_exec_call = kwargs

        assert pre_exec_call is not None
        assert post_exec_call is not None
        assert post_exec_call["success"] is True

    @pytest.mark.asyncio
    async def test_audit_logging_on_error(
        self, mock_policy_engine, mock_safety_pipeline, mock_audit_logger
    ):
        """Test audit logging captures execution errors."""

        async def test_func():
            raise ValueError("Test error")

        tool = PolicyAwareFunctionTool(
            func=test_func,
            tool_name="error_tool",
            policy_engine=mock_policy_engine,
            safety_pipeline=mock_safety_pipeline,
            audit_logger=mock_audit_logger,
        )

        with pytest.raises(ValueError):
            await tool.func()

        # Check audit logger was called with error
        calls = mock_audit_logger.call_args_list
        error_call = None

        for call in calls:
            kwargs = call[1] if call[1] else {}
            if kwargs.get("phase") == "execution_error":
                error_call = kwargs
                break

        assert error_call is not None
        assert error_call["success"] is False
        assert "Test error" in error_call["error"]

    @pytest.mark.asyncio
    async def test_no_audit_logger(
        self, mock_policy_engine, mock_safety_pipeline
    ):
        """Test tool works without audit logger."""

        async def test_func():
            return "Result"

        tool = PolicyAwareFunctionTool(
            func=test_func,
            tool_name="no_log_tool",
            policy_engine=mock_policy_engine,
            safety_pipeline=mock_safety_pipeline,
            audit_logger=None,  # No logger
        )

        result = await tool.func()

        assert result == "Result"  # Should still work

    @pytest.mark.asyncio
    async def test_enhanced_error_messages_with_calling_signature(
        self, mock_policy_engine, mock_safety_pipeline
    ):
        """Test that error messages include the tool name and calling signature."""

        async def test_func(file_path: str, max_lines: int = None):
            # Simulate file not found error
            raise FileNotFoundError(f"File not found: {file_path}")

        tool = PolicyAwareFunctionTool(
            func=test_func,
            tool_name="read_file",
            policy_engine=mock_policy_engine,
            safety_pipeline=mock_safety_pipeline,
        )

        # Execute with specific parameters
        with pytest.raises(FileNotFoundError) as exc_info:
            await tool.func(file_path="adh_cli/services/adk_service.py", max_lines=100)

        error_msg = str(exc_info.value)

        # Verify enhanced error message contains:
        # 1. Error type name
        assert "FileNotFoundError" in error_msg

        # 2. Tool name
        assert "read_file" in error_msg

        # 3. Parameter values in calling signature
        assert "file_path='adh_cli/services/adk_service.py'" in error_msg
        assert "max_lines=100" in error_msg

        # 4. Original error message
        assert "File not found" in error_msg