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

# Install dependencies using uv (editable + dev extras)
uv pip install -e '.[dev]'
```

### Installation (Alternative with pip)
```bash
# If not using uv, you can use standard pip
pip install -e '.[dev]'
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

The `adh_cli/core/policy_aware_llm_agent.py` provides ADK-based AI interactions:
- Uses Google ADK's LlmAgent for automatic tool orchestration
- Integrates policy engine with ADK agent
- Evaluates all tool calls against policies before execution
- Handles confirmation workflows for supervised operations
- Maintains audit logs of all tool executions
- Supports event streaming for real-time monitoring
- Session management for stateful conversations

### Screen Architecture
Each screen inherits from `textual.screen.Screen`:
- **ChatScreen**: Policy-aware chat with confirmation dialogs and safety checks
- **SettingsScreen**: Model configuration and API key management

### Async Patterns
- Chat messages are processed using `app.run_worker()` for non-blocking UI
- Input handling uses Textual's event system with `@on` decorators
- All ADK API calls are wrapped in async workers to maintain UI responsiveness

## Key Implementation Details

### Configuration

#### API Key Management
- Checks environment variables in order: config.api_key → GOOGLE_API_KEY → GEMINI_API_KEY
- Uses python-dotenv to load from .env file
- Runtime configuration updates via SettingsScreen

### Chat Session State
- Uses ADK's InMemorySessionService for state management
- Automatic multi-turn conversation handling with tool orchestration
- All tool calls go through policy evaluation before execution

### Textual Keybindings
Global bindings defined in `ADHApp.BINDINGS`:
- Navigation: h (Home), c (Chat), s (Settings)
- Actions: q (Quit), d (Toggle dark mode)
- Screen-specific: ESC (Back), Ctrl+L (Clear chat in ChatScreen)

### Tool System

#### Available Tools

All tools are available by default. Access control and confirmation requirements are managed by the policy engine.

- **read_file**: Read text files with size limits (automatic)
- **list_directory**: List directory contents (automatic)
- **get_file_info**: Get file/directory metadata (automatic)
- **create_directory**: Create directories with permission checks (automatic)
- **write_file**: Write content with backup creation (requires confirmation)
- **delete_file**: Delete files with confirmation requirements (requires confirmation)
- **execute_command**: Run shell commands with safety validation (requires confirmation by default)
- **fetch_url**: Fetch content from HTTP/HTTPS URLs (requires confirmation)

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
  - Read operations (read_file, list_directory, get_file_info): automatic
  - Directory creation: automatic
  - Write operations (write_file): require confirmation
  - Delete operations (delete_file): require confirmation
  - System files: denied
- **command_policies.yaml**: Command execution rules
  - Safe read commands: notify only
  - Git operations: read=automatic, write=confirmation
  - Package managers: require confirmation
  - File modification commands: require confirmation
  - Dangerous commands: manual review
  - Destructive commands: blocked
- **network_policies.yaml**: Network operation rules
  - HTTP/HTTPS fetching (fetch_url): require confirmation
  - Size limits enforced (10MB max)
  - Only HTTP/HTTPS schemes allowed

#### Custom Policies
Users can create custom policies in `~/.config/adh-cli/policies/`:
- YAML format with pattern matching
- Priority-based rule ordering
- Conditional restrictions
- Safety check requirements

### Testing

#### Test Coverage
- **205+ total tests** across the project
- Policy engine: 58 tests
- Core agents: 25 tests (PolicyAwareLlmAgent + PolicyAwareFunctionTool)
- ADK integration: 14 tests
- Shell tools: 28 tests
- UI components: 32 tests
- Safety checkers: 24 tests
- Plus additional service and tool tests

#### Running Tests
```bash
# Run all tests
pytest

# Run policy tests
pytest tests/policies/ tests/safety/

# Run core agent tests
pytest tests/core/

# Run ADK integration tests
pytest tests/integration/

# Run with coverage
pytest --cov=adh_cli

# Quick test run (no traceback)
pytest --tb=no -q
```

## Architecture Decision Records (ADRs)

This project uses ADRs to document architectural decisions. ADRs are located in `docs/adr/` and follow a structured format.

### ADR Status Taxonomy

