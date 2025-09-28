# ADH CLI

A Terminal User Interface (TUI) application built with Textual and Google AI Development Kit (ADK).

## Features

- 🎨 Modern TUI interface powered by Textual
- 🤖 Google ADK integration for AI-powered conversations
- ⚙️ Settings management for API configuration
- 💬 Interactive chat interface with history
- 🎯 Model selection and configuration
- 🌓 Dark/Light mode support

## Installation

### Using pip (development mode)

```bash
pip install -e .
```

### Using requirements.txt

```bash
pip install -r requirements.txt
```

## Configuration

Set your Google API key as an environment variable:

```bash
export GOOGLE_API_KEY="your-api-key-here"
```

Or configure it through the Settings screen in the application.

## Usage

Run the application:

```bash
adh-cli
```

Or with Python:

```bash
python -m adh_cli
```

### Debug mode

```bash
adh-cli --debug
```

## Keyboard Shortcuts

- `q` - Quit application
- `d` - Toggle dark mode
- `h` - Go to Home screen
- `c` - Go to Chat screen
- `s` - Go to Settings screen
- `ESC` - Go back to previous screen
- `Ctrl+L` - Clear chat (in Chat screen)

## Development

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

Run tests:

```bash
pytest
```

## Project Structure

```
adh-cli/
├── adh_cli/
│   ├── __init__.py
│   ├── __main__.py
│   ├── app.py              # Main application
│   ├── screens/            # TUI screens
│   │   ├── main_screen.py
│   │   ├── chat_screen.py
│   │   └── settings_screen.py
│   ├── widgets/            # Custom widgets
│   │   └── model_list.py
│   └── services/           # Business logic
│       └── adk_service.py  # Google ADK integration
├── pyproject.toml
├── requirements.txt
└── README.md
```

## License

MIT