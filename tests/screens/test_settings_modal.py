"""Tests for the settings modal."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, PropertyMock

from adh_cli.screens.settings_modal import SettingsModal
from adh_cli.config.models import ModelRegistry


class TestSettingsModal:
    """Test the SettingsModal class."""

    @pytest.fixture
    def modal(self, tmp_path):
        """Create a test modal instance with mocked config path."""
        # Create mock app
        mock_app = Mock()
        mock_app.theme = "adh-dark"
        mock_app.log = Mock()

        # Patch config path to use tmp_path
        config_file = tmp_path / "config.json"

        # Patch ConfigPaths at both import locations
        with (
            patch("adh_cli.screens.settings_modal.ConfigPaths") as mock_paths1,
            patch(
                "adh_cli.core.config_paths.ConfigPaths.get_config_file",
                return_value=config_file,
            ),
        ):
            mock_paths1.get_config_file.return_value = config_file

            # Patch the app property
            with patch.object(
                SettingsModal, "app", new_callable=PropertyMock
            ) as mock_app_prop:
                mock_app_prop.return_value = mock_app

                modal = SettingsModal()

                # Mock Textual components
                modal.query_one = Mock()
                modal.notify = Mock()
                modal.dismiss = Mock()

                yield modal, config_file

    def test_modal_initialization(self, modal):
        """Test modal initializes correctly."""
        modal_instance, _ = modal
        assert modal_instance is not None

    def test_discover_agents_empty_dir(self, modal, tmp_path):
        """Test agent discovery with no agents."""
        modal_instance, _ = modal

        # Point to empty agents directory
        with patch.object(Path, "parent", tmp_path):
            agents = modal_instance._discover_agents()

        # Should return default orchestrator
        assert "orchestrator" in agents

    def test_discover_agents_with_agents(self, modal, tmp_path):
        """Test agent discovery with multiple agents."""
        modal_instance, _ = modal

        # Create fake agents directory with agent.md files
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        # Create orchestrator agent
        orchestrator_dir = agents_dir / "orchestrator"
        orchestrator_dir.mkdir()
        (orchestrator_dir / "agent.md").write_text("# Orchestrator")

        # Create another agent
        planner_dir = agents_dir / "planner"
        planner_dir.mkdir()
        (planner_dir / "agent.md").write_text("# Planner")

        # Create a directory without agent.md (should be ignored)
        invalid_dir = agents_dir / "invalid"
        invalid_dir.mkdir()

        # Mock the agents directory path
        with patch.object(Path, "parent", tmp_path):
            with patch.object(Path, "iterdir", return_value=agents_dir.iterdir()):
                agents = modal_instance._discover_agents()

        # Should find both valid agents, orchestrator first
        assert len(agents) >= 2
        assert agents[0] == "orchestrator"
        assert "planner" in agents
        assert "invalid" not in agents

    def test_save_settings(self, modal):
        """Test saving settings to config file."""
        modal_instance, config_file = modal

        # Mock input values
        mock_api_input = Mock()
        mock_api_input.value = "test-api-key-123"

        mock_model_select = Mock()
        mock_model_select.value = "gemini-flash-latest"

        mock_orchestrator_select = Mock()
        mock_orchestrator_select.value = "orchestrator"

        def query_side_effect(selector, widget_type):
            if selector == "#api-key-input":
                return mock_api_input
            elif selector == "#model-select":
                return mock_model_select
            elif selector == "#orchestrator-select":
                return mock_orchestrator_select
            return Mock()

        modal_instance.query_one = Mock(side_effect=query_side_effect)

        # Save settings
        modal_instance.on_save_pressed()

        # Verify file was written
        assert config_file.exists()

        # Verify content
        with open(config_file, "r") as f:
            settings = json.load(f)

        assert settings["api_key"] == "test-api-key-123"
        assert settings["model"] == "gemini-flash-latest"
        assert settings["orchestrator_agent"] == "orchestrator"

        # Verify user was notified
        modal_instance.notify.assert_called_once()
        assert "saved successfully" in modal_instance.notify.call_args[0][0].lower()

        # Verify modal was dismissed
        modal_instance.dismiss.assert_called_once()

    def test_save_settings_invalid_model(self, modal):
        """Test saving with invalid model shows error."""
        modal_instance, config_file = modal

        # Mock input values with invalid model
        mock_api_input = Mock()
        mock_api_input.value = "test-api-key"

        mock_model_select = Mock()
        mock_model_select.value = "invalid-model-id"

        mock_orchestrator_select = Mock()
        mock_orchestrator_select.value = "orchestrator"

        def query_side_effect(selector, widget_type):
            if selector == "#api-key-input":
                return mock_api_input
            elif selector == "#model-select":
                return mock_model_select
            elif selector == "#orchestrator-select":
                return mock_orchestrator_select
            return Mock()

        modal_instance.query_one = Mock(side_effect=query_side_effect)

        # Save settings
        modal_instance.on_save_pressed()

        # Verify error notification was shown
        modal_instance.notify.assert_called_once()
        call_args = modal_instance.notify.call_args
        assert "severity" in call_args[1]
        assert call_args[1]["severity"] == "error"

        # Verify modal was NOT dismissed
        modal_instance.dismiss.assert_not_called()

        # Verify file was NOT written
        assert not config_file.exists()

    def test_reset_settings(self, modal):
        """Test resetting settings to defaults."""
        modal_instance, _ = modal

        # Mock input widgets
        mock_api_input = Mock()
        mock_model_select = Mock()
        mock_orchestrator_select = Mock()

        def query_side_effect(selector, widget_type):
            if selector == "#api-key-input":
                return mock_api_input
            elif selector == "#model-select":
                return mock_model_select
            elif selector == "#orchestrator-select":
                return mock_orchestrator_select
            return Mock()

        modal_instance.query_one = Mock(side_effect=query_side_effect)

        # Reset settings
        modal_instance.on_reset_pressed()

        # Verify values were reset
        assert mock_api_input.value == ""
        assert mock_model_select.value == ModelRegistry.DEFAULT.id
        assert mock_orchestrator_select.value == "orchestrator"

        # Verify notification
        modal_instance.notify.assert_called_once()
        assert "reset" in modal_instance.notify.call_args[0][0].lower()

    def test_close_button(self, modal):
        """Test close button dismisses modal."""
        modal_instance, _ = modal

        modal_instance.on_close_pressed()

        modal_instance.dismiss.assert_called_once()

    def test_dark_mode_toggle(self, modal):
        """Test dark mode toggle changes theme."""
        modal_instance, _ = modal

        # Mock Switch.Changed event
        mock_event = Mock()
        mock_event.value = True

        modal_instance.on_dark_mode_changed(mock_event)

        assert modal_instance.app.theme == "adh-dark"

        # Test light mode
        mock_event.value = False
        modal_instance.on_dark_mode_changed(mock_event)

        assert modal_instance.app.theme == "adh-light"

    def test_load_existing_settings(self, modal):
        """Test loading existing settings on mount."""
        modal_instance, config_file = modal

        # Create config file with settings
        settings = {
            "api_key": "existing-key",
            "model": "gemini-2.5-pro",
            "orchestrator_agent": "planner",
        }

        config_file.write_text(json.dumps(settings))

        # Mock input widgets
        mock_api_input = Mock()
        mock_model_select = Mock()
        mock_orchestrator_select = Mock()

        def query_side_effect(selector, widget_type):
            if selector == "#api-key-input":
                return mock_api_input
            elif selector == "#model-select":
                return mock_model_select
            elif selector == "#orchestrator-select":
                return mock_orchestrator_select
            return Mock()

        modal_instance.query_one = Mock(side_effect=query_side_effect)

        # Trigger on_mount
        modal_instance.on_mount()

        # Verify values were loaded
        assert mock_api_input.value == "existing-key"
        assert mock_model_select.value == "gemini-2.5-pro"
        assert mock_orchestrator_select.value == "planner"

    def test_load_settings_missing_file(self, modal):
        """Test loading settings when config file doesn't exist."""
        modal_instance, config_file = modal

        # Ensure config file doesn't exist
        assert not config_file.exists()

        # Mock input widgets
        mock_api_input = Mock()
        mock_model_select = Mock()
        mock_orchestrator_select = Mock()

        def query_side_effect(selector, widget_type):
            if selector == "#api-key-input":
                return mock_api_input
            elif selector == "#model-select":
                return mock_model_select
            elif selector == "#orchestrator-select":
                return mock_orchestrator_select
            return Mock()

        modal_instance.query_one = Mock(side_effect=query_side_effect)

        # Trigger on_mount - should not raise error
        modal_instance.on_mount()

        # Values should not be set (no calls to .value setter beyond initialization)
        # This test mainly ensures no exception is raised

    def test_load_settings_invalid_json(self, modal):
        """Test loading settings with corrupted config file."""
        modal_instance, config_file = modal

        # Create invalid JSON
        config_file.write_text("{invalid json")

        # Mock input widgets
        mock_api_input = Mock()
        mock_model_select = Mock()
        mock_orchestrator_select = Mock()

        def query_side_effect(selector, widget_type):
            if selector == "#api-key-input":
                return mock_api_input
            elif selector == "#model-select":
                return mock_model_select
            elif selector == "#orchestrator-select":
                return mock_orchestrator_select
            return Mock()

        modal_instance.query_one = Mock(side_effect=query_side_effect)

        # Trigger on_mount - should handle gracefully
        modal_instance.on_mount()

        # Should log warning but not crash
        modal_instance.app.log.warning.assert_called()

    def test_load_settings_invalid_model(self, modal):
        """Test loading settings with invalid model ID."""
        modal_instance, config_file = modal

        # Create config with invalid model
        settings = {
            "api_key": "test-key",
            "model": "invalid-model-id",
            "orchestrator_agent": "orchestrator",
        }

        config_file.write_text(json.dumps(settings))

        # Mock input widgets
        mock_api_input = Mock()
        mock_model_select = Mock()
        mock_model_select.value = None  # Simulate failure to set value
        mock_orchestrator_select = Mock()

        def query_side_effect(selector, widget_type):
            if selector == "#api-key-input":
                return mock_api_input
            elif selector == "#model-select":
                return mock_model_select
            elif selector == "#orchestrator-select":
                return mock_orchestrator_select
            return Mock()

        modal_instance.query_one = Mock(side_effect=query_side_effect)

        # Trigger on_mount - should handle gracefully
        modal_instance.on_mount()

        # API key should still be loaded
        assert mock_api_input.value == "test-key"
