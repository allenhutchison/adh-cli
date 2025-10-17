"""Tests for chat widgets."""

from adh_cli.ui.chat_widgets import AIMessage, ToolMessage, UserMessage


class TestToolMessage:
    """Test ToolMessage widget."""

    def test_tool_message_shows_contextual_info_for_execute_command(self):
        """Test ToolMessage displays command in title for execute_command."""
        widget = ToolMessage(
            tool_name="execute_command",
            content="Executing command...",
            status="executing",
            parameters={"command": "pytest tests/"},
        )

        # Title should include the command
        assert "execute_command" in widget.message_title
        assert "pytest tests/" in widget.message_title

    def test_tool_message_shows_contextual_info_for_write_file(self):
        """Test ToolMessage displays file path in title for write_file."""
        widget = ToolMessage(
            tool_name="write_file",
            content="Writing file...",
            status="executing",
            parameters={"file_path": "config.yaml", "content": "test"},
        )

        # Title should include the file path
        assert "write_file" in widget.message_title
        assert "config.yaml" in widget.message_title

    def test_tool_message_shows_contextual_info_for_delegate_to_agent(self):
        """Test ToolMessage displays agent and task in title for delegate_to_agent."""
        widget = ToolMessage(
            tool_name="delegate_to_agent",
            content="Delegating to agent...",
            status="executing",
            parameters={"agent": "tester", "task": "Run all tests"},
        )

        # Title should include the agent and task
        assert "delegate_to_agent" in widget.message_title
        assert "→ tester" in widget.message_title
        assert "Run all tests" in widget.message_title

    def test_tool_message_shows_agent_name_for_delegated_execution(self):
        """Test ToolMessage displays agent name when tool executed by delegated agent."""
        widget = ToolMessage(
            tool_name="read_file",
            content="Reading file...",
            status="executing",
            agent_name="code_reviewer",
            parameters={"file_path": "test.py"},
        )

        # Title should include agent name and file path
        assert "read_file" in widget.message_title
        assert "test.py" in widget.message_title
        assert "(via code_reviewer)" in widget.message_title

    def test_tool_message_without_parameters_shows_basic_title(self):
        """Test ToolMessage shows basic title when no parameters provided."""
        widget = ToolMessage(
            tool_name="some_tool",
            content="Executing...",
            status="executing",
        )

        # Title should only include tool name
        assert "some_tool" in widget.message_title
        # Should not have contextual info
        assert ":" not in widget.message_title.split("Tool:")[1].split("(via")[0]

    def test_tool_message_stores_parameters(self):
        """Test ToolMessage stores parameters for later use."""
        widget = ToolMessage(
            tool_name="execute_command",
            content="Executing...",
            status="executing",
            parameters={"command": "pytest tests/"},
        )

        # Widget should store the parameters
        assert widget.parameters == {"command": "pytest tests/"}


class TestAIMessage:
    """Test AIMessage widget."""

    def test_ai_message_initialization(self):
        """Test AIMessage initializes correctly."""
        widget = AIMessage(content="Hello, I'm the AI assistant.")

        assert widget.message_content == "Hello, I'm the AI assistant."
        assert "AI Response" in widget.message_title

    def test_ai_message_with_empty_content(self):
        """Test AIMessage handles empty content."""
        widget = AIMessage(content="")

        assert widget.message_content == ""


class TestUserMessage:
    """Test UserMessage widget."""

    def test_user_message_initialization(self):
        """Test UserMessage initializes correctly."""
        widget = UserMessage(content="Hello, AI!")

        assert widget.message_content == "Hello, AI!"

    def test_user_message_with_empty_content(self):
        """Test UserMessage handles empty content."""
        widget = UserMessage(content="")

        assert widget.message_content == ""
