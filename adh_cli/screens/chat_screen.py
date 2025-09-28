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

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+l", "clear_chat", "Clear Chat"),
    ]

    def __init__(self):
        """Initialize the chat screen."""
        super().__init__()
        self.adk_service = None
        self.chat_log = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the chat screen."""
        with Container(classes="container"):
            yield Static("[bold]ADK Chat Interface[/bold]", id="chat-title")

            with Vertical():
                yield RichLog(id="chat-log", wrap=True, highlight=True, markup=True)

                with Horizontal(id="input-container"):
                    yield Input(
                        placeholder="Type your message here...",
                        id="chat-input"
                    )
                    yield Button("Send", id="btn-send", variant="primary")

                with Horizontal(id="control-buttons"):
                    yield Button("Clear", id="btn-clear", variant="warning")
                    yield Button("Export", id="btn-export")
                    yield Button("Back", id="btn-back", variant="default")

    def on_mount(self) -> None:
        """Initialize services when screen is mounted."""
        try:
            self.adk_service = ADKService()
            self.chat_log = self.query_one("#chat-log", RichLog)
            self.chat_log.write("[system]Chat session started. ADK service connected.[/system]")
        except ValueError as e:
            self.chat_log = self.query_one("#chat-log", RichLog)
            self.chat_log.write(f"[red]Error: {str(e)}[/red]")
            self.chat_log.write(
                "[yellow]Please set your GOOGLE_API_KEY environment variable or configure it in settings.[/yellow]"
            )

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

    @on(Button.Pressed, "#btn-back")
    def on_back_pressed(self) -> None:
        """Go back to the main screen."""
        self.app.pop_screen()

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

        if not self.adk_service:
            self.chat_log.write("[red]ADK service not initialized. Please configure API key.[/red]")
            return

        self.chat_log.write(f"[blue]You:[/blue] {message}")
        input_widget.value = ""

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
                self.adk_service.start_chat()