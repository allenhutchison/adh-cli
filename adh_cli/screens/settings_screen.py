"""Settings screen for configuring the ADH CLI application."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Select, Static, Switch
from textual.binding import Binding


class SettingsScreen(Screen):
    """Settings configuration screen."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    MODEL_OPTIONS = [
        ("Gemini Flash Latest", "gemini-flash-latest"),
        ("Gemini Flash Lite Latest", "gemini-flash-lite-latest"),
        ("Gemini 2.5 Pro", "gemini-2.5-pro"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets for the settings screen."""
        with Container(classes="container"):
            yield Static("[bold]Settings[/bold]", id="settings-title")

            with Vertical():
                yield Label("API Configuration")

                yield Label("Google API Key:")
                yield Input(
                    placeholder="Enter your Google API key",
                    password=True,
                    id="api-key-input"
                )

                yield Label("\nModel Selection:")
                yield Select(
                    options=self.MODEL_OPTIONS,
                    value="models/gemini-2.0-flash-exp",
                    id="model-select"
                )

                yield Label("\nGeneration Parameters")

                with Horizontal():
                    yield Label("Temperature (0.0 - 1.0):")
                    yield Input(value="0.7", id="temperature-input")

                with Horizontal():
                    yield Label("Max Tokens:")
                    yield Input(value="2048", id="max-tokens-input")

                with Horizontal():
                    yield Label("Top P:")
                    yield Input(value="0.95", id="top-p-input")

                with Horizontal():
                    yield Label("Top K:")
                    yield Input(value="40", id="top-k-input")

                yield Label("\nInterface Settings")

                with Horizontal():
                    yield Label("Dark Mode:")
                    yield Switch(value=True, id="dark-mode-switch")

                with Horizontal():
                    yield Label("Auto-scroll:")
                    yield Switch(value=True, id="auto-scroll-switch")

                with Horizontal(id="button-container"):
                    yield Button("Save", id="btn-save", variant="primary")
                    yield Button("Reset", id="btn-reset", variant="warning")
                    yield Button("Back", id="btn-back", variant="default")

    @on(Button.Pressed, "#btn-save")
    def on_save_pressed(self) -> None:
        """Save settings."""
        api_key = self.query_one("#api-key-input", Input).value
        model = self.query_one("#model-select", Select).value
        temperature = self.query_one("#temperature-input", Input).value
        max_tokens = self.query_one("#max-tokens-input", Input).value
        top_p = self.query_one("#top-p-input", Input).value
        top_k = self.query_one("#top-k-input", Input).value

        import json
        import os

        settings = {
            "api_key": api_key,
            "model": model,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
            "top_p": float(top_p),
            "top_k": int(top_k),
        }

        config_dir = os.path.expanduser("~/.config/adh-cli")
        os.makedirs(config_dir, exist_ok=True)

        with open(os.path.join(config_dir, "config.json"), "w") as f:
            json.dump(settings, f, indent=2)

        self.notify("Settings saved successfully!", severity="information")

    @on(Button.Pressed, "#btn-reset")
    def on_reset_pressed(self) -> None:
        """Reset settings to defaults."""
        self.query_one("#api-key-input", Input).value = ""
        self.query_one("#model-select", Select).value = "models/gemini-2.0-flash-exp"
        self.query_one("#temperature-input", Input).value = "0.7"
        self.query_one("#max-tokens-input", Input).value = "2048"
        self.query_one("#top-p-input", Input).value = "0.95"
        self.query_one("#top-k-input", Input).value = "40"
        self.notify("Settings reset to defaults", severity="warning")

    @on(Button.Pressed, "#btn-back")
    def on_back_pressed(self) -> None:
        """Go back to the main screen."""
        self.app.pop_screen()

    @on(Switch.Changed, "#dark-mode-switch")
    def on_dark_mode_changed(self, event: Switch.Changed) -> None:
        """Toggle dark mode."""
        self.app.theme = "textual-dark" if event.value else "textual-light"

    def on_mount(self) -> None:
        """Load existing settings when screen is mounted."""
        import json
        import os

        config_path = os.path.expanduser("~/.config/adh-cli/config.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                settings = json.load(f)

            if "api_key" in settings:
                self.query_one("#api-key-input", Input).value = settings["api_key"]
            if "model" in settings:
                self.query_one("#model-select", Select).value = settings["model"]
            if "temperature" in settings:
                self.query_one("#temperature-input", Input).value = str(settings["temperature"])
            if "max_tokens" in settings:
                self.query_one("#max-tokens-input", Input).value = str(settings["max_tokens"])
            if "top_p" in settings:
                self.query_one("#top-p-input", Input).value = str(settings["top_p"])
            if "top_k" in settings:
                self.query_one("#top-k-input", Input).value = str(settings["top_k"])