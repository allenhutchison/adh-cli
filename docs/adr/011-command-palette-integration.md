# ADR 011: Command Palette Integration

**Status:** Accepted
**Date:** 2025-10-02
**Deciders:** Project Team
**Tags:** ui, commands, user-experience, textual

---

## Context

ADH CLI provides several actions that users can trigger via keybindings:
- Opening settings (API key, model selection, agent configuration)
- Viewing active policies
- Toggling safety checks
- Clearing chat history

However, keybindings have limitations:
1. **Discoverability**: Users must remember or look up keyboard shortcuts
2. **Conflicts**: Limited number of intuitive key combinations
3. **Platform differences**: Some key combinations may not work on all platforms
4. **Accessibility**: Not all users can easily use keyboard shortcuts

Textual provides a built-in command palette (Ctrl+P) that displays available commands in a searchable list. By default, it includes system commands (Quit, Change Theme, Show Keys, etc.), but applications can extend it with custom commands.

### Initial Attempts and Challenges

We attempted several approaches that failed:

1. **Direct class registration**: Initially tried adding provider classes directly to `COMMANDS`
   ```python
   COMMANDS = {ADHCommandProvider, SettingsCommandProvider}  # Lost default commands!
   ```
   **Problem**: This replaced Textual's default commands instead of extending them.

2. **Lambda callbacks**: Tried using lambda functions for action callbacks
   ```python
   lambda action=action: self.app.action(action)
   ```
   **Problem**: `self.app.action()` method doesn't exist. Also, closure issues with loop variables.

3. **run_action() calls**: Tried using Textual's action runner
   ```python
   self.app.run_action("show_settings")
   ```
   **Problem**: Actions weren't executing, unclear why this approach failed.

4. **Missing discover() method**: Initially only implemented `search()` method
   **Problem**: Commands didn't show up when palette first opened (empty query).

### Key Learnings

