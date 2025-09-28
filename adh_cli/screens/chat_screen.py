"""Chat screen for interacting with Google ADK."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, RichLog, Static
from textual.binding import Binding

from ..services.adk_service import ADKService, ADKConfig


class ChatScreen(Screen):
    """Chat screen for AI interactions."""

    CSS = """
    ChatScreen {
        layout: vertical;
    }

    #chat-title {
        height: 3;
        padding: 1 2;
        background: $boost;
        color: $text;
        text-align: center;
        content-align: center middle;
    }

    #chat-container {
        height: 1fr;
        padding: 0 1;
    }

    #chat-log {
        height: 100%;
        border: solid $primary;
        padding: 0 1;
        background: $surface;
    }

    #input-container {
        height: 3;
        padding: 0 1;
    }

    #chat-input {
        width: 1fr;
        margin-right: 1;
    }

    #control-buttons {
        height: 3;
        padding: 0 1;
        align: center middle;
    }

    #control-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+l", "clear_chat", "Clear Chat"),
        Binding("s", "show_settings", "Settings"),
    ]

    def __init__(self):
        """Initialize the chat screen."""
        super().__init__()
        self.adk_service = None
        self.chat_log = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the chat screen."""
        # Title at the top
        yield Static("[bold]💬 ADK Chat[/bold]", id="chat-title")

        # Main chat container that takes up most space
        with Container(id="chat-container"):
            yield RichLog(id="chat-log", wrap=True, highlight=True, markup=True)

        # Input area at the bottom
        with Horizontal(id="input-container"):
            yield Input(
                placeholder="Type your message here... (Enter to send)",
                id="chat-input"
            )
            yield Button("Send", id="btn-send", variant="primary")

        # Compact control buttons at very bottom
        with Horizontal(id="control-buttons"):
            yield Button("Clear Chat", id="btn-clear", variant="warning")
            yield Button("Export", id="btn-export", variant="success")
            yield Button("Settings", id="btn-settings", variant="default")

    def on_mount(self) -> None:
        """Initialize services when screen is mounted."""
        try:
            # Initialize ADK service with tools enabled
            self.adk_service = ADKService(enable_tools=True)
            self.chat_log = self.query_one("#chat-log", RichLog)
            self.chat_log.write("[system]Chat session started. ADK service connected.[/system]")
            self.chat_log.write("[dim]🔧 Tools enabled: execute_command, list_directory, read_file[/dim]")
            self.chat_log.write("[dim]Try asking me to run commands, list files, or read files![/dim]")
        except ValueError as e:
            self.chat_log = self.query_one("#chat-log", RichLog)
            self.chat_log.write(f"[red]Error: {str(e)}[/red]")
            self.chat_log.write(
                "[yellow]Please set your GOOGLE_API_KEY environment variable or configure it in settings.[/yellow]"
            )

        # Focus the input field
        self.query_one("#chat-input", Input).focus()

    @on(Input.Submitted, "#chat-input")
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle message submission."""
        await self.send_message()

    @on(Button.Pressed, "#btn-send")
    async def on_send_pressed(self) -> None:
        """Handle send button press."""
        await self.send_message()

    @on(Button.Pressed, "#btn-clear")
    def on_clear_pressed(self) -> None:
        """Clear the chat log."""
        self.action_clear_chat()

    @on(Button.Pressed, "#btn-settings")
    def on_settings_pressed(self) -> None:
        """Open settings modal."""
        from .settings_modal import SettingsModal
        self.app.push_screen(SettingsModal())

    @on(Button.Pressed, "#btn-export")
    def on_export_pressed(self) -> None:
        """Export chat history."""
        if self.chat_log:
            with open("chat_export.txt", "w") as f:
                for line in self.chat_log._lines:
                    f.write(str(line) + "\n")
            self.chat_log.write("[green]Chat exported to chat_export.txt[/green]")

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
            self.chat_log.write("[system]Chat cleared.[/system]")
            if self.adk_service:
                # Restart chat session
                self.adk_service.start_chat()

    def action_show_settings(self) -> None:
        """Show settings modal."""
        from .settings_modal import SettingsModal
        self.app.push_screen(SettingsModal())