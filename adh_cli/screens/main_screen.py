"""Main screen for the ADH CLI application."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static


class MainScreen(Screen):
    """Main screen of the application."""

    CSS = """
    MainScreen {
        align: center middle;
    }

    MainScreen .container {
        width: auto;
        min-width: 60;
        max-width: 100;
        height: auto;
        background: $surface;
        border: solid $primary;
        padding: 2 4;
        align: center middle;
    }

    #welcome-text {
        text-align: center;
        color: $text-primary;
        margin-bottom: 2;
    }

    #welcome-subtitle {
        text-align: center;
        color: $text-secondary;
        margin-bottom: 4;
    }

    #help-text {
        text-align: center;
        color: $text-muted;
        margin-top: 2;
    }

    MainScreen Horizontal {
        align: center middle;
        height: auto;
        margin: 2 0;
    }

    MainScreen Button {
        margin: 0 1;
        min-width: 16;
    }
    """

    def compose(self) -> ComposeResult:
        """Create child widgets for the main screen."""
        with Container(classes="container"):
            yield Static("[bold]Welcome to ADH CLI[/bold]", id="welcome-text")

            yield Static(
                "A Policy-Aware Terminal Interface for AI-Assisted Development",
                id="welcome-subtitle",
            )

            with Vertical():
                with Horizontal():
                    yield Button("Start Chat", id="btn-chat", variant="primary")
                    yield Button("Settings", id="btn-settings", variant="default")
                    yield Button("View Models", id="btn-models", variant="default")

                yield Static(
                    "Press 'c' for Chat, 's' for Settings, or 'q' to quit",
                    id="help-text",
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