ADRs use a precise status taxonomy to distinguish between decisions, implementations, and proposals:

- **Accepted**: Decision made and fully implemented as described
- **Accepted - Implementation Differs from Specification**: Core functionality implemented but details differ (document both)
- **Proposed**: Decision documented but awaits implementation
- **Proposed - Partially Implemented**: Some parts implemented, others pending (be specific about what's done)
- **Proposed - Not Implemented**: Future feature documented but not yet started
- **Superseded**: Replaced by another ADR (reference the replacement)

### Keeping ADRs Accurate

ADRs require active maintenance to remain trustworthy. When working on this codebase:

**1. Verify ADR Claims Before Major Work**
- If an ADR references test counts, file paths, or line counts, verify they're accurate
- If implementation has diverged from an ADR, update the ADR first
- Don't assume ADRs reflect current reality—check the code

**2. Update ADRs When Implementation Changes**
- If you implement a "Proposed" ADR, update its status to "Accepted"
- If implementation differs from design, add an implementation note explaining how
- If you remove features described in an ADR, mark it as "Superseded" or add a note

**3. Add Implementation Status Notes**
When an ADR's status is ambiguous, add a blockquote note at the top:

```markdown
> **Implementation Status (YYYY-MM-DD):** This ADR describes a proposed feature
> that has not yet been implemented. Current state: [describe reality].
> The proposed architecture remains future work.
```

**4. Keep Concrete Details Accurate**
These are key signals that ADRs have drifted:
- **Test counts** ("58 tests" → verify with actual count)
- **File paths** (`~/.adh-cli/` → check if moved to `~/.config/adh-cli/`)
- **Line counts** ("395 LOC" → verify with `wc -l`)
- **File existence** ("will create X.py" → check if X.py exists)

**5. Document Implementation Gaps**
If an ADR documents a decision but code doesn't implement it:
- Mark status as "Proposed - Not Implemented" or "Partially Implemented"
- Add note explaining what's missing
- If it's a critical gap (like ADR-021 tool registration), highlight it clearly

**6. Celebrate Implementation Improvements**
If implementation exceeds the original design:
- Update the ADR to reflect the better approach
- Add a note like "Implementation Note: Actual implementation uses X instead of Y, providing better Z"
- Don't pretend it matches the original spec

**7. Use Revision History**
Add entries to the revision history table at the bottom of ADRs:

```markdown
| Date | Change | Author |
|------|--------|--------|
| 2025-10-14 | Updated test counts, fixed file paths | AI Assistant |
```

### When to Create New ADRs

Create ADRs for:
- Architectural patterns that affect multiple components
- Technology choices (frameworks, libraries, patterns)
- Cross-cutting concerns (security, performance, observability)
- Significant refactorings that change component relationships

Don't create ADRs for:
- Implementation details of a single component
- Bug fixes (unless they reveal architectural issues)
- Routine feature additions that follow existing patterns

### ADR Review Checklist

When reviewing ADRs (quarterly or before major releases):

- [ ] Verify test counts match actual test suite
- [ ] Check file paths are correct and consistent
- [ ] Confirm line counts are reasonably accurate
- [ ] Verify claimed features actually exist
- [ ] Update status for implemented proposals
- [ ] Add implementation notes for divergent implementations
- [ ] Mark deferred features as "Not Implemented"
- [ ] Update revision history with review date

### Example: Good vs Bad ADR Updates

**Bad Update:**
```markdown
# ADR 042: New Feature X
Status: Proposed
[entire document describes feature not built]
```

**Good Update:**
```markdown
# ADR 042: New Feature X
Status: Proposed - Not Implemented

> **Implementation Status (2025-10-14):** This ADR describes a proposed
> feature that has not yet been implemented. File X.py and service Y do not
> exist. This remains future work pending prioritization.

[rest of document unchanged]
```

### Living Documentation Philosophy

ADRs serve multiple purposes:
- **Historical Record**: What was decided, when, and why
- **Implementation Guide**: How the system actually works today
- **Roadmap**: What's planned for the future
- **Onboarding Material**: How to understand the architecture

Keep these purposes clear through accurate status indicators and honest assessment of what's implemented vs. proposed.
