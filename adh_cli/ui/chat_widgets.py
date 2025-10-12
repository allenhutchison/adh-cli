"""Custom widgets for chat messages with copy functionality."""

import pyperclip
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Collapsible, Static
from rich.markdown import Markdown
from rich.text import Text


class CopyableMessage(Vertical):
    """A collapsible message with a copy button."""

    DEFAULT_CSS = """
    CopyableMessage {
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
        border: solid $border;
        background: $surface;
    }

    CopyableMessage.ai-message {
        border: solid $accent;
    }

    CopyableMessage.tool-message {
        border: solid $warning;
    }

    CopyableMessage .message-header {
        layout: horizontal;
        width: 100%;
        height: auto;
        padding: 0 1;
        background: $boost;
    }

    CopyableMessage .message-title {
        width: 1fr;
        content-align: left middle;
        padding: 0 1;
    }

    CopyableMessage .copy-button {
        min-width: 10;
        height: auto;
        padding: 0 1;
        margin: 0;
    }

    CopyableMessage Collapsible {
        width: 100%;
        border: none;
        background: $surface;
    }

    CopyableMessage .message-content {
        width: 100%;
        padding: 1 2;
    }
    """

    def __init__(
        self,
        title: str,
        content: str,
        message_type: str = "ai",
        collapsed: bool = False,
        **kwargs,
    ):
        """Initialize a copyable message.

        Args:
            title: Title for the collapsible
            content: Message content
            message_type: Type of message (ai, tool, user)
            collapsed: Whether to start collapsed
            **kwargs: Additional arguments
        """
        # Add the message type as a class
        if "classes" in kwargs:
            kwargs["classes"] = f"{kwargs['classes']} {message_type}-message"
        else:
            kwargs["classes"] = f"{message_type}-message"

        super().__init__(**kwargs)
        self.message_title = str(title) if title is not None else ""
        self.message_content = str(content) if content is not None else ""
        self.message_type = message_type
        self.start_collapsed = collapsed

    def compose(self) -> ComposeResult:
        """Compose the message widget."""
        # Header with title and copy button (always visible)
        with Horizontal(classes="message-header"):
            yield Static(self.message_title, classes="message-title")
            yield Button("📋 Copy", classes="copy-button", variant="primary")

        # Collapsible content
        with Collapsible(title="", collapsed=self.start_collapsed):
            yield from self.compose_content()

    def compose_content(self) -> ComposeResult:
        """Compose the content inside the collapsible.

        Subclasses can override this to customize content rendering.

        Returns:
            Content widgets
        """
        yield Static(self.message_content, classes="message-content", markup=False)

    @on(Button.Pressed, ".copy-button")
    def copy_message(self, event: Button.Pressed) -> None:
        """Handle copy button press."""
        event.stop()  # Prevent event from bubbling
        try:
            pyperclip.copy(self.message_content)
            self.app.notify("Message copied to clipboard", title="Success")
        except pyperclip.PyperclipException as e:
            self.app.notify(f"Failed to copy: {e}", title="Error", severity="error")


class AIMessage(CopyableMessage):
    """Collapsible AI message with markdown rendering and copy button."""

    DEFAULT_CSS = """
    AIMessage .message-content {
        padding: 1 2;
    }
    """

    def __init__(
        self,
        content: str,
        collapsed: bool = False,
        **kwargs,
    ):
        """Initialize an AI message.

        Args:
            content: AI message content (markdown)
            collapsed: Whether to start collapsed
            **kwargs: Additional arguments
        """
        # Ensure content is a string
        content_str = str(content) if content is not None else ""
        super().__init__(
            title="🤖 AI Response",
            content=content_str,
            message_type="ai",
            collapsed=collapsed,
            **kwargs,
        )

    def compose_content(self) -> ComposeResult:
        """Compose the AI message content with markdown rendering.

        Returns:
            Content widgets with markdown rendered
        """
        try:
            content_widget = Static(classes="message-content", markup=False)
            content_widget.update(Markdown(self.message_content))
            yield content_widget
        except Exception:
            # Fallback to plain text without markup
            yield Static(self.message_content, classes="message-content", markup=False)


class ToolMessage(CopyableMessage):
    """Collapsible tool execution message with copy button."""

    DEFAULT_CSS = """
    ToolMessage .message-content {
        padding: 1 2;
    }

    ToolMessage .tool-info {
        color: $text-muted;
    }
    """

    def __init__(
        self,
        tool_name: str,
        content: str,
        status: str = "success",
        collapsed: bool = False,
        agent_name: str = None,
        **kwargs,
    ):
        """Initialize a tool message.

        Args:
            tool_name: Name of the tool
            content: Tool execution details
            status: Execution status
            collapsed: Whether to start collapsed
            agent_name: Name of the agent that executed this tool (for delegation)
            **kwargs: Additional arguments
        """
        # Create title with tool name and status
        status_icons = {
            "pending": "⏳",
            "confirming": "❓",
            "executing": "▶️",
            "success": "✅",
            "failed": "❌",
            "blocked": "🚫",
            "cancelled": "⛔",
        }
        icon = status_icons.get(status, "🔧")

        # Add agent name if this was delegated to a sub-agent
        if agent_name and agent_name != "orchestrator":
            title = f"{icon} Tool: {tool_name} (via {agent_name})"
        else:
            title = f"{icon} Tool: {tool_name}"

        # Ensure content is a string
        content_str = str(content) if content is not None else ""

        super().__init__(
            title=title,
            content=content_str,
            message_type="tool",
            collapsed=collapsed,
            **kwargs,
        )
        self.tool_name = tool_name
        self.status = status
        self.agent_name = agent_name

    def update_status(self, status: str, content: str) -> None:
        """Update the tool message status and content.

        Args:
            status: New execution status
            content: New content to display
        """
        # Update internal state
        self.status = status
        self.message_content = str(content) if content is not None else ""

        # Update title with new status icon
        status_icons = {
            "pending": "⏳",
            "confirming": "❓",
            "executing": "▶️",
            "success": "✅",
            "failed": "❌",
            "blocked": "🚫",
            "cancelled": "⛔",
        }
        icon = status_icons.get(status, "🔧")

        # Build new title
        if self.agent_name and self.agent_name != "orchestrator":
            new_title = f"{icon} Tool: {self.tool_name} (via {self.agent_name})"
        else:
            new_title = f"{icon} Tool: {self.tool_name}"

        # Update the title widget in the header
        title_widget = self.query_one(".message-title", Static)
        title_widget.update(new_title)

        # Update the content widget in the collapsible
        content_widget = self.query_one(".message-content", Static)
        content_widget.update(self.message_content)


class UserMessage(Static):
    """Simple user message display (not collapsible)."""

    DEFAULT_CSS = """
    UserMessage {
        width: 100%;
        padding: 1 2;
        margin: 0 0 1 0;
        background: $panel;
        border-left: thick $primary;
    }

    UserMessage .user-label {
        color: $primary;
        text-style: bold;
    }
    """

    def __init__(self, content: str, **kwargs):
        """Initialize a user message.

        Args:
            content: User message content
            **kwargs: Additional arguments
        """
        # Ensure content is a string
        self.message_content = str(content) if content is not None else ""
        # Disable markup for user messages
        kwargs.setdefault("markup", False)
        super().__init__(**kwargs)

    def on_mount(self) -> None:
        """Update content when mounted."""
        message = Text()
        message.append("You: ", style="bold blue")
        message.append(self.message_content)
        self.update(message)
