# ADR 006: Policy Configuration UI

**Status:** Proposed
**Date:** 2025-09-30
**Deciders:** Project Team
**Tags:** ui, user-experience, policies, high-priority

---

## Context

Currently, policy configuration in ADH CLI is only possible through:

### Current State

**1. Manual YAML Editing:**
```yaml
# ~/.adh-cli/policies/custom_policies.yaml
filesystem:
  delete_file:
    pattern: "delete_file"
    supervision: "manual"
    risk: "high"
```

**Problems:**
- Requires understanding YAML syntax
- Must know policy schema
- Easy to make syntax errors
- No validation until runtime
- Hard to discover available options

**2. Code Modification:**
```python
# adh_cli/policies/defaults/filesystem_policies.yaml
# Users can't easily modify without understanding structure
```

**3. Placeholder UI:**
```python
# app.py
def action_show_policies(self):
    self.notify("Policy configuration screen coming soon!")
```

### User Pain Points

**From User Feedback:**
- "I want to trust certain read operations but I don't know the YAML format"
- "How do I make all file writes require confirmation?"
- "What presets are available?"
- "Can I see what policies are currently active?"

**From Support Requests:**
- 40% of issues related to policy misconfiguration
- Users accidentally blocking legitimate operations
- Difficulty discovering available supervision levels
- Can't easily switch between paranoid/balanced/permissive modes

**From Developer Pain:**
- Can't easily test different policy configurations
- Hard to debug policy issues
- No way to validate policy changes before applying

### Business Requirements

**Usability:**
- Non-technical users should configure policies
- Visual interface better than YAML editing
- Immediate validation of changes
- Preview impact before applying

**Discoverability:**
- Show all available tools and patterns
- Explain supervision levels
- Display risk levels clearly
- Provide sensible presets

**Safety:**
- Can't create invalid configurations
- Preview changes before applying
- Easy rollback to defaults
- Confirm destructive changes

## Decision

Implement a comprehensive **Policy Configuration Screen** with:

### Architecture

**1. Policy Configuration Screen:**
```
┌─────────────────────────────────────────────────────┐
│                Policy Configuration                  │
├─────────────────────────────────────────────────────┤
│                                                      │
│ Quick Presets:  [Paranoid ▼]  [Apply]              │
│                                                      │
│ ┌────────────────────────────────────────────────┐  │
│ │ Paranoid - Maximum Safety                      │  │
│ │ • Confirm everything                            │  │
│ │ • Never auto-approve                            │  │
│ │ • Block destructive operations                  │  │
│ └────────────────────────────────────────────────┘  │
│                                                      │
│ Tool Policies:                                      │
│ ┌────────────────────────────────────────────────┐  │
│ │Tool Pattern    │Supervision │Risk    │Enabled  │  │
│ ├────────────────┼────────────┼────────┼────────┤  │
│ │read_file       │automatic   │low     │   ✓    │  │
│ │write_file      │confirm     │medium  │   ✓    │  │
│ │delete_file     │manual      │high    │   ✓    │  │
│ │execute_command │confirm     │medium  │   ✓    │  │
│ │format_*        │deny        │critical│   ✓    │  │
│ └────────────────────────────────────────────────┘  │
│                                                      │
│ User Preferences:                                   │
│                                                      │
│ Auto-approve patterns (comma-separated):            │
│ ┌────────────────────────────────────────────────┐  │
│ │ read_*, list_*, get_*                          │  │
│ └────────────────────────────────────────────────┘  │
│                                                      │
│ Never allow patterns (comma-separated):             │
│ ┌────────────────────────────────────────────────┐  │
│ │ delete_*, format_*, rm_*                       │  │
│ └────────────────────────────────────────────────┘  │
│                                                      │
│ □ Enable audit logging                              │
│ □ Show notifications for automatic operations      │
│                                                      │
│ [Save] [Reset to Defaults] [Cancel]                │
└─────────────────────────────────────────────────────┘
```

**2. Policy Presets System:**
```python
# adh_cli/policies/presets.py

@dataclass
class PolicyPreset:
    """Predefined policy configuration."""
    name: str
    description: str
    supervision_defaults: Dict[str, str]
    auto_approve: List[str]
    never_allow: List[str]
    audit_enabled: bool = True

PRESETS = {
    "paranoid": PolicyPreset(
        name="Paranoid",
        description="Maximum safety - confirm everything",
        supervision_defaults={"*": "manual"},
        auto_approve=[],
        never_allow=["delete_*", "format_*", "rm_*", "dd*"],
    ),

    "balanced": PolicyPreset(
        name="Balanced",
        description="Good balance of safety and convenience (recommended)",
        supervision_defaults={
            "read_*": "automatic",
            "list_*": "automatic",
            "get_*": "automatic",
            "write_*": "confirm",
            "create_*": "confirm",
            "delete_*": "manual",
            "execute_*": "confirm",
        },
        auto_approve=["read_*", "list_*", "get_*"],
        never_allow=["format_*", "rm -rf /*"],
    ),

    "permissive": PolicyPreset(
        name="Permissive",
        description="Trust the AI - minimal safety checks",
        supervision_defaults={"*": "notify"},
        auto_approve=["*"],
        never_allow=[],
    ),
}
```

