"""Main application module for ADH CLI."""

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Welcome

from .screens.main_screen import MainScreen
from .screens.chat_screen import ChatScreen
from .screens.settings_screen import SettingsScreen


class ADHApp(App):
    """Main ADH CLI TUI Application."""

    CSS = """
    Screen {
        background: $surface;
    }

    .container {
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("d", "toggle_dark", "Toggle Dark Mode"),
        Binding("s", "show_settings", "Settings"),
    ]

    SCREENS = {
        "main": MainScreen,
        "chat": ChatScreen,
        "settings": SettingsScreen,
    }

    TITLE = "ADH CLI - Google ADK TUI"
    SUB_TITLE = "Powered by Textual"

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app after mounting."""
        self.push_screen("chat")

    def action_show_settings(self) -> None:
        """Show settings as a modal."""
        from .screens.settings_modal import SettingsModal
        self.push_screen(SettingsModal())

    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.theme = "textual-dark" if self.theme == "textual-light" else "textual-light"