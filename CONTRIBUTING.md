# Contributing to ADH CLI

Thanks for your interest in contributing! This guide helps you set up your environment, run checks locally, and submit high‑quality pull requests.

## Development Setup

- Requirements: Python 3.9+, [uv](https://github.com/astral-sh/uv) recommended.

```bash
uv venv
source .venv/bin/activate
uv pip install -e '.[dev]'

# Install git hooks
task hooks-install
```

## Running Checks

- Lint: `task lint`
- Format: `task format` (or autofix: `task lint-fix`)
- Tests: `task test`
- Coverage: `task test-cov`
- Type check: `task typecheck`

Pre-commit runs basic checks automatically on commit and push.

## Submitting Changes

1. Fork the repo and create a feature branch.
2. Write focused commits with clear subjects (imperative mood).
3. Ensure CI passes: lint, format check, tests.
4. Open a Pull Request with:
   - Summary of the change and motivation
   - Any screenshots for UI changes
   - Notes on testing or potential impacts

## PR Guidelines

- Keep diffs minimal and localized; avoid drive‑by refactors.
- Include/adjust tests for behavior changes.
- Avoid committing secrets; use environment variables for API keys.
- Follow repository style: type hints preferred, 4‑space indentation.

## Reporting Issues

Please open an issue with reproduction steps, expected vs. actual behavior, and environment details. Use the templates provided when possible.

## Code of Conduct

This project follows the Contributor Covenant. See `CODE_OF_CONDUCT.md`.

