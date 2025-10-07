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
