"""Centralized model configuration for the ADH CLI application."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from adh_cli.core.config_paths import ConfigPaths

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelConfig:
    """Configuration metadata for a Gemini model."""

    id: str
    full_id: str
    display_name: str
    description: str
    context_window: int
    max_output_tokens: int
    supports_function_calling: bool
    supports_streaming: bool
    cost_per_1k_input: float
    cost_per_1k_output: float
    recommended_for: Tuple[str, ...]
    deprecated: bool = False
    replacement: Optional[str] = None

    @property
    def api_id(self) -> str:
        """Return the identifier that should be sent to the API."""

        return self.full_id or self.id


class ModelRegistry:
    """Registry providing a single source of truth for Gemini models."""

    FLASH_LATEST = ModelConfig(
        id="gemini-flash-latest",
        full_id="models/gemini-flash-latest",
        display_name="Gemini Flash (Latest)",
        description="Fast, general-purpose model suitable for most tasks.",
        context_window=1_000_000,
        max_output_tokens=8_192,
        supports_function_calling=True,
        supports_streaming=True,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
        recommended_for=("chat", "analysis", "code", "general"),
    )

    FLASH_LITE_LATEST = ModelConfig(
        id="gemini-flash-lite-latest",
        full_id="models/gemini-flash-lite-latest",
        display_name="Gemini Flash Lite (Latest)",
        description="Ultra-fast, low-cost model for lightweight interactions.",
        context_window=1_000_000,
        max_output_tokens=8_192,
        supports_function_calling=True,
        supports_streaming=True,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
        recommended_for=("chat", "simple-tasks"),
    )

    PRO_25 = ModelConfig(
        id="gemini-2.5-pro",
        full_id="models/gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        description="Latest Pro model providing the highest quality outputs.",
        context_window=2_000_000,
        max_output_tokens=8_192,
        supports_function_calling=True,
        supports_streaming=True,
        cost_per_1k_input=0.00125,
        cost_per_1k_output=0.005,
        recommended_for=("complex-reasoning", "code-generation", "analysis"),
    )

    _ALL_MODELS: Tuple[ModelConfig, ...] = (
        FLASH_LATEST,
        FLASH_LITE_LATEST,
        PRO_25,
    )

    DEFAULT = FLASH_LATEST
    _ALIASES: Dict[str, str] = {
        "gemini-pro": PRO_25.id,
    }

    @classmethod
    def all_models(cls) -> Tuple[ModelConfig, ...]:
        """Return all registered models."""

        return cls._ALL_MODELS

    @classmethod
    @classmethod
    def _indexed_models(cls) -> Dict[str, ModelConfig]:
        """Return a mapping of model identifiers to configuration objects."""

        if not hasattr(cls, "_cached_indexed_models"):
            cls._cached_indexed_models = {model.id: model for model in cls.all_models()}
        return cls._cached_indexed_models

    @classmethod
    def get_by_id(cls, model_id: Optional[str]) -> Optional[ModelConfig]:
        """Return configuration for ``model_id`` if available."""

        if not model_id:
            return None

        clean_id = model_id.removeprefix("models/")
        models = cls._indexed_models()
        model = models.get(clean_id)
        if model:
            return model

        alias_target = cls._ALIASES.get(clean_id)
        if alias_target:
            return models.get(alias_target)

        return None

    @classmethod
    def get_display_name(cls, model_id: Optional[str]) -> str:
        """Return the display name for ``model_id`` or the id itself."""

        model = cls.get_by_id(model_id)
        return model.display_name if model else (model_id or "")

    @classmethod
    def ui_options(cls) -> List[Tuple[str, str]]:
        """Return options suitable for Textual ``Select`` widgets."""

        return [
            (model.display_name, model.id)
            for model in cls.all_models()
            if not model.deprecated
        ]

    @classmethod
    def validate_model_id(cls, model_id: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Validate ``model_id`` returning ``(is_valid, error_message)``."""

        if not model_id:
            return False, "Model identifier cannot be empty"

        model = cls.get_by_id(model_id)
        if not model:
            return False, f"Unknown model: {model_id}"

        if model.deprecated:
            message = f"Model {model.id} is deprecated."
            if model.replacement:
                message += f" Use {model.replacement} instead."
            return False, message

        return True, None


def _load_model_from_config() -> Optional[ModelConfig]:
    """Load the default model from the persisted configuration file."""

    config_file = ConfigPaths.get_config_file()
    if not config_file.exists():
        return None

    try:
        content = config_file.read_text(encoding="utf-8")
        if not content.strip():
            return None
        data = json.loads(content)
    except (OSError, json.JSONDecodeError):
        LOGGER.debug(
            "Failed to load configuration file for model selection", exc_info=True
        )
        return None

    model_id = data.get("model")
    return ModelRegistry.get_by_id(model_id)


def get_default_model() -> ModelConfig:
    """Return the default model configured for the application."""

    env_model = os.environ.get("ADH_MODEL")
    if env_model:
        model = ModelRegistry.get_by_id(env_model)
        if model:
            return model
        LOGGER.warning("Invalid ADH_MODEL=%s, falling back to defaults", env_model)

    config_model = _load_model_from_config()
    if config_model:
        return config_model

    return ModelRegistry.DEFAULT


def get_default_model_id() -> str:
    """Return the identifier for the default model."""

    return get_default_model().id
