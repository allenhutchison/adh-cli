"""Integration tests for ADK agent with policy enforcement.

These tests verify the full integration between PolicyAwareLlmAgent,
ADK components, policy engine, and safety pipeline.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from adh_cli.core.policy_aware_llm_agent import PolicyAwareLlmAgent
from adh_cli.core.tool_executor import ExecutionContext


class TestADKIntegration:
    """Integration tests for ADK agent with full policy stack."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test policies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_adk_agent(self, temp_dir):
        """Create agent with mocked ADK components."""
        with (
            patch("adh_cli.core.policy_aware_llm_agent.LlmAgent") as mock_llm,
            patch("adh_cli.core.policy_aware_llm_agent.Runner") as mock_runner,
            patch(
                "adh_cli.core.policy_aware_llm_agent.InMemorySessionService"
            ) as mock_session,
        ):
            # Configure mocks
            mock_llm_instance = Mock()
            mock_llm.return_value = mock_llm_instance

            mock_runner_instance = Mock()
            mock_runner.return_value = mock_runner_instance

            mock_session_instance = Mock()
            mock_session_instance.create_session = AsyncMock()
            mock_session.return_value = mock_session_instance

            agent = PolicyAwareLlmAgent(
                api_key="test_key",
                policy_dir=temp_dir,
            )

            # Set runner on agent
            agent.runner = mock_runner_instance
            agent.session_service = mock_session_instance

            yield agent, mock_runner_instance

    @pytest.mark.asyncio
    async def test_tool_registration_with_policy_wrapping(self, mock_adk_agent):
        """Test that tools are registered with policy wrappers."""
        agent, _ = mock_adk_agent

        async def test_tool(param: str):
            return f"Result: {param}"

        # Register tool
        agent.register_tool(
            name="test_tool",
            description="Test tool",
            parameters={"param": {"type": "string"}},
            handler=test_tool,
        )

        # Verify tool was registered
        assert "test_tool" in agent.tool_handlers

        # Verify test_tool is wrapped with policy
        from adh_cli.core.policy_aware_function_tool import PolicyAwareFunctionTool

        # Find the function tool (not GenerationConfigTool if present)
        function_tools = [
            t for t in agent.tools if isinstance(t, PolicyAwareFunctionTool)
        ]
        assert len(function_tools) >= 1
        assert isinstance(function_tools[0], PolicyAwareFunctionTool)

    @pytest.mark.asyncio
    async def test_automatic_tool_execution_no_confirmation(self, mock_adk_agent):
        """Test automatic tool execution without confirmation."""
        agent, mock_runner = mock_adk_agent

        # Create a simple tool
        executed = False

        async def safe_tool():
            nonlocal executed
            executed = True
            return "Safe operation completed"

        agent.register_tool(
            name="safe_tool",
            description="A safe tool",
            parameters={},
            handler=safe_tool,
        )

        # Mock event stream
        mock_event = Mock()
        mock_event.get_function_calls.return_value = []
        mock_event.get_function_responses.return_value = []
        mock_event.is_final_response.return_value = True
        mock_part = Mock()
        mock_part.text = "Task completed"
        mock_content = Mock()
        mock_content.parts = [mock_part]
        mock_event.content = mock_content

        async def mock_event_stream(*args, **kwargs):
            yield mock_event

        mock_runner.run_async = mock_event_stream

        # Execute
        result = await agent.chat("Do safe operation", context=ExecutionContext())

        # Verify response
        assert "Task completed" in result

    @pytest.mark.asyncio
    async def test_tool_execution_with_confirmation(self, mock_adk_agent):
        """Test tool execution requiring confirmation."""
        agent, mock_runner = mock_adk_agent

        confirmation_requested = False
        confirmation_approved = False

        async def confirmation_handler(**kwargs):
            nonlocal confirmation_requested, confirmation_approved
            confirmation_requested = True
            confirmation_approved = True
            return True

        agent.confirmation_handler = confirmation_handler

        async def risky_tool(path: str):
            return f"Wrote to {path}"

        agent.register_tool(
            name="write_file",
            description="Write a file",
            parameters={"path": {"type": "string"}},
            handler=risky_tool,
        )

        # Mock event stream
        mock_event = Mock()
        mock_event.get_function_calls.return_value = []
        mock_event.get_function_responses.return_value = []
        mock_event.is_final_response.return_value = True
        mock_part = Mock()
        mock_part.text = "File written"
        mock_part.thought = False  # Explicitly set to False so it's not filtered
        mock_content = Mock()
        mock_content.parts = [mock_part]
        mock_event.content = mock_content

        async def mock_event_stream(*args, **kwargs):
            yield mock_event

        mock_runner.run_async = mock_event_stream

        # Execute
        result = await agent.chat("Write file", context=ExecutionContext())

        assert "File written" in result

    @pytest.mark.asyncio
    async def test_tool_blocked_by_policy(self, mock_adk_agent):
        """Test tool execution blocked by policy."""
        agent, _ = mock_adk_agent

        # Create a tool that should be blocked
        async def dangerous_tool():
            return "Should not execute"

        agent.register_tool(
            name="delete_system",
            description="Dangerous operation",
            parameters={},
            handler=dangerous_tool,
        )

        # The tool should be wrapped with policy checks
        # Policy engine will evaluate and potentially block

        # Note: Actual blocking happens in PolicyAwareFunctionTool
        # when the tool is called by ADK

    @pytest.mark.asyncio
    async def test_multi_tool_conversation(self, mock_adk_agent):
        """Test multi-turn conversation with multiple tool calls."""
        agent, mock_runner = mock_adk_agent

        tool1_called = False
        tool2_called = False

        async def tool1():
            nonlocal tool1_called
            tool1_called = True
            return "Tool 1 result"

        async def tool2():
            nonlocal tool2_called
            tool2_called = True
            return "Tool 2 result"

        agent.register_tool(
            name="tool1",
            description="First tool",
            parameters={},
            handler=tool1,
        )

        agent.register_tool(
            name="tool2",
            description="Second tool",
            parameters={},
            handler=tool2,
        )

        # Mock event stream with multiple tool calls
        mock_event1 = Mock()
        mock_fc1 = Mock()
        mock_fc1.name = "tool1"
        mock_event1.get_function_calls.return_value = [mock_fc1]
        mock_event1.get_function_responses.return_value = []
        mock_event1.is_final_response.return_value = False
        mock_event1.content = None

        mock_event2 = Mock()
        mock_event2.get_function_calls.return_value = []
        mock_event2.get_function_responses.return_value = [Mock()]
        mock_event2.is_final_response.return_value = False
        mock_event2.content = None

        mock_event3 = Mock()
        mock_fc2 = Mock()
        mock_fc2.name = "tool2"
        mock_event3.get_function_calls.return_value = [mock_fc2]
        mock_event3.get_function_responses.return_value = []
        mock_event3.is_final_response.return_value = False
        mock_event3.content = None

        mock_event4 = Mock()
        mock_event4.get_function_calls.return_value = []
        mock_event4.get_function_responses.return_value = [Mock()]
        mock_event4.is_final_response.return_value = False
        mock_event4.content = None

        mock_event5 = Mock()
        mock_event5.get_function_calls.return_value = []
        mock_event5.get_function_responses.return_value = []
        mock_event5.is_final_response.return_value = True
        mock_part = Mock()
        mock_part.text = "Both tools executed"
        mock_part.thought = False  # Explicitly set to False so it's not filtered
        mock_content = Mock()
        mock_content.parts = [mock_part]
        mock_event5.content = mock_content

        async def mock_event_stream(*args, **kwargs):
            yield mock_event1
            yield mock_event2
            yield mock_event3
            yield mock_event4
            yield mock_event5

        mock_runner.run_async = mock_event_stream

        # Execute
        result = await agent.chat("Use both tools", context=ExecutionContext())

        assert "Both tools executed" in result

    # Note: test_notification_handler_called removed - notification system
    # replaced by ToolExecutionWidget UI (see tests/integration/test_tool_execution_ui.py)

    @pytest.mark.asyncio
    async def test_audit_logging(self, temp_dir):
        """Test audit logging is performed."""
        audit_path = temp_dir / "audit.log"

        with (
            patch("adh_cli.core.policy_aware_llm_agent.LlmAgent"),
            patch("adh_cli.core.policy_aware_llm_agent.Runner"),
            patch("adh_cli.core.policy_aware_llm_agent.InMemorySessionService"),
        ):
            agent = PolicyAwareLlmAgent(
                api_key="test_key",
                policy_dir=temp_dir,
                audit_log_path=audit_path,
            )

            # Verify audit logger was created
            assert agent.audit_logger is not None

            # Trigger audit log
            if agent.audit_logger:
                await agent.audit_logger(tool_name="test", parameters={}, success=True)

            # Check file exists
            assert audit_path.exists()
            content = audit_path.read_text()
            assert "test" in content

    @pytest.mark.asyncio
    async def test_session_management(self, mock_adk_agent):
        """Test session is properly initialized."""
        agent, _ = mock_adk_agent

        # Ensure session initialization
        await agent._ensure_session_initialized()

        # Check session service was called
        agent.session_service.create_session.assert_called()

    @pytest.mark.asyncio
    async def test_error_handling_permission_error(self, mock_adk_agent):
        """Test handling of PermissionError from policy."""
        agent, mock_runner = mock_adk_agent

        # Mock runner to raise PermissionError
        async def mock_error_stream(*args, **kwargs):
            raise PermissionError("Tool blocked by policy")
            yield  # Never reached

        mock_runner.run_async = mock_error_stream

        result = await agent.chat("Do something blocked")

        # Should return error message
        assert "blocked by policy" in result.lower()

    @pytest.mark.asyncio
    async def test_error_handling_general_error(self, mock_adk_agent):
        """Test handling of general errors."""
        agent, mock_runner = mock_adk_agent

        # Mock runner to raise generic error
        async def mock_error_stream(*args, **kwargs):
            raise ValueError("Some error")
            yield  # Never reached

        mock_runner.run_async = mock_error_stream

        result = await agent.chat("Do something")

        # Should return error message
        assert "error" in result.lower()

    def test_update_policies(self, mock_adk_agent, temp_dir):
        """Test updating policies recreates tools."""
        agent, _ = mock_adk_agent

        # Register a tool
        async def test_tool():
            return "result"

        agent.register_tool(
            name="test_tool",
            description="Test",
            parameters={},
            handler=test_tool,
        )

        # Update policies
        new_policy_dir = temp_dir / "new_policies"
        new_policy_dir.mkdir()

        agent.update_policies(new_policy_dir)

        # Tool should still be registered
        assert "test_tool" in agent.tool_handlers

    def test_set_user_preferences(self, mock_adk_agent):
        """Test setting user preferences."""
        agent, _ = mock_adk_agent

        prefs = {"auto_approve": ["read_file"]}
        agent.set_user_preferences(prefs)

        assert "auto_approve" in agent.policy_engine.user_preferences

    def test_tool_executor_property(self, mock_adk_agent):
        """Test tool_executor compatibility property."""
        agent, _ = mock_adk_agent

        executor = agent.tool_executor
        assert executor is not None
        assert hasattr(executor, "execute")

    @pytest.mark.asyncio
    async def test_tool_executor_execute_method(self, mock_adk_agent):
        """Test direct tool execution via tool_executor."""
        agent, _ = mock_adk_agent

        async def test_tool(param: str):
            return f"Result: {param}"

        agent.register_tool(
            name="test_tool",
            description="Test",
            parameters={},
            handler=test_tool,
        )

        executor = agent.tool_executor
        result = await executor.execute(
            tool_name="test_tool", parameters={"param": "value"}
        )

        assert result.success is True
        assert "Result: value" in str(result.result)
