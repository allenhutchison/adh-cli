# ADR 009: XDG-Compliant Configuration Directory

**Status:** Proposed
**Date:** 2025-10-02
**Deciders:** Project Team
**Tags:** configuration, refactoring, standards-compliance, medium-priority

---

## Context

ADH CLI currently stores configuration and data files in two separate locations:

1. **`~/.adh-cli/`** - Contains policies, backups, audit logs, and preferences
2. **`~/.config/adh-cli/`** - Contains application configuration (config.json)

### Current Structure

```
~/.adh-cli/
├── policies/
│   ├── audit.log
│   ├── commands.yaml
│   └── filesystem.yaml
├── policy_preferences.yaml
└── backups/

~/.config/adh-cli/
└── config.json
```

### Problems

1. **Non-Standard Location**: `~/.adh-cli/` does not follow XDG Base Directory specification
2. **Split Configuration**: Users must manage files in two separate locations
3. **Inconsistent Documentation**: Need to explain two different directories
4. **Code Complexity**: Path references scattered across 6+ files with inconsistent patterns
5. **User Confusion**: Not clear where to find configuration files

### Forces at Play

**XDG Base Directory Specification:**
- `~/.config/` - User-specific configuration files
- `~/.local/share/` - User-specific data files
- `~/.cache/` - User-specific non-essential cached data

Most modern CLI tools follow this standard (e.g., `gh`, `kubectl`, `aws-cli`, `rg`).

**Backward Compatibility:**
- Existing users have data in `~/.adh-cli/`
- Cannot break existing installations
- Need smooth migration path

## Decision

Consolidate all configuration and data files to **`~/.config/adh-cli/`** following XDG Base Directory specification guidelines.

### New Structure

```
~/.config/adh-cli/
├── config.json              # Application configuration
├── policies/
│   ├── defaults/            # Default policies (from project)
│   ├── custom/              # User custom policies
│   ├── commands.yaml        # Command execution policies
│   └── filesystem.yaml      # Filesystem policies
├── policy_preferences.yaml  # User policy overrides
├── audit.log                # Tool execution audit log
└── backups/                 # File modification backups
```

### Implementation Approach

#### 1. Centralized Path Management

Create `adh_cli/core/config_paths.py` module:

```python
class ConfigPaths:
    """Centralized configuration path management."""

    BASE_DIR = Path.home() / ".config" / "adh-cli"
    LEGACY_DIR = Path.home() / ".adh-cli"  # For migration

    @classmethod
    def get_base_dir(cls) -> Path:
        """Get base config directory, creating if needed."""

    @classmethod
    def get_config_file(cls) -> Path:
        """Get path to config.json."""

    @classmethod
    def get_policies_dir(cls) -> Path:
        """Get path to policies directory."""

    @classmethod
    def get_audit_log(cls) -> Path:
        """Get path to audit log."""

    @classmethod
    def get_backups_dir(cls) -> Path:
        """Get path to backups directory."""

    @classmethod
    def get_policy_preferences(cls) -> Path:
        """Get path to policy preferences file."""

    @classmethod
    def migrate_if_needed(cls) -> bool:
        """Migrate from legacy location if needed."""
```

#### 2. Automatic Migration

On application startup:
1. Check if `~/.adh-cli/` exists and `~/.config/adh-cli/` is empty/missing
2. Copy all files from old location to new location
3. Create `.migrated` marker file in old directory
4. Show user notification about migration
5. Keep old directory for manual cleanup

Migration will:
- Be automatic and transparent
- Preserve all existing data
- Log migration actions
- Never delete the old directory (user cleanup)
- Only run once (marker file prevents re-running)

#### 3. Code Updates

Replace all hardcoded path references:

**Before:**
```python
# Scattered across multiple files
policy_dir = Path.home() / ".adh-cli" / "policies"
config_path = os.path.expanduser("~/.config/adh-cli/config.json")
backup_dir = Path.home() / ".adh-cli" / "backups"
```

**After:**
```python
from adh_cli.core.config_paths import ConfigPaths

policy_dir = ConfigPaths.get_policies_dir()
config_path = ConfigPaths.get_config_file()
backup_dir = ConfigPaths.get_backups_dir()
```

Files to update:
- `adh_cli/app.py` (line 49)
- `adh_cli/screens/settings_modal.py` (lines 131, 166)
- `adh_cli/policies/policy_engine.py` (line 244)
- `adh_cli/safety/checkers/filesystem_checkers.py` (line 48)

## Consequences

### Positive

1. **Standards Compliance**: Follows XDG Base Directory specification
2. **Single Location**: All config and data in one place
3. **Better User Experience**: Familiar location for CLI tool users
4. **Simpler Documentation**: One directory to document
5. **Cleaner Code**: Centralized path management
6. **Future-Proof**: Easier to add caching, state, or other XDG directories later
7. **Tool Integration**: Standard location works with backup/sync tools

### Negative

1. **Migration Complexity**: Need to handle migration for existing users
2. **Testing Burden**: Must test migration paths thoroughly
3. **Deprecation Period**: Need to maintain backward compatibility checking

### Risks

