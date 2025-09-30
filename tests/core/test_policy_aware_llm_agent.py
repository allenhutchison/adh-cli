"""Tests for PolicyAwareLlmAgent."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile

from adh_cli.core.policy_aware_llm_agent import PolicyAwareLlmAgent
from adh_cli.core.tool_executor import ExecutionContext
from adh_cli.policies.policy_types import PolicyDecision, SupervisionLevel, RiskLevel


class TestPolicyAwareLlmAgent:
    """Test PolicyAwareLlmAgent class."""

    @pytest.fixture
    def agent_without_api_key(self):
        """Create agent without API key (for testing structure)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PolicyAwareLlmAgent(
                api_key=None,
                policy_dir=Path(tmpdir),
            )
            yield agent

    @pytest.fixture
    def agent_with_mock_adk(self):
        """Create agent with mocked ADK components."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('adh_cli.core.policy_aware_llm_agent.LlmAgent') as mock_llm_agent, \
                 patch('adh_cli.core.policy_aware_llm_agent.Runner') as mock_runner, \
                 patch('adh_cli.core.policy_aware_llm_agent.InMemorySessionService') as mock_session:

                # Configure mocks
                mock_agent_instance = Mock()
                mock_llm_agent.return_value = mock_agent_instance

                mock_runner_instance = Mock()
                mock_runner_instance.run_async = AsyncMock()
                mock_runner.return_value = mock_runner_instance

                mock_session_instance = Mock()
                mock_session_instance.create_session = AsyncMock()
                mock_session.return_value = mock_session_instance

                agent = PolicyAwareLlmAgent(
                    api_key="test_key",
                    policy_dir=Path(tmpdir),
                )

                agent.runner = mock_runner_instance
                agent.session_service = mock_session_instance

                yield agent

    def test_agent_initialization_without_api_key(self, agent_without_api_key):
        """Test agent initializes without API key."""
        assert agent_without_api_key.api_key is None
        assert agent_without_api_key.llm_agent is None
        assert agent_without_api_key.runner is None
        assert agent_without_api_key.policy_engine is not None
        assert agent_without_api_key.safety_pipeline is not None

    def test_agent_initialization_with_api_key(self):
        """Test agent initializes with API key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('adh_cli.core.policy_aware_llm_agent.LlmAgent'), \
                 patch('adh_cli.core.policy_aware_llm_agent.Runner'), \
                 patch('adh_cli.core.policy_aware_llm_agent.InMemorySessionService'):

                agent = PolicyAwareLlmAgent(
                    api_key="test_key",
                    policy_dir=Path(tmpdir),
                )

                assert agent.api_key == "test_key"
                assert agent.llm_agent is not None
                assert agent.runner is not None

    def test_register_tool_without_api_key(self, agent_without_api_key):
        """Test tool registration without API key."""
        async def test_func(param: str):
            return f"Result: {param}"

        agent_without_api_key.register_tool(
            name="test_tool",
            description="A test tool",
            parameters={"param": {"type": "string"}},
            handler=test_func,
        )

        assert len(agent_without_api_key.tools) == 1
        assert "test_tool" in agent_without_api_key.tool_handlers

    def test_register_multiple_tools(self, agent_without_api_key):
        """Test registering multiple tools."""
        async def tool1():
            return "tool1"

        async def tool2():
            return "tool2"

        agent_without_api_key.register_tool(
            name="tool1",
            description="Tool 1",
            parameters={},
            handler=tool1,
        )

        agent_without_api_key.register_tool(
            name="tool2",
            description="Tool 2",
            parameters={},
            handler=tool2,
        )

        assert len(agent_without_api_key.tools) == 2
        assert "tool1" in agent_without_api_key.tool_handlers
        assert "tool2" in agent_without_api_key.tool_handlers

    @pytest.mark.asyncio
    async def test_chat_without_api_key(self, agent_without_api_key):
        """Test chat fails gracefully without API key."""
        result = await agent_without_api_key.chat("Hello")

        assert "not initialized" in result.lower() or "api key" in result.lower()

    @pytest.mark.asyncio
    async def test_chat_with_mocked_adk(self, agent_with_mock_adk):
        """Test chat with mocked ADK components."""
        # Mock event stream
        mock_event = Mock()
        mock_event.get_function_calls.return_value = []
        mock_event.get_function_responses.return_value = []
        mock_event.is_final_response.return_value = True

        mock_part = Mock()
        mock_part.text = "Hello! How can I help you?"
        mock_content = Mock()
        mock_content.parts = [mock_part]
        mock_event.content = mock_content

        # Setup async generator
        async def mock_event_stream(*args, **kwargs):
            yield mock_event

        agent_with_mock_adk.runner.run_async = mock_event_stream

        result = await agent_with_mock_adk.chat("Hello", context=ExecutionContext())

        assert "Hello" in result
        assert "help" in result

    @pytest.mark.asyncio
    async def test_chat_with_function_calls(self, agent_with_mock_adk):
        """Test chat handles function calls in event stream."""
        # Mock event stream with function calls
        mock_fc = Mock()
        mock_fc.name = "test_tool"

        mock_event1 = Mock()
        mock_event1.get_function_calls.return_value = [mock_fc]
        mock_event1.get_function_responses.return_value = []
        mock_event1.is_final_response.return_value = False
        mock_event1.content = None

        mock_event2 = Mock()
        mock_event2.get_function_calls.return_value = []
        mock_event2.get_function_responses.return_value = [Mock()]
        mock_event2.is_final_response.return_value = False
        mock_event2.content = None

        mock_event3 = Mock()
        mock_event3.get_function_calls.return_value = []
        mock_event3.get_function_responses.return_value = []
        mock_event3.is_final_response.return_value = True
        mock_part = Mock()
        mock_part.text = "Task completed"
        mock_content = Mock()
        mock_content.parts = [mock_part]
        mock_event3.content = mock_content

        async def mock_event_stream(*args, **kwargs):
            yield mock_event1
            yield mock_event2
            yield mock_event3

        agent_with_mock_adk.runner.run_async = mock_event_stream

        result = await agent_with_mock_adk.chat("Do something", context=ExecutionContext())

        assert "Task completed" in result
        # Note: Tool execution notifications removed - now handled by ToolExecutionWidget UI

    @pytest.mark.asyncio
    async def test_chat_handles_permission_error(self, agent_with_mock_adk):
        """Test chat handles PermissionError from policy."""
        async def mock_event_stream(*args, **kwargs):
            raise PermissionError("Tool blocked by policy")
            yield  # Never reached

        agent_with_mock_adk.runner.run_async = mock_event_stream

        result = await agent_with_mock_adk.chat("Do something dangerous")

        assert "blocked by policy" in result.lower()

    @pytest.mark.asyncio
    async def test_chat_handles_general_error(self, agent_with_mock_adk):
        """Test chat handles general exceptions."""
        async def mock_event_stream(*args, **kwargs):
            raise ValueError("Some error")
            yield  # Never reached

        agent_with_mock_adk.runner.run_async = mock_event_stream

        result = await agent_with_mock_adk.chat("Hello")

        assert "error" in result.lower()

    def test_audit_logger_creation_with_path(self):
        """Test audit logger is created when path provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = Path(tmpdir) / "audit.log"

            agent = PolicyAwareLlmAgent(
                api_key=None,
                audit_log_path=audit_path,
            )

            assert agent.audit_logger is not None

    def test_audit_logger_none_without_path(self, agent_without_api_key):
        """Test audit logger is None when no path provided."""
        assert agent_without_api_key.audit_logger is None

    @pytest.mark.asyncio
    async def test_audit_logging_writes_to_file(self):
        """Test audit logger actually writes to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = Path(tmpdir) / "audit.log"

            agent = PolicyAwareLlmAgent(
                api_key=None,
                audit_log_path=audit_path,
            )

            # Trigger audit log
            if agent.audit_logger:
                await agent.audit_logger(
                    tool_name="test_tool",
                    parameters={"param": "value"},
                    success=True
                )

            # Check file was created and has content
            assert audit_path.exists()
            content = audit_path.read_text()
            assert "test_tool" in content
            assert "param" in content

    def test_update_policies(self, agent_without_api_key):
        """Test updating policies."""
        # Register a tool first
        async def test_func():
            return "result"

        agent_without_api_key.register_tool(
            name="test_tool",
            description="Test",
            parameters={},
            handler=test_func,
        )

        # Update policies
        with tempfile.TemporaryDirectory() as new_tmpdir:
            agent_without_api_key.update_policies(Path(new_tmpdir))

            # Tool should still be registered
            assert "test_tool" in agent_without_api_key.tool_handlers

    def test_set_user_preferences(self, agent_without_api_key):
        """Test setting user preferences."""
        prefs = {"auto_approve": ["read_file"], "never_allow": ["rm"]}

        agent_without_api_key.set_user_preferences(prefs)

        assert "auto_approve" in agent_without_api_key.policy_engine.user_preferences
        assert "never_allow" in agent_without_api_key.policy_engine.user_preferences

    def test_tool_executor_property(self, agent_without_api_key):
        """Test tool_executor property for compatibility."""
        executor = agent_without_api_key.tool_executor

        assert executor is not None
        assert hasattr(executor, 'execute')

    @pytest.mark.asyncio
    async def test_tool_executor_execute(self, agent_without_api_key):
        """Test tool_executor.execute method."""
        async def test_func(param: str):
            return f"Result: {param}"

        agent_without_api_key.register_tool(
            name="test_tool",
            description="Test",
            parameters={},
            handler=test_func,
        )

        executor = agent_without_api_key.tool_executor
        result = await executor.execute(
            tool_name="test_tool",
            parameters={"param": "value"}
        )

        assert result.success is True
        assert "Result: value" in str(result.result)

    @pytest.mark.asyncio
    async def test_tool_executor_execute_not_found(self, agent_without_api_key):
        """Test tool_executor.execute with non-existent tool."""
        executor = agent_without_api_key.tool_executor
        result = await executor.execute(
            tool_name="nonexistent",
            parameters={}
        )

        assert result.success is False
        assert "not found" in result.error.lower()