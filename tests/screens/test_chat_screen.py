"""Tests for the chat screen."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, PropertyMock
from pathlib import Path

from adh_cli.screens.chat_screen import ChatScreen
from adh_cli.core.tool_executor import ExecutionContext


class TestChatScreen:
    """Test the ChatScreen class."""

    @pytest.fixture
    def screen(self):
        """Create a test screen instance."""
        # Create mock app before creating screen
        mock_app = Mock()
        mock_app.api_key = 'test_key'
        mock_app.agent = Mock()  # App now provides the agent

        # Patch the app property
        with patch.object(ChatScreen, 'app', new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            screen = ChatScreen()

            # Mock Textual components
            screen.query_one = Mock()
            screen.run_worker = Mock()
            screen.set_timer = Mock()
            screen.notify = Mock()

            yield screen

    def test_screen_initialization(self, screen):
        """Test screen initializes with default values."""
        assert screen.agent is None
        assert screen.chat_log is None
        assert screen.notifications == []
        assert screen.safety_enabled is True
        assert isinstance(screen.context, ExecutionContext)

    def test_on_mount(self, screen):
        """Test screen mount gets agent from app."""
        mock_log = Mock()
        mock_input = Mock()
        mock_input.focus = Mock()

        # Make query_one return the appropriate mock based on selector
        def query_side_effect(selector, widget_type=None):
            if "#chat-log" in selector:
                return mock_log
            elif "#chat-input" in selector:
                return mock_input
            return Mock()

        screen.query_one.side_effect = query_side_effect

        screen.on_mount()

        # Check agent was taken from app
        assert screen.agent == screen.app.agent
        assert screen.chat_log == mock_log

        # Check initial messages were written
        assert mock_log.write.call_count >= 2

        # Check input was focused
        mock_input.focus.assert_called_once()

    def test_on_input_submitted_empty(self, screen):
        """Test submitting empty input does nothing."""
        mock_input = Mock()
        mock_input.value = "  "  # Empty/whitespace
        screen.query_one.return_value = mock_input

        from textual.widgets import Input
        event = Mock(spec=Input.Submitted)

        screen.on_input_submitted(event)

        # Should not process empty message
        screen.run_worker.assert_not_called()

    def test_on_input_submitted_with_message(self, screen):
        """Test submitting a message."""
        mock_input = Mock()
        mock_input.value = "Test message"
        mock_log = Mock()

        def query_side_effect(selector, widget_type):
            if widget_type.__name__ == 'Input':
                return mock_input
            elif widget_type.__name__ == 'RichLog':
                return mock_log
            return Mock()

        screen.query_one.side_effect = query_side_effect
        screen.chat_log = mock_log
        screen.agent = Mock()

        # Mock run_worker to capture the coroutine without running it
        async_task = None
        def capture_worker(coro, **kwargs):
            nonlocal async_task
            async_task = coro
            # Return a mock to avoid the coroutine warning
            return Mock()

        screen.run_worker = Mock(side_effect=capture_worker)

        from textual.widgets import Input
        event = Mock(spec=Input.Submitted)

        screen.on_input_submitted(event)

        # Check input was cleared
        assert mock_input.value == ""

        # Check worker was started
        screen.run_worker.assert_called_once()

        # Close the coroutine to avoid warning
        if async_task:
            async_task.close()

    @pytest.mark.asyncio
    async def test_get_ai_response(self, screen):
        """Test getting AI response."""
        screen.agent = Mock()
        screen.agent.chat = AsyncMock(return_value="AI response")
        screen.chat_log = Mock()
        screen._add_message = Mock()

        mock_status = Mock()
        screen.query_one.return_value = mock_status

        await screen.get_ai_response("User message")

        # Check agent was called
        screen.agent.chat.assert_called_once_with(
            message="User message",
            context=screen.context
        )

        # Check response was displayed
        screen._add_message.assert_called_with("AI", "AI response", is_user=False)

    @pytest.mark.asyncio
    async def test_get_ai_response_error(self, screen):
        """Test handling errors in AI response."""
        screen.agent = Mock()
        screen.agent.chat = AsyncMock(side_effect=Exception("Test error"))
        screen.chat_log = Mock()

        mock_status = Mock()
        screen.query_one.return_value = mock_status

        await screen.get_ai_response("User message")

        # Check error was displayed
        screen.chat_log.write.assert_called()
        assert "Error" in str(screen.chat_log.write.call_args)

    @pytest.mark.asyncio
    async def test_handle_confirmation_approved(self, screen):
        """Test handling confirmation approval."""
        from adh_cli.policies.policy_types import ToolCall, PolicyDecision

        screen.app.push_screen_wait = AsyncMock(return_value=True)

        tool_call = ToolCall(tool_name="test", parameters={})
        decision = PolicyDecision(
            allowed=True,
            supervision_level="confirm",
            risk_level="medium"
        )

        result = await screen.handle_confirmation(
            tool_call=tool_call,
            decision=decision
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_handle_confirmation_declined(self, screen):
        """Test handling confirmation decline."""
        screen.app.push_screen_wait = AsyncMock(return_value=False)

        result = await screen.handle_confirmation()

        assert result is False

    @pytest.mark.asyncio
    async def test_show_notification(self, screen):
        """Test showing notifications."""
        mock_container = Mock()
        screen.query_one.return_value = mock_container

        await screen.show_notification("Test message", level="info")

        # Check notification was mounted
        mock_container.mount.assert_called_once()

        # Check timer was set for auto-remove
        screen.set_timer.assert_called_once()

    def test_add_message_user(self, screen):
        """Test adding user message."""
        mock_log = Mock()
        screen.chat_log = mock_log

        screen._add_message("User", "Test message", is_user=True)

        # Check message was written (might be called multiple times)
        mock_log.write.assert_called()

        # Check that the message content was written
        all_calls = [str(call[0][0]) for call in mock_log.write.call_args_list if call[0]]
        combined_text = " ".join(all_calls)

        # User messages should contain the speaker and message
        # The format is "[bold cyan]User:[/bold cyan] Test message"
        assert "Test message" in combined_text

    def test_add_message_ai(self, screen):
        """Test adding AI message with markdown."""
        mock_log = Mock()
        screen.chat_log = mock_log

        screen._add_message("AI", "**Bold** message", is_user=False)

        # Check message was written
        mock_log.write.assert_called()

    def test_action_clear_chat(self, screen):
        """Test clearing chat."""
        screen.chat_log = Mock()

        screen.action_clear_chat()

        screen.chat_log.clear.assert_called_once()
        screen.chat_log.write.assert_called_with("[dim]Chat cleared.[/dim]")

    def test_action_show_policies(self, screen):
        """Test showing policies."""
        screen.agent = Mock()
        screen.agent.policy_engine = Mock()
        screen.agent.policy_engine.user_preferences = {"test": "pref"}
        screen.agent.policy_engine.rules = [Mock(), Mock()]
        screen.chat_log = Mock()

        screen.action_show_policies()

        # Check policy info was displayed
        assert screen.chat_log.write.call_count >= 3

    def test_action_toggle_safety_disable(self, screen):
        """Test disabling safety."""
        screen.agent = Mock()
        screen.safety_enabled = True
        screen.chat_log = Mock()
        mock_status = Mock()
        screen.query_one.return_value = mock_status

        screen.action_toggle_safety()

        assert screen.safety_enabled is False
        screen.agent.policy_engine.user_preferences = {"auto_approve": ["*"]}
        screen.chat_log.write.assert_called()

    def test_action_toggle_safety_enable(self, screen):
        """Test enabling safety."""
        screen.agent = Mock()
        screen.safety_enabled = False
        screen.chat_log = Mock()
        mock_status = Mock()
        screen.query_one.return_value = mock_status

        screen.action_toggle_safety()

        assert screen.safety_enabled is True
        screen.agent.policy_engine.user_preferences = {}
        screen.chat_log.write.assert_called()