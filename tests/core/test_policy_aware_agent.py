"""Tests for the PolicyAwareAgent class."""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import tempfile

from adh_cli.core.policy_aware_agent import PolicyAwareAgent
from adh_cli.core.tool_executor import ExecutionContext, ExecutionResult
from adh_cli.policies.policy_types import (
    PolicyDecision,
    SupervisionLevel,
    RiskLevel,
)


class TestPolicyAwareAgent:
    """Test the PolicyAwareAgent class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_genai_client(self):
        """Mock the Gemini API client."""
        with patch("adh_cli.core.policy_aware_agent.genai") as mock_genai:
            mock_client = Mock()
            mock_genai.Client.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def agent(self, temp_dir, mock_genai_client):
        """Create a PolicyAwareAgent for testing."""
        agent = PolicyAwareAgent(
            model_name="test-model",
            api_key="test-key",
            policy_dir=temp_dir,
            audit_log_path=temp_dir / "audit.log",
        )
        return agent

    def test_agent_initialization(self, agent):
        """Test that agent initializes correctly."""
        assert agent.model_name == "test-model"
        assert agent.api_key == "test-key"
        assert agent.policy_engine is not None
        assert agent.safety_pipeline is not None
        assert agent.tool_executor is not None
        assert len(agent.tool_definitions) == 0
        assert len(agent.tool_handlers) == 0

    def test_register_tool(self, agent):
        """Test registering a tool with the agent."""
        # Register a test tool
        async def test_handler(param1: str):
            return f"Result: {param1}"

        agent.register_tool(
            name="test_tool",
            description="A test tool",
            parameters={
                "param1": {"type": "string", "description": "Test parameter"},
            },
            handler=test_handler,
        )

        # Check tool is registered
        assert "test_tool" in agent.tool_handlers
        assert agent.tool_handlers["test_tool"] == test_handler
        assert len(agent.tool_definitions) == 1

    @pytest.mark.asyncio
    async def test_chat_without_tools(self, agent, mock_genai_client):
        """Test chat without tool calls."""
        # Mock Gemini response - ensure part doesn't have function_call attribute
        mock_part = Mock(spec=['text'])
        mock_part.text = "Hello! How can I help you?"

        mock_response = Mock()
        mock_response.candidates = [
            Mock(
                content=Mock(
                    parts=[mock_part]
                )
            )
        ]
        mock_genai_client.models.generate_content.return_value = mock_response

        # Send chat message
        response = await agent.chat("Hello")

        assert response == "Hello! How can I help you?"
        mock_genai_client.models.generate_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_with_tool_call(self, agent, mock_genai_client):
        """Test chat with tool execution."""
        # Register a test tool
        async def test_tool(param: str):
            return f"Tool result: {param}"

        agent.register_tool(
            name="test_tool",
            description="Test tool",
            parameters={"param": {"type": "string"}},
            handler=test_tool,
        )

        # Mock Gemini response with function call
        mock_function_call = Mock()
        mock_function_call.name = "test_tool"
        mock_function_call.args = '{"param": "test_value"}'  # Make sure args is a string

        mock_part_with_tool = Mock(spec=['function_call'])
        mock_part_with_tool.function_call = mock_function_call

        mock_response_with_tool = Mock()
        mock_response_with_tool.candidates = [
            Mock(
                content=Mock(
                    parts=[mock_part_with_tool]
                )
            )
        ]

        # Mock follow-up response after tool execution
        mock_part_final = Mock(spec=['text'])
        mock_part_final.text = "I used the tool and got the result."

        mock_response_final = Mock()
        mock_response_final.candidates = [
            Mock(
                content=Mock(
                    parts=[mock_part_final]
                )
            )
        ]

        # Set up side effects for multiple calls
        mock_genai_client.models.generate_content.side_effect = [
            mock_response_with_tool,
            mock_response_final,
        ]

        # Send chat message
        response = await agent.chat("Use the test tool")

        assert response == "I used the tool and got the result."
        assert mock_genai_client.models.generate_content.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_with_policies(self, agent):
        """Test direct tool execution with policies."""
        # Register a test tool
        async def test_tool(param: str):
            return f"Result: {param}"

        agent.tool_executor.register_tool("test_tool", test_tool)

        # Execute tool
        result = await agent.execute_with_policies(
            tool_name="test_tool",
            parameters={"param": "test"},
        )

        assert result.success is True
        assert result.result == "Result: test"
        assert result.policy_decision is not None

    @pytest.mark.asyncio
    async def test_execute_with_context(self, agent):
        """Test tool execution with context."""
        # Register a test tool
        async def test_tool():
            return "Result"

        agent.tool_executor.register_tool("test_tool", test_tool)

        # Create context
        context = ExecutionContext(
            user_id="user123",
            session_id="session456",
            agent_name="TestAgent",
        )

        # Execute tool
        result = await agent.execute_with_policies(
            tool_name="test_tool",
            parameters={},
            context=context,
        )

        assert result.success is True
        assert result.result == "Result"

    def test_update_policies(self, agent, temp_dir):
        """Test updating policies from a new directory."""
        new_policy_dir = temp_dir / "new_policies"
        new_policy_dir.mkdir()

        # Update policies
        agent.update_policies(new_policy_dir)

        assert agent.policy_engine.policy_dir == new_policy_dir
        assert agent.tool_executor.policy_engine.policy_dir == new_policy_dir

    def test_set_user_preferences(self, agent):
        """Test setting user preferences."""
        preferences = {
            "auto_approve": ["read_*"],
            "never_allow": ["delete_*"],
        }

        agent.set_user_preferences(preferences)

        assert agent.policy_engine.user_preferences == preferences

    @pytest.mark.asyncio
    async def test_handle_supervision_notify(self, agent):
        """Test handling NOTIFY supervision level."""
        # Mock notification handler
        agent.notification_handler = AsyncMock()

        # Create result with NOTIFY supervision
        result = ExecutionResult(
            success=True,
            result="Test",
            policy_decision=PolicyDecision(
                allowed=True,
                supervision_level=SupervisionLevel.NOTIFY,
                risk_level=RiskLevel.LOW,
            ),
        )

        # Handle supervision
        await agent._handle_supervision(result)

        agent.notification_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_supervision_manual(self, agent):
        """Test handling MANUAL supervision level."""
        # Mock notification handler
        agent.notification_handler = AsyncMock()

        # Create result with MANUAL supervision
        result = ExecutionResult(
            success=True,
            result="Test",
            policy_decision=PolicyDecision(
                allowed=True,
                supervision_level=SupervisionLevel.MANUAL,
                risk_level=RiskLevel.HIGH,
            ),
        )

        # Handle supervision
        await agent._handle_supervision(result)

        agent.notification_handler.assert_called_once()
        call_args = agent.notification_handler.call_args
        assert "Manual review" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_audit_logging(self, agent, temp_dir):
        """Test that audit logging works correctly."""
        # Register a test tool
        async def test_tool():
            return "Result"

        agent.tool_executor.register_tool("test_tool", test_tool)

        # Execute tool
        await agent.execute_with_policies(
            tool_name="test_tool",
            parameters={},
        )

        # Check audit log was created
        audit_log = temp_dir / "audit.log"
        assert audit_log.exists()

        # Read and verify log contents
        with open(audit_log, "r") as f:
            lines = f.readlines()

        assert len(lines) > 0
        for line in lines:
            event = json.loads(line)
            assert "timestamp" in event
            assert "event_type" in event
            assert "tool_name" in event

    @pytest.mark.asyncio
    async def test_execute_tool_call_with_confirmation(self, agent):
        """Test executing a tool call that requires confirmation."""
        # Mock confirmation handler
        agent.confirmation_handler = AsyncMock(return_value=True)

        # Mock policy decision to require confirmation
        agent.tool_executor.policy_engine.evaluate_tool_call = Mock(
            return_value=PolicyDecision(
                allowed=True,
                supervision_level=SupervisionLevel.CONFIRM,
                risk_level=RiskLevel.MEDIUM,
                requires_confirmation=True,
                confirmation_message="Confirm?",
            )
        )

        # Register a test tool
        async def test_tool():
            return "Executed"

        agent.tool_executor.register_tool("test_tool", test_tool)

        # Create mock function call
        function_call = Mock()
        function_call.name = "test_tool"
        function_call.args = "{}"

        # Execute tool call
        result = await agent._execute_tool_call(
            function_call,
            ExecutionContext(),
        )

        assert result["success"] is True
        assert result["result"] == "Executed"

    @pytest.mark.asyncio
    async def test_execute_tool_call_denied(self, agent):
        """Test executing a tool call that is denied by policy."""
        # Mock policy decision to deny
        agent.tool_executor.policy_engine.evaluate_tool_call = Mock(
            return_value=PolicyDecision(
                allowed=False,
                supervision_level=SupervisionLevel.DENY,
                risk_level=RiskLevel.CRITICAL,
                reason="Denied by policy",
            )
        )

        # Create mock function call
        function_call = Mock()
        function_call.name = "denied_tool"
        function_call.args = "{}"

        # Execute tool call
        result = await agent._execute_tool_call(
            function_call,
            ExecutionContext(),
        )

        assert result["success"] is False
        assert "denied by policy" in result["error"].lower()

    def test_create_audit_logger_no_path(self, agent):
        """Test creating audit logger with no path."""
        logger = agent._create_audit_logger(None)
        assert logger is None

    @pytest.mark.asyncio
    async def test_chat_with_history(self, agent, mock_genai_client):
        """Test chat with conversation history."""
        # Mock Gemini response - ensure part doesn't have function_call attribute
        mock_part = Mock(spec=['text'])
        mock_part.text = "Response with context"

        mock_response = Mock()
        mock_response.candidates = [
            Mock(
                content=Mock(
                    parts=[mock_part]
                )
            )
        ]
        mock_genai_client.models.generate_content.return_value = mock_response

        # Send chat message with history
        history = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"},
        ]

        response = await agent.chat("New message", history=history)

        assert response == "Response with context"

        # Verify history was included in the call
        call_args = mock_genai_client.models.generate_content.call_args
        contents = call_args[1]["contents"]
        assert len(contents) == 3  # History + new message