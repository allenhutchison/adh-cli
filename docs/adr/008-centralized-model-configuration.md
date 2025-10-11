# ADR 008: Centralized Model Configuration

**Status:** Accepted
**Date:** 2025-09-30
**Deciders:** Project Team
**Tags:** refactoring, configuration, maintainability, medium-priority

---

## Context

Model identifiers are currently scattered throughout the codebase, making it difficult to:
- Switch between models
- Add new models
- Maintain consistency
- Configure model-specific settings

### Current State - Scattered Configuration

**1. Core Agents (4 locations):**
```python
# adh_cli/core/policy_aware_llm_agent.py:32
model_name: str = "gemini-flash-latest"

# adh_cli/core/policy_aware_agent.py:22
model_name: str = "models/gemini-flash-latest"  # Note: different prefix!

# adh_cli/services/adk_agent_service.py:31
model_name: str = "gemini-flash-latest"

# adh_cli/agents/agent_loader.py:17
model: str = "gemini-flash-latest"
```

**2. UI Screens (6 locations):**
```python
# adh_cli/screens/settings_screen.py (3 places)
("Gemini Flash Latest", "gemini-flash-latest"),
("Gemini Flash Lite Latest", "gemini-flash-lite-latest"),
value="models/gemini-flash-latest"

# adh_cli/screens/settings_modal.py (4 places)
"Gemini Flash Latest": "gemini-flash-latest",
"Gemini Flash Lite Latest": "gemini-flash-lite-latest",
model_map.get(selected_option, "gemini-flash-latest")
reverse_model_map = {
    "gemini-flash-latest": "Gemini Flash Latest",
    ...
}
```

**3. Agent Metadata Files (2+ locations):**
```yaml
# adh_cli/agents/researcher/agent.md:4
model: gemini-flash-latest

# adh_cli/agents/code_reviewer/agent.md:4
model: gemini-flash-latest
```

**4. Application Initialization:**
```python
# adh_cli/app.py:91
model_name="gemini-flash-latest",
```

**5. Tests (multiple locations):**
```python
# tests/test_app.py:56
model_name="gemini-flash-latest",

# tests/agents/test_agent_loader.py
model="gemini-pro"
model="gemini-flash-latest"
```

### Problems with Current Approach

**1. Inconsistent Prefixes:**
```python
# Some use prefix:
"models/gemini-flash-latest"

# Some don't:
"gemini-flash-latest"

# Causes confusion and bugs
```

**2. No Single Source of Truth:**
- To add a new model, must update 15+ locations
- Easy to miss locations
- Inconsistent naming across codebase
- Hard to audit what models are supported

**3. No Model Metadata:**
```python
# No way to know:
# - Context window size
# - Cost per token
# - Supported features
# - Recommended use cases
# - Deprecation status
```

**4. Duplicate UI Code:**
```python
# settings_screen.py has model list
# settings_modal.py has same list
# Must keep in sync manually
```

**5. Hard to Test:**
```python
# Tests use hardcoded model names
# Can't easily test with different models
# No mock model for testing
```

**6. No Validation:**
```python
# Can pass invalid model name
# Only fails at API call time
# No autocomplete/suggestions
```

### User Impact

**To Change Default Model:**
1. Find all hardcoded references (grep)
2. Update each location
3. Risk missing some
4. Test manually
5. Update tests

**Current time: ~30 minutes, error-prone**

**To Add New Model:**
1. Find all model lists
2. Add to each list
3. Update UI mapping
4. Update documentation
5. Hope you didn't miss anything

**Current time: ~45 minutes, very error-prone**

## Decision

Implement a **centralized model configuration system** with:

### Architecture

