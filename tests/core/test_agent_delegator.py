"""Tests for AgentDelegator and agent delegation infrastructure."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import tempfile

from adh_cli.core.agent_delegator import AgentDelegator, AgentResponse
from adh_cli.tools.agent_tools import create_delegate_tool


class TestAgentResponse:
    """Test AgentResponse dataclass."""

    def test_successful_response(self):
        """Test creating a successful response."""
        response = AgentResponse(
            agent_name="planner",
            task_type="planning",
            result="Detailed plan here",
            metadata={"context": "test"},
            success=True
        )
        assert response.agent_name == "planner"
        assert response.task_type == "planning"
        assert response.result == "Detailed plan here"
        assert response.success is True
        assert response.error is None

    def test_failed_response(self):
        """Test creating a failed response."""
        response = AgentResponse(
            agent_name="planner",
            task_type="planning",
            result="",
            metadata={},
            success=False,
            error="Agent not found"
        )
        assert response.success is False
        assert response.error == "Agent not found"


class TestAgentDelegator:
    """Test AgentDelegator class."""

    @pytest.fixture
    def delegator(self):
        """Create delegator for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            delegator = AgentDelegator(
                api_key="test_api_key",
                policy_dir=Path(tmpdir),
                audit_log_path=Path(tmpdir) / "audit.log"
            )
            yield delegator

    def test_initialization(self, delegator):
        """Test delegator initialization."""
        assert delegator.api_key == "test_api_key"
        assert delegator._agent_cache == {}

    def test_task_type_inference(self, delegator):
        """Test task type inference from agent name."""
        assert delegator._infer_task_type("planner") == "planning"
        assert delegator._infer_task_type("code_reviewer") == "code_review"
        assert delegator._infer_task_type("researcher") == "research"
        assert delegator._infer_task_type("tester") == "testing"
        assert delegator._infer_task_type("unknown") == "general"

    @pytest.mark.asyncio
    async def test_delegation_success(self, delegator):
        """Test successful delegation to an agent."""
        with patch('adh_cli.core.agent_delegator.PolicyAwareLlmAgent') as mock_agent_class:
            # Setup mock agent
            mock_agent = Mock()
            mock_agent.chat = AsyncMock(return_value="This is the plan")
            mock_agent_class.return_value = mock_agent

            # Delegate task
            response = await delegator.delegate(
                agent_name="planner",
                task="Create a plan for feature X"
            )

            # Verify response
            assert response.success is True
            assert response.agent_name == "planner"
            assert response.task_type == "planning"
            assert response.result == "This is the plan"
            assert response.error is None

            # Verify agent was created with correct params
            mock_agent_class.assert_called_once()
            call_kwargs = mock_agent_class.call_args.kwargs
            assert call_kwargs["agent_name"] == "planner"
            assert call_kwargs["api_key"] == "test_api_key"

            # Verify chat was called
            mock_agent.chat.assert_called_once_with("Create a plan for feature X", context=None)

    @pytest.mark.asyncio
    async def test_delegation_with_context(self, delegator):
        """Test delegation with context parameters."""
        with patch('adh_cli.core.agent_delegator.PolicyAwareLlmAgent') as mock_agent_class:
            mock_agent = Mock()
            mock_agent.chat = AsyncMock(return_value="Plan with context")
            mock_agent_class.return_value = mock_agent

            context = {
                "user_id": "test_user",
                "working_dir": "/test/path",
                "requirements": "Must be fast"
            }

            response = await delegator.delegate(
                agent_name="planner",
                task="Plan feature",
                context=context
            )

            assert response.success is True
            assert response.metadata == context

            # Verify context was passed to chat
            mock_agent.chat.assert_called_once()
            call_args = mock_agent.chat.call_args
            exec_context = call_args.kwargs["context"]
            assert exec_context.user_id == "test_user"
            assert exec_context.metadata == context
            assert exec_context.metadata["working_dir"] == "/test/path"

    @pytest.mark.asyncio
    async def test_delegation_failure(self, delegator):
        """Test delegation when agent fails."""
        with patch('adh_cli.core.agent_delegator.PolicyAwareLlmAgent') as mock_agent_class:
            # Make agent initialization fail
            mock_agent_class.side_effect = Exception("Agent not found")

            response = await delegator.delegate(
                agent_name="nonexistent",
                task="Do something"
            )

            assert response.success is False
            assert response.error == "Agent not found"
            assert response.result == ""

    @pytest.mark.asyncio
    async def test_agent_caching(self, delegator):
        """Test that agents are cached after first use."""
        with patch('adh_cli.core.agent_delegator.PolicyAwareLlmAgent') as mock_agent_class:
            mock_agent = Mock()
            mock_agent.chat = AsyncMock(return_value="Result")
            mock_agent_class.return_value = mock_agent

            # First delegation
            await delegator.delegate(agent_name="planner", task="Task 1")
            assert "planner" in delegator._agent_cache

            # Second delegation - should use cached agent
            await delegator.delegate(agent_name="planner", task="Task 2")

            # Agent should only be created once
            assert mock_agent_class.call_count == 1

            # But chat should be called twice
            assert mock_agent.chat.call_count == 2

    @pytest.mark.asyncio
    async def test_register_agent_tools(self, delegator):
        """Test that appropriate tools are registered for agents."""
        with patch('adh_cli.core.agent_delegator.PolicyAwareLlmAgent') as mock_agent_class:
            mock_agent = Mock()
            mock_agent.chat = AsyncMock(return_value="Result")
            mock_agent.register_tool = Mock()
            mock_agent_class.return_value = mock_agent

            await delegator.delegate(agent_name="planner", task="Task")

            # Verify read-only tools were registered
            assert mock_agent.register_tool.call_count == 3  # read_file, list_directory, get_file_info
            tool_names = [call.kwargs["name"] for call in mock_agent.register_tool.call_args_list]
            assert "read_file" in tool_names
            assert "list_directory" in tool_names
            assert "get_file_info" in tool_names

    def test_clear_cache(self, delegator):
        """Test clearing the agent cache."""
        delegator._agent_cache = {"planner": Mock(), "reviewer": Mock()}
        assert len(delegator._agent_cache) == 2

        delegator.clear_cache()
        assert len(delegator._agent_cache) == 0

    def test_get_cached_agents(self, delegator):
        """Test retrieving list of cached agents."""
        assert delegator.get_cached_agents() == []

        delegator._agent_cache = {"planner": Mock(), "reviewer": Mock()}
        cached = delegator.get_cached_agents()
        assert set(cached) == {"planner", "reviewer"}


