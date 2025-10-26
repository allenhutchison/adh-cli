"""Tests for confirmation dialog."""

import pytest
from unittest.mock import Mock, AsyncMock
from textual.app import App, ComposeResult
from textual.widgets import Button, Label, Static

from adh_cli.ui.confirmation_dialog import ConfirmationDialog, PolicyNotification
from adh_cli.policies.policy_types import (
    PolicyDecision,
    RiskLevel,
    SupervisionLevel,
    SafetyCheck,
    Restriction,
    RestrictionType,
)


class ConfirmationDialogTestApp(App):
    """Test app for ConfirmationDialog."""

    def compose(self) -> ComposeResult:
        yield Static("Test App")


class TestConfirmationDialog:
    """Test the ConfirmationDialog."""

    @pytest.fixture
    def basic_decision(self):
        """Create a basic policy decision."""
        return PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.CONFIRM,
            risk_level=RiskLevel.MEDIUM,
        )

    @pytest.fixture
    def full_decision(self):
        """Create a fully populated policy decision."""
        return PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.MANUAL,
            risk_level=RiskLevel.HIGH,
            confirmation_message="This operation requires manual review",
            safety_checks=[
                SafetyCheck(name="backup_check", checker_class="BackupChecker"),
                SafetyCheck(name="permission_check", checker_class="PermissionChecker"),
            ],
            restrictions=[
                Restriction(
                    type=RestrictionType.SIZE_LIMIT, config={"max_size": 1000000}
                ),
                Restriction(
                    type=RestrictionType.PATH_PATTERN, config={"pattern": "/tmp/*"}
                ),
            ],
        )

    def test_initialization(self, basic_decision):
        """Test dialog initializes with correct attributes."""
        dialog = ConfirmationDialog(
            tool_name="test_tool",
            parameters={"arg1": "value1"},
            decision=basic_decision,
        )

        assert dialog.tool_name == "test_tool"
        assert dialog.parameters == {"arg1": "value1"}
        assert dialog.decision == basic_decision
        assert dialog.callback is None
        assert dialog.result is False

    def test_initialization_with_callback(self, basic_decision):
        """Test dialog initializes with callback."""
        callback = Mock()
        dialog = ConfirmationDialog(
            tool_name="test_tool",
            parameters={},
            decision=basic_decision,
            callback=callback,
        )

        assert dialog.callback is callback

    @pytest.mark.asyncio
    async def test_compose_basic_layout(self, basic_decision):
        """Test compose creates basic layout elements."""
        app = ConfirmationDialogTestApp()
        async with app.run_test() as pilot:
            dialog = ConfirmationDialog(
                tool_name="test_tool",
                parameters={"arg1": "value1"},
                decision=basic_decision,
            )
            await pilot.app.push_screen(dialog)

            # Check title exists
            title = dialog.query_one(".title", Label)
            assert "test_tool" in str(title.render())
            assert "⚠️" in str(title.render())

            # Check risk badge exists
            risk_badge = dialog.query_one(".risk-badge", Label)
            assert "MEDIUM" in str(risk_badge.render())

            # Check buttons exist
            confirm_btn = dialog.query_one("#confirm", Button)
            assert confirm_btn is not None
            cancel_btn = dialog.query_one("#cancel", Button)
            assert cancel_btn is not None

    @pytest.mark.asyncio
    async def test_risk_level_badges(self):
        """Test different risk level badges are displayed correctly."""
        risk_levels = [
            (RiskLevel.LOW, "risk-low"),
            (RiskLevel.MEDIUM, "risk-medium"),
            (RiskLevel.HIGH, "risk-high"),
            (RiskLevel.CRITICAL, "risk-critical"),
        ]

        for risk_level, expected_class in risk_levels:
            # Create fresh app for each iteration to avoid timeouts
            app = ConfirmationDialogTestApp()
            async with app.run_test() as pilot:
                decision = PolicyDecision(
                    allowed=True,
                    supervision_level=SupervisionLevel.CONFIRM,
                    risk_level=risk_level,
                )
                dialog = ConfirmationDialog(
                    tool_name="test_tool",
                    parameters={},
                    decision=decision,
                )
                await pilot.app.push_screen(dialog)

                risk_badge = dialog.query_one(".risk-badge", Label)
                assert expected_class in risk_badge.classes

    @pytest.mark.asyncio
    async def test_confirmation_message_display(self):
        """Test custom confirmation message is displayed."""
        app = ConfirmationDialogTestApp()
        async with app.run_test() as pilot:
            decision = PolicyDecision(
                allowed=True,
                supervision_level=SupervisionLevel.CONFIRM,
                risk_level=RiskLevel.MEDIUM,
                confirmation_message="Custom confirmation message",
            )
            dialog = ConfirmationDialog(
                tool_name="test_tool",
                parameters={},
                decision=decision,
            )
            await pilot.app.push_screen(dialog)

            # Check message is in details
            details = dialog.query_one(".details")
            static_widgets = details.query(Static)
            messages = [str(w.render()) for w in static_widgets]
            assert any("Custom confirmation message" in msg for msg in messages)

    @pytest.mark.asyncio
    async def test_parameters_display(self, basic_decision):
        """Test parameters are displayed."""
        app = ConfirmationDialogTestApp()
        async with app.run_test() as pilot:
            dialog = ConfirmationDialog(
                tool_name="test_tool",
                parameters={"arg1": "value1", "arg2": "value2"},
                decision=basic_decision,
            )
            await pilot.app.push_screen(dialog)

            # Check parameters are in details
            details = dialog.query_one(".details")
            static_widgets = details.query(Static)
            messages = [str(w.render()) for w in static_widgets]

            assert any("Parameters:" in msg for msg in messages)
            assert any("arg1" in msg and "value1" in msg for msg in messages)
            assert any("arg2" in msg and "value2" in msg for msg in messages)

    @pytest.mark.asyncio
    async def test_safety_checks_display(self):
        """Test safety checks are displayed."""
        app = ConfirmationDialogTestApp()
        async with app.run_test() as pilot:
            decision = PolicyDecision(
                allowed=True,
                supervision_level=SupervisionLevel.CONFIRM,
                risk_level=RiskLevel.MEDIUM,
                safety_checks=[
                    SafetyCheck(name="backup_check", checker_class="BackupChecker"),
                    SafetyCheck(
                        name="permission_check", checker_class="PermissionChecker"
                    ),
                ],
            )
            dialog = ConfirmationDialog(
                tool_name="test_tool",
                parameters={},
                decision=decision,
            )
            await pilot.app.push_screen(dialog)

            details = dialog.query_one(".details")
            static_widgets = details.query(Static)
            messages = [str(w.render()) for w in static_widgets]

            assert any("Safety Checks:" in msg for msg in messages)
            assert any("backup_check" in msg for msg in messages)
            assert any("permission_check" in msg for msg in messages)

    @pytest.mark.asyncio
    async def test_restrictions_display(self):
        """Test restrictions are displayed."""
        app = ConfirmationDialogTestApp()
        async with app.run_test() as pilot:
            decision = PolicyDecision(
                allowed=True,
                supervision_level=SupervisionLevel.CONFIRM,
                risk_level=RiskLevel.MEDIUM,
                restrictions=[
                    Restriction(
                        type=RestrictionType.SIZE_LIMIT, config={"max_size": 1000000}
                    ),
                    Restriction(
                        type=RestrictionType.PATH_PATTERN, config={"pattern": "/tmp/*"}
                    ),
                ],
            )
            dialog = ConfirmationDialog(
                tool_name="test_tool",
                parameters={},
                decision=decision,
            )
            await pilot.app.push_screen(dialog)

            details = dialog.query_one(".details")
            static_widgets = details.query(Static)
            messages = [str(w.render()) for w in static_widgets]

            assert any("Restrictions:" in msg for msg in messages)
            assert any("size_limit" in msg for msg in messages)

    @pytest.mark.asyncio
    async def test_modify_button_manual_supervision(self):
        """Test modify button appears for manual supervision level."""
        app = ConfirmationDialogTestApp()
        async with app.run_test() as pilot:
            decision = PolicyDecision(
                allowed=True,
                supervision_level=SupervisionLevel.MANUAL,
                risk_level=RiskLevel.HIGH,
            )
            dialog = ConfirmationDialog(
                tool_name="test_tool",
                parameters={},
                decision=decision,
            )
            await pilot.app.push_screen(dialog)

            # Check modify button exists
            modify_btn = dialog.query_one("#modify", Button)
            assert modify_btn is not None

    @pytest.mark.asyncio
    async def test_no_modify_button_confirm_supervision(self, basic_decision):
        """Test no modify button for confirm supervision level."""
        app = ConfirmationDialogTestApp()
        async with app.run_test() as pilot:
            dialog = ConfirmationDialog(
                tool_name="test_tool",
                parameters={},
                decision=basic_decision,
            )
            await pilot.app.push_screen(dialog)

            # Check modify button does not exist
            modify_buttons = dialog.query("#modify")
            assert len(modify_buttons) == 0

    @pytest.mark.asyncio
    async def test_confirm_button_action(self, basic_decision):
        """Test confirm button sets result and dismisses dialog."""
        app = ConfirmationDialogTestApp()
        async with app.run_test() as pilot:
            dialog = ConfirmationDialog(
                tool_name="test_tool",
                parameters={},
                decision=basic_decision,
            )
            await pilot.app.push_screen(dialog)

            # Click confirm button
            confirm_btn = dialog.query_one("#confirm", Button)
            confirm_btn.press()
            await pilot.pause()

            assert dialog.result is True

    @pytest.mark.asyncio
    async def test_cancel_button_action(self, basic_decision):
        """Test cancel button sets result and dismisses dialog."""
        app = ConfirmationDialogTestApp()
        async with app.run_test() as pilot:
            dialog = ConfirmationDialog(
                tool_name="test_tool",
                parameters={},
                decision=basic_decision,
            )
            await pilot.app.push_screen(dialog)

            # Click cancel button
            cancel_btn = dialog.query_one("#cancel", Button)
            cancel_btn.press()
            await pilot.pause()

            assert dialog.result is False

    @pytest.mark.asyncio
    async def test_confirm_with_callback(self, basic_decision):
        """Test confirm button calls callback with True."""
        app = ConfirmationDialogTestApp()
        callback = AsyncMock()

        async with app.run_test() as pilot:
            dialog = ConfirmationDialog(
                tool_name="test_tool",
                parameters={},
                decision=basic_decision,
                callback=callback,
            )
            await pilot.app.push_screen(dialog)

            # Click confirm button
            confirm_btn = dialog.query_one("#confirm", Button)
            confirm_btn.press()
            await pilot.pause()

            callback.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_cancel_with_callback(self, basic_decision):
        """Test cancel button calls callback with False."""
        app = ConfirmationDialogTestApp()
        callback = AsyncMock()

        async with app.run_test() as pilot:
            dialog = ConfirmationDialog(
                tool_name="test_tool",
                parameters={},
                decision=basic_decision,
                callback=callback,
            )
            await pilot.app.push_screen(dialog)

            # Click cancel button
            cancel_btn = dialog.query_one("#cancel", Button)
            cancel_btn.press()
            await pilot.pause()

            callback.assert_called_once_with(False)

    def test_css_classes_defined(self):
        """Test that CSS classes are properly defined."""
        decision = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.CONFIRM,
            risk_level=RiskLevel.MEDIUM,
        )
        dialog = ConfirmationDialog(
            tool_name="test_tool",
            parameters={},
            decision=decision,
        )
        css = dialog.DEFAULT_CSS

        # Check key classes are defined
        assert "ConfirmationDialog" in css
        assert ".title" in css
        assert ".risk-badge" in css
        assert ".risk-low" in css
        assert ".risk-medium" in css
        assert ".risk-high" in css
        assert ".risk-critical" in css
        assert ".details" in css
        assert ".button-container" in css