**1. Model Configuration Module:**
```python
# adh_cli/config/models.py
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
    cost_per_1m_input: float
    cost_per_1m_output: float
    recommended_for: Tuple[str, ...]
    deprecated: bool = False
    replacement: Optional[str] = None

    @property
    def api_id(self) -> str:
        """Return the identifier that should be sent to the API."""

        return self.full_id or self.id

class ModelRegistry:
    """Registry providing a single source of truth for Gemini models."""

    # Primary models
    FLASH_LATEST = ModelConfig(
        id="gemini-flash-latest",
        full_id="models/gemini-flash-latest",
        display_name="Gemini Flash (Latest)",
        description="Latest Flash model, currently pointing to Gemini 2.5 Flash Preview for best performance.",
        context_window=1_048_576,
        max_output_tokens=65_536,
        supports_function_calling=True,
        supports_streaming=True,
        cost_per_1m_input=0.30,
        cost_per_1m_output=2.50,
        recommended_for=["general", "chat", "code", "analysis"],
    )

    FLASH_LITE_LATEST = ModelConfig(
        id="gemini-flash-lite-latest",
        full_id="models/gemini-flash-lite-latest",
        display_name="Gemini Flash Lite (Latest)",
        description="Second generation small workhorse model, optimized for cost efficiency and low latency.",
        context_window=1_048_576,
        max_output_tokens=8_192,
        supports_function_calling=True,
        supports_streaming=True,
        cost_per_1m_input=0.10,
        cost_per_1m_output=0.40,
        recommended_for=["chat", "simple-tasks"],
    )

    PRO_25 = ModelConfig(
        id="gemini-2.5-pro",
        full_id="models/gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        description="State-of-the-art thinking model, capable of reasoning over complex problems in code, math, and STEM.",
        context_window=1_048_576,
        max_output_tokens=65_536,
        supports_function_calling=True,
        supports_streaming=True,
        cost_per_1m_input=1.25,  # ≤200k tokens; $2.50 for >200k tokens
        cost_per_1m_output=10.0,  # ≤200k tokens; $15.00 for >200k tokens
        recommended_for=["complex-reasoning", "code-generation", "analysis"],
    )

    _ALL_MODELS: Tuple[ModelConfig, ...] = (
        FLASH_LATEST,
        FLASH_LITE_LATEST,
        PRO_25,
    )

    DEFAULT = FLASH_LATEST

    # Note: Aliases are now loaded from configuration files (not hardcoded)
    # See adh_cli/config/defaults/model_aliases.json for built-in defaults
    # Users can override at ~/.config/adh-cli/model_aliases.json

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
```


**3. Update All Usage Points:**

**Core Agents:**
```python
# adh_cli/core/policy_aware_llm_agent.py
from adh_cli.config.models import get_default_model, ModelRegistry

class PolicyAwareLlmAgent:
    def __init__(
        self,
        model_name: Optional[str] = None,  # Now optional
        ...
    ):
        # Get model config
        if model_name:
            model_config = ModelRegistry.get_by_id(model_name)
            if not model_config:
                raise ValueError(f"Unknown model: {model_name}")
        else:
            model_config = get_default_model()

        # Validate model supports required features
        if not model_config.supports_function_calling:
            raise ValueError(
                f"Model {model_config.id} does not support function calling"
            )

        self.model_config = model_config
        self.model_name = model_config.full_id  # Use full ID for API
```

**UI Screens:**
```python
# adh_cli/screens/settings_screen.py
from adh_cli.config.models import ModelRegistry

class SettingsScreen(Screen):
    def compose(self):
        # Get options from registry
        yield Select(
            options=ModelRegistry.ui_options(),
            value=ModelRegistry.DEFAULT.id,
            id="model-select"
        )

    def on_save(self):
        model_id = self.query_one("#model-select", Select).value

        # Validate before saving
        valid, error = ModelRegistry.validate_model_id(model_id)
        if not valid:
            self.notify(error, severity="error")
            return

        # Save to config
        ...
```

**Agent Loader:**
```python
# adh_cli/agents/agent_loader.py
from adh_cli.config.models import ModelRegistry, get_default_model

def load_agent(agent_path: Path):
    # Parse metadata
    metadata = parse_frontmatter(agent_path)

    # Get model with fallback
    model_id = metadata.get("model")
    if model_id:
        model_config = ModelRegistry.get_by_id(model_id)
    else:
        model_config = get_default_model()

    # Create agent with validated model
    agent = create_agent(
        model=model_config.full_id,
        ...
    )
```

### Migration Strategy

**Phase 1: Add Model Registry (No Breaking Changes)**
```python
# Create adh_cli/config/models.py
# Add ModelRegistry with all current models
# Add helper functions
# Add tests
```

**Phase 2: Update Core (Internal Refactoring)**
```python
# Update PolicyAwareLlmAgent to use ModelRegistry
# Update PolicyAwareAgent to use ModelRegistry
# Update agent_loader to use ModelRegistry
# All existing code still works (backward compatible)
```

**Phase 3: Update UI (User-Visible)**
```python
# Update settings_screen.py to use ModelRegistry.ui_options()
# Update settings_modal.py to use ModelRegistry
# Remove duplicate model lists
# Users see same models, different implementation
```

**Phase 4: Update Tests**
```python
# Update tests to use ModelRegistry
# Add test helper: ModelRegistry.MOCK for testing
# More maintainable tests
```

**Phase 5: Cleanup**
```python
# Remove old hardcoded model references
# Update documentation
# Add deprecation warnings if needed
```

### Configuration File

**User Config:**
```yaml
# ~/.adh-cli/config.yaml
default_model: gemini-flash-latest

# Model-specific overrides
model_settings:
  gemini-pro-latest:
    temperature: 0.5
    max_tokens: 4096

  gemini-flash-latest:
    temperature: 0.7
    max_tokens: 2048
```

