"""Main screen for the ADH CLI application."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static, Label, Welcome


class MainScreen(Screen):
    """Main screen of the application."""

    def compose(self) -> ComposeResult:
        """Create child widgets for the main screen."""
        with Container(classes="container"):
            yield Static(
                "[bold]Welcome to ADH CLI[/bold]\n\n"
                "A Terminal User Interface for Google ADK\n",
                id="welcome-text"
            )

            with Vertical():
                yield Label("Choose an option to get started:")

                with Horizontal():
                    yield Button("Start Chat", id="btn-chat", variant="primary")
                    yield Button("Settings", id="btn-settings", variant="default")
                    yield Button("View Models", id="btn-models", variant="default")

                yield Static(
                    "\n[dim]Press 'c' for Chat, 's' for Settings, or 'q' to quit[/dim]",
                    id="help-text"
                )

    @on(Button.Pressed, "#btn-chat")
    def on_chat_pressed(self) -> None:
        """Handle chat button press."""
        self.app.push_screen("chat")

    @on(Button.Pressed, "#btn-settings")
    def on_settings_pressed(self) -> None:
        """Handle settings button press."""
        self.app.push_screen("settings")

    @on(Button.Pressed, "#btn-models")
    def on_models_pressed(self) -> None:
        """Handle models button press."""
        from ..widgets.model_list import ModelListDialog
        self.app.push_screen(ModelListDialog())