# Model Aliases Configuration

ADH CLI supports custom model aliases that allow you to define shorthand names for models with specific generation parameters. This feature is useful for:

- Creating presets for different use cases (e.g., "creative", "precise", "concise")
- Customizing model behavior (temperature, output length, etc.)
- Quickly switching between different configurations

## Configuration Architecture

Model aliases follow the same pattern as the policy system:

- **Built-in defaults**: Shipped with the package at `adh_cli/config/defaults/model_aliases.json`
- **User overrides**: Your custom aliases at `~/.config/adh-cli/model_aliases.json`

User-defined aliases override built-in defaults, allowing you to customize or replace any default alias.

## Configuration Location

User aliases are configured in: `~/.config/adh-cli/model_aliases.json`

## Configuration Format

```json
{
  "model_aliases": {
    "alias_name": {
      "model_id": "base-model-id",
      "parameters": {
        "temperature": 0.7,
        "max_output_tokens": 4096,
        "top_p": 0.95,
        "top_k": 40
      }
    }
  }
}
```

### Supported Parameters

- **`temperature`** (float, 0.0-2.0): Controls randomness in generation
  - Lower values (0.0-0.3): More deterministic, precise
  - Medium values (0.4-0.9): Balanced creativity
  - Higher values (1.0-2.0): More creative, diverse

- **`max_output_tokens`** (int): Maximum number of tokens in the response
  - Flash models: up to 65,536 tokens
  - Flash Lite: up to 8,192 tokens

- **`top_p`** (float, 0.0-1.0): Nucleus sampling threshold
  - Controls diversity by probability mass
  - Default: 0.95

- **`top_k`** (int): Number of highest probability tokens to consider
  - Limits the token sampling pool
  - Default: 40

## Example Aliases

### Creative Writing

```json
{
  "creative": {
    "model_id": "gemini-flash-latest",
    "parameters": {
      "temperature": 1.2,
      "top_p": 0.95
    }
  }
}
```

Use with: `adh-cli --model creative`

### Precise/Code Generation

```json
{
  "precise": {
    "model_id": "gemini-2.5-pro",
    "parameters": {
      "temperature": 0.1,
      "top_p": 0.9,
      "top_k": 20
    }
  }
}
```

Use with: `adh-cli --model precise`

### Concise Responses

```json
{
  "concise": {
    "model_id": "gemini-flash-lite-latest",
    "parameters": {
      "temperature": 0.7,
      "max_output_tokens": 2048
    }
  }
}
```

Use with: `adh-cli --model concise`

### Long-Form Analysis

```json
{
  "detailed": {
    "model_id": "gemini-2.5-pro",
    "parameters": {
      "temperature": 0.8,
      "max_output_tokens": 32768,
      "top_p": 0.95
    }
  }
}
```

Use with: `adh-cli --model detailed`

## Using Model Aliases

### In the TUI

1. Open Settings (Ctrl+S)
2. Select your custom alias from the model dropdown
3. The alias will appear as: `alias_name (Alias for Base Model Name)`

### In Agent Definitions

```yaml
---
name: creative-writer
description: Creative writing assistant
model: creative
tools:
  - file_read
  - file_write
---
```

### As Default Model

In `~/.config/adh-cli/config.json`:

```json
{
  "model": "precise"
}
```

### Via Environment Variable

```bash
export ADH_MODEL=creative
adh-cli
```

## Built-in Default Aliases

ADH CLI ships with several default aliases (defined in `adh_cli/config/defaults/model_aliases.json`):

- `gemini-pro` → `gemini-2.5-pro`
- `gemini-2.5-flash` → `gemini-flash-latest`
- `gemini-flash` → `gemini-flash-latest`

**These defaults are loaded from a configuration file (not hardcoded)**, making them:
- Easy to update without code changes
- Tested on every application run
- Overridable by creating user-defined aliases with the same name

To override a default alias, simply define it in your user config with custom parameters:

```json
{
  "model_aliases": {
    "gemini-pro": {
      "model_id": "gemini-2.5-pro",
      "parameters": {
        "temperature": 0.3,
        "max_output_tokens": 16384
      }
    }
  }
}
```

## Validation

The system validates:

- Model IDs must exist in the registry
- Parameter types must match expected types (float/int)
- Invalid configurations are logged but don't prevent startup

## Complete Example

Save this to `~/.config/adh-cli/model_aliases.json`:

```json
{
  "model_aliases": {
    "creative": {
      "model_id": "gemini-flash-latest",
      "parameters": {
        "temperature": 1.2,
        "top_p": 0.95
      }
    },
    "precise": {
      "model_id": "gemini-2.5-pro",
      "parameters": {
        "temperature": 0.1,
        "top_p": 0.9,
        "top_k": 20
      }
    },
    "concise": {
      "model_id": "gemini-flash-lite-latest",
      "parameters": {
        "temperature": 0.7,
        "max_output_tokens": 2048
      }
    },
    "detailed": {
      "model_id": "gemini-2.5-pro",
      "parameters": {
        "temperature": 0.8,
        "max_output_tokens": 32768,
        "top_p": 0.95
      }
    },
    "fast": {
      "model_id": "gemini-flash-lite-latest",
      "parameters": {
        "temperature": 0.7,
        "max_output_tokens": 4096
      }
    }
  }
}
```

Then use any alias:
```bash
adh-cli --model creative
```

## Architecture

Model aliases are implemented through:

1. **ModelAliasConfig**: Stores alias → (model_id, parameters) mapping
2. **ModelRegistry.get_model_and_config()**: Resolves aliases to base models + params
3. **GenerationConfigTool**: ADK tool that applies parameters to each LLM request
4. **PolicyAwareLlmAgent**: Automatically registers the config tool when using aliases

See `docs/adr/` for detailed architecture decisions.
