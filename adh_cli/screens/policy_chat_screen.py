"""Chat screen with policy-aware agent integration."""

from typing import Optional
from pathlib import Path
from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Input, RichLog, Static
from textual.binding import Binding
from rich.markdown import Markdown
from rich.panel import Panel

from ..core.policy_aware_agent import PolicyAwareAgent
from ..core.tool_executor import ExecutionContext
from ..ui.confirmation_dialog import ConfirmationDialog, SafetyWarningDialog, PolicyNotification
from ..tools import shell_tools
from ..services.clipboard_service import ClipboardService


class PolicyChatScreen(Screen):
    """Chat screen with policy enforcement."""

    CSS = """
    PolicyChatScreen {
        layout: vertical;
    }

    #chat-container {
        height: 1fr;
        padding: 1 1 0 1;
    }

    #chat-log {
        height: 100%;
        border: solid $primary;
        border-title-align: center;
        padding: 0 1;
        background: $surface;
    }

    #notification-area {
        height: auto;
        max-height: 10;
        padding: 0 1;
    }

    #input-container {
        height: auto;
        padding: 0 1 1 1;
    }

    #chat-input {
        width: 100%;
    }

    #chat-input:focus {
        border: solid $secondary;
    }

    #status-line {
        dock: bottom;
        height: 1;
        background: $panel;
        color: $text;
        padding: 0 1;
        width: 100%;
    }

    #status-line.thinking {
        background: $warning;
        color: $text;
    }

    #status-line.policy-check {
        background: $primary;
        color: $text;
    }
    """

    BINDINGS = [
        Binding("ctrl+l", "clear_chat", "Clear Chat"),
        Binding("ctrl+p", "show_policies", "Show Policies"),
        Binding("ctrl+s", "toggle_safety", "Toggle Safety"),
    ]

    def __init__(self):
        """Initialize the policy chat screen."""
        super().__init__()
        self.agent: Optional[PolicyAwareAgent] = None
        self.chat_log: Optional[RichLog] = None
        self.notifications = []
        self.safety_enabled = True
        self.context = ExecutionContext()

    def compose(self) -> ComposeResult:
        """Create child widgets for the chat screen."""
        # Status line
        yield Static(
            "Policy-Aware Chat - Safety: ON",
            id="status-line"
        )

        # Main chat container
        with Container(id="chat-container"):
            log = RichLog(
                id="chat-log",
                wrap=True,
                highlight=True,
                markup=True,
                auto_scroll=True
            )
            log.border_title = "Policy-Aware ADH Chat"
            log.can_focus = True
            yield log

        # Notification area for policy notifications
        with Container(id="notification-area"):
            pass

        # Input area
        with Horizontal(id="input-container"):
            yield Input(
                placeholder="Type your message here... (Ctrl+P for policies)",
                id="chat-input"
            )

    def on_mount(self) -> None:
        """Initialize services when screen is mounted."""
        self.chat_log = self.query_one("#chat-log", RichLog)

        try:
            # Initialize policy-aware agent
            self.agent = PolicyAwareAgent(
                api_key=self.app.api_key if hasattr(self.app, 'api_key') else None,
                policy_dir=Path.home() / ".adh-cli" / "policies",
                confirmation_handler=self.handle_confirmation,
                notification_handler=self.show_notification,
                audit_log_path=Path.home() / ".adh-cli" / "audit.log",
            )

            # Register tools
            self._register_tools()

            self.chat_log.write(
                "[dim]Policy-Aware Chat Ready. Tools will be executed according to configured policies.[/dim]"
            )
            self.chat_log.write(
                "[dim]Press Ctrl+P to view active policies, Ctrl+S to toggle safety checks.[/dim]"
            )

        except Exception as e:
            self.chat_log.write(f"[red]Error initializing agent: {str(e)}[/red]")

        # Focus input
        self.query_one("#chat-input", Input).focus()

    def _register_tools(self):
        """Register available tools with the agent."""
        if not self.agent:
            return

        # Register file system tools
        self.agent.register_tool(
            name="read_file",
            description="Read contents of a text file",
            parameters={
                "path": {"type": "string", "description": "File path to read"},
            },
            handler=shell_tools.read_file,
        )

        self.agent.register_tool(
            name="write_file",
            description="Write content to a file",
            parameters={
                "path": {"type": "string", "description": "File path to write"},
                "content": {"type": "string", "description": "Content to write"},
            },
            handler=shell_tools.write_file,
        )

        self.agent.register_tool(
            name="list_directory",
            description="List contents of a directory",
            parameters={
                "path": {"type": "string", "description": "Directory path to list"},
            },
            handler=shell_tools.list_directory,
        )

        self.agent.register_tool(
            name="execute_command",
            description="Execute a shell command",
            parameters={
                "command": {"type": "string", "description": "Command to execute"},
            },
            handler=shell_tools.execute_command,
        )

    @on(Input.Submitted, "#chat-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle message submission."""
        input_widget = self.query_one("#chat-input", Input)
        message = input_widget.value.strip()

        if not message:
            return

        # Clear input and show message
        input_widget.value = ""
        self._add_message("You", message, is_user=True)

        # Check agent availability
        if not self.agent:
            self.chat_log.write("[red]Agent not initialized.[/red]")
            return

        # Process message asynchronously
        self.run_worker(self.get_ai_response(message), exclusive=False)

    async def get_ai_response(self, message: str) -> None:
        """Get response from AI with policy enforcement."""
        status_line = self.query_one("#status-line", Static)

        # Update status
        status_line.add_class("thinking")
        status_line.update("⏳ Processing with policy checks...")

        try:
            # Get response from policy-aware agent
            response = await self.agent.chat(
                message=message,
                context=self.context,
            )

            # Show response
            self._add_message("AI", response, is_user=False)

        except Exception as e:
            self.chat_log.write(f"[red]Error: {str(e)}[/red]")
        finally:
            # Restore status
            status_line.remove_class("thinking")
            status_text = f"Policy-Aware Chat - Safety: {'ON' if self.safety_enabled else 'OFF'}"
            status_line.update(status_text)

    async def handle_confirmation(
        self,
        tool_call=None,
        decision=None,
        message=None,
        **kwargs
    ) -> bool:
        """Handle confirmation requests from policy engine.

        Args:
            tool_call: Tool call requiring confirmation
            decision: Policy decision
            message: Confirmation message
            **kwargs: Additional parameters

        Returns:
            True if confirmed, False otherwise
        """
        # Show confirmation dialog
        dialog = ConfirmationDialog(
            tool_name=tool_call.tool_name if tool_call else "Operation",
            parameters=tool_call.parameters if tool_call else {},
            decision=decision if decision else None,
        )

        # Push dialog and wait for result
        result = await self.app.push_screen_wait(dialog)
        return result if result is not None else False

    async def show_notification(self, message: str, level: str = "info"):
        """Show a policy notification.

        Args:
            message: Notification message
            level: Notification level
        """
        notification_area = self.query_one("#notification-area", Container)

        # Create notification widget
        notification = PolicyNotification(message=message, level=level)
        notification_area.mount(notification)

        # Auto-remove after 5 seconds
        self.set_timer(5.0, lambda: notification.remove())

    def _add_message(self, speaker: str, message: str, is_user: bool = False) -> None:
        """Add a message to the chat log.

        Args:
            speaker: The speaker name
            message: The message content
            is_user: Whether this is a user message
        """
        color = "cyan" if is_user else "green"
        speaker_text = f"[bold {color}]{speaker}:[/bold {color}]"

        # Try to render as markdown for AI responses
        if not is_user:
            try:
                md = Markdown(message)
                panel = Panel(
                    md,
                    title=speaker_text,
                    title_align="left",
                    border_style=color,
                    padding=(0, 1),
                )
                self.chat_log.write(panel)
            except Exception:
                # Fallback to plain text
                self.chat_log.write(f"{speaker_text}\n{message}")
        else:
            # User messages as simple text
            self.chat_log.write(f"{speaker_text} {message}")

        self.chat_log.write("")  # Add spacing

    def action_clear_chat(self) -> None:
        """Clear the chat log."""
        self.chat_log.clear()
        self.chat_log.write("[dim]Chat cleared.[/dim]")

    def action_show_policies(self) -> None:
        """Show active policies."""
        if not self.agent:
            return

        self.chat_log.write("[bold]Active Policies:[/bold]")

        # Show user preferences
        prefs = self.agent.policy_engine.user_preferences
        if prefs:
            self.chat_log.write("\n[cyan]User Preferences:[/cyan]")
            for key, value in prefs.items():
                self.chat_log.write(f"  {key}: {value}")

        # Show loaded rules count
        rule_count = len(self.agent.policy_engine.rules)
        self.chat_log.write(f"\n[cyan]Loaded Rules:[/cyan] {rule_count}")

        self.chat_log.write("")

    def action_toggle_safety(self) -> None:
        """Toggle safety checks on/off."""
        self.safety_enabled = not self.safety_enabled

        status_line = self.query_one("#status-line", Static)
        status_text = f"Policy-Aware Chat - Safety: {'ON' if self.safety_enabled else 'OFF'}"
        status_line.update(status_text)

        # Update agent preferences
        if self.agent:
            if not self.safety_enabled:
                # Disable safety by auto-approving everything
                self.agent.policy_engine.user_preferences = {
                    "auto_approve": ["*"],
                }
                self.chat_log.write("[yellow]⚠️ Safety checks disabled. All tools will execute automatically.[/yellow]")
            else:
                # Re-enable normal policy enforcement
                self.agent.policy_engine.user_preferences = {}
                self.chat_log.write("[green]✓ Safety checks enabled. Tools subject to policy enforcement.[/green]")

        self.chat_log.write("")