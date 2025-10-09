"""Chat screen with policy-aware agent integration."""

from typing import Optional
from textual import on, events
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import RichLog, TextArea, Footer
from textual.binding import Binding
from rich.markdown import Markdown
from rich.panel import Panel

from ..core.tool_executor import ExecutionContext
from ..ui.confirmation_dialog import ConfirmationDialog, PolicyNotification
from ..ui.tool_execution import ToolExecutionInfo
from ..policies.policy_types import PolicyDecision


class ChatTextArea(TextArea):
    """Custom TextArea that submits on Enter and inserts newline on Shift+Enter."""

    def action_submit(self) -> None:
        """Submit the message."""
        self.post_message(self.Submitted(self))

    async def _on_key(self, event: events.Key) -> None:
        """Handle Enter / Shift+Enter to support submissions and newlines."""
        key = event.key.lower()

        if key in {"enter", "return"}:
            if getattr(event, "shift", False):
                if self.read_only:
                    return
                event.stop()
                event.prevent_default()
                self._restart_blink()
                self.insert("\n")
                return

            event.stop()
            event.prevent_default()
            self.post_message(self.Submitted(self))
            return

        if key in {"ctrl+j", "newline"}:
            if self.read_only:
                return
            event.stop()
            event.prevent_default()
            self._restart_blink()
            self.insert("\n")
            return

        await super()._on_key(event)

    class Submitted(TextArea.Changed):
        """Message sent when user presses Enter."""

        pass


