"""Confirmation dialog for policy-enforced tool execution."""

from typing import Optional, Dict, Any, Callable
from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Label, RichLog
from textual.widget import Widget
from rich.text import Text
from rich.panel import Panel
from rich.table import Table

from adh_cli.policies.policy_types import PolicyDecision, RiskLevel, SupervisionLevel


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
        border: thick $primary;
        padding: 1 2;
    }

    ConfirmationDialog .title {
        text-align: center;
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    ConfirmationDialog .risk-badge {
        text-align: center;
        width: auto;
        padding: 0 1;
        margin-bottom: 1;
    }

    ConfirmationDialog .risk-low {
        background: $success;
        color: $text;
    }

    ConfirmationDialog .risk-medium {
        background: $warning;
        color: $text;
    }

    ConfirmationDialog .risk-high {
        background: $error;
        color: $text;
    }

    ConfirmationDialog .risk-critical {
        background: $error;
        color: $text;
        text-style: bold;
    }

    ConfirmationDialog .details {
        margin: 1 0;
        height: auto;
        max-height: 20;
        overflow-y: auto;
    }

    ConfirmationDialog .button-container {
        dock: bottom;
        height: 3;
        margin-top: 1;
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
        **kwargs
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
            yield Label(
                f"⚠️ Confirmation Required: {self.tool_name}",
                classes="title"
            )

            # Risk level badge
            risk_class = f"risk-{self.decision.risk_level.value}"
            yield Label(
                f"Risk Level: {self.decision.risk_level.value.upper()}",
                classes=f"risk-badge {risk_class}"
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
                    yield Static(self.decision.confirmation_message)

                # Parameters
                if self.parameters:
                    yield Static("")
                    yield Static("[bold]Parameters:[/bold]")
                    for key, value in self.parameters.items():
                        yield Static(f"  • {key}: {value}")

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


class SafetyWarningDialog(ModalScreen):
    """Dialog for displaying safety warnings."""

    DEFAULT_CSS = """
    SafetyWarningDialog {
        align: center middle;
    }

    SafetyWarningDialog > Container {
        width: 80%;
        max-width: 100;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $warning;
        padding: 1 2;
    }

    SafetyWarningDialog .title {
        text-align: center;
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }

    SafetyWarningDialog .warnings {
        margin: 1 0;
        height: auto;
        max-height: 20;
        overflow-y: auto;
    }

    SafetyWarningDialog .warning-item {
        margin: 0.5 0;
        padding: 0.5 1;
        background: $warning-light;
        border-left: thick $warning;
    }

    SafetyWarningDialog Button {
        margin: 0 1;
        min-width: 16;
    }
    """

    def __init__(
        self,
        warnings: list,
        callback: Optional[Callable] = None,
        **kwargs
    ):
        """Initialize safety warning dialog.

        Args:
            warnings: List of safety warnings
            callback: Callback function with user decision
        """
        super().__init__(**kwargs)
        self.warnings = warnings
        self.callback = callback

    def compose(self) -> ComposeResult:
        """Compose the dialog layout."""
        with Container():
            yield Label("⚠️ Safety Warnings Detected", classes="title")

            with Vertical(classes="warnings"):
                for warning in self.warnings:
                    with Container(classes="warning-item"):
                        yield Static(f"[bold]{warning.checker_name}[/bold]")
                        yield Static(warning.message)
                        if warning.risk_level:
                            yield Static(
                                f"Risk: {warning.risk_level.value}",
                                classes=f"risk-{warning.risk_level.value}"
                            )

            with Horizontal(classes="button-container"):
                yield Button("Override & Continue", variant="warning", id="override")
                yield Button("Cancel", variant="default", id="cancel")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "override":
            if self.callback:
                await self.callback(True)
            self.dismiss(True)
        else:
            if self.callback:
                await self.callback(False)
            self.dismiss(False)


class PolicyNotification(Widget):
    """Widget for displaying policy notifications."""

    DEFAULT_CSS = """
    PolicyNotification {
        height: 3;
        margin: 1 0;
        padding: 0 1;
        background: $primary-lighten-2;
        border: tall $primary;
    }

    PolicyNotification.info {
        background: $primary-lighten-2;
        border: tall $primary;
    }

    PolicyNotification.warning {
        background: $warning-lighten-2;
        border: tall $warning;
    }

    PolicyNotification.error {
        background: $error-lighten-2;
        border: tall $error;
    }

    PolicyNotification.success {
        background: $success-lighten-2;
        border: tall $success;
    }
    """

    def __init__(
        self,
        message: str,
        level: str = "info",
        **kwargs
    ):
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