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
from ..config.models import ModelRegistry


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
        max-width: 80;
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
        border: solid $primary;
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
                yield Select(
                    options=ModelRegistry.ui_options(),
                    id="model-select",
                    value=ModelRegistry.DEFAULT.id,
                )

                yield Label("\nOrchestrator Agent:")
                # Discover and populate agent list
                available_agents = self._discover_agents()
                yield Select.from_values(available_agents, id="orchestrator-select")

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
        model = self.query_one("#model-select", Select).value
        valid, error = ModelRegistry.validate_model_id(model)
        if not valid:
            self.notify(error or "Invalid model selected", severity="error")
            return
        orchestrator_agent = self.query_one("#orchestrator-select", Select).value

        settings = {
            "api_key": api_key,
            "model": model,
            "orchestrator_agent": orchestrator_agent,
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
        self.query_one("#model-select", Select).value = ModelRegistry.DEFAULT.id
        self.query_one("#orchestrator-select", Select).value = "orchestrator"
        self.notify("Settings reset to defaults", severity="warning")

    @on(Button.Pressed, "#btn-close")
    def on_close_pressed(self) -> None:
        """Close the modal."""
        self.dismiss()

    @on(Switch.Changed, "#dark-mode-switch")
    def on_dark_mode_changed(self, event: Switch.Changed) -> None:
        """Toggle dark mode."""
        self.app.theme = "textual-dark" if event.value else "textual-light"

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
                    model_value = settings["model"]
                    model_config = ModelRegistry.get_by_id(model_value)
                    if model_config:
                        try:
                            self.query_one(
                                "#model-select", Select
                            ).value = model_config.id
                        except Exception as exc:
                            self.app.log.warning(
                                "Failed to set model select value on mount: %s",
                                exc,
                            )
                if "orchestrator_agent" in settings:
                    try:
                        self.query_one("#orchestrator-select", Select).value = settings[
                            "orchestrator_agent"
                        ]
                    except Exception as exc:
                        # If setting the value fails (agent not found), use default
                        self.app.log.warning(
                            "Failed to set orchestrator select value on mount: %s",
                            exc,
                        )
            except Exception as exc:
                self.app.log.warning("Failed to load settings on mount: %s", exc)
