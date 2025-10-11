"""Centralized model configuration for the ADH CLI application."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, TypedDict, Any
from pathlib import Path  # Added Path import

from adh_cli.core.config_paths import ConfigPaths

LOGGER = logging.getLogger(__name__)


# Type alias for clarity
GenerationParamsDict = Dict[str, Any]


# --- NEW CONFIGURATION STRUCTURES ---
class GenerationParams(TypedDict, total=False):
    """Parameters for the Gemini GenerateContentConfig."""

    temperature: Optional[float]
    max_output_tokens: Optional[int]
    top_p: Optional[float]
    top_k: Optional[int]


@dataclass(frozen=True)
class ModelAliasConfig:
    """User-defined alias mapping to an underlying model and custom generation config."""

    model_id: str
    parameters: GenerationParams


# --- END NEW CONFIGURATION STRUCTURES ---


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
    cost_per_1m_input: float
    cost_per_1m_output: float
    recommended_for: Tuple[str, ...]
    deprecated: bool = False
    replacement: Optional[str] = None

    @property
    def api_id(self) -> str:
        """Return the identifier that should be sent to the API."""

        return self.full_id or self.id


def _load_json_config(path: Path) -> Dict[str, Any]:
    """Loads and returns content of a JSON file."""
    if not path.exists():
        return {}
    try:
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            return {}
        return json.loads(content)
    except (OSError, json.JSONDecodeError):
        LOGGER.debug(f"Failed to load configuration file: {path}", exc_info=True)
        return {}


class ModelRegistry:
    """Registry providing a single source of truth for Gemini models."""

    FLASH_LATEST = ModelConfig(
        id="gemini-flash-latest",
        full_id="gemini-flash-latest",
        display_name="Gemini Flash (Latest)",
        description="Latest Flash model, currently pointing to Gemini 2.5 Flash Preview for best performance.",
        context_window=1_048_576,
        max_output_tokens=65_536,
        supports_function_calling=True,
        supports_streaming=True,
        cost_per_1m_input=0.30,
        cost_per_1m_output=2.50,
        recommended_for=("chat", "analysis", "code", "general"),
    )

    FLASH_LITE_LATEST = ModelConfig(
        id="gemini-flash-lite-latest",
        full_id="gemini-flash-lite-latest",
        display_name="Gemini Flash Lite (Latest)",
        description="Second generation small workhorse model, optimized for cost efficiency and low latency.",
        context_window=1_048_576,
        max_output_tokens=8_192,
        supports_function_calling=True,
        supports_streaming=True,
        cost_per_1m_input=0.10,
        cost_per_1m_output=0.40,
        recommended_for=("chat", "simple-tasks"),
    )

    PRO_25 = ModelConfig(
        id="gemini-2.5-pro",
        full_id="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        description="State-of-the-art thinking model, capable of reasoning over complex problems in code, math, and STEM.",
        context_window=1_048_576,
        max_output_tokens=65_536,
        supports_function_calling=True,
        supports_streaming=True,
        cost_per_1m_input=1.25,  # ≤200k tokens; $2.50 for >200k tokens
        cost_per_1m_output=10.0,  # ≤200k tokens; $15.00 for >200k tokens
        recommended_for=("complex-reasoning", "code-generation", "analysis"),
    )

    _ALL_MODELS: Tuple[ModelConfig, ...] = (
        FLASH_LATEST,
        FLASH_LITE_LATEST,
        PRO_25,
    )

    DEFAULT = FLASH_LATEST

    @classmethod
    def all_models(cls) -> Tuple[ModelConfig, ...]:
        """Return all registered models."""

        return cls._ALL_MODELS

    @classmethod
    def _indexed_models(cls) -> Dict[str, ModelConfig]:
        """Return a mapping of model identifiers to configuration objects."""

        if not hasattr(cls, "_cached_indexed_models"):
            cls._cached_indexed_models = {model.id: model for model in cls.all_models()}
        return cls._cached_indexed_models

    @classmethod
    def _load_rich_aliases(cls) -> Dict[str, ModelAliasConfig]:
        """Load model aliases from default and user config files.

        Loads built-in default aliases first, then user-defined aliases which can override them.
        This follows the same pattern as the policy engine.
        """
        if hasattr(cls, "_cached_rich_aliases"):
            return cls._cached_rich_aliases

        all_aliases: Dict[str, ModelAliasConfig] = {}

        # Helper function to parse aliases from a data dict
        def parse_aliases(
            data: Dict[str, Any], source: str
        ) -> Dict[str, ModelAliasConfig]:
            aliases: Dict[str, ModelAliasConfig] = {}
            for alias_name, alias_data in data.get("model_aliases", {}).items():
                if not isinstance(alias_data, dict) or "model_id" not in alias_data:
                    LOGGER.warning(
                        "Invalid model alias structure for '%s' in %s",
                        alias_name,
                        source,
                    )
                    continue

                # Extract underlying model ID
                model_id = alias_data["model_id"]

                # Extract and filter generation parameters
                # Map parameter names to their expected types for casting
                param_types: Dict[str, type] = {
                    "temperature": float,
                    "top_p": float,
                    "max_output_tokens": int,
                    "top_k": int,
                }

                params: GenerationParams = {}
                raw_params = alias_data.get("parameters", {})

                for key, cast_func in param_types.items():
                    if key in raw_params:
                        try:
                            value = cast_func(raw_params[key])
                            # Type-safe assignment to TypedDict
                            if key == "temperature":
                                params["temperature"] = value  # type: ignore[typeddict-item]
                            elif key == "top_p":
                                params["top_p"] = value  # type: ignore[typeddict-item]
                            elif key == "max_output_tokens":
                                params["max_output_tokens"] = value  # type: ignore[typeddict-item]
                            elif key == "top_k":
                                params["top_k"] = value  # type: ignore[typeddict-item]
                        except (ValueError, TypeError):
                            LOGGER.warning(
                                "Invalid type for parameter '%s' in alias '%s' (%s)",
                                key,
                                alias_name,
                                source,
                            )

                aliases[alias_name] = ModelAliasConfig(
                    model_id=model_id,
                    parameters=params,
                )
            return aliases

        # 1. Load built-in default aliases (always available)
        default_file = Path(__file__).parent / "defaults" / "model_aliases.json"
        default_data = _load_json_config(default_file)
        if default_data:
            default_aliases = parse_aliases(default_data, "default")
            all_aliases.update(default_aliases)

        # 2. Load user-defined aliases (can override defaults)
        user_file = ConfigPaths.get_model_aliases_file()
        user_data = _load_json_config(user_file)
        if user_data:
            user_aliases = parse_aliases(user_data, "user")
            all_aliases.update(user_aliases)  # User aliases override defaults

        cls._cached_rich_aliases = all_aliases
        return all_aliases

    @classmethod
    def get_model_and_config(
        cls, model_id: Optional[str]
    ) -> Tuple[Optional[ModelConfig], GenerationParams]:
        """Return ModelConfig and any custom GenerationParams for the given model_id/alias.

        Returns:
            Tuple of (ModelConfig, GenerationParams dict)
        """
        if not model_id:
            return None, {}

        clean_id = model_id.removeprefix("models/")
        models = cls._indexed_models()

        # 1. Check for a direct model ID match
        model = models.get(clean_id)
        if model:
            return model, {}

        # 2. Check for an alias match
        rich_aliases = cls._load_rich_aliases()
        alias_config = rich_aliases.get(clean_id)

        if alias_config:
            # Resolve the alias to its underlying base model ID
            target_model = models.get(alias_config.model_id)
            if target_model:
                return target_model, alias_config.parameters
            else:
                LOGGER.warning(
                    "Alias '%s' points to unknown model: %s",
                    clean_id,
                    alias_config.model_id,
                )
                return None, {}

        return None, {}

    @classmethod
    def get_by_id(cls, model_id: Optional[str]) -> Optional[ModelConfig]:
        """Return configuration for ``model_id`` if available."""

        # Now uses the combined resolver
        model, _ = cls.get_model_and_config(model_id)
        return model

    @classmethod
    def get_display_name(cls, model_id: Optional[str]) -> str:
        """Return the display name for ``model_id`` or the id itself."""

        # Note: This logic implicitly uses the underlying model's display name,
        # which is correct for aliases.
        model = cls.get_by_id(model_id)
        return model.display_name if model else (model_id or "")

    @classmethod
    def ui_options(cls) -> List[Tuple[str, str]]:
        """Return options suitable for Textual ``Select`` widgets.

        Includes built-in models and user-defined aliases.
        """
        options = []

        # 1. Built-in models
        for model in cls.all_models():
            if not model.deprecated:
                options.append((model.display_name, model.id))

        # 2. User-defined aliases (only if they resolve to a valid model)
        # Sort and deduplicate built-in models and aliases
        rich_aliases = cls._load_rich_aliases()
        for alias_id, alias_config in rich_aliases.items():
            if alias_id not in cls._indexed_models():
                # Only add if it's a true alias and resolves to a known model
                target_model = cls.get_by_id(alias_config.model_id)
                if target_model:
                    options.append(
                        (
                            f"{alias_id} (Alias for {target_model.display_name})",
                            alias_id,
                        )
                    )

        # Deduplicate by id, prioritize the first appearance (built-in models)
        unique_options: List[Tuple[str, str]] = []
        seen_ids = set()
        for display_name, model_id in options:
            if model_id not in seen_ids:
                unique_options.append((display_name, model_id))
                seen_ids.add(model_id)

        return unique_options

    @classmethod
    def validate_model_id(cls, model_id: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Validate ``model_id`` returning ``(is_valid, error_message)``."""

        if not model_id:
            return False, "Model identifier cannot be empty"

        # Uses get_by_id, which now resolves aliases
        model = cls.get_by_id(model_id)
        if not model:
            # Check if it's an alias pointing to an unknown model
            clean_id = model_id.removeprefix("models/")
            rich_aliases = cls._load_rich_aliases()
            alias_config = rich_aliases.get(clean_id)
            if alias_config:
                return (
                    False,
                    f"Alias '{model_id}' points to unknown base model: {alias_config.model_id}",
                )

            return False, f"Unknown model or alias: {model_id}"

        if model.deprecated:
            message = f"Model {model.id} is deprecated."
            if model.replacement:
                message += f" Use {model.replacement} instead."
            return False, message

        return True, None


def _load_model_from_config() -> Optional[ModelConfig]:
    """Load the default model from the persisted configuration file."""

    config_file = ConfigPaths.get_config_file()
    data = _load_json_config(config_file)  # Use the new helper function

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