class TestPolicyNotification:
    """Test the PolicyNotification widget."""

    def test_initialization_info(self):
        """Test notification initializes with info level."""
        notif = PolicyNotification("Test message", level="info")

        assert notif.message == "Test message"
        assert notif.level == "info"
        assert "info" in notif.classes

    def test_initialization_warning(self):
        """Test notification initializes with warning level."""
        notif = PolicyNotification("Warning message", level="warning")

        assert notif.level == "warning"
        assert "warning" in notif.classes

    def test_initialization_error(self):
        """Test notification initializes with error level."""
        notif = PolicyNotification("Error message", level="error")

        assert notif.level == "error"
        assert "error" in notif.classes

    def test_initialization_success(self):
        """Test notification initializes with success level."""
        notif = PolicyNotification("Success message", level="success")

        assert notif.level == "success"
        assert "success" in notif.classes

    def test_render_info(self):
        """Test rendering info notification."""
        notif = PolicyNotification("Info message", level="info")
        rendered = notif.render()

        assert "ℹ️" in str(rendered)
        assert "Info message" in str(rendered)

    def test_render_warning(self):
        """Test rendering warning notification."""
        notif = PolicyNotification("Warning message", level="warning")
        rendered = notif.render()

        assert "⚠️" in str(rendered)
        assert "Warning message" in str(rendered)

    def test_render_error(self):
        """Test rendering error notification."""
        notif = PolicyNotification("Error message", level="error")
        rendered = notif.render()

        assert "❌" in str(rendered)
        assert "Error message" in str(rendered)

    def test_render_success(self):
        """Test rendering success notification."""
        notif = PolicyNotification("Success message", level="success")
        rendered = notif.render()

        assert "✅" in str(rendered)
        assert "Success message" in str(rendered)

    def test_render_unknown_level(self):
        """Test rendering with unknown level defaults to info icon."""
        notif = PolicyNotification("Unknown level", level="unknown")
        rendered = notif.render()

        assert "ℹ️" in str(rendered)
        assert "Unknown level" in str(rendered)

    def test_css_classes_defined(self):
        """Test that CSS classes are properly defined."""
        notif = PolicyNotification("Test", level="info")
        css = notif.DEFAULT_CSS

        # Check key classes are defined
        assert "PolicyNotification" in css
        assert ".info" in css
        assert ".warning" in css
        assert ".error" in css
        assert ".success" in css
