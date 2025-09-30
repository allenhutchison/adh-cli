# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ADH CLI is a policy-aware agentic Terminal User Interface (TUI) application built with Textual and Google AI Development Kit (ADK/Gemini API). It provides a safe, policy-controlled interface for AI-assisted development with Google's Gemini models, featuring comprehensive safety checks and tool execution controls.

## Development Environment

### Package Manager
This project uses **uv** for Python package and virtual environment management. uv is a fast Python package installer and resolver written in Rust.

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows

# Install dependencies using uv
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt

# Install package in editable mode
uv pip install -e .
```

### Installation (Alternative with pip)
```bash
# If not using uv, you can use standard pip
pip install -e .

# Install development dependencies
pip install -r requirements-dev.txt
```

### Running the Application
```bash
# Run the application
adh-cli

# Run with custom policy directory
adh-cli --policy-dir /path/to/policies

# Run in debug mode
adh-cli --debug

# Disable safety checks (use with caution)
adh-cli --no-safety

# Run via Python module
python -m adh_cli
```

### Testing
```bash
# Run all tests
pytest

# Run tests with async support
pytest --asyncio-mode=auto
```

### Textual Development Tools
```bash
# Run Textual console for debugging (in separate terminal)
textual console

# Run with dev mode enabled
textual run --dev adh_cli.app:ADHApp
```

## Architecture

### Application Structure
- **Main Entry**: `adh_cli/__main__.py` - CLI entry point using Click
- **App Core**: `adh_cli/app.py` - Main Textual app class with policy-aware agent integration
- **Screen System**: Uses Textual's screen stack for navigation between Main, Chat, and Settings screens

### Google ADK Integration

#### Policy-Aware Agent
The `adh_cli/core/policy_aware_agent.py` provides safe AI interactions:
- Integrates policy engine with ADK agent
- Evaluates all tool calls against policies before execution
- Handles confirmation workflows for supervised operations
- Maintains audit logs of all tool executions

### Screen Architecture
Each screen inherits from `textual.screen.Screen`:
- **MainScreen**: Welcome screen with navigation options
- **ChatScreen**: Policy-aware chat with confirmation dialogs and safety checks
- **SettingsScreen**: Model configuration and API key management

### Async Patterns
- Chat messages are processed using `app.run_worker()` for non-blocking UI
- Input handling uses Textual's event system with `@on` decorators
- All ADK API calls are wrapped in async workers to maintain UI responsiveness

## Key Implementation Details

### API Key Management
- Checks environment variables in order: config.api_key → GOOGLE_API_KEY → GEMINI_API_KEY
- Uses python-dotenv to load from .env file
- Runtime configuration updates via SettingsScreen

### Chat Session State
- PolicyAwareAgent maintains conversation state through ADK's LlmAgent
- Stateful chat sessions with tool execution history
- All tool calls go through policy evaluation before execution

### Textual Keybindings
Global bindings defined in `ADHApp.BINDINGS`:
- Navigation: h (Home), c (Chat), s (Settings)
- Actions: q (Quit), d (Toggle dark mode)
- Screen-specific: ESC (Back), Ctrl+L (Clear chat in ChatScreen)

### Tool System

#### Available Tools
- **read_file**: Read text files with size limits
- **write_file**: Write content with backup creation
- **list_directory**: List directory contents
- **execute_command**: Run shell commands with safety validation
- **create_directory**: Create directories with permission checks
- **delete_file**: Delete files with confirmation requirements
- **get_file_info**: Get file/directory metadata

#### Policy-Controlled Execution
- **Tool Executor** (`adh_cli/core/tool_executor.py`):
  - Intercepts all tool calls for policy evaluation
  - Runs safety checks before execution
  - Handles user confirmation workflows
  - Applies parameter modifications from safety checks
  - Maintains audit logs

#### Safety Features
- **Policy Engine** (`adh_cli/policies/policy_engine.py`):
  - Evaluates tool calls against configurable rules
  - Supports supervision levels: automatic, notify, confirm, manual, deny
  - Risk assessment: none, low, medium, high, critical
  - User preference overrides

- **Safety Checkers** (`adh_cli/safety/checkers/`):
  - BackupChecker: Creates automatic backups
  - DiskSpaceChecker: Validates available space
  - PermissionChecker: Verifies file permissions
  - SizeLimitChecker: Enforces file size limits
  - SensitiveDataChecker: Detects API keys, passwords
  - CommandValidator: Validates shell commands
  - SandboxChecker: Enforces directory boundaries

### Error Handling
- API key validation on service initialization
- Graceful error display in chat UI for API failures
- User-friendly messages for configuration issues
- Tool execution errors are caught and displayed in chat
- Policy violations shown with clear explanations
- Safety check failures with override options
- Timeout handling for long-running operations

### Policy Configuration

#### Default Policies
Located in `adh_cli/policies/defaults/`:
- **filesystem_policies.yaml**: File operation rules
  - Read operations: automatic
  - Write operations: require confirmation
  - Delete operations: manual review
  - System files: denied
- **command_policies.yaml**: Command execution rules
  - Safe commands: notify only
  - Package managers: require confirmation
  - Dangerous commands: manual review
  - Destructive commands: blocked

#### Custom Policies
Users can create custom policies in `~/.adh-cli/policies/`:
- YAML format with pattern matching
- Priority-based rule ordering
- Conditional restrictions
- Safety check requirements

### Testing

#### Test Coverage
- **247 total tests** across the project
- Policy engine: 58 tests
- Core integration: 33 tests
- Shell tools: 28 tests
- UI components: 31 tests
- Plus 97 existing tests

#### Running Tests
```bash
# Run all tests
pytest

# Run policy tests
pytest tests/policies/ tests/safety/

# Run integration tests
pytest tests/core/

# Run with coverage
pytest --cov=adh_cli
```