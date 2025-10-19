"""Settings modal for configuring the ADH CLI application."""

from pathlib import Path
from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, Switch
from textual.binding import Binding

from ..config.models import ModelRegistry
from ..config.settings_manager import (
    load_config_data,
    set_settings,
    DEFAULT_THEME,
)


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
        with Container(classes="form-constrained"):
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

                # Theme Selection (all built-in Textual themes)
                yield Label("Theme:")
                yield Select(
                    options=[
                        ("Textual Dark", "textual-dark"),
                        ("Textual Light", "textual-light"),
                        ("Nord", "nord"),
                        ("Gruvbox", "gruvbox"),
                        ("Dracula", "dracula"),
                        ("Tokyo Night", "tokyo-night"),
                        ("Catppuccin Mocha", "catppuccin-mocha"),
                        ("Catppuccin Latte", "catppuccin-latte"),
                        ("Monokai", "monokai"),
                        ("Solarized Light", "solarized-light"),
                        ("Flexoki", "flexoki"),
                        ("Textual ANSI", "textual-ansi"),
                    ],
                    id="theme-select",
                    value=DEFAULT_THEME,
                )

                # REMOVED: Dark Mode Switch
                # with Horizontal():
                #     yield Label("Dark Mode:")
                #     yield Switch(value=True, id="dark-mode-switch")

                with Horizontal():
                    yield Label("Auto-scroll:")
                    yield Switch(value=True, id="auto-scroll-switch")

            # Fixed-action buttons docked to modal bottom
            with Horizontal(id="button-container"):
                yield Button("Save", id="btn-save", variant="primary")
                yield Button("Reset", id="btn-reset", variant="warning")
                yield Button("Close", id="btn-close", variant="default")

    @on(Select.Changed, "#theme-select")
    def on_theme_select_changed(self, event: Select.Changed) -> None:
        """Apply the selected theme immediately (theme property setter handles persistence)."""
        selected_theme = event.value
        previous_theme = self.app.theme

        try:
            # Setting theme property automatically applies and saves
            self.app.theme = selected_theme
        except (IOError, OSError) as e:
            # Rollback on failure
            self.app.theme = previous_theme
            self.query_one("#theme-select", Select).value = previous_theme
            self.app.notify(f"Failed to save theme setting: {e}", severity="error")

    @on(Button.Pressed, "#btn-save")
    def on_save_pressed(self) -> None:
        """Save settings (excluding theme, which is saved on change)."""
        api_key = self.query_one("#api-key-input", Input).value
        model = self.query_one("#model-select", Select).value
        valid, error = ModelRegistry.validate_model_id(model)
        if not valid:
            self.notify(error or "Invalid model selected", severity="error")
            return
        orchestrator_agent = self.query_one("#orchestrator-select", Select).value

        # Prepare updates dictionary
        updates = {
            "api_key": api_key,
            "model": model,
            "orchestrator_agent": orchestrator_agent,
        }

        # Use the new centralized settings manager to save all updated values
        set_settings(updates)  # <--- MODIFIED SAVE LOGIC

        self.notify(
            "Settings saved successfully! Restart required for agent change.",
            severity="information",
        )
        self.dismiss()

    @on(Button.Pressed, "#btn-reset")
    def on_reset_pressed(self) -> None:
        """Reset settings to defaults and save them."""
        # Reset form fields
        self.query_one("#api-key-input", Input).value = ""
        self.query_one("#model-select", Select).value = ModelRegistry.DEFAULT.id
        self.query_one("#orchestrator-select", Select).value = "orchestrator"
        self.query_one("#theme-select", Select).value = DEFAULT_THEME

        # Save the reset theme persistently (theme select handler will trigger)
        # No need to manually save theme here - the Select.Changed event will fire

        self.notify("Settings reset to defaults", severity="warning")

    @on(Button.Pressed, "#btn-close")
    def on_close_pressed(self) -> None:
        """Close the modal."""
        self.dismiss()

    # REMOVED: The obsolete @on(Switch.Changed, "#dark-mode-switch") handler

    def on_mount(self) -> None:
        """Load existing settings when modal is mounted."""
        # Use the new manager to load all settings
        settings = load_config_data()  # <--- MODIFIED

        if settings:
            # Load API Key
            if "api_key" in settings:
                self.query_one("#api-key-input", Input).value = settings["api_key"]

            # Load Model
            if "model" in settings:
                model_value = settings["model"]
                model_config = ModelRegistry.get_by_id(model_value)
                if model_config:
                    try:
                        self.query_one("#model-select", Select).value = model_config.id
                    except Exception as exc:
                        self.app.log.warning(
                            "Failed to set model select value on mount: %s",
                            exc,
                        )

            # Load Orchestrator Agent
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

            # --- NEW: Load Theme Select ---
            if "theme" in settings:
                try:
                    # Set the select widget value to the saved theme
                    self.query_one("#theme-select", Select).value = settings["theme"]
                except Exception as exc:
                    self.app.log.warning(
                        "Failed to set theme select value on mount: %s",
                        exc,
                    )
            # --- END NEW ---
