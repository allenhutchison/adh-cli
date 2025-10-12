"""Confirmation dialog for policy-enforced tool execution."""

from typing import Optional, Dict, Any, Callable
from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Label
from textual.widget import Widget
from rich.text import Text

from adh_cli.policies.policy_types import PolicyDecision, SupervisionLevel


class ConfirmationDialog(ModalScreen):
    """Modal dialog for tool execution confirmation."""

    DEFAULT_CSS = """
    ConfirmationDialog {
        align: center middle;
    }

    ConfirmationDialog > Container {
        width: 80%;
        max-width: 100;
        height: auto;
        max-height: 80%;
        background: $surface;
        /* Neutral frame; rely on badges and buttons for emphasis */
        border: solid $border;
        padding: 2;
    }

    ConfirmationDialog .title {
        text-align: center;
        text-style: bold;
        color: $text-primary;
        margin-bottom: 1;
    }

    ConfirmationDialog .risk-badge {
        text-align: center;
        width: auto;
        padding: 0 2;
        margin-bottom: 1;
        text-style: bold;
    }

    ConfirmationDialog .risk-low {
        background: $risk-low;
        color: $text-on-success;
    }

    ConfirmationDialog .risk-medium {
        background: $risk-medium;
        color: $text-on-warning;
    }

    ConfirmationDialog .risk-high {
        background: $risk-high;
        color: $text-on-error;
    }

    ConfirmationDialog .risk-critical {
        background: $risk-critical;
        color: $text-on-error;
        text-style: bold;
    }

    ConfirmationDialog .details {
        margin: 1 0;
        height: auto;
        max-height: 20;
        overflow-y: auto;
        color: $text-secondary;
    }

    ConfirmationDialog .button-container {
        dock: bottom;
        height: 3;
        margin-top: 2;
        align: center middle;
    }

    ConfirmationDialog Button {
        margin: 0 1;
        min-width: 16;
    }
    """

    def __init__(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        decision: PolicyDecision,
        callback: Optional[Callable] = None,
        **kwargs,
    ):
        """Initialize confirmation dialog.

        Args:
            tool_name: Name of tool requesting confirmation
            parameters: Tool parameters
            decision: Policy decision requiring confirmation
            callback: Callback function with confirmation result
        """
        super().__init__(**kwargs)
        self.tool_name = tool_name
        self.parameters = parameters
        self.decision = decision
        self.callback = callback
        self.result = False

    def compose(self) -> ComposeResult:
        """Compose the dialog layout."""
        with Container():
            # Title
            yield Label(f"⚠️ Confirmation Required: {self.tool_name}", classes="title")

            # Risk level badge
            risk_class = f"risk-{self.decision.risk_level.value}"
            yield Label(
                f"Risk Level: {self.decision.risk_level.value.upper()}",
                classes=f"risk-badge {risk_class}",
            )

            # Decision details
            with Vertical(classes="details"):
                # Supervision level
                yield Static(
                    f"[bold]Supervision:[/bold] {self.decision.supervision_level.value}"
                )

                # Custom confirmation message
                if self.decision.confirmation_message:
                    yield Static("")
                    # Disable markup for user-controlled content
                    yield Static(self.decision.confirmation_message, markup=False)

                # Parameters
                if self.parameters:
                    yield Static("")
                    yield Static("[bold]Parameters:[/bold]")
                    for key, value in self.parameters.items():
                        # Disable markup for parameter values to avoid parse errors
                        # with complex object representations
                        yield Static(f"  • {key}: {value}", markup=False)

                # Safety checks
                if self.decision.safety_checks:
                    yield Static("")
                    yield Static("[bold]Safety Checks:[/bold]")
                    for check in self.decision.safety_checks:
                        yield Static(f"  ✓ {check.name}")

                # Restrictions
                if self.decision.restrictions:
                    yield Static("")
                    yield Static("[bold]Restrictions:[/bold]")
                    for restriction in self.decision.restrictions:
                        yield Static(f"  • {restriction.type.value}")

            # Buttons
            with Horizontal(classes="button-container"):
                yield Button("Confirm", variant="primary", id="confirm")
                yield Button("Cancel", variant="default", id="cancel")
                if self.decision.supervision_level == SupervisionLevel.MANUAL:
                    yield Button("Modify", variant="warning", id="modify")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "confirm":
            self.result = True
            if self.callback:
                await self.callback(True)
            self.dismiss(True)
        elif event.button.id == "cancel":
            self.result = False
            if self.callback:
                await self.callback(False)
            self.dismiss(False)
        elif event.button.id == "modify":
            # TODO: Implement parameter modification screen
            self.dismiss(None)


class PolicyNotification(Widget):
    """Widget for displaying policy notifications."""

    DEFAULT_CSS = """
    PolicyNotification {
        height: auto;
        margin: 1 0;
        padding: 1 2;
        border: solid $border;
        background: $panel;
    }

    PolicyNotification.info {
        background: $primary-lighten-2;
        border: solid $primary;
        color: $text-on-primary;
    }

    PolicyNotification.warning {
        background: $warning-lighten-2;
        border: solid $warning;
        color: $text-on-warning;
    }

    PolicyNotification.error {
        background: $error-lighten-2;
        border: solid $error;
        color: $text-on-error;
    }

    PolicyNotification.success {
        background: $success-lighten-2;
        border: solid $success;
        color: $text-on-success;
    }
    """

    def __init__(self, message: str, level: str = "info", **kwargs):
        """Initialize notification widget.

        Args:
            message: Notification message
            level: Notification level (info, warning, error, success)
        """
        super().__init__(**kwargs)
        self.message = message
        self.level = level
        self.add_class(level)

    def render(self) -> Text:
        """Render the notification."""
        icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅",
        }
        icon = icons.get(self.level, "ℹ️")
        return Text(f"{icon} {self.message}")
