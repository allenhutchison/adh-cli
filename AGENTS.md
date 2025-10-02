# Repository Guidelines

## Project Structure & Module Organization
- `adh_cli/`: application code (Textual TUI). Key areas: `app.py`, `screens/`, `services/`, `tools/`, CLI entry `__main__.py`.
- `tests/`: pytest suite mirrored by area, e.g. `tests/screens/test_chat_screen.py`.
- `docs/`, `screenshots/`: documentation assets and UI snapshots.
- `pyproject.toml`: dependencies, tasks, pytest/coverage config. `Makefile`: friendly wrappers.

## Build, Test, and Development Commands
- `make help`: list available commands.
- `task run` or `make run`: run the installed CLI (`adh-cli`).
- `task dev` or `make dev`: run with Textual dev tools.
- `task test` / `task test-cov`: run tests / with coverage.
- `task lint` / `task format`: lint and format with Ruff.
- `task build` / `make build`: build distributions.
- Optional: `task console` (Textual console), `task clean`, `task install-dev`.

## Coding Style & Naming Conventions
- Python 3.9+; 4-space indentation; prefer type hints.
- Use Ruff for linting and formatting: `task lint`, `task format`.
- Naming: packages/modules `snake_case`; classes `PascalCase`; functions/vars `snake_case`.
- Keep modules focused; place UI in `screens/`, services in `services/`, tools in `tools/`.

## Testing Guidelines
- Frameworks: `pytest`, `pytest-asyncio`, coverage configured in `pyproject.toml`.
- Conventions (pytest ini): files `test_*.py`, classes `Test*`, functions `test_*`.
- Run all tests: `task test`; with coverage: `task test-cov`.
- Add tests under `tests/<area>/test_<module>.py`; avoid coverage regressions.

## Commit & Pull Request Guidelines
- Commit subject: imperative, concise (e.g., "Add settings keybinding").
- Reference scope/ADR when relevant (e.g., "Implement ADR-010: …").
- PRs: clear description, linked issues, before/after screenshots for TUI changes, CLI output where helpful.
- Required: tests pass, `task lint` and `task format` clean, docs updated (`README.md`, `docs/`, `screenshots/`).

## Security & Configuration Tips
- API keys via env (`GOOGLE_API_KEY`/`GEMINI_API_KEY`) or `.env` (dotenv). Never commit secrets.
- Avoid logging sensitive values; scrub screenshots.

## Agent-Specific Instructions
- Prefer `Makefile`/`task` commands over custom scripts.
- Keep diffs minimal and localized; update/extend tests with changes.
- See `CLAUDE.md` and `GEMINI.md` for assistant usage conventions.