class ChatScreen(Screen):
    """Chat screen with policy enforcement."""

    CSS = """
    ChatScreen {
        layout: vertical;
    }

    #chat-container {
        height: 1fr;
        width: 100%;
        padding: 1 2 0 2;
    }

    #chat-log {
        height: 100%;
        width: 100%;
        border: solid $border;
        border-title-align: center;
        padding: 2;
        background: $surface;
    }

    #chat-input {
        width: 100%;
        height: auto;
        max-height: 10;
        /* Remove bottom margin so input sits flush above the status bar */
        margin: 0 2 0 2;
        border: solid $border;
        background: $panel;
        color: $text-primary;
    }

    #chat-input:focus {
        border: solid $border-focus;
    }
    """

    BINDINGS = [
        Binding("ctrl+l", "clear_chat", "Clear Chat"),
        Binding("ctrl+slash", "show_policies", "Show Policies"),
        Binding("ctrl+s", "toggle_safety", "Toggle Safety"),
        Binding("ctrl+comma", "app.show_settings", "Settings"),
    ]

    def __init__(self):
        """Initialize the policy chat screen."""
        super().__init__()
        self.agent = None  # Will be set from app
        self.chat_log: Optional[RichLog] = None
        self.notifications = []
        self.safety_enabled = True
        self.context = ExecutionContext()

    def compose(self) -> ComposeResult:
        """Create child widgets for the chat screen."""
        # Main chat container
        with Container(id="chat-container"):
            log = RichLog(
                id="chat-log", wrap=True, highlight=True, markup=True, auto_scroll=True
            )
            # Border title will be set dynamically by _update_chat_title()
            log.can_focus = True
            yield log

        # Input area (ChatTextArea for multi-line support)
        text_area = ChatTextArea(id="chat-input")
        text_area.show_line_numbers = False
        text_area.border_title = (
            "Type your message (Enter to send, Shift+Enter or Ctrl+J for new line)"
        )
        yield text_area

        # Footer to display key bindings
        yield Footer()

    def on_mount(self) -> None:
        """Initialize services when screen is mounted."""
        self.chat_log = self.query_one("#chat-log", RichLog)

        # Set initial border title with safety status
        self._update_chat_title()

        try:
            # Get agent from app (already initialized with tools)
            if hasattr(self.app, "agent"):
                self.agent = self.app.agent

                # Register execution manager callbacks if agent has manager
                if (
                    hasattr(self.agent, "execution_manager")
                    and self.agent.execution_manager
                ):
                    self.agent.execution_manager.on_execution_start = (
                        self.on_execution_start
                    )
                    self.agent.execution_manager.on_execution_update = (
                        self.on_execution_update
                    )
                    self.agent.execution_manager.on_execution_complete = (
                        self.on_execution_complete
                    )
                    self.agent.execution_manager.on_confirmation_required = (
                        self.on_confirmation_required
                    )

                # Display agent info
                from rich.text import Text

                agent_name = getattr(self.agent, "agent_name", "orchestrator")

                welcome = Text()
                welcome.append("Policy-Aware Chat Ready ", style="dim")
                welcome.append(f"(Agent: {agent_name})", style="dim cyan")
                self.chat_log.write(welcome)

                self.chat_log.write(
                    "[dim]Tools will be executed according to configured policies.[/dim]"
                )
                self.chat_log.write("")  # Spacing

                # Keyboard shortcuts
                shortcuts = Text()
                shortcuts.append("Keyboard shortcuts: ", style="dim")
                shortcuts.append("Enter", style="bold")
                shortcuts.append(" send | ", style="dim")
                shortcuts.append("Shift+Enter", style="bold")
                shortcuts.append(" / ", style="dim")
                shortcuts.append("Ctrl+J", style="bold")
                shortcuts.append(" newline | ", style="dim")
                shortcuts.append("Ctrl+/", style="bold")
                shortcuts.append(" policies | ", style="dim")
                shortcuts.append("Ctrl+S", style="bold")
                shortcuts.append(" safety | ", style="dim")
                shortcuts.append("Ctrl+L", style="bold")
                shortcuts.append(" clear", style="dim")
                self.chat_log.write(shortcuts)
                self.chat_log.write("")  # Spacing
            else:
                raise Exception("App does not have an agent initialized")

        except Exception as e:
            self.chat_log.write(f"[red]Error accessing agent: {str(e)}[/red]")

        # Focus input
        self.query_one("#chat-input", ChatTextArea).focus()

    @on(ChatTextArea.Submitted, "#chat-input")
    def on_input_submitted(self, event: ChatTextArea.Submitted) -> None:
        """Handle message submission when Enter is pressed."""
        input_widget = self.query_one("#chat-input", ChatTextArea)
        message = input_widget.text.strip()

        if not message:
            return

        # Clear input and show message
        input_widget.clear()
        self._add_message("You", message, is_user=True)

        # Check agent availability
        if not self.agent:
            self.chat_log.write("[red]Agent not initialized.[/red]")
            return

        # Process message asynchronously
        self.run_worker(self.get_ai_response(message), exclusive=False)

    async def get_ai_response(self, message: str) -> None:
        """Get response from AI with policy enforcement."""
        # Show processing indicator
        self._update_chat_title(processing=True)

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
            # Clear processing indicator
            self._update_chat_title(processing=False)

    async def handle_confirmation(
        self, tool_call=None, decision=None, message=None, **kwargs
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

    def _update_chat_title(self, processing: bool = False) -> None:
        """Update the chat log border title with status information.

        Args:
            processing: Whether to show processing indicator
        """
        safety_status = "ON" if self.safety_enabled else "OFF"
        title = f"Policy-Aware ADH Chat • Safety: {safety_status}"

        if processing:
            title += " • ⏳ Processing..."

        self.chat_log.border_title = title

    def _add_message(self, speaker: str, message: str, is_user: bool = False) -> None:
        """Add a message to the chat log.

        Args:
            speaker: The speaker name
            message: The message content
            is_user: Whether this is a user message
        """
        # Use theme colors instead of hardcoded colors
        # Colors are defined in adh_cli/ui/theme.py
        if is_user:
            # User messages - bright blue, more prominent
            from rich.text import Text

            user_message = Text()
            user_message.append("You: ", style="bold blue")
            user_message.append(message, style="white")
            self.chat_log.write(user_message)
        else:
            # AI messages - render as markdown in a panel
            try:
                md = Markdown(message)
                panel = Panel(
                    md,
                    title="[bold cyan]AI:[/bold cyan]",
                    title_align="left",
                    border_style="cyan",
                    padding=(0, 1),
                )
                self.chat_log.write(panel)
            except Exception:
                # Fallback to plain text
                self.chat_log.write(f"[bold cyan]AI:[/bold cyan]\n{message}")

        self.chat_log.write("")  # Add spacing

    def _add_tool_message(self, info: ToolExecutionInfo) -> None:
        """Add a tool execution message to the chat log.

        Args:
            info: Tool execution information
        """
        from rich.text import Text
        from ..ui.tool_execution import format_parameters_inline

        # Determine border style based on state
        state_styles = {
            "pending": "dim",
            "confirming": "yellow",
            "executing": "blue",
            "success": "green",
            "failed": "red",
            "blocked": "red",
            "cancelled": "dim",
        }
        border_style = state_styles.get(info.state.value, "white")

        # Build content
        content = Text()

        # Status line
        content.append(f"{info.status_icon} ", style="bold")
        content.append(info.status_text, style=border_style)
        content.append("\n\n")

        # Parameters (compact inline format)
        if info.parameters:
            inline_params = format_parameters_inline(
                info.parameters, max_params=3, max_value_length=60
            )
            content.append("Parameters: ", style="dim")
            content.append(inline_params, style="")
            content.append("\n")

        # Risk level (if confirming)
        if info.state.value == "confirming" and info.policy_decision:
            risk = info.policy_decision.risk_level
            risk_colors = {
                "none": "green",
                "low": "green",
                "medium": "yellow",
                "high": "red",
                "critical": "bold red",
            }
            risk_color = risk_colors.get(risk.value, "white")
            content.append("Risk: ", style="dim")
            content.append(f"{risk.value.upper()}", style=risk_color)
            content.append("\n")

        # Error message (if failed)
        if info.state.value == "failed" and info.error:
            content.append("\n")
            content.append("Error: ", style="bold red")
            content.append(str(info.error), style="red")

        # Result preview (if success and result exists)
        if info.state.value == "success" and info.result:
            result_str = str(info.result)
            if len(result_str) > 200:
                result_str = result_str[:200] + "..."
            content.append("\n")
            content.append("Result: ", style="dim")
            content.append(result_str, style="dim")

        # Create panel with agent name if from delegated agent
        if info.agent_name and info.agent_name != "orchestrator":
            title = f"[bold]🔧 Tool: {info.tool_name}[/bold] [dim](via {info.agent_name})[/dim]"
        else:
            title = f"[bold]🔧 Tool: {info.tool_name}[/bold]"

        panel = Panel(
            content,
            title=title,
            title_align="left",
            border_style=border_style,
            padding=(0, 1),
        )

        self.chat_log.write(panel)
        self.chat_log.write("")  # Add spacing

    def action_clear_chat(self) -> None:
        """Clear the chat log."""
        self.chat_log.clear()
        self.chat_log.write("[dim]Chat cleared.[/dim]")
        # Reset title to normal state (no processing indicator)
        self._update_chat_title()

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

        # Update chat title to reflect safety status
        self._update_chat_title()

        # Update agent preferences
        if self.agent:
            if not self.safety_enabled:
                # Disable safety by auto-approving everything
                self.agent.policy_engine.user_preferences = {
                    "auto_approve": ["*"],
                }
                self.chat_log.write(
                    "[yellow]⚠️ Safety checks disabled. All tools will execute automatically.[/yellow]"
                )
            else:
                # Re-enable normal policy enforcement
                self.agent.policy_engine.user_preferences = {}
                self.chat_log.write(
                    "[green]✓ Safety checks enabled. Tools subject to policy enforcement.[/green]"
                )

        self.chat_log.write("")

    # Tool Execution Manager Callbacks

    def on_execution_start(self, info: ToolExecutionInfo) -> None:
        """Handle execution start event from manager.

        Args:
            info: Execution information
        """
        # Add tool message to chat log
        self._add_tool_message(info)

    def on_execution_update(self, info: ToolExecutionInfo) -> None:
        """Handle execution update event from manager.

        Args:
            info: Updated execution information
        """
        # Nothing needed - updates will be shown via on_execution_complete
        pass

    def on_execution_complete(self, info: ToolExecutionInfo) -> None:
        """Handle execution complete event from manager.

        Args:
            info: Completed execution information
        """
        # Add completion message to chat log
        self._add_tool_message(info)

    async def on_confirmation_required(
        self, info: ToolExecutionInfo, decision: PolicyDecision
    ) -> None:
        """Handle confirmation required event from manager.

        Args:
            info: Execution information requiring confirmation
            decision: Policy decision
        """
        # Show modal confirmation dialog
        dialog = ConfirmationDialog(
            tool_name=info.tool_name,
            parameters=info.parameters,
            decision=decision,
        )

        # Push dialog and wait for user response
        result = await self.app.push_screen_wait(dialog)

        # Handle user response
        if result:
            # User confirmed - notify execution manager to proceed
            self.agent.execution_manager.confirm_execution(info.id)
        else:
            # User cancelled - notify execution manager to abort
            self.agent.execution_manager.cancel_execution(info.id)