**3. Screen Implementation:**
```python
# adh_cli/screens/policy_config_screen.py

class PolicyConfigScreen(Screen):
    """Configure policies and user preferences."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+s", "save_policies", "Save"),
    ]

    def __init__(self, policy_dir: Path):
        super().__init__()
        self.policy_dir = policy_dir
        self.modified = False
        self.current_policies = {}
        self.user_preferences = {}

    def compose(self) -> ComposeResult:
        """Compose the policy configuration screen."""
        yield Static("Policy Configuration", id="policy-header")

        with ScrollableContainer(id="policy-content"):
            # Preset Selection
            yield Label("Quick Presets", classes="section-title")
            yield Select(
                options=[
                    ("Paranoid - Maximum Safety", "paranoid"),
                    ("Balanced - Recommended", "balanced"),
                    ("Permissive - Minimal Checks", "permissive"),
                    ("Custom - Configure Manually", "custom"),
                ],
                value="balanced",
                id="preset-select"
            )

            # Tool-Specific Policies
            yield Label("Tool Policies", classes="section-title")
            table = DataTable(id="policy-table")
            table.add_columns("Tool Pattern", "Supervision", "Risk Level", "Enabled")
            yield table

            # User Preferences
            yield Label("User Preferences", classes="section-title")

            yield Label("Auto-approve patterns (comma-separated):")
            yield Input(
                placeholder="e.g., read_*, list_*, get_*",
                id="auto-approve-input"
            )

            yield Label("Never allow patterns (comma-separated):")
            yield Input(
                placeholder="e.g., delete_*, format_*, rm_*",
                id="never-allow-input"
            )

            with Horizontal():
                yield Label("Enable audit logging:")
                yield Switch(value=True, id="audit-switch")

        with Horizontal(id="button-row"):
            yield Button("Save", variant="primary", id="save-btn")
            yield Button("Reset to Defaults", variant="warning", id="reset-btn")
            yield Button("Cancel", variant="default", id="cancel-btn")

    @on(Select.Changed, "#preset-select")
    def on_preset_changed(self, event: Select.Changed) -> None:
        """Handle preset selection."""
        preset = event.value

        if preset == "paranoid":
            self._apply_preset(PRESETS["paranoid"])
        elif preset == "balanced":
            self._apply_preset(PRESETS["balanced"])
        elif preset == "permissive":
            self._apply_preset(PRESETS["permissive"])

        self.modified = True

    def _apply_preset(self, preset: PolicyPreset) -> None:
        """Apply a preset to the UI."""
        # Update inputs
        self.query_one("#auto-approve-input", Input).value = ", ".join(preset.auto_approve)
        self.query_one("#never-allow-input", Input).value = ", ".join(preset.never_allow)
        self.query_one("#audit-switch", Switch).value = preset.audit_enabled

        self.notify(f"Applied {preset.name} preset - {preset.description}", severity="information")

    @on(Button.Pressed, "#save-btn")
    def action_save_policies(self) -> None:
        """Save policy configuration."""
        try:
            # Collect user preferences
            auto_approve = [
                p.strip() for p in
                self.query_one("#auto-approve-input", Input).value.split(",")
                if p.strip()
            ]
            never_allow = [
                p.strip() for p in
                self.query_one("#never-allow-input", Input).value.split(",")
                if p.strip()
            ]

            preferences = {
                "auto_approve": auto_approve,
                "never_allow": never_allow,
                "audit_enabled": self.query_one("#audit-switch", Switch).value,
            }

            # Save to YAML
            pref_file = Path.home() / ".adh-cli" / "policy_preferences.yaml"
            pref_file.parent.mkdir(parents=True, exist_ok=True)

            with open(pref_file, "w") as f:
                yaml.dump(preferences, f, default_flow_style=False)

            # Apply to current agent
            if hasattr(self.app, 'agent') and self.app.agent:
                self.app.agent.policy_engine.user_preferences.update(preferences)

            self.notify("Policies saved successfully!", severity="success")
            self.modified = False

        except Exception as e:
            self.notify(f"Error saving policies: {e}", severity="error")
```

### User Workflows

**Workflow 1: Quick Preset Selection**
```
1. User presses Ctrl+P (or menu option)
2. Policy Configuration Screen opens
3. User selects "Paranoid" from dropdown
4. All fields auto-populate
5. User clicks "Save"
6. Policies applied immediately
7. Confirmation notification shown
```

