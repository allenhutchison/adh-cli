# ADH CLI

A Terminal User Interface (TUI) application built with Textual and Google AI Development Kit (ADK/Gemini API).

## Features

- 🎨 Modern TUI interface powered by Textual
- 🤖 Google Gemini AI integration for intelligent conversations
- 💬 Interactive chat interface with markdown rendering
- 📋 Cross-platform clipboard support (copy/export chat history)
- 🛠️ AI tool integration for file operations and command execution
- ⚙️ Settings management for API configuration
- 🎯 Model selection and configuration
- 🌓 Dark/Light mode support
- ⌨️ Vim-style command mode in chat

## Installation

### Prerequisites

- Python 3.9+ (recommended: Python 3.12+)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd adh-cli

# Using uv (recommended)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt

# Or using pip
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install in development mode
uv pip install -e .
```

### Development Setup

```bash
# Install development dependencies
uv pip install -r requirements-dev.txt

# Or use the task command
task install-dev
```

## Configuration

### API Key Setup

Set your Google API key as an environment variable:

```bash
export GOOGLE_API_KEY="your-api-key-here"
# or
export GEMINI_API_KEY="your-api-key-here"
```

Or create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your-api-key-here
```

You can also configure it through the Settings screen in the application.

## Usage

### Running the Application

```bash
# Using the installed command
adh-cli

# Using Python module
python -m adh_cli

# Using task runner
task run

# Debug mode
adh-cli --debug
```

### Run via uvx (no install)

Using uvx you can run directly from GitHub without installing:

```bash
# From GitHub shorthand (recommended)
uvx --from gh:allenhutchison/adh-cli adh-cli

# Or from a git URL
uvx --from git+https://github.com/allenhutchison/adh-cli.git adh-cli

# Pass options and environment as usual
GOOGLE_API_KEY=your-key uvx --from gh:allenhutchison/adh-cli adh-cli -- --debug
```

Notes:
- Requires `uv` v0.4.0+.
- `adh-cli` is the console script name exposed by the package.
- Ensure `GOOGLE_API_KEY` or `GEMINI_API_KEY` is set in your environment.

### Development Mode

```bash
# Run with Textual dev tools
task dev

# Open Textual console in another terminal for debugging
task console
```

## Keyboard Shortcuts

### Global
- `q` - Quit application
- `d` - Toggle dark mode
- `h` - Go to Home screen
- `c` - Go to Chat screen
- `s` - Go to Settings screen
- `ESC` - Go back/Toggle command mode

### Chat Screen
- `Enter` - Send message
- `ESC` - Toggle command mode
- `Ctrl+L` - Clear chat

### Command Mode (in Chat)
- `c` - Clear chat
- `y` - Yank (copy) chat to clipboard
- `e` - Export chat to file
- `s` - Open settings
- `q` - Quit application
- `i` or `ESC` - Return to input mode

## Development

### Available Commands

The project uses `taskipy` for task management (similar to npm scripts):

```bash
task test         # Run tests
task test-v       # Run tests with verbose output
task test-cov     # Run tests with coverage report
task lint         # Run linter (ruff)
task format       # Format code
task dev          # Run in development mode
task build        # Build distribution package
task clean        # Clean build artifacts
```

Or use Make:

```bash
make help         # Show all available commands
make test         # Run tests
make test-cov     # Run tests with coverage
make dev          # Run in development mode
```

### Running Tests

```bash
# Run all tests
task test

# Run with coverage
task test-cov

# Run specific test file
pytest tests/services/test_clipboard_service.py -v

# Run with watch mode (requires pytest-watch)
task test-watch
```

### Test Coverage

Current test coverage:
- Overall: 35% coverage
- `clipboard_service.py`: 90% coverage
- `chat_screen.py`: 78% coverage
- 32 tests, all passing

## Project Structure

```
adh-cli/
├── adh_cli/
│   ├── __init__.py
│   ├── __main__.py         # Entry point
│   ├── app.py              # Main Textual application
│   ├── screens/            # TUI screens
│   │   ├── main_screen.py  # Home screen
│   │   ├── chat_screen.py  # Chat interface with gutter layout
│   │   ├── settings_modal.py
│   │   └── settings_screen.py
│   ├── services/           # Business logic
│   │   ├── adk_service.py  # Google Gemini API integration
│   │   └── clipboard_service.py  # Cross-platform clipboard
│   └── tools/              # AI tool implementations
│       └── shell_tools.py  # File and command execution tools
├── tests/                  # Test suite
│   ├── services/
│   │   └── test_clipboard_service.py
│   └── screens/
│       └── test_chat_screen.py
├── Makefile               # Make commands
├── pyproject.toml         # Project configuration & task definitions
├── requirements.txt       # Runtime dependencies
├── requirements-dev.txt   # Development dependencies
├── CLAUDE.md             # AI assistant instructions
└── README.md             # This file
```

## Key Technologies

- **[Textual](https://textual.textualize.io/)** - Modern TUI framework
- **[Google Gemini API](https://ai.google.dev/)** - AI language model
- **[Rich](https://rich.readthedocs.io/)** - Terminal formatting and markdown rendering
- **[Click](https://click.palletsprojects.com/)** - CLI framework
- **[pytest](https://pytest.org/)** - Testing framework
- **[uv](https://github.com/astral-sh/uv)** - Fast Python package manager

## Recent Updates

- ✨ Enhanced chat display with gutter-style speaker labels
- 🎨 Improved markdown rendering for AI responses
- 📋 Refactored clipboard functionality into reusable service
- 🧪 Added comprehensive test suite (32 tests)
- 🛠️ Added task runner support (taskipy) for npm-style commands
- 📊 Configured test coverage reporting
- 🔧 Added Makefile for traditional command interface

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `task test`
4. Check coverage: `task test-cov`
5. Format code: `task format`
6. Commit your changes
7. Push to your branch
8. Open a Pull Request

## License

MIT
