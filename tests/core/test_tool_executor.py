"""Tests for the ToolExecutor class."""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime

from adh_cli.core.tool_executor import (
    ToolExecutor,
    ExecutionContext,
    ExecutionResult,
)
from adh_cli.policies.policy_engine import PolicyEngine
from adh_cli.policies.policy_types import (
    ToolCall,
    PolicyDecision,
    SupervisionLevel,
    RiskLevel,
    SafetyCheck,
)
from adh_cli.safety.pipeline import SafetyPipeline
from adh_cli.safety.base_checker import SafetyResult, SafetyStatus


class TestToolExecutor:
    """Test the ToolExecutor class."""

    @pytest.fixture
    def mock_policy_engine(self):
        """Create a mock policy engine."""
        engine = Mock(spec=PolicyEngine)
        engine.evaluate_tool_call = Mock(
            return_value=PolicyDecision(
                allowed=True,
                supervision_level=SupervisionLevel.AUTOMATIC,
                risk_level=RiskLevel.LOW,
            )
        )
        return engine

    @pytest.fixture
    def mock_safety_pipeline(self):
        """Create a mock safety pipeline."""
        pipeline = Mock(spec=SafetyPipeline)
        pipeline.checkers = {}  # Initialize empty checkers dict
        pipeline.run = AsyncMock(  # Keep for backward compat
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
        pipeline.register_checker = Mock()
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
    def tool_executor(self, mock_policy_engine, mock_safety_pipeline):
        """Create a ToolExecutor with mocked dependencies."""
        return ToolExecutor(
            policy_engine=mock_policy_engine,
            safety_pipeline=mock_safety_pipeline,
        )

    @pytest.mark.asyncio
    async def test_execute_allowed_tool(self, tool_executor):
        """Test executing a tool that is allowed by policy."""
        # Register a test tool
        async def test_tool(param1: str):
            return f"Result: {param1}"

        tool_executor.register_tool("test_tool", test_tool)

        # Execute the tool
        result = await tool_executor.execute(
            tool_name="test_tool",
            parameters={"param1": "test_value"},
        )

        assert result.success is True
        assert result.result == "Result: test_value"
        assert result.error is None
        assert result.policy_decision.allowed is True

    @pytest.mark.asyncio
    async def test_execute_denied_tool(self, tool_executor):
        """Test executing a tool that is denied by policy."""
        # Mock policy to deny execution
        tool_executor.policy_engine.evaluate_tool_call.return_value = PolicyDecision(
            allowed=False,
            supervision_level=SupervisionLevel.DENY,
            risk_level=RiskLevel.CRITICAL,
            reason="Tool execution denied by policy",
        )

        # Register a test tool
        async def test_tool():
            return "Should not execute"

        tool_executor.register_tool("denied_tool", test_tool)

        # Execute the tool
        result = await tool_executor.execute(
            tool_name="denied_tool",
            parameters={},
        )

        assert result.success is False
        assert result.result is None
        assert "denied by policy" in result.error.lower()
        assert result.policy_decision.allowed is False

    @pytest.mark.asyncio
    async def test_execute_with_confirmation(self, tool_executor):
        """Test executing a tool that requires confirmation."""
        # Mock policy to require confirmation
        tool_executor.policy_engine.evaluate_tool_call.return_value = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.CONFIRM,
            risk_level=RiskLevel.MEDIUM,
            requires_confirmation=True,
            confirmation_message="Confirm this operation?",
        )

        # Mock confirmation handler to approve
        tool_executor.confirmation_handler = AsyncMock(return_value=True)

        # Register a test tool
        async def test_tool():
            return "Executed after confirmation"

        tool_executor.register_tool("confirm_tool", test_tool)

        # Execute the tool
        result = await tool_executor.execute(
            tool_name="confirm_tool",
            parameters={},
        )

        assert result.success is True
        assert result.result == "Executed after confirmation"
        tool_executor.confirmation_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_confirmation_declined(self, tool_executor):
        """Test executing a tool when confirmation is declined."""
        # Mock policy to require confirmation
        tool_executor.policy_engine.evaluate_tool_call.return_value = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.CONFIRM,
            risk_level=RiskLevel.MEDIUM,
            requires_confirmation=True,
            confirmation_message="Confirm this operation?",
        )

        # Mock confirmation handler to decline
        tool_executor.confirmation_handler = AsyncMock(return_value=False)

        # Register a test tool
        async def test_tool():
            return "Should not execute"

        tool_executor.register_tool("confirm_tool", test_tool)

        # Execute the tool
        result = await tool_executor.execute(
            tool_name="confirm_tool",
            parameters={},
        )

        assert result.success is False
        assert result.error == "User declined execution"
        tool_executor.confirmation_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_safety_failure(self, tool_executor):
        """Test executing a tool that fails safety checks."""
        tool_executor.policy_engine.evaluate_tool_call.return_value.safety_checks = [
            SafetyCheck(name="test", checker_class="TestChecker")
        ]
        tool_executor.safety_pipeline.run_checks.return_value = Mock(
            check_results=[
                SafetyResult(
                    checker_name="TestChecker",
                    status=SafetyStatus.FAILED,
                    message="Safety check failed",
                    risk_level=RiskLevel.HIGH,
                )
            ]
        )

        # Register a test tool
        async def test_tool():
            return "Should not execute"

        tool_executor.register_tool("unsafe_tool", test_tool)

        # Execute the tool
        result = await tool_executor.execute(
            tool_name="unsafe_tool",
            parameters={},
        )

        assert result.success is False
        assert "Safety checks failed" in result.error
        assert len(result.safety_results) > 0

    @pytest.mark.asyncio
    async def test_execute_with_safety_warning_override(self, tool_executor):
        """Test executing a tool with safety warnings that are overridden."""
        # Mock safety pipeline to return warning
        tool_executor.safety_pipeline.run_checks.return_value = Mock(
            check_results=[
                SafetyResult(
                    checker_name="TestChecker",
                    status=SafetyStatus.WARNING,
                    message="Safety warning",
                    risk_level=RiskLevel.MEDIUM,
                    can_override=True,
                )
            ]
        )

        # Mock override confirmation to approve
        tool_executor.confirmation_handler = AsyncMock(return_value=True)

        # Register a test tool
        async def test_tool():
            return "Executed with warning override"

        tool_executor.register_tool("warning_tool", test_tool)

        # Execute the tool
        result = await tool_executor.execute(
            tool_name="warning_tool",
            parameters={},
        )

        assert result.success is True
        assert result.result == "Executed with warning override"

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self, tool_executor):
        """Test executing a tool that doesn't exist."""
        result = await tool_executor.execute(
            tool_name="nonexistent_tool",
            parameters={},
        )

        assert result.success is False
        assert "not found in registry" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, tool_executor):
        """Test executing a tool that times out."""
        # Set a short timeout in the decision
        tool_executor.policy_engine.evaluate_tool_call.return_value = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.AUTOMATIC,
            risk_level=RiskLevel.LOW,
            metadata={"timeout": 0.1},  # 100ms timeout
        )

        # Register a slow tool
        async def slow_tool():
            await asyncio.sleep(1)  # Sleep for 1 second
            return "Should timeout"

        tool_executor.register_tool("slow_tool", slow_tool)

        # Execute the tool
        result = await tool_executor.execute(
            tool_name="slow_tool",
            parameters={},
        )

        assert result.success is False
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_exception(self, tool_executor):
        """Test executing a tool that raises an exception."""
        # Register a failing tool
        async def failing_tool():
            raise ValueError("Test error")

        tool_executor.register_tool("failing_tool", failing_tool)

        # Execute the tool
        result = await tool_executor.execute(
            tool_name="failing_tool",
            parameters={},
        )

        assert result.success is False
        assert "Test error" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_context(self, tool_executor):
        """Test executing a tool with execution context."""
        context = ExecutionContext(
            user_id="test_user",
            session_id="test_session",
            agent_name="test_agent",
            request_id="test_request",
        )

        # Register a test tool
        async def test_tool():
            return "Result with context"

        tool_executor.register_tool("context_tool", test_tool)

        # Execute the tool
        result = await tool_executor.execute(
            tool_name="context_tool",
            parameters={},
            context=context,
        )

        assert result.success is True
        assert result.result == "Result with context"

        # Verify context was passed to policy evaluation
        call_args = tool_executor.policy_engine.evaluate_tool_call.call_args
        tool_call = call_args[0][0]
        assert tool_call.agent_name == "test_agent"
        assert tool_call.request_id == "test_request"

    @pytest.mark.asyncio
    async def test_execute_with_audit_logging(self, tool_executor):
        """Test that audit logging is called correctly."""
        # Mock audit logger
        tool_executor.audit_logger = AsyncMock()

        # Register a test tool
        async def test_tool(**kwargs):
            return "Result"

        tool_executor.register_tool("audit_tool", test_tool)

        # Execute the tool
        result = await tool_executor.execute(
            tool_name="audit_tool",
            parameters={"param": "value"},
        )

        assert result.success is True

        # Verify audit logger was called
        assert tool_executor.audit_logger.call_count >= 2  # policy_evaluated and tool_executed

    @pytest.mark.asyncio
    async def test_parameter_modifications(self, tool_executor):
        """Test that parameter modifications from safety checks are applied."""
        # Mock safety result with parameter modifications
        safety_result = SafetyResult(
            checker_name="ModifyChecker",
            status=SafetyStatus.PASSED,
            message="Modified parameters",
            risk_level=RiskLevel.LOW,
        )
        safety_result.parameter_modifications = {"new_param": "new_value"}

        tool_executor.policy_engine.evaluate_tool_call.return_value.safety_checks = [
            SafetyCheck(name="test", checker_class="TestChecker")
        ]
        tool_executor.safety_pipeline.run_checks.return_value = Mock(
            check_results=[safety_result]
        )

        # Register a tool that checks parameters
        async def test_tool(**kwargs):
            return kwargs

        tool_executor.register_tool("modify_tool", test_tool)

        # Execute the tool
        result = await tool_executor.execute(
            tool_name="modify_tool",
            parameters={"original_param": "original_value"},
        )

        assert result.success is True
        assert "new_param" in result.result
        assert result.result["new_param"] == "new_value"
        assert result.result["original_param"] == "original_value"

    @pytest.mark.asyncio
    async def test_safety_checks_from_policy(self, tool_executor):
        """Test that safety checks from policy decision are executed."""
        # Mock policy to include safety checks
        tool_executor.policy_engine.evaluate_tool_call.return_value = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.AUTOMATIC,
            risk_level=RiskLevel.LOW,
            safety_checks=[
                SafetyCheck(
                    name="test_check",
                    checker_class="TestChecker",
                    config={"key": "value"},
                    required=True,
                )
            ],
        )

        # Register a test tool
        async def test_tool():
            return "Result"

        tool_executor.register_tool("checked_tool", test_tool)

        # Mock register_checker method and mock the checker module
        tool_executor.safety_pipeline.register_checker = Mock()
        tool_executor.safety_pipeline.checkers = {}  # Start with empty checkers

        # Patch the getattr to return a mock TestChecker class
        mock_checker_class = Mock()

        with patch('adh_cli.core.tool_executor.getattr', return_value=mock_checker_class) as mock_getattr:
            # Execute the tool
            result = await tool_executor.execute(
                tool_name="checked_tool",
                parameters={},
            )

            assert result.success is True

            # Verify safety pipeline was configured and run
            tool_executor.safety_pipeline.register_checker.assert_called_with("TestChecker", mock_checker_class)
            tool_executor.safety_pipeline.run_checks.assert_called_once()


