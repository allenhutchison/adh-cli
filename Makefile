# Makefile for ADH CLI
# This Makefile delegates to taskipy for consistency

.PHONY: help test test-v test-cov lint format dev clean install run build sync-deps docs-tools

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

test:  ## Run tests
	task test

test-v:  ## Run tests with verbose output
	task test-v

test-cov:  ## Run tests with coverage report
	task test-cov

test-watch:  ## Run tests in watch mode
	task test-watch

lint:  ## Run linter
	task lint

format:  ## Format code
	task format

typecheck:  ## Run type checking
	task typecheck

dev:  ## Run app in development mode
	task dev

console:  ## Run Textual console for debugging
	task console

build:  ## Build distribution packages
	task build

clean:  ## Clean build artifacts
	task clean

install:  ## Install the package
	uv pip install -e .

install-dev:  ## Install development dependencies
	task install-dev

run:  ## Run the application
	task run

sync-deps:  ## Sync requirements files with pyproject.toml
	task sync-deps

docs-tools: ## Generate Tools Reference docs from specs
	task docs-tools

.DEFAULT_GOAL := help
