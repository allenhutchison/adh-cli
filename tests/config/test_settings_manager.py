import json
from pathlib import Path
import pytest
from unittest.mock import MagicMock

# The module under test
from adh_cli.config.settings_manager import (
    load_config_data,
    set_settings,
    get_setting,
    get_theme_setting,
    validate_theme,
    DEFAULT_THEME,
    VALID_THEMES,
)


# Mock the ConfigPaths dependency
@pytest.fixture
def mock_config_file(tmp_path: Path, monkeypatch):
    """Fixture to mock ConfigPaths.get_config_file to return a temp file path."""
    temp_config_file = tmp_path / "config.json"
    mock_config_paths = MagicMock()
    mock_config_paths.get_config_file.return_value = temp_config_file

    # We must patch the dependency in the settings_manager module
    monkeypatch.setattr(
        "adh_cli.config.settings_manager.ConfigPaths", mock_config_paths
    )

    return temp_config_file


def test_load_config_data_missing_file(mock_config_file: Path):
    """Test loading data when the config file does not exist."""
    assert not mock_config_file.exists()
    assert load_config_data() == {}


def test_load_config_data_empty_file(mock_config_file: Path):
    """Test loading data from an empty config file."""
    mock_config_file.write_text("")
    assert load_config_data() == {}


def test_load_config_data_corrupt_json(mock_config_file: Path):
    """Test loading data from a file with invalid JSON."""
    mock_config_file.write_text("this is not json")
    # This should log a warning and return empty dict
    assert load_config_data() == {}


def test_set_settings_new_file(mock_config_file: Path):
    """Test setting a new configuration when the file doesn't exist."""
    updates = {"api_key": "123", "theme": "textual-light"}
    set_settings(updates)

    # Check that the file was created and contains the updates
    assert mock_config_file.exists()
    content = json.loads(mock_config_file.read_text())
    assert content == updates


def test_set_settings_existing_file_merge(mock_config_file: Path):
    """Test setting new configuration and merging with existing data."""
    initial_data = {"api_key": "old_key", "model": "default-model"}
    mock_config_file.write_text(json.dumps(initial_data))

    updates = {"api_key": "new_key", "theme": "textual-light"}
    set_settings(updates)

    # Check that the file content is a merge
    expected_data = {
        "api_key": "new_key",
        "model": "default-model",
        "theme": "textual-light",
    }
    content = json.loads(mock_config_file.read_text())
    assert content == expected_data


def test_get_setting_exists(mock_config_file: Path):
    """Test retrieving an existing setting."""
    data = {"test_key": "test_value"}
    mock_config_file.write_text(json.dumps(data))
    assert get_setting("test_key") == "test_value"


def test_get_setting_does_not_exist(mock_config_file: Path):
    """Test retrieving a non-existing setting."""
    data = {"test_key": "test_value"}
    mock_config_file.write_text(json.dumps(data))

    # Test with default value
    assert get_setting("non_existent", "default") == "default"
    # Test without default value
    assert get_setting("non_existent") is None


def test_get_theme_setting_saved(mock_config_file: Path):
    """Test retrieving a saved theme setting."""
    data = {"theme": "textual-light"}
    mock_config_file.write_text(json.dumps(data))
    assert get_theme_setting() == "textual-light"


def test_get_theme_setting_default(mock_config_file: Path):
    """Test retrieving theme setting when none is saved."""
    # Ensure config file is empty or missing
    if mock_config_file.exists():
        mock_config_file.unlink()

    assert get_theme_setting() == DEFAULT_THEME


def test_get_theme_setting_other_settings_exist(mock_config_file: Path):
    """Test retrieving theme setting when other settings exist but theme is missing."""
    data = {"api_key": "test-key"}
    mock_config_file.write_text(json.dumps(data))
    assert get_theme_setting() == DEFAULT_THEME


def test_validate_theme_valid():
    """Test theme validation with valid theme names."""
    assert validate_theme("textual-dark") is True
    assert validate_theme("nord") is True
    assert validate_theme("gruvbox") is True
    assert validate_theme("dracula") is True


def test_validate_theme_invalid():
    """Test theme validation with invalid theme names."""
    assert validate_theme("invalid-theme") is False
    assert validate_theme("") is False
    assert validate_theme("random") is False


def test_get_theme_setting_invalid_theme_fallback(mock_config_file: Path):
    """Test that invalid saved theme falls back to default."""
    data = {"theme": "invalid-theme-name"}
    mock_config_file.write_text(json.dumps(data))
    # Should return default since saved theme is invalid
    assert get_theme_setting() == DEFAULT_THEME


def test_valid_themes_constant():
    """Test that VALID_THEMES contains expected themes."""
    expected_themes = {
        "textual-dark",
        "textual-light",
        "nord",
        "gruvbox",
        "dracula",
        "tokyo-night",
        "catppuccin-mocha",
        "catppuccin-latte",
        "monokai",
        "solarized-light",
        "flexoki",
        "textual-ansi",
    }
    assert VALID_THEMES == expected_themes
