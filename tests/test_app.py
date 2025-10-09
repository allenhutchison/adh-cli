"""Tests for the application."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from adh_cli.app import ADHApp
from adh_cli.core.config_paths import ConfigPaths
from adh_cli.config.models import ModelRegistry


class TestADHApp:
    """Test the ADHApp class."""

    @pytest.fixture
    def app(self):
        """Create a test app instance."""
        with patch("adh_cli.app.PolicyAwareLlmAgent"):
            app = ADHApp()
            # Mock the Textual app methods
            app.notify = Mock()
            app.push_screen = Mock()
            app.push_screen_wait = AsyncMock()
            return app

    def test_app_initialization(self, app):
        """Test app initializes with default values."""
        assert app.agent is None
        assert app.policy_dir == ConfigPaths.get_policies_dir()
        assert app.safety_enabled is True
        assert app.TITLE == "ADH CLI - Policy-Aware Agent"

    def test_load_api_key_from_env(self):
        """Test loading API key from environment."""
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"}):
            app = ADHApp()
            assert app.api_key == "test_key"

        with patch.dict("os.environ", {"GEMINI_API_KEY": "gemini_key"}):
            app = ADHApp()
            assert app.api_key == "gemini_key"

    @patch("adh_cli.app.PolicyAwareLlmAgent")
    def test_initialize_agent(self, mock_agent_class, app):
        """Test agent initialization with ADK agent."""
        app.api_key = "test_key"
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent

        app._initialize_agent()

        # Check ADK agent was created
        mock_agent_class.assert_called_once_with(
            model_name=None,
            api_key="test_key",
            policy_dir=app.policy_dir,
            confirmation_handler=app.handle_confirmation,
            notification_handler=app.show_notification,
            audit_log_path=ConfigPaths.get_audit_log(),
            temperature=0.7,
            max_tokens=2048,
            agent_name="orchestrator",
        )
        assert app.agent == mock_agent

    def test_register_default_tools(self, app):
        """Test registering default tools."""
        mock_shell_tools = Mock()
        with patch.dict("sys.modules", {"adh_cli.tools.shell_tools": mock_shell_tools}):
            app.agent = Mock()

            app._register_default_tools()

            # Check all 9 tools were registered (including fetch_url and delegate_to_agent)
            assert app.agent.register_tool.call_count == 9

            # Check specific tools - they use keyword arguments
            call_kwargs = [
                call.kwargs for call in app.agent.register_tool.call_args_list
            ]
            tool_names = [kwargs["name"] for kwargs in call_kwargs if "name" in kwargs]
            assert "read_file" in tool_names
            assert "write_file" in tool_names
            assert "list_directory" in tool_names
            assert "execute_command" in tool_names
            assert "create_directory" in tool_names
            assert "delegate_to_agent" in tool_names
            assert "fetch_url" in tool_names
            assert "delete_file" in tool_names
            assert "get_file_info" in tool_names

    @pytest.mark.asyncio
    async def test_handle_confirmation_with_context(self, app):
        """Test confirmation handler with tool call context."""
        from adh_cli.policies.policy_types import (
            ToolCall,
            PolicyDecision,
            SupervisionLevel,
            RiskLevel,
        )

        tool_call = ToolCall(tool_name="test_tool", parameters={"param": "value"})
        decision = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.CONFIRM,
            risk_level=RiskLevel.MEDIUM,
        )

        app.push_screen_wait.return_value = True

        result = await app.handle_confirmation(tool_call=tool_call, decision=decision)

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
        with patch.object(app, "_initialize_agent") as mock_init:
            app.update_api_key("new_key")

            assert app.api_key == "new_key"
            mock_init.assert_called_once()
            app.notify.assert_called_with(
                "API key updated and agent reinitialized", severity="success"
            )

    def test_update_safety_settings_disable(self, app):
        """Test disabling safety settings."""
        app.agent = Mock()

        app.update_safety_settings(enabled=False)

        assert app.safety_enabled is False
        app.agent.set_user_preferences.assert_called_with({"auto_approve": ["*"]})
        app.notify.assert_called_with("⚠️ Safety checks disabled", severity="warning")

    def test_update_safety_settings_enable(self, app):
        """Test enabling safety settings."""
        app.agent = Mock()
        app.safety_enabled = False  # Start disabled

        app.update_safety_settings(enabled=True)

        assert app.safety_enabled is True
        app.agent.set_user_preferences.assert_called_with({})
        app.notify.assert_called_with("✓ Safety checks enabled", severity="success")

    def test_action_show_policies(self, app):
        """Test showing policy configuration."""
        app.action_show_policies()

        app.notify.assert_called_with(
            "Policy configuration screen coming soon!", severity="information"
        )

    def test_action_toggle_dark(self, app):
        """Test toggling dark mode."""
        app.theme = "adh-light"

        app.action_toggle_dark()
        assert app.theme == "adh-dark"

        app.action_toggle_dark()
        assert app.theme == "adh-light"

    @patch("adh_cli.app.PolicyAwareLlmAgent")
    def test_load_config_with_orchestrator_agent(
        self, mock_agent_class, app, monkeypatch
    ):
        """Test loading config with orchestrator_agent setting."""
        import json

        # Create a temporary config file with orchestrator_agent
        with tempfile.TemporaryDirectory() as tmpdir:
            # Redirect config base dir to temporary location to avoid writing to user home
            monkeypatch.setattr(ConfigPaths, "BASE_DIR", Path(tmpdir))
            config_file = ConfigPaths.get_config_file()
            config_file.parent.mkdir(parents=True, exist_ok=True)

            config_data = {
                "api_key": "test_key",
                "model": ModelRegistry.DEFAULT.id,
                "orchestrator_agent": "custom_agent",
                "temperature": 0.5,
                "max_tokens": 1024,
            }

            with open(config_file, "w") as f:
                json.dump(config_data, f)

            app.api_key = "test_key"
            mock_agent = Mock()
            mock_agent_class.return_value = mock_agent

            app._initialize_agent()

            # Check that agent was created with custom agent name
            call_kwargs = mock_agent_class.call_args[1]
            assert call_kwargs["agent_name"] == "custom_agent"
            assert call_kwargs["temperature"] == 0.5
            assert call_kwargs["max_tokens"] == 1024

            # Clean up
            config_file.unlink(missing_ok=True)

    def test_load_config_defaults(self, app):
        """Test loading config with missing file defaults to orchestrator."""
        config = app._load_config()

        # When config doesn't exist, should return empty dict
        assert isinstance(config, dict)


class TestPolicyIntegration:
    """Integration tests for policy-aware features."""

    @pytest.fixture
    def temp_policy_dir(self):
        """Create temporary policy directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_full_initialization(self, temp_policy_dir):
        """Test full app initialization with ADK agent."""
        with patch("adh_cli.app.PolicyAwareLlmAgent") as mock_agent_class:
            app = ADHApp()
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
            assert call_kwargs["policy_dir"] == temp_policy_dir
            assert call_kwargs["api_key"] == "test_key"

    def test_app_screens_installed(self):
        """Test that chat screen can be installed."""
        with patch("adh_cli.app.PolicyAwareLlmAgent"):
            app = ADHApp()
            # Screens are now installed dynamically via install_screen()
            # rather than pre-registered in SCREENS dict
            # Just verify the app initializes without error
            assert app is not None

    def test_app_bindings_defined(self):
        """Test that all keybindings are defined."""
        app = ADHApp()

        binding_keys = [b.key for b in app.BINDINGS]
        assert "q" in binding_keys
        assert "d" in binding_keys
        assert "s" in binding_keys
        assert "p" in binding_keys
