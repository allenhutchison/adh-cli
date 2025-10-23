"""Tests for the settings modal."""

import json
import pytest
from unittest.mock import Mock, patch, PropertyMock

from adh_cli.screens.settings_modal import SettingsModal
from adh_cli.config.models import ModelRegistry


class TestSettingsModal:
    """Test the SettingsModal class."""

    @pytest.fixture
    def modal(self, tmp_path):
        """Create a test modal instance with mocked config path and logger."""
        # Create mock app
        mock_app = Mock()
        mock_app.theme = "textual-dark"
        mock_app.log = Mock()
        mock_app.log.warning = Mock()  # Mock the warning log explicitly

        # Patch config path to use tmp_path
        config_file = tmp_path / "config.json"

        # Patch ConfigPaths.get_config_file to use tmp_path
        with patch(
            "adh_cli.config.settings_manager.ConfigPaths.get_config_file",
            return_value=config_file,
        ):
            # Patch the app property
            with patch.object(
                SettingsModal, "app", new_callable=PropertyMock
            ) as mock_app_prop:
                mock_app_prop.return_value = mock_app

                modal = SettingsModal()

                # Mock Textual components
                modal.notify = Mock()
                modal.dismiss = Mock()

                # Mock the query_one function to be set later
                modal.query_one = Mock()

                yield modal, config_file

    @pytest.fixture
    def mock_ui_widgets(self, modal):
        """Mocks the UI widgets queried by the modal."""
        modal_instance, _ = modal

        # For Input, we need to ensure .value returns something predictable
        mock_api_key_input = Mock()
        mock_api_key_input.value = None  # Initial state for Input widget

        # For Select, we need to ensure .value is set
        mock_model_select = Mock()
        mock_model_select.value = ModelRegistry.DEFAULT.id

        mock_orchestrator_select = Mock()
        mock_orchestrator_select.value = "orchestrator"

        mock_theme_select = Mock()
        mock_theme_select.value = "textual-dark"

        widgets = {
            "#api-key-input": mock_api_key_input,
            "#model-select": mock_model_select,
            "#orchestrator-select": mock_orchestrator_select,
            "#theme-select": mock_theme_select,
        }

        def query_side_effect(selector, widget_type=None):
            return widgets.get(selector, Mock())

        modal_instance.query_one = Mock(side_effect=query_side_effect)
        return widgets

    def test_modal_initialization(self, modal):
        """Test modal initializes correctly."""
        modal_instance, _ = modal
        assert modal_instance is not None

    def test_discover_agents_empty_dir(self, modal, tmp_path):
        """Test agent discovery with no agents."""
        modal_instance, _ = modal

        # Point to empty agents directory
        with patch("adh_cli.screens.settings_modal.Path") as MockPath:
            # Make Path(__file__).parent.parent return the temporary directory
            MockPath.return_value.parent.parent = tmp_path
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
        with patch("adh_cli.screens.settings_modal.Path") as MockPath:
            # Make Path(__file__).parent.parent return the temporary directory
            MockPath.return_value.parent.parent = tmp_path
            agents = modal_instance._discover_agents()

        # Should find both valid agents, orchestrator first
        assert len(agents) >= 2
        assert agents[0] == "orchestrator"
        assert "planner" in agents
        assert "invalid" not in agents

    def test_save_settings(self, modal, mock_ui_widgets):
        """Test saving settings to config file (non-theme fields)."""
        modal_instance, config_file = modal

        # Set values on mocked widgets
        mock_ui_widgets["#api-key-input"].value = "test-api-key-123"
        mock_ui_widgets["#model-select"].value = "gemini-flash-latest"
        mock_ui_widgets["#orchestrator-select"].value = "orchestrator"

        # Save settings
        modal_instance.on_save_pressed()

        # Verify file was written
        assert config_file.exists()

        # Verify content (theme setting should be preserved if it exists or ignored if not set)
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

    def test_save_settings_invalid_model(self, modal, mock_ui_widgets):
        """Test saving with invalid model shows error."""
        modal_instance, config_file = modal

        # Set values on mocked widgets with invalid model
        mock_ui_widgets["#api-key-input"].value = "test-api-key"
        mock_ui_widgets["#model-select"].value = "invalid-model-id"
        mock_ui_widgets["#orchestrator-select"].value = "orchestrator"

        # Save settings
        modal_instance.on_save_pressed()

        # Verify error notification was shown
        modal_instance.notify.assert_called_once()
        call_args = modal_instance.notify.call_args
        assert "severity" in call_args[1]
        assert call_args[1]["severity"] == "error"

        # Verify modal was NOT dismissed
        modal_instance.dismiss.assert_not_called()

        # Verify file was NOT written (or only contained previous data)
        assert not config_file.exists() or json.loads(config_file.read_text()) == {}

    def test_reset_settings(self, modal, mock_ui_widgets):
        """Test resetting settings to defaults."""
        modal_instance, _ = modal

        # Reset settings
        modal_instance.on_reset_pressed()

        # Verify values were reset
        assert (
            mock_ui_widgets["#api-key-input"].value == ""
        )  # FIXED: Assert for empty string
        assert mock_ui_widgets["#model-select"].value == ModelRegistry.DEFAULT.id
        assert mock_ui_widgets["#orchestrator-select"].value == "orchestrator"

        # Verify app theme was reset
        assert modal_instance.app.theme == "textual-dark"

        # Verify notification
        modal_instance.notify.assert_called_once()
        assert "reset" in modal_instance.notify.call_args[0][0].lower()

    def test_theme_select_changes_and_saves(self, modal, tmp_path):
        """Test selecting a theme immediately applies it and saves to config."""
        modal_instance, config_file = modal

        # Mock Select.Changed event for the theme select
        mock_event = Mock()
        mock_event.value = "textual-light"

        # The modal starts with textual-dark (default)
        initial_theme = modal_instance.app.theme
        assert initial_theme == "textual-dark"

        # Create a custom property mock that saves to config when set
        theme_value = {"current": initial_theme}

        def theme_setter(self, value):
            theme_value["current"] = value
            # Simulate what ADHApp.theme setter does
            from adh_cli.config.settings_manager import set_settings

            set_settings({"theme": value})

        type(modal_instance.app).theme = property(
            lambda self: theme_value["current"], theme_setter
        )

        # Patch ConfigPaths to use tmp_path for this test
        with patch(
            "adh_cli.config.settings_manager.ConfigPaths.get_config_file",
            return_value=config_file,
        ):
            # Trigger the change handler
            modal_instance.on_theme_select_changed(mock_event)

            # 1. Verify theme is immediately applied
            assert modal_instance.app.theme == "textual-light"

            # 2. Verify setting is persisted
            assert config_file.exists()
            settings = json.loads(config_file.read_text())
            assert settings["theme"] == "textual-light"

    def test_close_button(self, modal):
        """Test close button dismisses modal."""
        modal_instance, _ = modal

        modal_instance.on_close_pressed()

        modal_instance.dismiss.assert_called_once()

    def test_load_existing_settings(self, modal, mock_ui_widgets):
        """Test loading existing settings on mount, including theme."""
        modal_instance, config_file = modal

        # Create config file with settings
        settings = {
            "api_key": "existing-key",
            "model": "gemini-2.5-pro",
            "orchestrator_agent": "planner",
            "theme": "textual-light",  # ADDED: Theme setting
        }

        config_file.write_text(json.dumps(settings))

        # Trigger on_mount
        modal_instance.on_mount()

        # Verify values were loaded
        assert mock_ui_widgets["#api-key-input"].value == "existing-key"
        assert mock_ui_widgets["#model-select"].value == "gemini-2.5-pro"
        assert mock_ui_widgets["#orchestrator-select"].value == "planner"
        assert (
            mock_ui_widgets["#theme-select"].value == "textual-light"
        )  # ADDED: Theme check

    def test_load_settings_missing_file(self, modal, mock_ui_widgets):
        """Test loading settings when config file doesn't exist."""
        modal_instance, config_file = modal

        # Ensure config file doesn't exist
        assert not config_file.exists()

        # Trigger on_mount - should not raise error
        modal_instance.on_mount()

        # Values should retain defaults set in mock_ui_widgets
        assert mock_ui_widgets["#api-key-input"].value is None
        assert mock_ui_widgets["#model-select"].value == ModelRegistry.DEFAULT.id
        assert (
            mock_ui_widgets["#theme-select"].value == "textual-dark"
        )  # Check theme default

    def test_load_settings_invalid_json(self, modal, mock_ui_widgets):
        """Test loading settings with corrupted config file."""
        modal_instance, config_file = modal

        # Create invalid JSON
        config_file.write_text("{invalid json")

        # Trigger on_mount - should handle gracefully
        modal_instance.on_mount()

        # Test passes if it doesn't crash, and no widget values were changed due to missing settings

    def test_load_settings_invalid_model(self, modal, mock_ui_widgets):
        """Test loading settings with invalid model ID."""
        modal_instance, config_file = modal

        # Create config with invalid model
        settings = {
            "api_key": "test-key",
            "model": "invalid-model-id",
            "orchestrator_agent": "orchestrator",
        }

        config_file.write_text(json.dumps(settings))

        # Set a known initial value for the model select widget
        mock_ui_widgets["#model-select"].value = "initial-value"

        # Trigger on_mount - should handle gracefully
        modal_instance.on_mount()

        # Valid settings should still be loaded
        assert mock_ui_widgets["#api-key-input"].value == "test-key"
        assert mock_ui_widgets["#orchestrator-select"].value == "orchestrator"

        # The invalid model should not have changed the select widget's value
        assert mock_ui_widgets["#model-select"].value == "initial-value"
