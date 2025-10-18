"""Textual widget for displaying tool execution state and handling confirmations."""

from typing import Optional, Callable
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widget import Widget
from textual.widgets import Static, Button
from rich.text import Text

from adh_cli.ui.tool_execution import (
    ToolExecutionInfo,
    ToolExecutionState,
    format_parameters_inline,
    format_parameters_expanded,
    get_tool_context_summary,
)


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
        border: solid $border;
        background: $surface;
    }

    ToolExecutionWidget.executing {
        border: solid $border;
        border-left: tall $primary;
        background: $panel;
    }

    ToolExecutionWidget.confirming {
        border: solid $border;
        border-left: tall $warning;
        background: $panel;
    }

    ToolExecutionWidget.success {
        border: solid $border;
        border-left: tall $success;
        background: $surface;
    }

    ToolExecutionWidget.failed {
        border: solid $border;
        border-left: tall $error;
        background: $surface;
    }

    ToolExecutionWidget.blocked {
        border: solid $border;
        border-left: tall $warning;
        background: $surface;
    }

    ToolExecutionWidget #tool-content {
        width: 100%;
        height: auto;
    }

    ToolExecutionWidget .header {
        width: 100%;
        height: auto;
        color: $text-primary;
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
        color: $text-secondary;
    }

    ToolExecutionWidget .button-container {
        width: 100%;
        height: 5;
        min-height: 5;
        align: center middle;
        margin-top: 1;
        visibility: visible;
        opacity: 1.0;
    }

    ToolExecutionWidget #confirm-btn {
        margin: 0 1;
        min-width: 12;
        width: auto;
        height: 3;
        min-height: 3;
        visibility: visible;
        opacity: 1.0;
        background: $primary;
        color: $foreground;
        border: solid $primary;
        padding: 0 2;
    }

    ToolExecutionWidget #cancel-btn {
        margin: 0 1;
        min-width: 12;
        width: auto;
        height: 3;
        min-height: 3;
        visibility: visible;
        opacity: 1.0;
        background: $panel;
        color: $text-primary;
        border: solid $border;
        padding: 0 2;
    }

    ToolExecutionWidget #details-btn {
        margin: 0 1;
        min-width: 12;
        width: auto;
        height: 3;
        min-height: 3;
        visibility: visible;
        opacity: 1.0;
        background: $panel;
        color: $text-primary;
        border: solid $border;
        padding: 0 2;
    }

    ToolExecutionWidget .risk-badge {
        text-style: bold;
    }

    ToolExecutionWidget .risk-badge-low {
        color: $success;
    }

    ToolExecutionWidget .risk-badge-medium {
        color: $warning;
    }

    ToolExecutionWidget .risk-badge-high {
        color: $warning-darken-2;
    }

    ToolExecutionWidget .risk-badge-critical {
        color: $error;
        text-style: bold;
    }
    """

    def __init__(
        self,
        execution_info: ToolExecutionInfo,
        on_confirm: Optional[Callable] = None,
        on_cancel: Optional[Callable] = None,
        on_details: Optional[Callable] = None,
        **kwargs,
    ):
        """Initialize tool execution widget.

        Args:
            execution_info: Tool execution information to display
            on_confirm: Callback when user confirms (async callable)
            on_cancel: Callback when user cancels (async callable)
            on_details: Callback when user requests details (async callable)
        """
        super().__init__(**kwargs)
        self._info = execution_info
        self._expanded = False
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.on_details = on_details

    @property
    def execution_info(self) -> Optional[ToolExecutionInfo]:
        """Get current execution info."""
        return self._info

    @property
    def expanded(self) -> bool:
        """Get expanded state."""
        return self._expanded

    @expanded.setter
    def expanded(self, value: bool) -> None:
        """Set expanded state."""
        self._expanded = value
        if self.is_mounted:
            self._update_display()

    def compose(self) -> ComposeResult:
        """Compose the widget layout."""
        with Container(id="tool-content"):
            yield Static(id="header", classes="header")
            yield Static(id="params", classes="params-compact")

            # Confirmation buttons (only shown when confirming)
            with Horizontal(id="button-container", classes="button-container"):
                yield Button("✓ Confirm", variant="primary", id="confirm-btn")
                yield Button("✗ Cancel", variant="default", id="cancel-btn")
                yield Button("📋 Details", variant="default", id="details-btn")

    def on_mount(self) -> None:
        """Handle widget mount."""
        # Hide buttons initially
        button_container = self.query_one("#button-container", Horizontal)
        button_container.styles.display = "none"

        # Force update during mount (is_mounted will be False during on_mount)
        self._update_display(force=True)

    def _update_display(self, force: bool = False) -> None:
        """Update the widget display based on current state.

        Args:
            force: If True, skip the is_mounted check (for use during on_mount)
        """
        if not self._info:
            return

        if not force and not self.is_mounted:
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

        # Force refresh to apply changes
        self.refresh()

    def _update_header(self) -> None:
        """Update the header display."""
        info = self.execution_info
        header = self.query_one("#header", Static)

        # Start with icon and tool name
        header_text = f"{info.status_icon} {info.tool_name}"

        # Add contextual information (e.g., command, file path)
        context = get_tool_context_summary(info.tool_name, info.parameters)
        if context:
            header_text += f": {context}"

        # Add agent name if this is a delegated agent execution
        if info.agent_name and info.agent_name != "orchestrator":
            header_text += f" (via {info.agent_name})"

        # Risk badge (if confirming)
        if info.state == ToolExecutionState.CONFIRMING and info.policy_decision:
            risk = info.policy_decision.risk_level
            risk_class = f"risk-badge-{risk.value}"
            risk_text = Text()
            risk_text.append(" " * 10)  # Padding
            risk_text.append(f"Risk: {risk.value.upper()}", style=risk_class)
            header_text += f" {risk_text.plain}"

        # Status
        header_text += f" [{info.status_text}]"

        header.update(header_text)

    def _update_parameters(self) -> None:
        """Update parameter display."""
        info = self.execution_info
        params_widget = self.query_one("#params", Static)

        if not info.parameters:
            params_widget.update("")
            params_widget.display = False
            return

        params_widget.display = True

        # Show parameters: expanded view or compact summary
        if self.expanded or info.state == ToolExecutionState.CONFIRMING:
            # Expanded view
            params_widget.remove_class("params-compact")
            params_widget.add_class("params-expanded")

            formatted = format_parameters_expanded(
                info.parameters, max_value_length=200
            )
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
            # Always show a concise inline summary for non-expanded states
            inline = format_parameters_inline(
                info.parameters, max_params=3, max_value_length=60
            )
            params_widget.update(inline)
            params_widget.display = True

    def _update_buttons(self) -> None:
        """Update button visibility and state."""
        info = self.execution_info
        button_container = self.query_one("#button-container", Horizontal)

        # Show/hide buttons based on state
        if info.state == ToolExecutionState.CONFIRMING and info.requires_confirmation:
            # Force visibility via both property and styles
            button_container.display = True
            button_container.styles.display = "block"
            button_container.styles.height = 5  # Force explicit height
            button_container.styles.min_height = 5
            button_container.styles.visibility = "visible"
            button_container.styles.opacity = 1.0

            # Make sure buttons themselves are visible
            for btn in button_container.query(Button):
                btn.display = True
                btn.styles.height = 3  # Force button height
                btn.styles.visibility = "visible"
                btn.styles.opacity = 1.0

            # Update details button text
            details_btn = self.query_one("#details-btn", Button)
            if self.expanded:
                details_btn.label = "▲ Collapse"
            else:
                details_btn.label = "📋 Details"
        else:
            # Hide buttons
            button_container.display = False
            button_container.styles.display = "none"

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "confirm-btn":
            if self.on_confirm:
                await self.on_confirm(self._info)
        elif event.button.id == "cancel-btn":
            if self.on_cancel:
                await self.on_cancel(self._info)
        elif event.button.id == "details-btn":
            # Toggle expanded state
            self._expanded = not self._expanded
            self._update_display()
            if self.on_details:
                await self.on_details(self._info, self._expanded)

    def update_info(self, execution_info: ToolExecutionInfo) -> None:
        """Update the execution info and refresh display.

        Args:
            execution_info: New execution information
        """
        self._info = execution_info
        if self.is_mounted:
            self._update_display()

    def set_expanded(self, expanded: bool) -> None:
        """Set the expanded state.

        Args:
            expanded: Whether to show expanded details
        """
        self._expanded = expanded
        if self.is_mounted:
            self._update_display()
