"""Unit tests for the chat screen."""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from textual.app import App
from textual.widgets import Input, RichLog, Static
from rich.table import Table
from rich.markdown import Markdown
from rich.text import Text

from adh_cli.screens.chat_screen import ChatScreen
from adh_cli.services.clipboard_service import ClipboardService


class TestChatScreen:
    """Test cases for the ChatScreen class."""

    @pytest.mark.asyncio
    async def test_chat_screen_initialization(self):
        """Test that chat screen initializes correctly."""
        screen = ChatScreen()

        assert screen.adk_service is None
        assert screen.chat_log is None
        assert screen.command_mode is False

    @pytest.mark.asyncio
    async def test_chat_screen_compose(self):
        """Test that chat screen composes widgets correctly."""
        screen = ChatScreen()

        # Get composed widgets
        app = App()
        async with app.run_test() as pilot:
            await app.push_screen(screen)
            await pilot.pause()

            # Should have status line
            status_line = screen.query_one("#status-line", Static)
            assert status_line is not None

            # Should have chat log
            chat_log = screen.query_one("#chat-log", RichLog)
            assert chat_log is not None

            # Should have input field
            chat_input = screen.query_one("#chat-input", Input)
            assert chat_input is not None

    @patch('adh_cli.screens.chat_screen.ADKService')
    @pytest.mark.asyncio
    async def test_on_mount_with_valid_api_key(self, mock_adk_service):
        """Test on_mount with valid API key."""
        mock_service = Mock()
        mock_adk_service.return_value = mock_service

        screen = ChatScreen()

        app = App()
        async with app.run_test() as pilot:
            await app.push_screen(screen)
            await pilot.pause()

            # ADK service should be initialized
            assert screen.adk_service == mock_service
            mock_adk_service.assert_called_once_with(enable_tools=True)

            # Chat log should be set
            assert screen.chat_log is not None

    @patch('adh_cli.screens.chat_screen.ADKService')
    @pytest.mark.asyncio
    async def test_on_mount_without_api_key(self, mock_adk_service):
        """Test on_mount without API key."""
        mock_adk_service.side_effect = ValueError("No API key")

        screen = ChatScreen()

        app = App()
        async with app.run_test() as pilot:
            await app.push_screen(screen)
            await pilot.pause()

            # Service should not be initialized
            assert screen.adk_service is None

            # Error should be displayed in chat log
            chat_log = screen.query_one("#chat-log", RichLog)
            assert chat_log is not None

    def test_add_message_user(self):
        """Test _add_message for user messages."""
        screen = ChatScreen()
        screen.chat_log = Mock()

        screen._add_message("You", "Hello AI", is_user=True)

        # Should create a table with user styling
        screen.chat_log.write.assert_called()
        call_args = screen.chat_log.write.call_args_list[0][0][0]
        assert isinstance(call_args, Table)

    def test_add_message_ai_plain(self):
        """Test _add_message for plain AI messages."""
        screen = ChatScreen()
        screen.chat_log = Mock()

        screen._add_message("AI", "Hello user", is_user=False)

        # Should create a table with AI styling
        screen.chat_log.write.assert_called()
        call_args = screen.chat_log.write.call_args_list[0][0][0]
        assert isinstance(call_args, Table)

    def test_add_message_ai_markdown(self):
        """Test _add_message for AI messages with markdown."""
        screen = ChatScreen()
        screen.chat_log = Mock()

        message = "Here's some **bold** text and a list:\n- Item 1\n- Item 2"
        screen._add_message("AI", message, is_user=False)

        # Should create a table with markdown content
        screen.chat_log.write.assert_called()
        call_args = screen.chat_log.write.call_args_list[0][0][0]
        assert isinstance(call_args, Table)

    @patch('adh_cli.screens.chat_screen.ADKService')
    @pytest.mark.asyncio
    async def test_on_input_submitted(self, mock_adk_service):
        """Test handling input submission."""
        mock_service = Mock()
        mock_service.send_message_streaming.return_value = "AI response"
        mock_adk_service.return_value = mock_service

        screen = ChatScreen()

        app = App()
        async with app.run_test() as pilot:
            await app.push_screen(screen)
            await pilot.pause()

            # Type and submit a message
            input_widget = screen.query_one("#chat-input", Input)
            input_widget.value = "Test message"

            # Trigger submission
            await pilot.press("enter")
            await pilot.pause()

            # Input should be cleared
            assert input_widget.value == ""

    def test_action_clear_chat(self):
        """Test clearing the chat."""
        screen = ChatScreen()
        screen.chat_log = Mock()
        screen.adk_service = Mock()

        screen.action_clear_chat()

        # Chat log should be cleared
        screen.chat_log.clear.assert_called_once()
        screen.chat_log.write.assert_called()

        # Chat session should be restarted
        screen.adk_service.start_chat.assert_called_once()

    def test_action_toggle_command_mode(self):
        """Test toggling command mode."""
        screen = ChatScreen()
        screen.command_mode = False

        # Create mock widgets
        status_line = Mock()
        input_widget = Mock()
        screen.query_one = Mock(side_effect=lambda id, type: {
            "#status-line": status_line,
            "#chat-input": input_widget
        }.get(id.split(",")[0]))

        # Toggle to command mode
        screen.action_toggle_command_mode()

        assert screen.command_mode is True
        status_line.add_class.assert_called_with("command-mode")
        input_widget.blur.assert_called_once()

        # Toggle back to input mode
        screen.action_toggle_command_mode()

        assert screen.command_mode is False
        status_line.remove_class.assert_called_with("command-mode")
        input_widget.focus.assert_called_once()

    @patch.object(ClipboardService, 'copy_to_clipboard')
    def test_action_copy_chat(self, mock_copy):
        """Test copying chat to clipboard."""
        mock_copy.return_value = (True, "Success")

        screen = ChatScreen()
        screen.chat_log = Mock()

        # Mock chat log lines
        mock_line1 = Mock()
        mock_line1.text = "You: Hello"
        mock_line2 = Mock()
        mock_line2.text = "AI: Hi there"
        screen.chat_log.lines = [mock_line1, mock_line2]

        screen.action_copy_chat()

        # Clipboard service should be called with chat content
        mock_copy.assert_called_once()
        copied_text = mock_copy.call_args[0][0]
        assert "You: Hello" in copied_text
        assert "AI: Hi there" in copied_text

    @patch('builtins.open', create=True)
    @patch.object(ClipboardService, 'copy_to_clipboard')
    def test_action_export_chat(self, mock_copy, mock_open):
        """Test exporting chat to file."""
        mock_copy.return_value = (True, "Success")
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        screen = ChatScreen()
        screen.chat_log = Mock()

        # Mock chat log lines
        mock_line = Mock()
        mock_line.text = "Chat content"
        screen.chat_log.lines = [mock_line]

        screen.action_export_chat()

        # File should be opened for writing
        mock_open.assert_called_once_with("chat_export.txt", "w")
        mock_file.write.assert_called()

        # Clipboard should also be called
        mock_copy.assert_called_once()

    def test_on_key_command_mode(self):
        """Test keyboard handling in command mode."""
        screen = ChatScreen()
        screen.command_mode = True
        screen.action_clear_chat = Mock()
        screen.action_export_chat = Mock()
        screen.action_copy_chat = Mock()

        # Test 'c' for clear
        event = Mock()
        event.key = "c"
        screen.on_key(event)
        screen.action_clear_chat.assert_called_once()

        # Test 'e' for export
        event.key = "e"
        screen.on_key(event)
        screen.action_export_chat.assert_called_once()

        # Test 'y' for yank/copy
        event.key = "y"
        screen.on_key(event)
        screen.action_copy_chat.assert_called_once()

    def test_on_key_input_mode(self):
        """Test keyboard handling in input mode."""
        screen = ChatScreen()
        screen.command_mode = False

        # Mock methods shouldn't be called
        screen.action_clear_chat = Mock()
        screen.action_export_chat = Mock()

        event = Mock()
        event.key = "c"
        screen.on_key(event)

        # Should not trigger actions in input mode
        screen.action_clear_chat.assert_not_called()
        screen.action_export_chat.assert_not_called()


class TestChatScreenIntegration:
    """Integration tests for chat screen."""

    @pytest.mark.asyncio
    @patch('adh_cli.screens.chat_screen.ADKService')
    async def test_full_chat_flow(self, mock_adk_service):
        """Test a complete chat interaction flow."""
        mock_service = Mock()
        mock_service.send_message_streaming.return_value = "AI response"
        mock_adk_service.return_value = mock_service

        screen = ChatScreen()

        app = App()
        async with app.run_test() as pilot:
            await app.push_screen(screen)
            await pilot.pause()

            # Send a message
            input_widget = screen.query_one("#chat-input", Input)
            input_widget.value = "Hello AI"
            await pilot.press("enter")
            await pilot.pause()

            # Toggle command mode
            await pilot.press("escape")
            assert screen.command_mode is True

            # Clear chat
            await pilot.press("c")
            await pilot.pause()

            # Return to input mode
            await pilot.press("escape")
            assert screen.command_mode is False