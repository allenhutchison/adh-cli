"""Tests for the policy-aware application."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from adh_cli.app_policy import PolicyAwareADHApp
from adh_cli.core.policy_aware_agent import PolicyAwareAgent


class TestPolicyAwareADHApp:
    """Test the PolicyAwareADHApp class."""

    @pytest.fixture
    def app(self):
        """Create a test app instance."""
        with patch('adh_cli.app_policy.PolicyAwareAgent'):
            app = PolicyAwareADHApp()
            # Mock the Textual app methods
            app.notify = Mock()
            app.push_screen = Mock()
            app.push_screen_wait = AsyncMock()
            return app

    def test_app_initialization(self, app):
        """Test app initializes with default values."""
        assert app.agent is None
        assert app.policy_dir == Path.home() / ".adh-cli" / "policies"
        assert app.safety_enabled is True
        assert app.TITLE == "ADH CLI - Policy-Aware Agent"

    def test_load_api_key_from_env(self):
        """Test loading API key from environment."""
        with patch.dict('os.environ', {'GOOGLE_API_KEY': 'test_key'}):
            app = PolicyAwareADHApp()
            assert app.api_key == 'test_key'

        with patch.dict('os.environ', {'GEMINI_API_KEY': 'gemini_key'}):
            app = PolicyAwareADHApp()
            assert app.api_key == 'gemini_key'

    @patch('adh_cli.app_policy.PolicyAwareAgent')
    def test_initialize_agent(self, mock_agent_class, app):
        """Test agent initialization."""
        app.api_key = 'test_key'
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent

        app._initialize_agent()

        # Check agent was created
        mock_agent_class.assert_called_once_with(
            api_key='test_key',
            policy_dir=app.policy_dir,
            confirmation_handler=app.handle_confirmation,
            notification_handler=app.show_notification,
            audit_log_path=app.policy_dir / "audit.log",
        )
        assert app.agent == mock_agent

    @patch('adh_cli.tools.shell_tools')
    def test_register_default_tools(self, mock_shell_tools, app):
        """Test registering default tools."""
        app.agent = Mock()

        app._register_default_tools()

        # Check tools were registered
        assert app.agent.register_tool.call_count >= 4  # At least 4 tools

        # Check specific tools
        call_args = [call.args for call in app.agent.register_tool.call_args_list]
        tool_names = [args[0] for args in call_args if args]
        assert 'read_file' in tool_names
        assert 'write_file' in tool_names
        assert 'list_directory' in tool_names
        assert 'execute_command' in tool_names

    @pytest.mark.asyncio
    async def test_handle_confirmation_with_context(self, app):
        """Test confirmation handler with tool call context."""
        from adh_cli.policies.policy_types import ToolCall, PolicyDecision, SupervisionLevel, RiskLevel

        tool_call = ToolCall(
            tool_name="test_tool",
            parameters={"param": "value"}
        )
        decision = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.CONFIRM,
            risk_level=RiskLevel.MEDIUM
        )

        app.push_screen_wait.return_value = True

        result = await app.handle_confirmation(
            tool_call=tool_call,
            decision=decision
        )

        assert result is True
        app.push_screen_wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_confirmation_simple(self, app):
        """Test simple confirmation without context."""
        app.push_screen_wait.return_value = False

        result = await app.handle_confirmation(message="Confirm?")

        assert result is False

    @pytest.mark.asyncio
    async def test_show_notification_levels(self, app):
        """Test notification with different severity levels."""
        await app.show_notification("Test message", level="info")
        app.notify.assert_called_with("Test message", severity="information")

        await app.show_notification("Warning", level="warning")
        app.notify.assert_called_with("Warning", severity="warning")

        await app.show_notification("Error", level="error")
        app.notify.assert_called_with("Error", severity="error")

        await app.show_notification("Success", level="success")
        app.notify.assert_called_with("Success", severity="information")

    def test_update_api_key(self, app):
        """Test updating API key reinitializes agent."""
        with patch.object(app, '_initialize_agent') as mock_init:
            app.update_api_key("new_key")

            assert app.api_key == "new_key"
            mock_init.assert_called_once()
            app.notify.assert_called_with(
                "API key updated and agent reinitialized",
                severity="success"
            )

    def test_update_safety_settings_disable(self, app):
        """Test disabling safety settings."""
        app.agent = Mock()

        app.update_safety_settings(enabled=False)

        assert app.safety_enabled is False
        app.agent.set_user_preferences.assert_called_with({
            "auto_approve": ["*"]
        })
        app.notify.assert_called_with(
            "⚠️ Safety checks disabled",
            severity="warning"
        )

    def test_update_safety_settings_enable(self, app):
        """Test enabling safety settings."""
        app.agent = Mock()
        app.safety_enabled = False  # Start disabled

        app.update_safety_settings(enabled=True)

        assert app.safety_enabled is True
        app.agent.set_user_preferences.assert_called_with({})
        app.notify.assert_called_with(
            "✓ Safety checks enabled",
            severity="success"
        )

    def test_action_show_policies(self, app):
        """Test showing policy configuration."""
        app.action_show_policies()

        app.notify.assert_called_with(
            "Policy configuration screen coming soon!",
            severity="information"
        )

    def test_action_toggle_dark(self, app):
        """Test toggling dark mode."""
        app.theme = "textual-light"

        app.action_toggle_dark()
        assert app.theme == "textual-dark"

        app.action_toggle_dark()
        assert app.theme == "textual-light"


class TestPolicyIntegration:
    """Integration tests for policy-aware features."""

    @pytest.fixture
    def temp_policy_dir(self):
        """Create temporary policy directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_full_initialization(self, temp_policy_dir):
        """Test full app initialization with real components."""
        with patch('adh_cli.app_policy.PolicyAwareAgent') as mock_agent_class:
            app = PolicyAwareADHApp()
            app.policy_dir = temp_policy_dir
            app.api_key = "test_key"
            app.notify = Mock()

            mock_agent = Mock()
            mock_agent_class.return_value = mock_agent

            # Initialize
            app._initialize_agent()

            # Verify agent was created correctly
            assert app.agent is not None
            mock_agent_class.assert_called_once()

            # Check policy directory in call
            call_kwargs = mock_agent_class.call_args[1]
            assert call_kwargs['policy_dir'] == temp_policy_dir
            assert call_kwargs['api_key'] == "test_key"

    def test_app_screens_defined(self):
        """Test that all required screens are defined."""
        app = PolicyAwareADHApp()

        assert "main" in app.SCREENS
        assert "chat" in app.SCREENS
        assert "settings" in app.SCREENS

    def test_app_bindings_defined(self):
        """Test that all keybindings are defined."""
        app = PolicyAwareADHApp()

        binding_keys = [b.key for b in app.BINDINGS]
        assert "q" in binding_keys
        assert "d" in binding_keys
        assert "s" in binding_keys
        assert "p" in binding_keys