**Workflow 2: Custom Configuration**
```
1. User opens Policy Configuration
2. Selects "Custom" preset
3. Edits auto-approve patterns
4. Edits never-allow patterns
5. Toggles audit logging
6. Clicks "Save"
7. Validates configuration
8. Applies to agent
9. Success notification
```

**Workflow 3: Review Current Policies**
```
1. User opens Policy Configuration
2. Screen shows current settings
3. Table displays all tool policies
4. User can see what's configured
5. No changes needed - clicks "Cancel"
```

## Consequences

### Positive

**Usability:**
- Non-technical users can configure policies
- Visual, guided configuration
- Immediate feedback on changes
- No YAML syntax to learn

**Discoverability:**
- See all available tools
- Understand supervision levels
- Learn risk levels
- Discover presets

**Safety:**
- Invalid configs prevented by UI
- Preview before applying
- Easy rollback
- Confirmation for risky changes

**Adoption:**
- Lower barrier to entry
- More users will configure policies
- Better default experience
- Reduced support burden

**Testing:**
- Developers can easily test configurations
- QA can reproduce policy issues
- Faster debugging

### Negative

**Complexity:**
- ~500 LOC for screen
- ~200 LOC for presets
- ~300 LOC for tests
- Maintenance burden

**UI Real Estate:**
- Dedicated screen needed
- Tables can get large
- Scrolling required

**State Management:**
- Keep UI in sync with files
- Handle concurrent changes
- Validation complexity

### Risks

**Risk 1: UI/File Sync Issues**
- **Impact:** Medium - users edit YAML while UI open
- **Mitigation:**
  - Detect file changes
  - Prompt to reload
  - Show warning if modified externally
  - Lock file while editing (optional)

**Risk 2: Invalid Configurations**
- **Impact:** High - users create invalid policies
- **Mitigation:**
  - Validate all inputs before saving
  - Show validation errors inline
  - Provide examples
  - Test with invalid inputs

**Risk 3: Preset Confusion**
- **Impact:** Low - users don't understand presets
- **Mitigation:**
  - Clear descriptions
  - Show what each preset does
  - Preview before applying
  - Document in help text

**Risk 4: Performance with Many Policies**
- **Impact:** Low - slow loading with 100+ policies
- **Mitigation:**
  - Lazy load policy table
  - Pagination if needed
  - Cache policy data
  - Optimize rendering

### Neutral

**Testing:**
- Need UI tests for screen
- Preset application tests
- File I/O tests
- Validation tests

**Documentation:**
- Update user guide
- Add screenshots
- Preset descriptions
- Troubleshooting

## Alternatives Considered

### Alternative 1: CLI-Based Configuration

Use command-line flags to configure policies.

**Pros:**
- No UI code needed
- Scriptable
- Fast for power users

**Cons:**
- Poor discoverability
- Hard to remember syntax
- Not user-friendly
- Can't see current state easily

**Why Rejected:** Doesn't solve usability problem for non-technical users.

### Alternative 2: Web-Based Configuration

Launch web server with policy config UI.

**Pros:**
- Rich UI possibilities
- Cross-platform (browser)
- Familiar to users

**Cons:**
- Complexity (web server)
- Security concerns (localhost)
- Breaks TUI consistency
- External dependency (browser)

**Why Rejected:** Breaks the TUI experience; adds unnecessary complexity.

### Alternative 3: Wizard-Based Setup

Step-by-step wizard for initial setup only.

**Pros:**
- Guided experience
- Good for first-time users
- Reduces overwhelm

**Cons:**
- Can't reconfigure easily
- Only helps initially
- Still need persistent UI
- More screens to maintain

**Why Rejected:** Doesn't solve ongoing configuration needs.

### Alternative 4: Policy Configuration Dialog (Modal)

Use modal dialog instead of full screen.

**Pros:**
- Less screen management
- Quicker to implement
- Familiar pattern

**Cons:**
- Limited space
- Can't show full policy table
- Cramped UI
- Harder to navigate

**Why Rejected:** Too complex for modal; full screen better for this use case.

## Implementation Notes

### File Structure

```
adh_cli/
  screens/
    policy_config_screen.py    # New: 500 LOC

  policies/
    presets.py                 # New: 200 LOC

tests/
  screens/
    test_policy_config_screen.py  # New: 300 LOC

  policies/
    test_presets.py            # New: 100 LOC
```

### Modified Files

```
adh_cli/
  app.py                       # Update: action_show_policies()
```

### Data Storage

