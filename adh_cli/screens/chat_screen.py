"""Chat screen with policy-aware agent integration."""

from typing import Optional, TYPE_CHECKING
from pathlib import Path
import pyperclip
from textual import on, events
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.widgets import TextArea, Static
from textual.binding import Binding
from rich.text import Text

from ..core.tool_executor import ExecutionContext
from ..ui.confirmation_dialog import ConfirmationDialog, PolicyNotification
from ..ui.tool_execution import (
    ToolExecutionInfo,
    ToolExecutionState,
    format_parameters_inline,
)
from ..ui.chat_widgets import AIMessage, ToolMessage, UserMessage
from ..ui.status_footer import StatusFooter
from ..policies.policy_types import PolicyDecision
from ..session import SessionRecorder

if TYPE_CHECKING:
    from ..core.policy_aware_llm_agent import PolicyAwareLlmAgent


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

    # Base title for the chat log border
    BASE_TITLE = "Policy-Aware ADH Chat"

    # Default title for the chat input border
    DEFAULT_INPUT_TITLE = (
        "Type your message (Enter to send, Shift+Enter or Ctrl+J for new line)"
    )

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

    #chat-messages {
        width: 100%;
        height: auto;
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
        border: solid $primary;
    }

    .info-message {
        color: $text-muted;
        padding: 0 0 1 0;
    }
    """

    BINDINGS = [
        Binding("ctrl+l", "clear_chat", "Clear Chat"),
        Binding("ctrl+y", "copy_chat", "Copy Chat"),
        Binding("ctrl+e", "export_session", "Export Session"),
        Binding("ctrl+slash", "show_policies", "Show Policies"),
        Binding("ctrl+s", "toggle_safety", "Toggle Safety"),
        Binding("ctrl+comma", "app.show_settings", "Settings"),
    ]

    def __init__(self):
        """Initialize the policy chat screen."""
        super().__init__()
        self.agent = None  # Will be set from app
        self.chat_log: Optional[VerticalScroll] = None
        self.notifications = []
        self.safety_enabled = True
        self.context = ExecutionContext()
        self._processing_requests = 0  # Counter for concurrent AI requests
        self._message_history = []  # Track plain text messages for copying
        self._message_history_ids = {}  # Map execution ID -> message history index
        self._tool_widgets = {}  # Map execution ID -> ToolMessage widget
        self._streaming_positions = {}  # Map execution ID -> last streaming position
        self.chat_input: Optional[ChatTextArea] = None

        # Session recorder for transcript capture
        self.session_recorder = SessionRecorder()

    def compose(self) -> ComposeResult:
        """Create child widgets for the chat screen."""
        # Main chat container with scrollable messages
        with Container(id="chat-container"):
            with VerticalScroll(id="chat-log") as vs:
                vs.can_focus = True
                # Messages will be mounted here
                pass

        # Input area (ChatTextArea for multi-line support)
        text_area = ChatTextArea(id="chat-input")
        text_area.show_line_numbers = False
        text_area.border_title = self.DEFAULT_INPUT_TITLE
        yield text_area

        # Custom footer to display environment info and key shortcuts
        yield StatusFooter()

    def on_mount(self) -> None:
        """Initialize services when screen is mounted."""
        self.chat_log = self.query_one("#chat-log", VerticalScroll)
        self.chat_input = self.query_one("#chat-input", ChatTextArea)

        # Set initial border title with safety status
        self._update_chat_title()

        # Show initial messages (regardless of agent status)
        self._mount_info_message(
            "[dim]Tools will be executed according to configured policies.[/dim]"
        )
        self._show_keyboard_shortcuts()

        try:
            # Get agent from app (may not be initialized yet if async loading)
            if hasattr(self.app, "agent") and self.app.agent:
                self.update_agent(self.app.agent)
            else:
                # Agent is still initializing - show status in input border
                self.chat_input.border_title = "⏳ Initializing agent..."

        except Exception as e:
            self._mount_info_message(f"[red]Error accessing agent: {str(e)}[/red]")

        # Focus input
        self.query_one("#chat-input", ChatTextArea).focus()

    def _show_keyboard_shortcuts(self) -> None:
        """Display keyboard shortcuts in the chat log."""
        shortcuts = Text()
        shortcuts.append("Keyboard shortcuts: ", style="dim")
        shortcuts.append("Enter", style="bold")
        shortcuts.append(" send | ", style="dim")
        shortcuts.append("Shift+Enter", style="bold")
        shortcuts.append(" / ", style="dim")
        shortcuts.append("Ctrl+J", style="bold")
        shortcuts.append(" newline | ", style="dim")
        shortcuts.append("Ctrl+Y", style="bold")
        shortcuts.append(" copy | ", style="dim")
        shortcuts.append("Ctrl+E", style="bold")
        shortcuts.append(" export | ", style="dim")
        shortcuts.append("Ctrl+/", style="bold")
        shortcuts.append(" policies | ", style="dim")
        shortcuts.append("Ctrl+S", style="bold")
        shortcuts.append(" safety | ", style="dim")
        shortcuts.append("Ctrl+L", style="bold")
        shortcuts.append(" clear", style="dim")
        self._mount_info_message(shortcuts)

    def update_agent(self, agent: "PolicyAwareLlmAgent") -> None:
        """Update the agent reference and register callbacks.

        This is called either during on_mount (if agent is already ready)
        or later when async agent initialization completes.

        Args:
            agent: The PolicyAwareLlmAgent instance
        """
        self.agent = agent

        # Clear initialization message from input border
        self.chat_input.border_title = ""

        # Register execution manager callbacks if agent has manager
        if hasattr(self.agent, "execution_manager") and self.agent.execution_manager:
            self.agent.execution_manager.on_execution_start = self.on_execution_start
            self.agent.execution_manager.on_execution_update = self.on_execution_update
            self.agent.execution_manager.on_execution_complete = (
                self.on_execution_complete
            )
            self.agent.execution_manager.on_confirmation_required = (
                self.on_confirmation_required
            )

        # Register thinking callback
        if hasattr(self.agent, "on_thinking"):
            self.agent.on_thinking = self.on_thinking

        # Display agent ready message
        agent_name = getattr(self.agent, "agent_name", "orchestrator")

        welcome = Text()
        welcome.append("Policy-Aware Chat Ready ", style="dim")
        welcome.append(f"(Agent: {agent_name})", style="dim cyan")
        self._mount_info_message(welcome)

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

        # If the screen's agent isn't set, try to get it from the app.
        # This is the one-time binding when the agent finishes async initialization.
        if not self.agent and hasattr(self.app, "agent") and self.app.agent:
            self.update_agent(self.app.agent)

        # Now, check if the agent is available on the screen.
        if not self.agent:
            self._mount_info_message("[red]Agent not initialized.[/red]")
            return

        # Process message asynchronously
        self.run_worker(self.get_ai_response(message), exclusive=False)

    async def get_ai_response(self, message: str) -> None:
        """Get response from AI with policy enforcement."""
        # Increment processing counter and update title
        self._processing_requests += 1
        self._update_chat_title()

        try:
            # Get response from policy-aware agent
            response = await self.agent.chat(
                message=message,
                context=self.context,
            )

            # Show response
            self._add_message("AI", response, is_user=False)

        except Exception as e:
            self._mount_info_message(f"[red]Error: {str(e)}[/red]")
        finally:
            # Decrement counter and update title
            self._processing_requests -= 1
            self._update_chat_title()
            # Hide thinking display
            self.hide_thinking()

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

    def _update_chat_title(self) -> None:
        """Update the chat log border title with status information."""
        safety_status = "ON" if self.safety_enabled else "OFF"

        title_parts = [
            self.BASE_TITLE,
            f"Safety: {safety_status}",
        ]

        if self._processing_requests > 0:
            title_parts.append("⏳ Processing...")

        self.chat_log.border_title = " • ".join(title_parts)

    def show_thinking(self, thought_text: str) -> None:
        """Show model thinking in the input border title.

        Args:
            thought_text: The thinking/reasoning text from the model
        """
        if self.chat_input:
            # Extract just the first line of the thought
            first_line = thought_text.split("\n")[0].strip()

            # Strip common markdown formatting (bold, italic, code)
            # Remove **bold** and __bold__
            first_line = first_line.replace("**", "").replace("__", "")
            # Remove *italic* and _italic_ (but not __ which we already handled)
            first_line = first_line.replace("*", "").replace("_", "")
            # Remove `code` backticks
            first_line = first_line.replace("`", "")

            # Truncate to reasonable length for border title (~100 chars)
            max_length = 100
            if len(first_line) > max_length:
                first_line = first_line[: max_length - 3] + "..."

            # Update input border title with thinking indicator
            self.chat_input.border_title = f"💭 {first_line}"

    def hide_thinking(self) -> None:
        """Restore the default input border title."""
        if self.chat_input:
            self.chat_input.border_title = self.DEFAULT_INPUT_TITLE

    def _mount_info_message(self, content) -> None:
        """Mount an info message to the chat log.

        Args:
            content: Rich renderable or markup string
        """
        info_widget = Static(content, classes="info-message")
        self.chat_log.mount(info_widget)
        self.chat_log.scroll_end(animate=False)

    def _add_message(self, speaker: str, message: str, is_user: bool = False) -> None:
        """Add a message to the chat log.

        Args:
            speaker: The speaker name
            message: The message content
            is_user: Whether this is a user message
        """
        # Track message in history for copying
        self._message_history.append(f"{speaker}: {message}")

        # Record in session transcript (async, non-blocking)
        role = "user" if is_user else "ai"
        self.run_worker(
            self.session_recorder.record_chat_turn(role=role, content=message),
            exclusive=False,
        )

        # Mount appropriate widget based on message type
        if is_user:
            # User messages - simple non-collapsible widget
            widget = UserMessage(content=message)
        else:
            # AI messages - collapsible with copy button, start expanded
            widget = AIMessage(content=message, collapsed=False)

        self.chat_log.mount(widget)
        self.chat_log.scroll_end(animate=False)

    def _build_tool_content(self, info: ToolExecutionInfo) -> str:
        """Build content text for a tool execution message.

        Args:
            info: Tool execution information

        Returns:
            Formatted content string
        """
        content_parts = []

        # Status line
        content_parts.append(f"{info.status_icon} {info.status_text}")
        content_parts.append("")  # Blank line

        # Parameters (compact inline format)
        if info.parameters:
            inline_params = format_parameters_inline(
                info.parameters, max_params=3, max_value_length=60
            )
            content_parts.append(f"Parameters: {inline_params}")

        # Risk level (if confirming)
        if info.state.value == "confirming" and info.policy_decision:
            risk = info.policy_decision.risk_level
            content_parts.append(f"Risk: {risk.value.upper()}")

        # Error message (if failed)
        if info.state.value == "failed" and info.error:
            content_parts.append("")  # Blank line
            content_parts.append(f"Error: {info.error}")

        # Result preview (if success and result exists)
        if info.state.value == "success" and info.result:
            result_str = str(info.result)
            # Don't truncate for copying - user can collapse it
            content_parts.append("")  # Blank line
            content_parts.append(f"Result:\n{result_str}")

        return "\n".join(content_parts)

    def _add_tool_message(self, info: ToolExecutionInfo) -> ToolMessage:
        """Add a tool execution message to the chat log.

        Args:
            info: Tool execution information

        Returns:
            The created ToolMessage widget
        """
        # Build content text
        content = self._build_tool_content(info)

        # Track in message history for copying
        agent_suffix = (
            f" (via {info.agent_name})"
            if info.agent_name and info.agent_name != "orchestrator"
            else ""
        )
        history_index = len(self._message_history)
        self._message_history.append(f"Tool {info.tool_name}{agent_suffix}: {content}")
        # Map execution ID to history index for robust updates
        self._message_history_ids[info.id] = history_index

        # Create tool message widget
        widget = ToolMessage(
            tool_name=info.tool_name,
            content=content,
            status=info.state.value,
            collapsed=True,  # Start collapsed
            agent_name=info.agent_name,
            parameters=info.parameters,
        )

        self.chat_log.mount(widget)
        self.chat_log.scroll_end(animate=False)

        return widget

    def action_clear_chat(self) -> None:
        """Clear the chat log."""
        # Close current session (async, run in background)
        self.run_worker(self.session_recorder.close(), exclusive=False)

        # Remove all child widgets
        self.chat_log.remove_children()
        self._message_history.clear()
        self._message_history_ids.clear()
        self._tool_widgets.clear()
        self._mount_info_message("[dim]Chat cleared.[/dim]")
        # Reset title to normal state (no processing indicator)
        self._update_chat_title()

        # Start new session
        self.session_recorder = SessionRecorder()

    def action_copy_chat(self) -> None:
        """Copy the entire chat log to clipboard."""
        if not self._message_history:
            self.notify("No messages to copy", title="Info", severity="information")
            return

        try:
            # Join all messages with double newlines
            chat_text = "\n\n".join(self._message_history)
            pyperclip.copy(chat_text)
            self.notify(
                f"Copied {len(self._message_history)} messages to clipboard",
                title="Success",
            )
        except pyperclip.PyperclipException as e:
            self.notify(f"Failed to copy: {e}", title="Error", severity="error")

    def action_export_session(self) -> None:
        """Export the current session to markdown file."""
        if not self._message_history:
            self.notify("No messages to export", title="Info", severity="information")
            return

        try:
            # Generate output filename
            session_id = self.session_recorder.session_id
            # XDG Base Directory compliant
            output_dir = Path.home() / ".local" / "share" / "adh-cli" / "exports"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"session_{session_id}.md"

            # Export to markdown
            markdown_content = self.session_recorder.export_markdown(output_file)

            # Also save JSONL location
            jsonl_file = self.session_recorder.session_file

            self.notify(
                f"Session exported:\nMarkdown: {output_file}\nJSONL: {jsonl_file}",
                title="Export Complete",
                timeout=10,
            )

            # Also copy markdown to clipboard for convenience
            pyperclip.copy(markdown_content)

        except (pyperclip.PyperclipException, IOError, OSError) as e:
            self.notify(f"Failed to export: {e}", title="Error", severity="error")

    def action_show_policies(self) -> None:
        """Show active policies."""
        if not self.agent:
            return

        self._mount_info_message("[bold]Active Policies:[/bold]")

        # Show user preferences
        prefs = self.agent.policy_engine.user_preferences
        if prefs:
            self._mount_info_message("\n[cyan]User Preferences:[/cyan]")
            for key, value in prefs.items():
                self._mount_info_message(f"  {key}: {value}")

        # Show loaded rules count
        rule_count = len(self.agent.policy_engine.rules)
        self._mount_info_message(f"\n[cyan]Loaded Rules:[/cyan] {rule_count}")

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
                self._mount_info_message(
                    "[yellow]⚠️ Safety checks disabled. All tools will execute automatically.[/yellow]"
                )
            else:
                # Re-enable normal policy enforcement
                self.agent.policy_engine.user_preferences = {}
                self._mount_info_message(
                    "[green]✓ Safety checks enabled. Tools subject to policy enforcement.[/green]"
                )

    # Tool Execution Manager Callbacks

    def on_execution_start(self, info: ToolExecutionInfo) -> None:
        """Handle execution start event from manager.

        Args:
            info: Execution information
        """
        # Add tool message to chat log and track it for updates
        widget = self._add_tool_message(info)
        self._tool_widgets[info.id] = widget

    def on_execution_update(self, info: ToolExecutionInfo) -> None:
        """Handle execution update event from manager.

        Args:
            info: Updated execution information
        """
        # Handle streaming output updates
        if info.streaming_output:
            widget = self._tool_widgets.get(info.id)
            if widget and hasattr(widget, "append_output"):
                # Track the last position we've seen to avoid re-appending old output
                if not hasattr(self, "_streaming_positions"):
                    self._streaming_positions = {}

                last_pos = self._streaming_positions.get(info.id, 0)
                new_outputs = info.streaming_output[last_pos:]

                # Append each new output chunk
                for stream_name, data in new_outputs:
                    widget.append_output(stream_name, data)

                # Update our position tracker
                self._streaming_positions[info.id] = len(info.streaming_output)

    def on_execution_complete(self, info: ToolExecutionInfo) -> None:
        """Handle execution complete event from manager.

        Args:
            info: Completed execution information
        """
        # Record tool invocation in session transcript (async, non-blocking)
        success = info.state is ToolExecutionState.SUCCESS
        result_str = str(info.result) if info.result is not None else None
        error_str = info.error if info.error is not None else None

        self.run_worker(
            self.session_recorder.record_tool_invocation(
                tool_name=info.tool_name,
                parameters=info.parameters,
                success=success,
                result=result_str,
                error=error_str,
                agent_name=info.agent_name,
            ),
            exclusive=False,
        )

        # Check if we have an existing widget for this execution
        widget = self._tool_widgets.get(info.id)

        if widget:
            # Update the existing widget with the completion status
            content = self._build_tool_content(info)

            # Update the widget
            widget.update_status(info.state.value, content)

            # Update message history for copying using execution ID
            if info.id in self._message_history_ids:
                agent_suffix = (
                    f" (via {info.agent_name})"
                    if info.agent_name and info.agent_name != "orchestrator"
                    else ""
                )
                history_entry = f"Tool {info.tool_name}{agent_suffix}: {content}"
                history_index = self._message_history_ids[info.id]
                self._message_history[history_index] = history_entry
                # Clean up the ID mapping
                del self._message_history_ids[info.id]

            # Clean up the widget reference
            del self._tool_widgets[info.id]
        else:
            # Fallback: create new message if widget not found
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

    def on_thinking(self, thought_text: str) -> None:
        """Handle thinking events from the model.

        Args:
            thought_text: The thinking/reasoning text from the model
        """
        # Update the thinking display
        self.show_thinking(thought_text)
