"""Tests for centralized model configuration."""

import json

import pytest

from adh_cli.config.models import (
    ModelRegistry,
    get_default_model,
    get_default_model_id,
    _load_json_config,
)
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


# --- Model Aliases Tests ---


def test_load_json_config_nonexistent_file(tmp_path):
    """Loading a non-existent file should return empty dict."""
    
    non_existent = tmp_path / "does_not_exist.json"
    result = _load_json_config(non_existent)
    assert result == {}


def test_load_json_config_empty_file(tmp_path):
    """Loading an empty file should return empty dict."""
    
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("")
    result = _load_json_config(empty_file)
    assert result == {}


def test_load_json_config_valid_file(tmp_path):
    """Loading a valid JSON file should return parsed content."""
    
    valid_file = tmp_path / "valid.json"
    data = {"key": "value", "number": 42}
    valid_file.write_text(json.dumps(data))
    result = _load_json_config(valid_file)
    assert result == data


def test_load_json_config_invalid_json(tmp_path):
    """Loading invalid JSON should return empty dict and not crash."""
    
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{invalid json")
    result = _load_json_config(invalid_file)
    assert result == {}


def test_get_model_and_config_direct_model():
    """Getting a direct model ID should return model and empty params."""
    
    model, params = ModelRegistry.get_model_and_config(ModelRegistry.FLASH_LATEST.id)
    assert model is not None
    assert model.id == ModelRegistry.FLASH_LATEST.id
    assert params == {}


def test_get_model_and_config_simple_alias():
    """Getting a simple built-in alias should return model and empty params."""
    
    # Clear cache to ensure we're testing the actual logic
    if hasattr(ModelRegistry, "_cached_rich_aliases"):
        delattr(ModelRegistry, "_cached_rich_aliases")
    
    model, params = ModelRegistry.get_model_and_config("gemini-pro")
    assert model is not None
    assert model.id == ModelRegistry.PRO_25.id
    assert params == {}


def test_get_model_and_config_unknown():
    """Getting an unknown model should return None and empty params."""
    
    model, params = ModelRegistry.get_model_and_config("unknown-model-xyz")
    assert model is None
    assert params == {}


def test_get_model_and_config_none():
    """Getting None should return None and empty params."""
    
    model, params = ModelRegistry.get_model_and_config(None)
    assert model is None
    assert params == {}


def test_load_rich_aliases_from_file(monkeypatch, tmp_path):
    """Custom aliases should be loaded from the config file."""
    
    # Clear cache
    if hasattr(ModelRegistry, "_cached_rich_aliases"):
        delattr(ModelRegistry, "_cached_rich_aliases")
    
    monkeypatch.setattr(ConfigPaths, "BASE_DIR", tmp_path)
    
    # Create a model aliases file
    aliases_file = ConfigPaths.get_model_aliases_file()
    aliases_file.parent.mkdir(parents=True, exist_ok=True)
    
    aliases_data = {
        "model_aliases": {
            "creative": {
                "model_id": ModelRegistry.FLASH_LATEST.id,
                "parameters": {
                    "temperature": 1.2,
                    "top_p": 0.95
                }
            },
            "precise": {
                "model_id": ModelRegistry.PRO_25.id,
                "parameters": {
                    "temperature": 0.1,
                    "max_output_tokens": 8192,
                    "top_k": 20
                }
            }
        }
    }
    aliases_file.write_text(json.dumps(aliases_data))
    
    # Load and verify
    model, params = ModelRegistry.get_model_and_config("creative")
    assert model is not None
    assert model.id == ModelRegistry.FLASH_LATEST.id
    assert params["temperature"] == 1.2
    assert params["top_p"] == 0.95
    
    model, params = ModelRegistry.get_model_and_config("precise")
    assert model is not None
    assert model.id == ModelRegistry.PRO_25.id
    assert params["temperature"] == 0.1
    assert params["max_output_tokens"] == 8192
    assert params["top_k"] == 20


def test_custom_alias_overrides_simple_alias(monkeypatch, tmp_path):
    """Custom aliases should override built-in simple aliases."""
    
    # Clear cache
    if hasattr(ModelRegistry, "_cached_rich_aliases"):
        delattr(ModelRegistry, "_cached_rich_aliases")
    
    monkeypatch.setattr(ConfigPaths, "BASE_DIR", tmp_path)
    
    # Create a custom alias that overrides "gemini-pro"
    aliases_file = ConfigPaths.get_model_aliases_file()
    aliases_file.parent.mkdir(parents=True, exist_ok=True)
    
    aliases_data = {
        "model_aliases": {
            "gemini-pro": {
                "model_id": ModelRegistry.FLASH_LATEST.id,
                "parameters": {
                    "temperature": 0.5
                }
            }
        }
    }
    aliases_file.write_text(json.dumps(aliases_data))
    
    # Should now resolve to Flash with custom params
    model, params = ModelRegistry.get_model_and_config("gemini-pro")
    assert model is not None
    assert model.id == ModelRegistry.FLASH_LATEST.id
    assert params["temperature"] == 0.5


def test_invalid_alias_structure_logged(monkeypatch, tmp_path, caplog):
    """Invalid alias structures should be logged but not crash."""
    
    # Clear cache
    if hasattr(ModelRegistry, "_cached_rich_aliases"):
        delattr(ModelRegistry, "_cached_rich_aliases")
    
    monkeypatch.setattr(ConfigPaths, "BASE_DIR", tmp_path)
    
    aliases_file = ConfigPaths.get_model_aliases_file()
    aliases_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Missing model_id
    aliases_data = {
        "model_aliases": {
            "bad_alias": {
                "parameters": {"temperature": 0.5}
            }
        }
    }
    aliases_file.write_text(json.dumps(aliases_data))
    
    model, params = ModelRegistry.get_model_and_config("bad_alias")
    assert model is None
    assert params == {}


def test_alias_pointing_to_unknown_model(monkeypatch, tmp_path):
    """Alias pointing to unknown model should return None."""
    
    # Clear cache
    if hasattr(ModelRegistry, "_cached_rich_aliases"):
        delattr(ModelRegistry, "_cached_rich_aliases")
    
    monkeypatch.setattr(ConfigPaths, "BASE_DIR", tmp_path)
    
    aliases_file = ConfigPaths.get_model_aliases_file()
    aliases_file.parent.mkdir(parents=True, exist_ok=True)
    
    aliases_data = {
        "model_aliases": {
            "broken": {
                "model_id": "nonexistent-model",
                "parameters": {}
            }
        }
    }
    aliases_file.write_text(json.dumps(aliases_data))
    
    model, params = ModelRegistry.get_model_and_config("broken")
    assert model is None
    assert params == {}


def test_validate_model_id_with_alias(monkeypatch, tmp_path):
    """Validation should work with custom aliases."""
    
    # Clear cache
    if hasattr(ModelRegistry, "_cached_rich_aliases"):
        delattr(ModelRegistry, "_cached_rich_aliases")
    
    monkeypatch.setattr(ConfigPaths, "BASE_DIR", tmp_path)
    
    aliases_file = ConfigPaths.get_model_aliases_file()
    aliases_file.parent.mkdir(parents=True, exist_ok=True)
    
    aliases_data = {
        "model_aliases": {
            "valid_alias": {
                "model_id": ModelRegistry.FLASH_LATEST.id,
                "parameters": {}
            },
            "invalid_alias": {
                "model_id": "nonexistent",
                "parameters": {}
            }
        }
    }
    aliases_file.write_text(json.dumps(aliases_data))
    
    # Valid alias should pass validation
    is_valid, error = ModelRegistry.validate_model_id("valid_alias")
    assert is_valid
    assert error is None
    
    # Invalid alias should fail with specific error
    is_valid, error = ModelRegistry.validate_model_id("invalid_alias")
    assert not is_valid
    assert "points to unknown base model" in error


def test_ui_options_includes_custom_aliases(monkeypatch, tmp_path):
    """UI options should include custom aliases."""
    
    # Clear cache
    if hasattr(ModelRegistry, "_cached_rich_aliases"):
        delattr(ModelRegistry, "_cached_rich_aliases")
    
    monkeypatch.setattr(ConfigPaths, "BASE_DIR", tmp_path)
    
    aliases_file = ConfigPaths.get_model_aliases_file()
    aliases_file.parent.mkdir(parents=True, exist_ok=True)
    
    aliases_data = {
        "model_aliases": {
            "my_custom": {
                "model_id": ModelRegistry.FLASH_LATEST.id,
                "parameters": {"temperature": 0.8}
            }
        }
    }
    aliases_file.write_text(json.dumps(aliases_data))
    
    options = ModelRegistry.ui_options()
    
    # Check that custom alias is included
    alias_option = None
    for display_name, model_id in options:
        if model_id == "my_custom":
            alias_option = (display_name, model_id)
            break
    
    assert alias_option is not None
    assert "my_custom" in alias_option[0]
    assert "Alias for" in alias_option[0]


def test_generation_params_type_conversion(monkeypatch, tmp_path):
    """Parameters should be correctly type-converted."""
    
    # Clear cache
    if hasattr(ModelRegistry, "_cached_rich_aliases"):
        delattr(ModelRegistry, "_cached_rich_aliases")
    
    monkeypatch.setattr(ConfigPaths, "BASE_DIR", tmp_path)
    
    aliases_file = ConfigPaths.get_model_aliases_file()
    aliases_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Provide params as strings (JSON parses them correctly)
    aliases_data = {
        "model_aliases": {
            "test": {
                "model_id": ModelRegistry.FLASH_LATEST.id,
                "parameters": {
                    "temperature": "0.7",  # String that should convert to float
                    "max_output_tokens": "4096",  # String that should convert to int
                    "top_p": 0.95,  # Already correct type
                    "top_k": 40  # Already correct type
                }
            }
        }
    }
    aliases_file.write_text(json.dumps(aliases_data))
    
    model, params = ModelRegistry.get_model_and_config("test")
    assert model is not None
    assert isinstance(params["temperature"], float)
    assert params["temperature"] == 0.7
    assert isinstance(params["max_output_tokens"], int)
    assert params["max_output_tokens"] == 4096
    assert isinstance(params["top_p"], float)
    assert isinstance(params["top_k"], int)


def test_default_aliases_always_loaded():
    """Built-in default aliases should always be loaded from the package."""
    
    # Clear cache to force reload
    if hasattr(ModelRegistry, "_cached_rich_aliases"):
        delattr(ModelRegistry, "_cached_rich_aliases")
    
    # Test that default aliases are present
    model, params = ModelRegistry.get_model_and_config("gemini-pro")
    assert model is not None
    assert model.id == ModelRegistry.PRO_25.id
    assert params == {}  # Default aliases have no custom parameters
    
    model, params = ModelRegistry.get_model_and_config("gemini-2.5-flash")
    assert model is not None
    assert model.id == ModelRegistry.FLASH_LATEST.id
    
    model, params = ModelRegistry.get_model_and_config("gemini-flash")
    assert model is not None
    assert model.id == ModelRegistry.FLASH_LATEST.id


def test_user_aliases_override_defaults(monkeypatch, tmp_path):
    """User-defined aliases should override built-in defaults."""
    
    # Clear cache
    if hasattr(ModelRegistry, "_cached_rich_aliases"):
        delattr(ModelRegistry, "_cached_rich_aliases")
    
    monkeypatch.setattr(ConfigPaths, "BASE_DIR", tmp_path)
    
    # Create user config that overrides "gemini-pro" with custom parameters
    aliases_file = ConfigPaths.get_model_aliases_file()
    aliases_file.parent.mkdir(parents=True, exist_ok=True)
    
    aliases_data = {
        "model_aliases": {
            "gemini-pro": {
                "model_id": ModelRegistry.FLASH_LATEST.id,  # Different model
                "parameters": {
                    "temperature": 0.9  # Custom parameter
                }
            }
        }
    }
    aliases_file.write_text(json.dumps(aliases_data))
    
    # Should resolve to the user's override
    model, params = ModelRegistry.get_model_and_config("gemini-pro")
    assert model is not None
    assert model.id == ModelRegistry.FLASH_LATEST.id  # Changed from default
    assert params["temperature"] == 0.9  # Has custom parameter
    
    # Other default aliases should still work
    model, params = ModelRegistry.get_model_and_config("gemini-flash")
    assert model is not None
    assert model.id == ModelRegistry.FLASH_LATEST.id
    assert params == {}  # No custom parameters
    
    # Clean up cache to avoid affecting other tests
    if hasattr(ModelRegistry, "_cached_rich_aliases"):
        delattr(ModelRegistry, "_cached_rich_aliases")


def test_default_aliases_file_exists():
    """The built-in default aliases file must exist in the package."""
    from pathlib import Path
    
    # Get the path to the default aliases file
    # Go from tests/config/ up to project root, then into adh_cli/config/defaults/
    test_dir = Path(__file__).parent  # tests/config/
    project_root = test_dir.parent.parent  # project root
    default_file = project_root / "adh_cli" / "config" / "defaults" / "model_aliases.json"
    
    # File must exist
    assert default_file.exists(), "Default model_aliases.json file is missing from package"
    
    # File must be valid JSON
    content = default_file.read_text()
    data = json.loads(content)  # Will raise if invalid JSON
    
    # Must have model_aliases key
    assert "model_aliases" in data, "Default file missing 'model_aliases' key"
    
    # Must contain expected default aliases
    aliases = data["model_aliases"]
    assert "gemini-pro" in aliases, "Missing default alias: gemini-pro"
    assert "gemini-2.5-flash" in aliases, "Missing default alias: gemini-2.5-flash"
    assert "gemini-flash" in aliases, "Missing default alias: gemini-flash"
    
    # Each alias must have model_id
    for alias_name, alias_data in aliases.items():
        assert "model_id" in alias_data, f"Alias '{alias_name}' missing model_id"
        assert "parameters" in alias_data, f"Alias '{alias_name}' missing parameters"


def test_system_works_without_user_aliases(monkeypatch, tmp_path):
    """System should work fine when user has no custom aliases file."""
    
    # Clear cache
    if hasattr(ModelRegistry, "_cached_rich_aliases"):
        delattr(ModelRegistry, "_cached_rich_aliases")
    
    # Point to empty user config directory (no model_aliases.json)
    monkeypatch.setattr(ConfigPaths, "BASE_DIR", tmp_path)
    
    # Default aliases should still work (loaded from package defaults)
    model, params = ModelRegistry.get_model_and_config("gemini-pro")
    assert model is not None
    assert model.id == ModelRegistry.PRO_25.id
    
    # Clean up cache
    if hasattr(ModelRegistry, "_cached_rich_aliases"):
        delattr(ModelRegistry, "_cached_rich_aliases")


def test_invalid_default_alias_logged(monkeypatch, tmp_path, caplog):
    """Invalid entries in default file should be logged but not crash."""
    
    # Clear cache
    if hasattr(ModelRegistry, "_cached_rich_aliases"):
        delattr(ModelRegistry, "_cached_rich_aliases")
    
    # We can't easily modify the package's default file, but we can test
    # that the system handles user config with mixed valid/invalid gracefully
    monkeypatch.setattr(ConfigPaths, "BASE_DIR", tmp_path)
    
    aliases_file = ConfigPaths.get_model_aliases_file()
    aliases_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Mix of valid and invalid aliases
    aliases_data = {
        "model_aliases": {
            "valid": {
                "model_id": ModelRegistry.FLASH_LATEST.id,
                "parameters": {}
            },
            "invalid_no_model": {
                "parameters": {}  # Missing model_id
            },
            "invalid_bad_param": {
                "model_id": ModelRegistry.FLASH_LATEST.id,
                "parameters": {
                    "temperature": "not-a-number"  # Invalid type
                }
            }
        }
    }
    aliases_file.write_text(json.dumps(aliases_data))
    
    # Should load valid alias and log warnings for invalid ones
    aliases = ModelRegistry._load_rich_aliases()
    
    # Valid alias should be present
    assert "valid" in aliases
    
    # Invalid aliases should be skipped
    assert "invalid_no_model" not in aliases
    
    # Alias with bad param should still load (just param is skipped)
    assert "invalid_bad_param" in aliases
    
    # Default aliases should still be available
    assert "gemini-pro" in aliases
    
    # Clean up cache
    if hasattr(ModelRegistry, "_cached_rich_aliases"):
        delattr(ModelRegistry, "_cached_rich_aliases")
