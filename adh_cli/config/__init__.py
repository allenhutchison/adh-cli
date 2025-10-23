"""Configuration utilities for the ADH CLI application."""

from .models import ModelConfig, ModelRegistry, get_default_model, get_default_model_id
from .settings_manager import (
    get_setting,
    set_settings,
    get_theme_setting,
    load_config_data,
    validate_theme,
    DEFAULT_THEME,
    VALID_THEMES,
    THEME_OPTIONS,
)

__all__ = [
    # Model configuration
    "ModelConfig",
    "ModelRegistry",
    "get_default_model",
    "get_default_model_id",
    # Settings management
    "get_setting",
    "set_settings",
    "get_theme_setting",
    "load_config_data",
    "validate_theme",
    "DEFAULT_THEME",
    "VALID_THEMES",
    "THEME_OPTIONS",
]
