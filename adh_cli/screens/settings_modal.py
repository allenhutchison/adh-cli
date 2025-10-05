"""Settings modal for configuring the ADH CLI application."""

import json
from pathlib import Path
from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, Switch
from textual.binding import Binding

from ..core.config_paths import ConfigPaths


class SettingsModal(ModalScreen):
    """Settings configuration modal."""

    def _discover_agents(self):
        """Discover available agents from the agents directory.

        Returns:
            List of agent names
        """
        agents_dir = Path(__file__).parent.parent / "agents"
        agents = []

        if agents_dir.exists():
            for agent_path in agents_dir.iterdir():
                # Check if it's a directory and has an agent.md file
                if agent_path.is_dir() and (agent_path / "agent.md").exists():
                    agents.append(agent_path.name)

        # Sort alphabetically and ensure orchestrator is first if it exists
        agents.sort()
        if "orchestrator" in agents:
            agents.remove("orchestrator")
            agents.insert(0, "orchestrator")

        return agents if agents else ["orchestrator"]

    DEFAULT_CSS = """
    SettingsModal {
        align: center middle;
    }

    SettingsModal > Container {
        background: $surface;
        /* Neutral frame for consistency with chat transcript */
        border: solid $border;
        padding: 2;
        width: 70;
        max-width: $form-max-width;
        max-height: 80%;
        overflow: hidden;
    }

    #settings-title {
        text-align: center;
        margin-bottom: 2;
        text-style: bold;
        color: $text-primary;
    }

    SettingsModal Label {
        color: $text-primary;
        margin-top: 1;
    }

    SettingsModal Input {
        border: solid $border;
        margin-bottom: 1;
        width: 100%;
        background: $panel;
        color: $text-primary;
    }

    SettingsModal Input:focus {
        border: solid $border-focus;
    }

    SettingsModal Select {
        margin-bottom: 1;
        width: 100%;
    }

    /* In horizontal rows, make the field fill remaining space */
    SettingsModal Horizontal > Input,
    SettingsModal Horizontal > Select,
    SettingsModal Horizontal > Switch {
        width: 1fr;
        margin-left: 1;
    }

    /* Ensure labels in horizontal rows are visible and readable */
    SettingsModal Horizontal {
        height: auto;
    }

    SettingsModal Horizontal > Label {
        width: 24;
        min-width: 16;
        color: $text-primary;
    }

    /* Scroll area for main form content */
    #settings-scroll {
        height: 1fr;
        width: 100%;
        padding-right: 1;
    }

    #button-container {
        dock: bottom;
        align: center middle;
        height: 3;
        padding-top: 1;
    }

    #button-container Button {
        margin: 0 1;
        min-width: 12;
    }
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Close"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets for the settings modal."""
        with Container():
            yield Static("Settings", id="settings-title")

            # Scrollable content area
            with VerticalScroll(id="settings-scroll"):
                yield Label("API Configuration")

                yield Label("Google API Key:")
                yield Input(
                    placeholder="Enter your Google API key",
                    password=True,
                    id="api-key-input",
                )

                yield Label("\nModel Selection:")
                yield Select.from_values(
                    [
                        "Gemini Flash Latest",
                        "Gemini Flash Lite Latest",
                        "Gemini 2.5 Pro",
                    ],
                    id="model-select",
                )

                yield Label("\nOrchestrator Agent:")
                # Discover and populate agent list
                available_agents = self._discover_agents()
                yield Select.from_values(available_agents, id="orchestrator-select")

                yield Label("\nGeneration Parameters")

                with Horizontal():
                    yield Label("Temperature (0.0-1.0):")
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

            # Fixed-action buttons docked to modal bottom
            with Horizontal(id="button-container"):
                yield Button("Save", id="btn-save", variant="primary")
                yield Button("Reset", id="btn-reset", variant="warning")
                yield Button("Close", id="btn-close", variant="default")

    @on(Button.Pressed, "#btn-save")
    def on_save_pressed(self) -> None:
        """Save settings."""
        api_key = self.query_one("#api-key-input", Input).value
        selected_option = self.query_one("#model-select", Select).value
        # Map display text to actual model string
        model_map = {
            "Gemini Flash Latest": "gemini-flash-latest",
            "Gemini Flash Lite Latest": "gemini-flash-lite-latest",
            "Gemini 2.5 Pro": "gemini-2.5-pro",
        }
        model = model_map.get(selected_option, "gemini-flash-latest")
        orchestrator_agent = self.query_one("#orchestrator-select", Select).value
        temperature = self.query_one("#temperature-input", Input).value
        max_tokens = self.query_one("#max-tokens-input", Input).value
        top_p = self.query_one("#top-p-input", Input).value
        top_k = self.query_one("#top-k-input", Input).value

        settings = {
            "api_key": api_key,
            "model": model,
            "orchestrator_agent": orchestrator_agent,
            "temperature": float(temperature) if temperature else 0.7,
            "max_tokens": int(max_tokens) if max_tokens else 2048,
            "top_p": float(top_p) if top_p else 0.95,
            "top_k": int(top_k) if top_k else 40,
        }

        config_file = ConfigPaths.get_config_file()
        with open(config_file, "w") as f:
            json.dump(settings, f, indent=2)

        self.notify(
            "Settings saved successfully! Restart required for agent change.",
            severity="information",
        )
        self.dismiss()

    @on(Button.Pressed, "#btn-reset")
    def on_reset_pressed(self) -> None:
        """Reset settings to defaults."""
        self.query_one("#api-key-input", Input).value = ""
        self.query_one("#model-select", Select).value = "Gemini Flash Latest"
        self.query_one("#orchestrator-select", Select).value = "orchestrator"
        self.query_one("#temperature-input", Input).value = "0.7"
        self.query_one("#max-tokens-input", Input).value = "2048"
        self.query_one("#top-p-input", Input).value = "0.95"
        self.query_one("#top-k-input", Input).value = "40"
        self.notify("Settings reset to defaults", severity="warning")

    @on(Button.Pressed, "#btn-close")
    def on_close_pressed(self) -> None:
        """Close the modal."""
        self.dismiss()

    @on(Switch.Changed, "#dark-mode-switch")
    def on_dark_mode_changed(self, event: Switch.Changed) -> None:
        """Toggle dark mode."""
        self.app.theme = "adh-dark" if event.value else "adh-light"

    def on_mount(self) -> None:
        """Load existing settings when modal is mounted."""
        config_path = ConfigPaths.get_config_file()
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    settings = json.load(f)

                if "api_key" in settings:
                    self.query_one("#api-key-input", Input).value = settings["api_key"]
                if "model" in settings:
                    # Find the display text for the saved model value
                    model_value = settings["model"]
                    reverse_map = {
                        "gemini-flash-latest": "Gemini Flash Latest",
                        "gemini-flash-lite-latest": "Gemini Flash Lite Latest",
                        "gemini-2.5-pro": "Gemini 2.5 Pro",
                    }
                    if model_value in reverse_map:
                        try:
                            self.query_one("#model-select", Select).value = reverse_map[
                                model_value
                            ]
                        except Exception:
                            # If setting the value fails, just skip it
                            pass
                if "orchestrator_agent" in settings:
                    try:
                        self.query_one("#orchestrator-select", Select).value = settings[
                            "orchestrator_agent"
                        ]
                    except Exception:
                        # If setting the value fails (agent not found), use default
                        pass
                if "temperature" in settings:
                    self.query_one("#temperature-input", Input).value = str(
                        settings["temperature"]
                    )
                if "max_tokens" in settings:
                    self.query_one("#max-tokens-input", Input).value = str(
                        settings["max_tokens"]
                    )
                if "top_p" in settings:
                    self.query_one("#top-p-input", Input).value = str(settings["top_p"])
                if "top_k" in settings:
                    self.query_one("#top-k-input", Input).value = str(settings["top_k"])
            except Exception:
                pass