Through reading the [Textual Command Palette documentation](https://textual.textualize.io/guide/command_palette/) and experimentation, we discovered:

1. **Lazy Loading Pattern**: Command providers should be registered as factory functions, not classes
   ```python
   def get_adh_commands_provider():
       from .commands import ADHCommandProvider
       return ADHCommandProvider

   COMMANDS = App.COMMANDS | {get_adh_commands_provider}
   ```

2. **discover() vs search()**:
   - `discover()`: Called when palette opens with empty query, shows default/suggested commands
   - `search(query)`: Called when user types, filters commands based on query
   - Both should be implemented for good UX

3. **Callback Pattern**: Call action methods directly, don't use string-based action dispatching
   ```python
   # ✓ Correct
   def _run_settings(self) -> None:
       self.app.action_show_settings()

   # ✗ Wrong
   def _run_settings(self) -> None:
       self.app.run_action("show_settings")  # Doesn't work reliably
   ```

4. **Screen vs App Actions**: Some actions are defined on screens, not the app
   - App-level: `action_show_settings()`, `action_toggle_dark()`
   - Screen-level: `action_show_policies()`, `action_toggle_safety()`, `action_clear_chat()`
   - Must check which object has the action and call appropriately

## Decision

Extend Textual's default command palette with ADH CLI-specific commands using custom `Provider` subclasses.

### Architecture

```
User presses Ctrl+P
    ↓
Textual Command Palette opens
    ↓
Calls discover() on all registered providers
    ↓
ADHCommandProvider.discover() yields:
  - Settings
  - Show Policies
  - Toggle Safety
  - Clear Chat
    ↓
SettingsCommandProvider.discover() yields:
  - Configure API Key
  - Select Model
  - Change Orchestrator Agent
  - Adjust Temperature
  - Configure Max Tokens
    ↓
User sees all commands listed
    ↓
User types search query
    ↓
Calls search(query) on all providers
    ↓
Providers yield matching commands (fuzzy matched)
    ↓
User selects command
    ↓
Callback executes (calls action method directly)
```

### Implementation

#### 1. Command Provider Classes (`adh_cli/commands.py`)

```python
from textual.command import Provider, Hit, Hits

class ADHCommandProvider(Provider):
    """Provides core ADH CLI commands."""

    async def discover(self) -> Hits:
        """Show all commands when palette first opens."""
        commands = [
            ("Settings", "Open settings", self._run_settings),
            ("Show Policies", "Display policies", self._run_show_policies),
            # ...
        ]
        for name, help_text, callback in commands:
            yield Hit(1, name, callback, help=help_text)

    async def search(self, query: str) -> Hits:
        """Filter commands based on user query."""
        matcher = self.matcher(query)
        # Same commands list as discover()
        for name, help_text, callback in commands:
            score = matcher.match(name)
            if score > 0:
                yield Hit(score, matcher.highlight(name), callback, help=help_text)

    def _run_settings(self) -> None:
        """Execute settings action."""
        self.app.action_show_settings()  # Call method directly

    def _run_show_policies(self) -> None:
        """Execute show policies action."""
        if hasattr(self.screen, 'action_show_policies'):
            self.screen.action_show_policies()  # Screen-level action
```

#### 2. Lazy Provider Registration (`adh_cli/app.py`)

```python
def get_adh_commands_provider():
    """Lazy load ADH command provider."""
    from .commands import ADHCommandProvider
    return ADHCommandProvider

def get_settings_commands_provider():
    """Lazy load settings command provider."""
    from .commands import SettingsCommandProvider
    return SettingsCommandProvider

class ADHApp(App):
    # Extend defaults, don't replace them
    COMMANDS = App.COMMANDS | {
        get_adh_commands_provider,
        get_settings_commands_provider
    }
```

#### 3. Keybindings Updated (`adh_cli/screens/chat_screen.py`)

Also updated keybindings to avoid conflicts:
- `Ctrl+/` → Show Policies (was Ctrl+P, which opens command palette)
- `Ctrl+,` → Settings (works when input has focus)
- `Ctrl+S` → Toggle Safety
- `Ctrl+L` → Clear Chat

## Consequences

### Positive

1. **Discoverability**: All commands visible in searchable palette
2. **Accessibility**: Works alongside keyboard shortcuts, doesn't replace them
3. **Extensibility**: Easy to add new commands by adding entries to providers
4. **Standard UX**: Follows Textual conventions (Ctrl+P)
5. **No Conflicts**: Preserves all Textual's default commands
6. **Searchable**: Users can type to filter (e.g., "api" finds "Configure API Key")
7. **Contextual Help**: Each command shows help text in palette

### Negative

1. **Code Duplication**: Command lists in both `discover()` and `search()` methods
   - **Mitigation**: Could extract to shared constant, but current approach is clear
2. **Screen Action Detection**: Must use `hasattr()` to check if screen has action
   - **Mitigation**: Document which actions are where, consider moving to app-level
3. **Indirect Calls**: Callbacks add indirection between palette and actions
   - **Mitigation**: Callbacks are simple one-liners, minimal overhead

### Neutral

1. **Two Providers**: Could combine into one, but separation is clearer
2. **Lazy Loading**: Required pattern adds boilerplate but improves startup time

## Alternatives Considered

### Alternative 1: String-Based Action Dispatch

Use `run_action("action_name")` for all callbacks.

**Pros:**
- Less code (no callback methods needed)
- More flexible (actions can be dynamically named)

**Cons:**
- Doesn't work reliably (discovered during implementation)
- Harder to debug (string typos not caught at import time)
- No IDE autocomplete or refactoring support

**Rejected because:** Couldn't get it working reliably, direct method calls are clearer.

### Alternative 2: Single Mega-Provider

One provider class for all commands.

**Pros:**
- Single point of definition
- Simpler COMMANDS registration

**Cons:**
- Less organized (settings vs core commands mixed)
- Harder to extend (would become very large)
- Less clear categorization

**Rejected because:** Separation by concern (core commands vs settings) is clearer.

### Alternative 3: Dynamic Action Discovery

Automatically discover all `action_*` methods from app and screen.

**Pros:**
- No manual command list maintenance
- Automatically includes new actions

**Cons:**
- All actions would be exposed (some might be internal)
- No control over command names or help text
- No categorization
- Complex implementation

**Rejected because:** Explicit is better than implicit for user-facing commands.

## Implementation Notes

### Command List Maintenance

When adding new commands:

1. Define action method on app or screen: `def action_my_command(self)`
2. Add to provider's command list in both `discover()` and `search()`
3. Add callback method: `def _run_my_command(self)`
4. Update help text to describe what command does

### Testing

Providers are tested indirectly through UI tests. Direct provider testing is challenging because:
- Providers require `screen` and `app` context
- Command palette is a Textual built-in widget
- End-to-end testing in TUI is complex

Current approach:
- Ensure action methods work (unit tested)
- Manual testing of command palette
- Could add integration tests if issues arise

### Future Enhancements

1. **Context-Aware Commands**: Show different commands based on current screen
2. **Recent Commands**: Track recently used commands, show them first
3. **Command Arguments**: Some commands could accept parameters (e.g., "Open File: ...")
4. **Keyboard Shortcuts in Palette**: Show keybinding next to command (e.g., "Settings (Ctrl+,)")
5. **Command Categories**: Group commands by category in palette

## References

- [Textual Command Palette Guide](https://textual.textualize.io/guide/command_palette/)
- [Textual Command API Reference](https://textual.textualize.io/api/command/)
- [Textual Provider Class](https://textual.textualize.io/api/command/#textual.command.Provider)
- [Textual Hit Class](https://textual.textualize.io/api/command/#textual.command.Hit)

## Related ADRs

- ADR-001: Textual TUI Framework (established use of Textual)
- ADR-010: Markdown-Driven Agent Definition (settings commands configure agents)

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-10-02 | Initial decision and implementation | Allen Hutchison |