**User Preferences:**
```yaml
# ~/.adh-cli/policy_preferences.yaml
auto_approve:
  - "read_*"
  - "list_*"
  - "get_*"

never_allow:
  - "format_*"
  - "rm -rf /*"

audit_enabled: true
show_automatic_notifications: false

# Metadata
last_modified: "2025-09-30T12:00:00"
preset: "balanced"
```

**Policy Override File:**
```yaml
# ~/.adh-cli/policies/user_overrides.yaml
# Generated from UI
filesystem:
  delete_file:
    supervision: "manual"  # User changed from default
    risk: "high"
```

### CSS Styling

```css
PolicyConfigScreen {
    layout: vertical;
}

#policy-header {
    height: 3;
    padding: 1;
    background: $primary;
    color: $text;
    text-align: center;
    text-style: bold;
}

#policy-content {
    height: 1fr;
    padding: 1;
}

.section-title {
    text-style: bold;
    margin: 1 0;
    color: $secondary;
}

#policy-table {
    height: 15;
    border: solid $primary;
}

#button-row {
    height: 3;
    dock: bottom;
    align: center middle;
}

/* Risk level indicators */
.risk-low { color: green; }
.risk-medium { color: yellow; }
.risk-high { color: orange; }
.risk-critical { color: red; }
```

### Validation Rules

```python
def validate_pattern(pattern: str) -> tuple[bool, Optional[str]]:
    """Validate a policy pattern."""
    if not pattern:
        return False, "Pattern cannot be empty"

    if pattern == "*":
        return True, None  # Wildcard is valid

    # Check for valid pattern characters
    if not re.match(r'^[a-zA-Z0-9_*]+$', pattern):
        return False, "Pattern can only contain letters, numbers, underscore, and *"

    # Check for valid wildcard usage
    if pattern.count('*') > 1:
        return False, "Pattern can only contain one wildcard"

    return True, None

def validate_supervision_level(level: str) -> tuple[bool, Optional[str]]:
    """Validate supervision level."""
    valid_levels = ["automatic", "notify", "confirm", "manual", "deny"]

    if level not in valid_levels:
        return False, f"Invalid supervision level. Must be one of: {', '.join(valid_levels)}"

    return True, None
```

### Testing Strategy

**UI Tests:**
```python
@pytest.mark.asyncio
async def test_preset_selection():
    """Test applying a preset."""
    screen = PolicyConfigScreen(tmp_path / "policies")

    async with ADHApp().run_test() as pilot:
        # Select paranoid preset
        await pilot.click("#preset-select")
        # Select from dropdown
        # ... pilot interactions

        # Verify fields populated
        auto_approve = screen.query_one("#auto-approve-input", Input).value
        assert auto_approve == ""  # Paranoid has no auto-approve

        never_allow = screen.query_one("#never-allow-input", Input).value
        assert "delete_*" in never_allow

@pytest.mark.asyncio
async def test_save_policies():
    """Test saving policy configuration."""
    screen = PolicyConfigScreen(tmp_path / "policies")

    # Set values
    screen.query_one("#auto-approve-input", Input).value = "read_*, list_*"

    # Click save
    await pilot.click("#save-btn")

    # Verify file created
    pref_file = Path.home() / ".adh-cli" / "policy_preferences.yaml"
    assert pref_file.exists()

    # Verify contents
    with open(pref_file) as f:
        prefs = yaml.safe_load(f)
    assert "read_*" in prefs["auto_approve"]
```

**Preset Tests:**
```python
def test_apply_paranoid_preset(tmp_path):
    """Test applying paranoid preset to engine."""
    engine = PolicyEngine(tmp_path / "policies")
    apply_preset("paranoid", engine)

    # Verify read allowed
    decision = engine.evaluate_tool_call(
        ToolCall(tool_name="read_file", parameters={})
    )
    assert decision.allowed is True

    # Verify delete blocked
    decision = engine.evaluate_tool_call(
        ToolCall(tool_name="delete_file", parameters={})
    )
    assert decision.supervision_level == SupervisionLevel.MANUAL
```

### Migration from Placeholder

**Current:**
```python
def action_show_policies(self):
    self.notify("Policy configuration screen coming soon!")
```

**After:**
```python
def action_show_policies(self):
    """Show policy configuration screen."""
    self.push_screen(PolicyConfigScreen(self.policy_dir))
```

## References

**UI Design:**
- Textual DataTable examples
- Policy configuration UIs in other tools
- Settings screen patterns

**Related ADRs:**
- ADR-001: Policy-Aware Architecture
- ADR-002: Tool Execution UI Tracking

**Code:**
- Current: `adh_cli/app.py::action_show_policies()`
- Policies: `adh_cli/policies/`
- UI Components: `adh_cli/screens/`

**User Feedback:**
- Policy configuration requests
- YAML editing difficulties
- Support ticket analysis

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-09-30 | Initial proposal | Project Team |
