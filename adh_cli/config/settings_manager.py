"""Centralized settings management for ADH CLI.

Settings Schema:
    {
        "api_key": str,              # Google API key for Gemini models
        "model": str,                # Model ID (e.g., "gemini-flash-latest")
        "orchestrator_agent": str,   # Agent name (e.g., "orchestrator", "planner")
        "theme": str,                # Theme name (e.g., "textual-dark", "nord")
    }
"""

import json
from typing import Any, Dict
import logging

from adh_cli.core.config_paths import ConfigPaths

LOGGER = logging.getLogger(__name__)

# Default theme if none is saved
DEFAULT_THEME = "textual-dark"

# Valid Textual theme names (all built-in themes)
VALID_THEMES = {
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

# Theme options for UI dropdowns (display name, theme ID)
THEME_OPTIONS = [
    ("Textual Dark", "textual-dark"),
    ("Textual Light", "textual-light"),
    ("Nord", "nord"),
    ("Gruvbox", "gruvbox"),
    ("Dracula", "dracula"),
    ("Tokyo Night", "tokyo-night"),
    ("Catppuccin Mocha", "catppuccin-mocha"),
    ("Catppuccin Latte", "catppuccin-latte"),
    ("Monokai", "monokai"),
    ("Solarized Light", "solarized-light"),
    ("Flexoki", "flexoki"),
    ("Textual ANSI", "textual-ansi"),
]


def load_config_data() -> Dict[str, Any]:
    """Loads configuration data from config.json."""
    config_file = ConfigPaths.get_config_file()
    if not config_file.exists():
        return {}
    try:
        content = config_file.read_text(encoding="utf-8")
        if not content.strip():
            return {}
        return json.loads(content)
    except (json.JSONDecodeError, IOError) as e:
        LOGGER.warning(
            f"Failed to load config file: {e}. Using empty configuration.",
            exc_info=True,
        )
        return {}


def _save_config_data(data: Dict[str, Any]) -> None:
    """Saves the configuration data to config.json."""
    config_file = ConfigPaths.get_config_file()
    try:
        # Ensure the directory exists
        config_file.parent.mkdir(parents=True, exist_ok=True)
        # Write the updated configuration
        config_file.write_text(json.dumps(data, indent=4), encoding="utf-8")
    except IOError as e:
        LOGGER.error(f"Failed to save config file: {e}", exc_info=True)


def get_setting(key: str, default: Any = None) -> Any:
    """Retrieve a setting from the config file."""
    data = load_config_data()
    return data.get(key, default)


def set_settings(updates: Dict[str, Any]) -> None:
    """Load existing settings, apply updates, and save back."""
    data = load_config_data()
    data.update(updates)
    _save_config_data(data)


def validate_theme(theme: str) -> bool:
    """Check if a theme name is valid.

    Args:
        theme: Theme name to validate

    Returns:
        True if theme is a valid Textual theme name
    """
    return theme in VALID_THEMES


def get_theme_setting() -> str:
    """Retrieve the saved theme setting, falling back to default.

    Returns:
        A valid theme name. If the saved theme is invalid, returns DEFAULT_THEME.
    """
    theme = get_setting("theme", DEFAULT_THEME)
    # Validate and fallback to default if invalid
    return theme if validate_theme(theme) else DEFAULT_THEME
