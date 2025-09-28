"""Chat screen for interacting with Google ADK."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Input, Label, RichLog, Static
from textual.binding import Binding
from rich.markdown import Markdown
from rich.text import Text
from rich.table import Table
from rich.console import Group
from rich.padding import Padding

from ..services.adk_service import ADKService, ADKConfig
from ..services.clipboard_service import ClipboardService


class ChatScreen(Screen):
    """Chat screen for AI interactions."""

    CSS = """
    ChatScreen {
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

    #status-line.command-mode {
        background: $primary;
    }

    #status-line.thinking {
        background: $warning;
        color: $text;
    }

    """

    BINDINGS = [
        Binding("escape", "toggle_command_mode", "Command Mode", show=False),
        Binding("ctrl+l", "clear_chat", "Clear Chat"),
    ]

    def __init__(self):
        """Initialize the chat screen."""
        super().__init__()
        self.adk_service = None
        self.chat_log = None
        self.command_mode = False

    def compose(self) -> ComposeResult:
        """Create child widgets for the chat screen."""
        # Status line docked at the bottom
        yield Static(
            "INPUT MODE - Press ESC for commands",
            id="status-line"
        )

        # Main chat container that takes up most space
        with Container(id="chat-container"):
            log = RichLog(id="chat-log", wrap=True, highlight=True, markup=True, auto_scroll=True)
            log.border_title = "ADH Chat"
            log.can_focus = True
            yield log

        # Input area (above the docked status line)
        with Horizontal(id="input-container"):
            yield Input(
                placeholder="Type your message here... (Enter to send, ESC for command mode)",
                id="chat-input"
            )

    def on_mount(self) -> None:
        """Initialize services when screen is mounted."""
        self.chat_log = self.query_one("#chat-log", RichLog)

        try:
            # Initialize ADK service with tools enabled
            self.adk_service = ADKService(enable_tools=True)
            self.chat_log.write("[dim]Ready. Type a message or press ESC for commands.[/dim]")
        except ValueError as e:
            self.chat_log.write(f"[red]Error: {str(e)}[/red]")
            self.chat_log.write(
                "[yellow]Please set your GOOGLE_API_KEY or press 's' for settings.[/yellow]"
            )

        # Focus the input field
        self.query_one("#chat-input", Input).focus()

    @on(Input.Submitted, "#chat-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle message submission."""
        input_widget = self.query_one("#chat-input", Input)
        message = input_widget.value.strip()

        if not message:
            return

        # Immediately clear input and show message - synchronously for instant feedback
        input_widget.value = ""
        # Display user message with gutter effect
        self._add_message("You", message, is_user=True)

        # Check service availability
        if not self.adk_service:
            self.chat_log.write("[red]ADK service not initialized. Please configure API key.[/red]")
            return

        # Now make the async API call using run_worker
        self.run_worker(self.get_ai_response(message), exclusive=False)

    async def get_ai_response(self, message: str) -> None:
        """Get response from AI asynchronously."""
        status_line = self.query_one("#status-line", Static)

        # Update status bar to show waiting state with special styling
        status_line.add_class("thinking")
        status_line.update("⏳ AI is thinking...")

        def update_status(status: str):
            """Callback to update status bar with AI activity."""
            # Use app.call_from_thread for thread-safe UI updates
            def _update():
                # Add different colors based on status type
                if "🔧" in status:  # Tool call
                    status_line.update(f"[bold cyan]{status}[/bold cyan]")
                elif "💭" in status:  # Thinking/reasoning
                    status_line.update(f"[dim yellow]{status}[/dim yellow]")
                elif "❌" in status:  # Error
                    status_line.update(f"[bold red]{status}[/bold red]")
                else:
                    status_line.update(status)

            # Use app.call_from_thread for thread-safe UI updates
            self.app.call_from_thread(_update)

        try:
            # Use streaming method with status callback
            response = await self.app.run_worker(
                lambda: self.adk_service.send_message_streaming(message, update_status),
                thread=True
            ).wait()

            # Show response with markdown rendering
            self._add_message("AI", response, is_user=False)
        except Exception as e:
            self.chat_log.write(f"[red]Error: {str(e)}[/red]")
        finally:
            # Restore status bar to normal state
            status_line.remove_class("thinking")
            if self.command_mode:
                status_line.add_class("command-mode")
                status_line.update("[bold]COMMAND MODE[/bold] - (s)ettings (c)lear (y)ank/copy (e)xport (q)uit (i/ESC)nput")
            else:
                status_line.remove_class("command-mode")
                status_line.update("INPUT MODE - Press ESC for commands")

    def _add_message(self, speaker: str, message: str, is_user: bool = False) -> None:
        """Add a message with a gutter-style speaker label.

        Args:
            speaker: The speaker name (You/AI)
            message: The message content
            is_user: Whether this is a user message
        """
        # Create a table for the gutter effect
        table = Table(show_header=False, show_edge=False, padding=(0, 1), box=None)

        # Add columns: one for speaker (fixed width), one for content (expand)
        table.add_column(width=6, justify="right", style="bold blue" if is_user else "bold green")
        table.add_column(ratio=1)

        # Check if message has markdown
        has_markdown = any(marker in message for marker in ['```', '**', '##', '- ', '* ', '1. '])

        if has_markdown and not is_user:
            # For AI markdown responses, render the markdown
            content = Markdown(message)
        else:
            # For user messages or simple text, just use plain text
            content = Text(message)

        # Add the row with speaker and content
        table.add_row(speaker + ":", content)

        # Write the table to the log
        self.chat_log.write(table)
        self.chat_log.write("")  # Add spacing between messages

    def action_clear_chat(self) -> None:
        """Clear the chat log."""
        if self.chat_log:
            self.chat_log.clear()
            self.chat_log.write("[dim]Chat cleared.[/dim]")
            if self.adk_service:
                # Restart chat session
                self.adk_service.start_chat()

    def action_show_settings(self) -> None:
        """Show settings modal."""
        from .settings_modal import SettingsModal
        self.app.push_screen(SettingsModal())

    def action_toggle_command_mode(self) -> None:
        """Toggle command mode on/off."""
        self.command_mode = not self.command_mode
        status_line = self.query_one("#status-line", Static)
        input_widget = self.query_one("#chat-input", Input)

        if self.command_mode:
            # Enter command mode
            status_line.add_class("command-mode")
            status_line.update("[bold]COMMAND MODE[/bold] - (s)ettings (c)lear (y)ank/copy (e)xport (q)uit (i/ESC)nput")
            input_widget.blur()
        else:
            # Exit command mode
            status_line.remove_class("command-mode")
            status_line.update("INPUT MODE - Press ESC for commands")
            input_widget.focus()

    def on_key(self, event) -> None:
        """Handle key presses in command mode."""
        if not self.command_mode:
            return

        key = event.key

        if key == "s":
            # Settings
            self.action_show_settings()
            event.prevent_default()
        elif key == "c":
            # Clear chat
            self.action_clear_chat()
            event.prevent_default()
        elif key == "e":
            # Export
            self.action_export_chat()
            event.prevent_default()
        elif key == "y":
            # Copy (yank) chat history to clipboard
            self.action_copy_chat()
            event.prevent_default()
        elif key == "q":
            # Quit
            self.app.exit()
            event.prevent_default()
        elif key == "i":
            # Return to input mode
            self.action_toggle_command_mode()
            event.prevent_default()

    def action_export_chat(self) -> None:
        """Export chat history to file and optionally to clipboard."""
        if not self.chat_log:
            return

        try:
            # Build plain text from chat log lines
            chat_lines = []
            for line in self.chat_log.lines:
                if hasattr(line, 'text'):
                    text = line.text.strip()
                    if text:  # Only add non-empty lines
                        chat_lines.append(text)

            chat_text = "\n".join(chat_lines)

            if not chat_text:
                self.chat_log.write("[yellow]No chat history to export.[/yellow]")
                return

            # Save to file
            with open("chat_export.txt", "w") as f:
                f.write(chat_text)

            # Also copy to clipboard for convenience
            success, message = ClipboardService.copy_to_clipboard(chat_text)

            if success:
                self.chat_log.write("[green]Chat exported to chat_export.txt and copied to clipboard![/green]")
            else:
                self.chat_log.write("[green]Chat exported to chat_export.txt[/green]")
                self.chat_log.write(f"[dim yellow]Note: {message}[/dim yellow]")

        except Exception as e:
            self.chat_log.write(f"[red]Error exporting chat: {str(e)}[/red]")

    def action_copy_chat(self) -> None:
        """Copy chat history to clipboard."""
        if not self.chat_log:
            return

        try:
            # Build chat text from chat log lines
            chat_lines = []
            for line in self.chat_log.lines:
                if hasattr(line, 'text'):
                    text = line.text.strip()
                    if text:  # Only add non-empty lines
                        chat_lines.append(text)

            chat_text = "\n".join(chat_lines)

            if not chat_text:
                self.chat_log.write("[yellow]No chat history to copy.[/yellow]")
                return

            # Use the clipboard service
            success, message = ClipboardService.copy_to_clipboard(chat_text)

            if success:
                self.chat_log.write(f"[green]Copied {len(chat_lines)} lines to clipboard![/green]")
            else:
                self.chat_log.write(f"[red]{message}[/red]")

        except Exception as e:
            self.chat_log.write(f"[red]Error copying to clipboard: {str(e)}[/red]")