class TestDelegateToolCreation:
    """Test delegate_to_agent tool creation."""

    @pytest.mark.asyncio
    async def test_create_delegate_tool_success(self):
        """Test creating and using delegate_to_agent tool."""
        mock_delegator = Mock()
        mock_delegator.delegate = AsyncMock(return_value=AgentResponse(
            agent_name="planner",
            task_type="planning",
            result="Detailed plan",
            metadata={},
            success=True
        ))

        delegate_tool = create_delegate_tool(mock_delegator)

        result = await delegate_tool(
            agent="planner",
            task="Create plan",
            context={"working_dir": "."}
        )

        assert result == "Detailed plan"
        mock_delegator.delegate.assert_called_once_with(
            agent_name="planner",
            task="Create plan",
            context={"working_dir": "."}
        )

    @pytest.mark.asyncio
    async def test_create_delegate_tool_failure(self):
        """Test delegate_to_agent tool with failed delegation."""
        mock_delegator = Mock()
        mock_delegator.delegate = AsyncMock(return_value=AgentResponse(
            agent_name="planner",
            task_type="planning",
            result="",
            metadata={},
            success=False,
            error="Connection timeout"
        ))

        delegate_tool = create_delegate_tool(mock_delegator)

        result = await delegate_tool(agent="planner", task="Create plan")

        assert "⚠️ Delegation to planner failed" in result
        assert "Connection timeout" in result

    @pytest.mark.asyncio
    async def test_create_delegate_tool_no_context(self):
        """Test delegate_to_agent tool without context."""
        mock_delegator = Mock()
        mock_delegator.delegate = AsyncMock(return_value=AgentResponse(
            agent_name="planner",
            task_type="planning",
            result="Plan",
            metadata={},
            success=True
        ))

        delegate_tool = create_delegate_tool(mock_delegator)

        await delegate_tool(agent="planner", task="Task")

        # Should pass empty dict if context not provided
        mock_delegator.delegate.assert_called_once()
        call_kwargs = mock_delegator.delegate.call_args.kwargs
        assert call_kwargs["context"] == {}
