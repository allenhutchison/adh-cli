# ADH CLI

ADH CLI is a policy-aware Terminal User Interface (TUI) for working with Google’s Gemini / ADK platform. It combines a chat-forward experience with tool orchestration, safety checks, and human-in-the-loop confirmation so you can explore ideas safely from your terminal.

## Highlights
- **Policy-aware orchestration** – Every tool call flows through a policy engine (`PolicyDecision`, safety pipeline, audit logging) before execution.
- **Human-in-the-loop tooling** – The tool execution manager shows pending/active runs, supports confirmation and cancellation, and keeps a local history.
- **Optional Google web tools** – Gemini’s built-in web search and URL context (requires Python 3.10+).
- **Configurable agents** – Agents are defined in Markdown (`adh_cli/agents/`) and loaded at runtime with variable substitution and model overrides.
- **Themed Textual UI** – Dark/light themes, command palette integrations, clipboard export, and keyboard-friendly chat navigation.
- **XDG-compliant storage** – Config, policies, audit logs, and backups live under `~/.config/adh-cli/` via `ConfigPaths`.
- **Well-tested codebase** – 300+ pytest cases cover core logic, UI widgets, policies, safety checks, and services.

## Quick Start

### Prerequisites
- Python 3.10 or newer
- [`uv`](https://github.com/astral-sh/uv) for fast, reproducible environments (pip works too)

### Clone & Install
```bash
git clone https://github.com/allenhutchison/adh-cli.git
cd adh-cli

# Create and activate a virtual environment (uv recommended)
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install the project with development extras
uv pip install -e '.[dev]'
# or use the task helper
task install-dev
```

### First Run
```bash
# Provide a Gemini API key via env or .env
export GOOGLE_API_KEY="your-api-key"  # or GEMINI_API_KEY

# Launch the TUI
adh-cli              # console script entry point
# or use the task wrapper
task run

# Enable Textual dev tools
task dev             # launches with inspector + auto-reload

# Serve the TUI in a browser (Ctrl+C to stop)
task serve-web
```

You can also run without cloning by using `uvx`:
```bash
GOOGLE_API_KEY=your-key \
uvx --from gh:allenhutchison/adh-cli adh-cli -- --debug
```

## Configuration
- **Environment** – `GOOGLE_API_KEY` or `GEMINI_API_KEY` (optionally via `.env`).
- **Persistent settings** – Stored under `~/.config/adh-cli/config.json` (model, orchestrator agent, temperature, etc.).
- **Policies** – Defaults ship with the package (`adh_cli/policies/defaults`). User overrides live in `~/.config/adh-cli/policies/`.
- **Audit & backups** – Audit log (`audit.log`) and tool backups live under the same XDG directory.
- **Model aliases** – Define custom model aliases with generation parameters in `~/.config/adh-cli/model_aliases.json`. See `docs/MODEL_ALIASES.md` for examples.
- **Docs** – See `docs/TOOLS.md` and `docs/TOOL_UI_DESIGN.md` for tool catalogues and UI notes.

## Development Workflow
All development helpers are exposed through `taskipy` (invoked with `task <name>` inside the virtualenv):

| Command | Description |
| --- | --- |
| `task lint` | Run Ruff checks (`ruff check adh_cli tests`). |
| `task format` | Format with Ruff (`ruff format`). |
| `task test` | Run the full pytest suite (329 tests). |
| `task test-cov` | Pytest with coverage reporting. |
| `task typecheck` | Run mypy over `adh_cli`. |
| `task dev` | Start the Textual app with the dev inspector. |
| `task serve-web` | Serve the Textual app over HTTP using `textual serve`. |
| `task console` | Open the Textual console alongside the TUI. |
| `task build` | Build source and wheel distributions. |
| `task docs-tools` | Regenerate tool documentation from the registry. |

Textual's `serve` subcommand expects a shell command, not a Python import path. If you prefer to run it manually, use:

```bash
textual serve "python -m adh_cli"
```

Attempting to pass `adh_cli.app:ADHApp` directly will fail with `command not found` because the server tries to execute that string as a command.

### Running Tests Manually
```bash
pytest                       # same as task test
pytest tests/ui/test_tool_execution_widget.py -k confirm  # focused run
```
CI (GitHub Actions) runs Ruff lint/format checks and pytest on Python 3.9, 3.10, 3.11, and 3.12 using uv.

## Project Layout
```
adh_cli/
├── app.py                    # Textual App wiring, policy-aware agent bootstrap
├── __main__.py               # CLI entry point (Click)
├── agents/                   # Markdown agent definitions
├── core/                     # Delegators, policy-aware tools, config paths
├── policies/                 # Default policy definitions & schemas
├── safety/                   # Safety pipeline + checkers
├── screens/                  # Textual screens (chat, main, settings modal)
├── services/                 # Clipboard & prompt services, ADK adapters
├── tools/                    # Tool implementations (shell, filesystem)
├── ui/                       # Widgets, execution manager, theming, styles
└── commands.py               # Command palette providers

tests/
├── agents/ / core/ / policies/ / safety/ / ui/ ...  # mirrored coverage
└── integration/             # End-to-end Textual + tool execution tests

docs/                        # Architecture notes, tool catalogues
```

## Contributing
Pull requests are welcome! Before submitting:
1. Run `task lint`, `task format`, and `task test`.
2. Ensure new functionality has accompanying tests.
3. Update docs/README when behaviour changes.
4. (Optional) install git hooks with `task hooks-install`.

See `CONTRIBUTING.md` for more detail on workflow and coding guidelines.

## License
MIT