**Environment Variables:**
```bash
# Override default model
export ADH_MODEL=gemini-pro-latest

# Override temperature
export ADH_MODEL_TEMPERATURE=0.8

# Override max tokens
export ADH_MODEL_MAX_TOKENS=4096
```

## Consequences

### Positive

**Maintainability:**
- Single source of truth for models
- Add new model in one place
- Update model metadata centrally
- Easy to deprecate old models

**Consistency:**
- No more prefix confusion
- Standardized model naming
- Consistent across UI/code/docs
- Better validation

**Discoverability:**
- See all available models in one place
- Model descriptions and use cases
- Cost information visible
- Feature support documented

**Flexibility:**
- Easy to switch models via env var
- Per-model configuration
- User preferences saved
- Test with mock models

**Better Errors:**
```python
# Before:
# API error at runtime (cryptic)

# After:
raise ValueError(
    f"Model '{model_id}' does not support function calling. "
    f"Use one of: {', '.join(m.id for m in ModelRegistry.all_models() if m.supports_function_calling)}"
)
```

### Negative

**Migration Effort:**
- Update 15+ files
- Need comprehensive testing
- Risk of missing references
- Documentation updates

**New Abstraction:**
- Developers must learn ModelRegistry API
- One more layer of indirection
- Adds ~200 LOC

**Breaking Changes (Minor):**
- Model IDs must be validated
- Some hardcoded references won't work
- Tests need updates

### Risks

**Risk 1: Missed References**
- **Impact:** Medium - some hardcoded model still exists
- **Mitigation:**
  - Comprehensive grep search
  - Add deprecation warnings
  - Gradual migration
  - Test coverage

**Risk 2: Model API Changes**
- **Impact:** Low - Google changes model IDs
- **Mitigation:**
  - Easy to update in one place
  - Version model config
  - Add migration helpers
  - Document changes

**Risk 3: Config File Corruption**
- **Impact:** Low - invalid config breaks app
- **Mitigation:**
  - Validate on load
  - Fall back to defaults
  - Clear error messages
  - Schema validation

### Neutral

**Testing:**
- Add ModelRegistry tests (~50 LOC)
- Update existing tests to use registry
- Add validation tests
- Test mock model support

**Documentation:**
- Update user guide
- Document model selection
- Explain configuration file
- Migration guide

## Alternatives Considered

### Alternative 1: Keep Current Approach

Don't refactor, just document where models are defined.

**Pros:**
- No work required
- No migration risk
- Known issues

**Cons:**
- Problems persist
- Getting worse over time
- Hard to maintain

**Why Rejected:** Technical debt is growing; better to fix now.

### Alternative 2: Simple Constants File

Just create a constants file with model IDs.

**Pros:**
- Simple
- Easy to implement
- Quick win

**Cons:**
- No metadata
- No validation
- No configuration
- Doesn't solve UI duplication

**Why Rejected:** Doesn't go far enough; will need to refactor again later.

### Alternative 3: External Config File Only

Put everything in YAML config file.

**Pros:**
- User-editable
- No code changes needed
- Very flexible

**Cons:**
- No validation
- No type safety
- Harder to document
- Easy to corrupt

**Why Rejected:** Need type safety and validation; YAML as supplement, not primary.

### Alternative 4: Use Enum

Define models as Python Enum.

**Pros:**
- Type-safe
- IDE autocomplete
- Simple

**Cons:**
- Can't have metadata
- Can't validate
- Can't load from config
- Limited flexibility

**Why Rejected:** Not flexible enough for model metadata and configuration.

## Implementation Notes

### File Structure

```
adh_cli/
  config/
    __init__.py                # New
    models.py                  # New: 300 LOC

tests/
  config/
    __init__.py                # New
    test_models.py             # New: 150 LOC
```

### Modified Files

```
adh_cli/
  core/
    policy_aware_llm_agent.py  # Update: use ModelRegistry
    policy_aware_agent.py      # Update: use ModelRegistry

  services/
    adk_agent_service.py       # Update: use ModelRegistry

  agents/
    agent_loader.py            # Update: use ModelRegistry

  screens/
    settings_screen.py         # Update: use ModelRegistry.ui_options()
    settings_modal.py          # Update: use ModelRegistry.ui_options()

  app.py                       # Update: use get_default_model()

tests/
  test_app.py                  # Update: use ModelRegistry
  agents/
    test_agent_loader.py       # Update: use ModelRegistry
```

### Testing Strategy

