"""Tests for centralized model configuration."""

import json

import pytest

from adh_cli.config.models import ModelRegistry, get_default_model, get_default_model_id
from adh_cli.core.config_paths import ConfigPaths


def test_get_by_id_supports_aliases():
    """Aliases like ``gemini-pro`` map to the canonical configuration."""

    config = ModelRegistry.get_by_id("gemini-pro")
    assert config is not None
    assert config.id == ModelRegistry.PRO_25.id
    assert config.full_id == ModelRegistry.PRO_25.full_id


def test_all_defined_aliases():
    """All aliases in _ALIASES should resolve to valid models."""
    
    # Test aliases that don't conflict with actual model IDs
    # Note: "gemini-flash-latest" is both an actual model ID and an alias,
    # so the actual model ID takes precedence
    aliases_to_test = {
        "gemini-pro": ModelRegistry.PRO_25.id,
        "gemini-2.5-flash": ModelRegistry.FLASH_LATEST.id,
        "gemini-flash": ModelRegistry.FLASH_LATEST.id,
    }
    
    for alias, expected_id in aliases_to_test.items():
        config = ModelRegistry.get_by_id(alias)
        assert config is not None, f"Alias '{alias}' should resolve to a model"
        assert config.id == expected_id, f"Alias '{alias}' should resolve to '{expected_id}'"
    
    # Test that gemini-flash-latest resolves (as an actual model ID, not alias)
    config = ModelRegistry.get_by_id("gemini-flash-latest")
    assert config is not None
    assert config.id == ModelRegistry.FLASH_LATEST.id


def test_get_by_id_strips_models_prefix():
    """Model IDs with 'models/' prefix should be handled correctly."""
    
    # Test with and without prefix
    config_without = ModelRegistry.get_by_id(ModelRegistry.FLASH_LATEST.id)
    config_with = ModelRegistry.get_by_id(f"models/{ModelRegistry.FLASH_LATEST.id}")
    
    assert config_without is not None
    assert config_with is not None
    assert config_without.id == config_with.id


def test_all_registered_models_retrievable():
    """All models in _ALL_MODELS should be retrievable by their ID."""
    
    for model in ModelRegistry.all_models():
        retrieved = ModelRegistry.get_by_id(model.id)
        assert retrieved is not None, f"Model '{model.id}' should be retrievable"
        assert retrieved.id == model.id
        assert retrieved.display_name == model.display_name


def test_get_display_name():
    """get_display_name should return proper display names."""
    
    # Test with valid model ID
    display_name = ModelRegistry.get_display_name(ModelRegistry.FLASH_LATEST.id)
    assert display_name == ModelRegistry.FLASH_LATEST.display_name
    
    # Test with alias
    display_name = ModelRegistry.get_display_name("gemini-pro")
    assert display_name == ModelRegistry.PRO_25.display_name
    
    # Test with unknown model (should return the ID itself)
    unknown_id = "unknown-model-xyz"
    display_name = ModelRegistry.get_display_name(unknown_id)
    assert display_name == unknown_id
    
    # Test with None (should return empty string)
    display_name = ModelRegistry.get_display_name(None)
    assert display_name == ""


def test_model_config_properties():
    """ModelConfig should have all expected properties."""
    
    model = ModelRegistry.FLASH_LATEST
    
    # Test basic properties
    assert isinstance(model.id, str)
    assert isinstance(model.full_id, str)
    assert isinstance(model.display_name, str)
    assert isinstance(model.description, str)
    assert isinstance(model.context_window, int)
    assert isinstance(model.max_output_tokens, int)
    assert isinstance(model.supports_function_calling, bool)
    assert isinstance(model.supports_streaming, bool)
    assert isinstance(model.cost_per_1m_input, float)
    assert isinstance(model.cost_per_1m_output, float)
    assert isinstance(model.recommended_for, tuple)
    assert isinstance(model.deprecated, bool)
    
    # Test api_id property
    assert model.api_id == model.full_id or model.api_id == model.id


def test_ui_options_returns_display_and_id():
    """UI options should expose display name and canonical identifier."""

    options = ModelRegistry.ui_options()
    assert (ModelRegistry.DEFAULT.display_name, ModelRegistry.DEFAULT.id) in options


@pytest.mark.parametrize(
    "model_id,expected",
    [
        (ModelRegistry.DEFAULT.id, True),
        ("gemini-pro", True),
        ("unknown-model", False),
        ("", False),
        (None, False),
    ],
)
def test_validate_model_id(model_id, expected):
    """Validation returns a boolean flag indicating support."""

    is_valid, _ = ModelRegistry.validate_model_id(model_id)  # type: ignore[arg-type]
    assert is_valid is expected


def test_get_default_model_prefers_environment(monkeypatch, tmp_path):
    """Environment variable should override persisted configuration."""

    monkeypatch.setenv("ADH_MODEL", ModelRegistry.PRO_25.id)
    monkeypatch.setattr(ConfigPaths, "BASE_DIR", tmp_path)

    # Even if a different model is persisted, env should win
    config_file = ConfigPaths.get_config_file()
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps({"model": ModelRegistry.FLASH_LITE_LATEST.id}))

    model = get_default_model()
    assert model.id == ModelRegistry.PRO_25.id
    assert get_default_model_id() == ModelRegistry.PRO_25.id


def test_get_default_model_reads_config(monkeypatch, tmp_path):
    """Persisted configuration should override the hard-coded default."""

    monkeypatch.delenv("ADH_MODEL", raising=False)
    monkeypatch.setattr(ConfigPaths, "BASE_DIR", tmp_path)

    config_file = ConfigPaths.get_config_file()
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps({"model": ModelRegistry.FLASH_LITE_LATEST.id}))

    model = get_default_model()
    assert model.id == ModelRegistry.FLASH_LITE_LATEST.id


def test_get_default_model_falls_back(monkeypatch, tmp_path):
    """If nothing else is configured, use the registry default."""

    monkeypatch.delenv("ADH_MODEL", raising=False)
    monkeypatch.setattr(ConfigPaths, "BASE_DIR", tmp_path)

    model = get_default_model()
    assert model.id == ModelRegistry.DEFAULT.id
