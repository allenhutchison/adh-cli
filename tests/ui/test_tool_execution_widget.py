"""Tests for ToolExecutionWidget."""

import pytest
from unittest.mock import AsyncMock
from datetime import datetime
from textual.app import App
from textual.widgets import Static

from adh_cli.ui.tool_execution_widget import ToolExecutionWidget
from adh_cli.ui.tool_execution import ToolExecutionInfo, ToolExecutionState
from adh_cli.policies.policy_types import (
    PolicyDecision,
    SupervisionLevel,
    RiskLevel,
    SafetyCheck,
)
from adh_cli.ui.theme import get_themes


class ToolExecutionTestApp(App):
    """Test app with ADH themes registered."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Register ADH themes for testing
        for theme_name, theme in get_themes().items():
            self.register_theme(theme)
        self.theme = "adh-dark"

    def compose(self):
        # Will be overridden by test
        pass


class TestToolExecutionWidget:
    """Test ToolExecutionWidget display and interaction."""

    @pytest.mark.asyncio
    async def test_widget_initialization(self):
        """Test widget initializes with execution info."""
        info = ToolExecutionInfo(
            id="test-1",
            tool_name="read_file",
            parameters={"file_path": "test.txt"},
            state=ToolExecutionState.EXECUTING,
        )

        widget = ToolExecutionWidget(execution_info=info)

        assert widget.execution_info == info
        assert widget.expanded is False

    @pytest.mark.asyncio
    async def test_widget_shows_executing_state(self):
        """Test widget displays executing state correctly."""
        info = ToolExecutionInfo(
            id="test-1",
            tool_name="read_file",
            parameters={"file_path": "test.txt"},
            state=ToolExecutionState.EXECUTING,
        )

        widget = ToolExecutionWidget(execution_info=info)

        # Mount widget in test app
        class _TestApp(ToolExecutionTestApp):
            def compose(self):
                yield widget

        async with _TestApp().run_test() as pilot:
            # Wait for widget to mount and update
            await pilot.pause()
            # Check CSS class applied
            assert "executing" in widget.classes

    @pytest.mark.asyncio
    async def test_widget_shows_success_state(self):
        """Test widget displays success state correctly."""
        info = ToolExecutionInfo(
            id="test-1",
            tool_name="read_file",
            state=ToolExecutionState.SUCCESS,
            started_at=datetime(2024, 1, 1, 12, 0, 0),
            completed_at=datetime(2024, 1, 1, 12, 0, 1),
        )

        widget = ToolExecutionWidget(execution_info=info)

        class _TestApp(ToolExecutionTestApp):
            def compose(self):
                yield widget

        async with _TestApp().run_test() as pilot:
            await pilot.pause()
            assert "success" in widget.classes

    @pytest.mark.asyncio
    async def test_widget_shows_failed_state(self):
        """Test widget displays failed state correctly."""
        info = ToolExecutionInfo(
            id="test-1",
            tool_name="read_file",
            state=ToolExecutionState.FAILED,
            error="File not found",
        )

        widget = ToolExecutionWidget(execution_info=info)

        class _TestApp(ToolExecutionTestApp):
            def compose(self):
                yield widget

        async with _TestApp().run_test() as pilot:
            await pilot.pause()
            assert "failed" in widget.classes

    @pytest.mark.asyncio
    async def test_buttons_hidden_for_automatic_execution(self):
        """Test confirmation buttons are hidden for automatic execution."""
        info = ToolExecutionInfo(
            id="test-1",
            tool_name="read_file",
            state=ToolExecutionState.EXECUTING,
            requires_confirmation=False,
        )

        widget = ToolExecutionWidget(execution_info=info)

        class _TestApp(ToolExecutionTestApp):
            def compose(self):
                yield widget

        async with _TestApp().run_test() as pilot:
            await pilot.pause()
            button_container = widget.query_one("#button-container")
            assert button_container.display is False

    @pytest.mark.asyncio
    async def test_buttons_visible_for_confirmation(self):
        """Test confirmation buttons are visible when confirmation required."""
        info = ToolExecutionInfo(
            id="test-1",
            tool_name="write_file",
            parameters={"file_path": "test.txt", "content": "hello"},
            state=ToolExecutionState.CONFIRMING,
            requires_confirmation=True,
            policy_decision=PolicyDecision(
                allowed=True,
                supervision_level=SupervisionLevel.CONFIRM,
                risk_level=RiskLevel.MEDIUM,
            ),
        )

        widget = ToolExecutionWidget(execution_info=info)

        class _TestApp(ToolExecutionTestApp):
            def compose(self):
                yield widget

        async with _TestApp().run_test() as pilot:
            await pilot.pause()
            button_container = widget.query_one("#button-container")
            assert button_container.display is True

    @pytest.mark.asyncio
    async def test_confirm_button_triggers_callback(self):
        """Test confirm button calls the on_confirm callback."""
        info = ToolExecutionInfo(
            id="test-1",
            tool_name="write_file",
            state=ToolExecutionState.CONFIRMING,
            requires_confirmation=True,
            policy_decision=PolicyDecision(
                allowed=True,
                supervision_level=SupervisionLevel.CONFIRM,
                risk_level=RiskLevel.MEDIUM,
            ),
        )

        on_confirm = AsyncMock()
        widget = ToolExecutionWidget(execution_info=info, on_confirm=on_confirm)

        class _TestApp(ToolExecutionTestApp):
            def compose(self):
                yield widget

        async with _TestApp().run_test() as pilot:
            await pilot.pause()
            # Click confirm button
            await pilot.click("#confirm-btn")

            # Check callback was called
            on_confirm.assert_called_once()
            call_args = on_confirm.call_args[0]
            assert call_args[0].id == "test-1"

    @pytest.mark.asyncio
    async def test_cancel_button_triggers_callback(self):
        """Test cancel button calls the on_cancel callback."""
        info = ToolExecutionInfo(
            id="test-1",
            tool_name="write_file",
            state=ToolExecutionState.CONFIRMING,
            requires_confirmation=True,
            policy_decision=PolicyDecision(
                allowed=True,
                supervision_level=SupervisionLevel.CONFIRM,
                risk_level=RiskLevel.MEDIUM,
            ),
        )

        on_cancel = AsyncMock()
        widget = ToolExecutionWidget(execution_info=info, on_cancel=on_cancel)

        class _TestApp(ToolExecutionTestApp):
            def compose(self):
                yield widget

        async with _TestApp().run_test() as pilot:
            await pilot.pause()
            # Click cancel button
            await pilot.click("#cancel-btn")

            # Check callback was called
            on_cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_details_button_toggles_expanded(self):
        """Test details button toggles expanded state."""
        info = ToolExecutionInfo(
            id="test-1",
            tool_name="write_file",
            parameters={"file_path": "test.txt", "content": "hello world"},
            state=ToolExecutionState.CONFIRMING,
            requires_confirmation=True,
            policy_decision=PolicyDecision(
                allowed=True,
                supervision_level=SupervisionLevel.CONFIRM,
                risk_level=RiskLevel.MEDIUM,
            ),
        )

        on_details = AsyncMock()
        widget = ToolExecutionWidget(execution_info=info, on_details=on_details)

        class _TestApp(ToolExecutionTestApp):
            def compose(self):
                yield widget

        async with _TestApp().run_test() as pilot:
            await pilot.pause()
            # Initially not expanded
            assert widget.expanded is False

            # Click details button
            await pilot.click("#details-btn")
            await pilot.pause()

            # Should be expanded now
            assert widget.expanded is True
            on_details.assert_called_once()

            # Test toggle via set_expanded method (Textual pilot has issues with double-click)
            widget.set_expanded(False)
            assert widget.expanded is False

    @pytest.mark.asyncio
    async def test_parameters_display_compact(self):
        """Test parameters display in compact mode."""
        info = ToolExecutionInfo(
            id="test-1",
            tool_name="read_file",
            parameters={"file_path": "test.txt", "max_lines": 100},
            state=ToolExecutionState.EXECUTING,
        )

        widget = ToolExecutionWidget(execution_info=info)

        class _TestApp(ToolExecutionTestApp):
            def compose(self):
                yield widget

        async with _TestApp().run_test() as pilot:
            await pilot.pause()
            params_widget = widget.query_one("#params", Static)

            # Should show inline format - get the rich renderable
            # Static widgets store their content in _renderable or we can render it
            content = str(params_widget.render())
            assert "file_path" in content
            assert "max_lines" in content
            assert "|" in content  # Separator

    @pytest.mark.asyncio
    async def test_parameters_display_expanded(self):
        """Test parameters display in expanded mode."""
        info = ToolExecutionInfo(
            id="test-1",
            tool_name="write_file",
            parameters={
                "file_path": "test.txt",
                "content": "hello world",
                "create_dirs": True,
            },
            state=ToolExecutionState.CONFIRMING,
            requires_confirmation=True,
            policy_decision=PolicyDecision(
                allowed=True,
                supervision_level=SupervisionLevel.CONFIRM,
                risk_level=RiskLevel.MEDIUM,
                safety_checks=[
                    SafetyCheck(name="BackupChecker", checker_class="BackupChecker")
                ],
            ),
        )

        widget = ToolExecutionWidget(execution_info=info)
        widget.expanded = True

        class _TestApp(ToolExecutionTestApp):
            def compose(self):
                yield widget

        async with _TestApp().run_test() as pilot:
            await pilot.pause()
            params_widget = widget.query_one("#params", Static)

            # Should show expanded format with bullets
            content = str(params_widget.render())
            assert "Parameters:" in content
            assert "•" in content  # Bullet points
            assert "Safety Checks:" in content
            assert "BackupChecker" in content

    @pytest.mark.asyncio
    async def test_update_info_method(self):
        """Test update_info method changes the display."""
        initial_info = ToolExecutionInfo(
            id="test-1", tool_name="read_file", state=ToolExecutionState.EXECUTING
        )

        widget = ToolExecutionWidget(execution_info=initial_info)

        class _TestApp(ToolExecutionTestApp):
            def compose(self):
                yield widget

        async with _TestApp().run_test() as pilot:
            await pilot.pause()
            assert "executing" in widget.classes

            # Update to success state
            updated_info = ToolExecutionInfo(
                id="test-1", tool_name="read_file", state=ToolExecutionState.SUCCESS
            )
            widget.update_info(updated_info)

            # Should update CSS class
            assert "success" in widget.classes
            assert "executing" not in widget.classes

    @pytest.mark.asyncio
    async def test_set_expanded_method(self):
        """Test set_expanded method changes expanded state."""
        info = ToolExecutionInfo(
            id="test-1",
            tool_name="write_file",
            state=ToolExecutionState.CONFIRMING,
            requires_confirmation=True,
            parameters={"file_path": "test.txt"},
        )

        widget = ToolExecutionWidget(execution_info=info)

        class _TestApp(ToolExecutionTestApp):
            def compose(self):
                yield widget

        async with _TestApp().run_test() as pilot:
            await pilot.pause()
            assert widget.expanded is False

            # Set expanded
            widget.set_expanded(True)
            assert widget.expanded is True

            # Set collapsed
            widget.set_expanded(False)
            assert widget.expanded is False