**Risk 1: Migration Failures**
- **Impact**: Users lose configuration or policy data
- **Mitigation**:
  - Never delete old directory
  - Copy files (don't move)
  - Log all migration actions
  - Comprehensive testing with various data scenarios
  - Dry-run mode in tests

**Risk 2: Permission Issues**
- **Impact**: Cannot create `~/.config/adh-cli/`
- **Mitigation**:
  - Graceful error handling
  - Clear error messages
  - Fall back to old location if new location inaccessible
  - Check permissions before migration

**Risk 3: Partial Migrations**
- **Impact**: Some files in old location, some in new
- **Mitigation**:
  - Atomic migration (all or nothing where possible)
  - Use marker file to track completion
  - Verify all expected files after migration
  - Allow re-running if marker file missing

### Neutral

1. **Path Length**: Slightly longer paths (`~/.config/adh-cli` vs `~/.adh-cli`)
2. **Change Notice**: Users will see migration notification (one-time)

## Alternatives Considered

### Alternative 1: Split XDG Directories

Use proper XDG separation:
- `~/.config/adh-cli/` - config.json only
- `~/.local/share/adh-cli/` - policies, backups, audit log
- `~/.cache/adh-cli/` - temporary files

**Pros:**
- Pure XDG compliance
- Semantic separation

**Cons:**
- Three directories instead of one
- More complex migration
- Over-engineered for current needs
- Policies are arguably "configuration"

**Rejected because:** Configuration, policies, and audit logs are all closely related. Having them in one location is simpler and adequate for this use case.

### Alternative 2: Keep Current Split

Leave `~/.adh-cli/` as-is, keep `~/.config/adh-cli/` for config.json only.

**Pros:**
- No migration needed
- No risk of breaking existing setups

**Cons:**
- Maintains non-standard structure
- Continues user confusion
- Misses opportunity for improvement

**Rejected because:** Does not solve the underlying problem and perpetuates technical debt.

### Alternative 3: Environment Variable Override

Add `ADH_CLI_CONFIG_DIR` environment variable to override default location.

**Pros:**
- Maximum flexibility
- Power users can customize

**Cons:**
- Adds complexity
- Most users won't use it
- Documentation overhead

**Decision:** Not implementing now, but not preventing future addition if needed.

### Alternative 4: Only Update Documentation

Document both locations as intentional, explain their purposes.

**Pros:**
- Zero code changes
- No migration risk

**Cons:**
- Doesn't solve the problem
- Still non-standard

**Rejected because:** Does not address the core issue.

## Implementation Notes

### Phase 1: Foundation (High Priority)

1. **Create `config_paths.py`**
   - Implement `ConfigPaths` class
   - Add comprehensive docstrings
   - Include path validation
   - Add directory creation logic

2. **Add Migration Logic**
   - Implement `migrate_if_needed()`
   - Create detailed migration logging
   - Add marker file handling
   - Include rollback capability

3. **Add Tests**
   - Test all ConfigPaths methods with temp directories
   - Test migration with various scenarios:
     - Empty old directory
     - Full old directory
     - Partially migrated state
     - Permission errors
     - Existing new directory

### Phase 2: Integration (High Priority)

1. **Update `app.py`**
   - Call `ConfigPaths.migrate_if_needed()` in `__init__`
   - Replace hardcoded `policy_dir`
   - Add migration notification

2. **Update All Path References**
   - `settings_modal.py` - config.json paths
   - `policy_engine.py` - policy preferences path
   - `filesystem_checkers.py` - backups directory

3. **Update Tests**
   - Fix tests using hardcoded paths
   - Add ConfigPaths to test fixtures

### Phase 3: Polish (Medium Priority)

1. **Documentation Updates**
   - Update `CLAUDE.md` with new paths
   - Add migration notes to README
   - Document ConfigPaths API

2. **Deprecation Notice**
   - Add one-time notification for migrated users
   - Include instructions for manual cleanup
   - Document in CHANGELOG

### Testing Strategy

**Unit Tests:**
- ConfigPaths methods with various inputs
- Directory creation edge cases
- Path validation

**Integration Tests:**
- Full migration flow
- App initialization with migration
- Config file access after migration

**Manual Testing:**
- Fresh install (no old directory)
- Existing install (old directory present)
- Partially migrated state
- Permission denied scenarios

### Migration Message Example

```
✓ Configuration migrated to ~/.config/adh-cli/

Your ADH CLI configuration has been moved to follow XDG standards.
Old location: ~/.adh-cli/
New location: ~/.config/adh-cli/

All your settings, policies, and data have been preserved.
You can safely delete ~/.adh-cli/ when ready.

This message will only appear once.
```

### Future Enhancements

1. **Cache Directory**: Add `~/.cache/adh-cli/` for temporary files if needed
2. **State Directory**: Add `~/.local/state/adh-cli/` for session state if needed
3. **Environment Override**: Add `ADH_CLI_CONFIG_DIR` if users request it
4. **Config Validation**: Add schema validation for config.json
5. **Backup Management**: Automatic cleanup of old backups

## References

- Related ADRs: ADR-004 (Secure API Key Storage), ADR-010 (Markdown-Driven Agents)
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html)
- [Python platformdirs library](https://github.com/platformdirs/platformdirs)
- Examples: GitHub CLI (`~/.config/gh/`), Kubernetes (`~/.kube/config`)

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-10-02 | Initial decision | Allen Hutchison |