class TestExecutionContext:
    """Test the ExecutionContext class."""

    def test_execution_context_creation(self):
        """Test creating an execution context."""
        context = ExecutionContext(
            user_id="user123",
            session_id="session456",
            agent_name="TestAgent",
            request_id="req789",
            metadata={"key": "value"},
        )

        assert context.user_id == "user123"
        assert context.session_id == "session456"
        assert context.agent_name == "TestAgent"
        assert context.request_id == "req789"
        assert context.metadata["key"] == "value"

    def test_execution_context_defaults(self):
        """Test execution context with defaults."""
        context = ExecutionContext()

        assert context.user_id is None
        assert context.session_id is None
        assert context.agent_name is None
        assert context.request_id is None
        assert context.metadata == {}


class TestExecutionResult:
    """Test the ExecutionResult class."""

    def test_execution_result_success(self):
        """Test successful execution result."""
        result = ExecutionResult(
            success=True,
            result="Test result",
            execution_time=1.5,
        )

        assert result.success is True
        assert result.result == "Test result"
        assert result.error is None
        assert result.execution_time == 1.5

    def test_execution_result_failure(self):
        """Test failed execution result."""
        result = ExecutionResult(
            success=False,
            error="Test error",
        )

        assert result.success is False
        assert result.result is None
        assert result.error == "Test error"

    def test_execution_result_with_metadata(self):
        """Test execution result with full metadata."""
        decision = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.AUTOMATIC,
            risk_level=RiskLevel.LOW,
        )

        safety_results = [
            SafetyResult(
                checker_name="TestChecker",
                status=SafetyStatus.PASSED,
                message="Check passed",
                risk_level=RiskLevel.LOW,
            )
        ]

        result = ExecutionResult(
            success=True,
            result="Test",
            policy_decision=decision,
            safety_results=safety_results,
            metadata={"key": "value"},
        )

        assert result.policy_decision == decision
        assert result.safety_results == safety_results
        assert result.metadata["key"] == "value"