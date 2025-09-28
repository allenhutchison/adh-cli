# Makefile for ADH CLI

.PHONY: help test test-v test-cov lint format dev clean install run build

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

test:  ## Run tests
	pytest

test-v:  ## Run tests with verbose output
	pytest -v

test-cov:  ## Run tests with coverage report
	pytest --cov=adh_cli --cov-report=term-missing

test-watch:  ## Run tests in watch mode
	pytest-watch

lint:  ## Run linter
	ruff check adh_cli tests

format:  ## Format code
	ruff format adh_cli tests

typecheck:  ## Run type checking
	mypy adh_cli

dev:  ## Run app in development mode
	textual run --dev adh_cli.app:ADHApp

console:  ## Run Textual console for debugging
	textual console

build:  ## Build distribution packages
	python -m build

clean:  ## Clean build artifacts
	rm -rf build dist *.egg-info .pytest_cache .coverage __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

install:  ## Install the package
	uv pip install -e .

install-dev:  ## Install development dependencies
	uv pip install -e '.[dev]' -r requirements-dev.txt

run:  ## Run the application
	adh-cli

.DEFAULT_GOAL := help