**Unit Tests:**
```python
class TestModelRegistry:
    def test_get_by_id(self):
        """Test getting model by ID."""
        model = ModelRegistry.get_by_id("gemini-flash-latest")
        assert model is not None
        assert model.display_name == "Gemini Flash (Latest)"

    def test_get_by_id_with_prefix(self):
        """Test getting model with prefix."""
        model = ModelRegistry.get_by_id("models/gemini-flash-latest")
        assert model is not None
        assert model.id == "gemini-flash-latest"

    def test_validate_model_id(self):
        """Test model validation."""
        valid, error = ModelRegistry.validate_model_id("gemini-flash-latest")
        assert valid is True
        assert error is None

    def test_validate_invalid_model(self):
        """Test validation of invalid model."""
        valid, error = ModelRegistry.validate_model_id("invalid-model")
        assert valid is False
        assert "Unknown model" in error

    def test_ui_options(self):
        """Test UI options generation."""
        options = ModelRegistry.ui_options()
        assert len(options) > 0
        assert all(isinstance(opt, tuple) and len(opt) == 2 for opt in options)

    def test_deprecated_model_excluded(self):
        """Test deprecated models excluded from UI."""
        # Add deprecated model
        deprecated = ModelConfig(
            id="old-model",
            full_id="models/old-model",
            display_name="Old Model",
            description="Deprecated",
            deprecated=True,
            ...
        )

        options = ModelRegistry.ui_options()
        assert not any(opt[1] == "old-model" for opt in options)
```

**Integration Tests:**
```python
@pytest.mark.integration
def test_agent_with_configured_model():
    """Test creating agent with model from registry."""
    model = ModelRegistry.PRO_25

    agent = PolicyAwareLlmAgent(
        api_key="test",
        model_name=model.id
    )

    assert agent.model_config == model
    assert agent.model_name == model.full_id
```

### Migration Checklist

- [ ] Create `adh_cli/config/models.py`
- [ ] Add ModelRegistry with all models
- [ ] Add tests for ModelRegistry
- [ ] Update PolicyAwareLlmAgent
- [ ] Update PolicyAwareAgent
- [ ] Update ADKAgentService
- [ ] Update agent_loader
- [ ] Update settings_screen
- [ ] Update settings_modal
- [ ] Update app.py
- [ ] Update all tests
- [ ] Add deprecation warnings
- [ ] Update documentation
- [ ] Remove old hardcoded references

### Example Usage

**Before:**
```python
# Must know exact model ID
agent = PolicyAwareLlmAgent(
    model_name="gemini-flash-latest",  # or is it "models/gemini-flash-latest"?
    api_key="...",
)
```

**After:**
```python
# Use registry
from adh_cli.config.models import ModelRegistry

agent = PolicyAwareLlmAgent(
    model_name=ModelRegistry.PRO_25.id,  # Type-safe, validated
    api_key="...",
)

# Or use default
agent = PolicyAwareLlmAgent(api_key="...")  # Uses configured default

# Or from environment
# export ADH_MODEL=gemini-2.5-pro
agent = PolicyAwareLlmAgent(api_key="...")
```

## References

**Configuration Patterns:**
- [12-Factor App Configuration](https://12factor.net/config)
- [Python Configuration Best Practices](https://martin-thoma.com/configuration-files-in-python/)

**Related ADRs:**
- ADR-003: Google ADK Integration
- ADR-004: Secure API Key Storage

**Similar Implementations:**
- LangChain model configuration
- OpenAI Python SDK model handling
- Anthropic Claude SDK model registry

**Code:**
- Current: Multiple files with hardcoded models
- Will create: `adh_cli/config/models.py`

**External Resources:**
- [Gemini Models Documentation](https://ai.google.dev/models/gemini)
- [Google AI Model Pricing](https://ai.google.dev/pricing)

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-09-30 | Initial proposal | Project Team |
| 2025-10-11 | Updated to reflect configuration-driven aliases with generation parameters support | Project Team |

## Updates (2025-10-11)

### Enhanced Alias System

The original ADR described hardcoded aliases in `_ALIASES`. This has been enhanced to support:

**1. Configuration-Driven Aliases:**
- Built-in defaults: `adh_cli/config/defaults/model_aliases.json`
- User overrides: `~/.config/adh-cli/model_aliases.json`
- Follows same pattern as policy system

**2. Generation Parameters:**
```json
{
  "model_aliases": {
    "creative": {
      "model_id": "gemini-flash-latest",
      "parameters": {
        "temperature": 1.2,
        "top_p": 0.95
      }
    }
  }
}
```

**3. Benefits:**
- No code changes to update default aliases
- User-defined aliases with custom generation parameters
- Tests alias loading on every application run
- Easy to maintain and extend

**Implementation:**
- `ModelRegistry._load_rich_aliases()` loads from files
- `GenerationConfigTool` applies parameters via ADK
- `ModelAliasConfig` dataclass stores alias configuration
- Comprehensive test coverage (382 tests pass)

**Documentation:**
- See `docs/MODEL_ALIASES.md` for complete guide
- See `docs/model_aliases.example.json` for examples
