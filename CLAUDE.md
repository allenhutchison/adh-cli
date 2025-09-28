# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ADH CLI is a Terminal User Interface (TUI) application built with Textual and Google AI Development Kit (ADK/Gemini API). It provides an interactive chat interface with Google's Gemini models through a modern terminal interface.

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
# Run via installed command
adh-cli

# Run via Python module
python -m adh_cli

# Run in debug mode
adh-cli --debug
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
- **App Core**: `adh_cli/app.py` - Main Textual app class with screen routing and keybindings
- **Screen System**: Uses Textual's screen stack for navigation between Main, Chat, and Settings screens

### Google ADK Integration
The `adh_cli/services/adk_service.py` handles all Google Gemini API interactions:
- Manages API authentication (supports GOOGLE_API_KEY and GEMINI_API_KEY env vars)
- Provides both single-shot text generation and stateful chat sessions
- Configurable model parameters (temperature, max_tokens, top_p, top_k)
- Default model: `models/gemini-2.0-flash-exp`

### Screen Architecture
Each screen inherits from `textual.screen.Screen`:
- **MainScreen**: Welcome screen with navigation options
- **ChatScreen**: Async message handling with RichLog widget for conversation display
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
- ADKService maintains `_chat_session` for conversation continuity
- History can be provided when starting new chat sessions
- Chat export functionality saves conversation to `chat_export.txt`

### Textual Keybindings
Global bindings defined in `ADHApp.BINDINGS`:
- Navigation: h (Home), c (Chat), s (Settings)
- Actions: q (Quit), d (Toggle dark mode)
- Screen-specific: ESC (Back), Ctrl+L (Clear chat in ChatScreen)

### Tool System
The application includes a tool system that allows the AI to execute commands:
- **execute_command**: Run shell commands with safety checks
- **list_directory**: List directory contents with structured output
- **read_file**: Read text files up to 10MB

Implementation details:
- Tools are defined in `adh_cli/tools/shell_tools.py`
- ADKService uses pattern matching to detect when the AI wants to use tools
- Tool handlers are registered in `_setup_tool_handlers()` method
- Safety features include command blocking, file size limits, and timeout controls
- Enable tools by passing `enable_tools=True` when initializing ADKService

### Error Handling
- API key validation on service initialization
- Graceful error display in chat UI for API failures
- User-friendly messages for configuration issues
- Tool execution errors are caught and displayed in chat