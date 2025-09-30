"""Textual widget for displaying tool execution state and handling confirmations."""

from typing import Optional, Callable
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static, Button
from textual.reactive import reactive
from rich.text import Text

from adh_cli.ui.tool_execution import (
    ToolExecutionInfo,
    ToolExecutionState,
    format_parameters_inline,
    format_parameters_expanded,
)
from adh_cli.policies.policy_types import RiskLevel


class ToolExecutionWidget(Widget):
    """Widget for displaying tool execution status and handling confirmations.

    This widget displays tool execution information in various states:
    - Compact display for automatic/executing tools
    - Inline confirmation for low/medium risk operations
    - Expanded details view when requested
    - Success/failure status when complete
    """

    DEFAULT_CSS = """
    ToolExecutionWidget {
        height: auto;
        margin: 0 0 1 0;
        padding: 1 2;
        border: solid $primary;
        background: $surface;
    }

    ToolExecutionWidget.executing {
        border: solid $accent;
        background: $accent-lighten-3;
    }

    ToolExecutionWidget.confirming {
        border: solid $warning;
        background: $warning-lighten-3;
    }

    ToolExecutionWidget.success {
        border: solid $success;
        background: $success-lighten-3;
    }

    ToolExecutionWidget.failed {
        border: solid $error;
        background: $error-lighten-3;
    }

    ToolExecutionWidget.blocked {
        border: solid $error;
        background: $error-lighten-2;
    }

    ToolExecutionWidget .header {
        width: 100%;
        height: 1;
    }

    ToolExecutionWidget .params-compact {
        width: 100%;
        height: auto;
        color: $text-muted;
        margin-top: 0;
    }

    ToolExecutionWidget .params-expanded {
        width: 100%;
        height: auto;
        margin-top: 1;
        padding: 0 2;
    }

    ToolExecutionWidget .button-container {
        width: 100%;
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    ToolExecutionWidget Button {
        margin: 0 1;
        min-width: 12;
    }

    ToolExecutionWidget .risk-badge {
        color: $text;
        text-style: bold;
    }

    ToolExecutionWidget .risk-badge-low {
        color: $success;
    }

    ToolExecutionWidget .risk-badge-medium {
        color: $warning;
    }

    ToolExecutionWidget .risk-badge-high {
        color: $error;
    }

    ToolExecutionWidget .risk-badge-critical {
        color: $error;
        text-style: bold;
    }
    """

    # Reactive properties
    execution_info = reactive(None)
    expanded = reactive(False)

    def __init__(
        self,
        execution_info: ToolExecutionInfo,
        on_confirm: Optional[Callable] = None,
        on_cancel: Optional[Callable] = None,
        on_details: Optional[Callable] = None,
        **kwargs
    ):
        """Initialize tool execution widget.

        Args:
            execution_info: Tool execution information to display
            on_confirm: Callback when user confirms (async callable)
            on_cancel: Callback when user cancels (async callable)
            on_details: Callback when user requests details (async callable)
        """
        super().__init__(**kwargs)
        self._info = execution_info  # Store internally before widget is mounted
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.on_details = on_details
        self.expanded = False

    def compose(self) -> ComposeResult:
        """Compose the widget layout."""
        with Container():
            yield Static(id="header", classes="header")
            yield Static(id="params", classes="params-compact")

            # Confirmation buttons (only shown when confirming)
            with Horizontal(id="button-container", classes="button-container"):
                yield Button("✓ Confirm", variant="primary", id="confirm-btn")
                yield Button("✗ Cancel", variant="default", id="cancel-btn")
                yield Button("📋 Details", variant="default", id="details-btn")

    def on_mount(self) -> None:
        """Handle widget mount."""
        # Set reactive property now that widget is mounted
        self.execution_info = self._info
        self._update_display()

    def watch_execution_info(self, new_info: ToolExecutionInfo) -> None:
        """React to execution info changes."""
        # Update internal storage
        if new_info:
            self._info = new_info
        self._update_display()

    def watch_expanded(self, is_expanded: bool) -> None:
        """React to expanded state changes."""
        self._update_display()

    def get_execution_info(self) -> Optional[ToolExecutionInfo]:
        """Get current execution info.

        Returns info whether widget is mounted or not.

        Returns:
            Current execution information
        """
        return self.execution_info if self.is_mounted else self._info

    def _update_display(self) -> None:
        """Update the widget display based on current state."""
        if not self._info or not self.is_mounted:
            return

        info = self._info

        # Update CSS classes for state
        self.remove_class("executing", "confirming", "success", "failed", "blocked")
        if info.state == ToolExecutionState.EXECUTING:
            self.add_class("executing")
        elif info.state == ToolExecutionState.CONFIRMING:
            self.add_class("confirming")
        elif info.state == ToolExecutionState.SUCCESS:
            self.add_class("success")
        elif info.state == ToolExecutionState.FAILED:
            self.add_class("failed")
        elif info.state == ToolExecutionState.BLOCKED:
            self.add_class("blocked")

        # Update header
        self._update_header()

        # Update parameters display
        self._update_parameters()

        # Update button visibility
        self._update_buttons()

    def _update_header(self) -> None:
        """Update the header display."""
        info = self.execution_info
        header = self.query_one("#header", Static)

        # Build header text
        parts = []

        # Icon and tool name
        parts.append(f"{info.status_icon} {info.tool_name}")

        # Risk badge (if confirming)
        if info.state == ToolExecutionState.CONFIRMING and info.policy_decision:
            risk = info.policy_decision.risk_level
            risk_class = f"risk-badge-{risk.value}"
            risk_text = Text()
            risk_text.append(" " * 10)  # Padding
            risk_text.append(f"Risk: {risk.value.upper()}", style=risk_class)
            parts.append(risk_text.plain)

        # Status
        parts.append(f"[{info.status_text}]")

        header.update(" ".join(parts))

    def _update_parameters(self) -> None:
        """Update parameter display."""
        info = self.execution_info
        params_widget = self.query_one("#params", Static)

        if not info.parameters:
            params_widget.update("")
            params_widget.display = False
            return

        params_widget.display = True

        if self.expanded:
            # Expanded view
            params_widget.remove_class("params-compact")
            params_widget.add_class("params-expanded")

            formatted = format_parameters_expanded(info.parameters, max_value_length=200)
            lines = ["[bold]Parameters:[/bold]"]
            for key, value, original_len in formatted:
                lines.append(f"  • {key}: {value}")

            # Add safety checks if available
            if info.policy_decision and info.policy_decision.safety_checks:
                lines.append("")
                lines.append("[bold]Safety Checks:[/bold]")
                for check in info.policy_decision.safety_checks:
                    lines.append(f"  ✓ {check.name}")

            params_widget.update("\n".join(lines))
        else:
            # Compact view
            params_widget.remove_class("params-expanded")
            params_widget.add_class("params-compact")

            inline = format_parameters_inline(info.parameters, max_params=3, max_value_length=50)
            params_widget.update(inline)

    def _update_buttons(self) -> None:
        """Update button visibility and state."""
        info = self.execution_info
        button_container = self.query_one("#button-container", Horizontal)

        # Only show buttons when confirming
        if info.state == ToolExecutionState.CONFIRMING and info.requires_confirmation:
            button_container.display = True

            # Update details button text
            details_btn = self.query_one("#details-btn", Button)
            if self.expanded:
                details_btn.label = "▲ Collapse"
            else:
                details_btn.label = "📋 Details"
        else:
            button_container.display = False

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "confirm-btn":
            if self.on_confirm:
                await self.on_confirm(self.execution_info)
        elif event.button.id == "cancel-btn":
            if self.on_cancel:
                await self.on_cancel(self.execution_info)
        elif event.button.id == "details-btn":
            # Toggle expanded state
            self.expanded = not self.expanded
            if self.on_details:
                await self.on_details(self.execution_info, self.expanded)

    def update_info(self, execution_info: ToolExecutionInfo) -> None:
        """Update the execution info and refresh display.

        Args:
            execution_info: New execution information
        """
        self.execution_info = execution_info

    def set_expanded(self, expanded: bool) -> None:
        """Set the expanded state.

        Args:
            expanded: Whether to show expanded details
        """
        self.expanded = expanded