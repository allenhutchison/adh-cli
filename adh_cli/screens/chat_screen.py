"""Chat screen for interacting with Google ADK."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Input, Label, RichLog, Static
from textual.binding import Binding

from ..services.adk_service import ADKService, ADKConfig


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
            log = RichLog(id="chat-log", wrap=True, highlight=True, markup=True)
            log.border_title = "ADH Chat"
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
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle message submission."""
        await self.send_message()


    async def send_message(self) -> None:
        """Send a message to the ADK service."""
        input_widget = self.query_one("#chat-input", Input)
        message = input_widget.value.strip()

        if not message:
            return

        # Clear input immediately after getting the message
        input_widget.value = ""
        input_widget.focus()

        if not self.adk_service:
            self.chat_log.write("[red]ADK service not initialized. Please configure API key.[/red]")
            return

        self.chat_log.write(f"[blue]You:[/blue] {message}")

        try:
            worker = self.app.run_worker(
                lambda: self.adk_service.send_message(message),
                thread=True
            )
            response = await worker.wait()
            self.chat_log.write(f"[green]AI:[/green] {response}")
        except Exception as e:
            self.chat_log.write(f"[red]Error: {str(e)}[/red]")

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
            status_line.update("[bold]COMMAND MODE[/bold] - (s)ettings (c)lear (e)xport (q)uit (i/ESC)nput")
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
        elif key == "q":
            # Quit
            self.app.exit()
            event.prevent_default()
        elif key == "i":
            # Return to input mode
            self.action_toggle_command_mode()
            event.prevent_default()

    def action_export_chat(self) -> None:
        """Export chat history."""
        if self.chat_log:
            with open("chat_export.txt", "w") as f:
                for line in self.chat_log._lines:
                    f.write(str(line) + "\n")
            self.chat_log.write("[green]Chat exported to chat_export.txt[/green]")