# ADR 004: Secure API Key Storage with System Keychain

**Status:** Proposed - Not Implemented
**Date:** 2025-09-30
**Deciders:** Project Team
**Tags:** security, critical, compliance

> **Implementation Status (2025-10-14):** This ADR describes a proposed future enhancement that has not yet been implemented. The application currently stores API keys using environment variables (GOOGLE_API_KEY, GEMINI_API_KEY) loaded via python-dotenv from .env files. Keychain integration and secure storage remain future work.

---

## Context

Currently, API keys are stored in plaintext JSON files in the user's home directory:

```python
# Current implementation in settings_screen.py
config_path = Path.home() / ".adh-cli" / "settings.json"
with open(config_path, "r") as f:
    settings = json.load(f)
    # API key stored as: {"api_key": "AIza..."}
```

### Security Vulnerabilities

**1. Plaintext Storage:**
- API keys visible to any process with user permissions
- Exposed in file system backups
- Readable by malware or other users (on shared systems)
- Violates Google's API key security best practices

**2. Version Control Risk:**
- Settings files might accidentally be committed to git
- API keys could leak in repository history
- Hard to audit who has access

**3. Compliance Issues:**
- Fails PCI-DSS requirements (if applicable)
- Not SOC 2 compliant
- Violates OWASP secure storage guidelines

**4. Cross-Platform Inconsistency:**
- No standard secure storage mechanism
- Different security properties on different OS

### Impact Assessment

**Who is affected:**
- All users storing API keys locally
- Organizations with security policies
- Users on shared/multi-user systems

**Data at risk:**
- Google API keys (access to Gemini)
- Potentially other credentials in future

**Attack vectors:**
- File system access
- Backup/sync services
- Process memory dumps
- Malware/spyware

## Decision

Implement secure credential storage using the **system keychain** via the `keyring` library:

### Architecture

**1. SecretsService Abstraction:**
```python
# adh_cli/services/secrets_service.py
import keyring
from typing import Optional

class SecretsService:
    """Secure storage for API keys and sensitive data."""

    SERVICE_NAME = "adh-cli"

    @staticmethod
    def store_api_key(key: str) -> None:
        """Store API key securely in system keychain."""
        keyring.set_password(
            SecretsService.SERVICE_NAME,
            "google_api_key",
            key
        )

    @staticmethod
    def get_api_key() -> Optional[str]:
        """Retrieve API key from secure storage."""
        return keyring.get_password(
            SecretsService.SERVICE_NAME,
            "google_api_key"
        )

    @staticmethod
    def delete_api_key() -> None:
        """Remove API key from keychain."""
        try:
            keyring.delete_password(
                SecretsService.SERVICE_NAME,
                "google_api_key"
            )
        except keyring.errors.PasswordDeleteError:
            pass
```

**2. Platform-Specific Backends:**
- **macOS**: Keychain Access (native, secure enclave)
- **Linux**: Secret Service API (GNOME Keyring, KWallet)
- **Windows**: Windows Credential Locker

**3. Fallback Strategy:**
If system keychain unavailable:
- Warn user about security risk
- Fall back to encrypted file storage
- Use `cryptography` library with machine-specific key
- Never fall back to plaintext

### Migration Path

**Phase 1: Automatic Migration (First Run)**
```python
def migrate_api_key_to_keychain():
    """Migrate existing API key from JSON to keychain."""
    config_path = Path.home() / ".adh-cli" / "settings.json"

    if not config_path.exists():
        return

    try:
        with open(config_path) as f:
            settings = json.load(f)

        if "api_key" in settings:
            # Store in keychain
            SecretsService.store_api_key(settings["api_key"])

            # Remove from JSON
            del settings["api_key"]

            # Save updated settings
            with open(config_path, "w") as f:
                json.dump(settings, f, indent=2)

            logger.info("API key migrated to secure storage")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
```

**Phase 2: Update All Access Points**
- `app.py::_load_api_key()` - Check keychain first
- `settings_screen.py` - Use SecretsService
- `settings_modal.py` - Use SecretsService

**Phase 3: Remove Plaintext Support**
- Delete old JSON loading code (after 2-3 releases)
- Update documentation
- Add warning for old config files

### API Key Loading Priority

```python
def _load_api_key(self):
    """Load API key from secure storage or environment."""
    # 1. Environment variables (highest priority)
    api_key = (
        os.environ.get("GOOGLE_API_KEY") or
        os.environ.get("GEMINI_API_KEY")
    )
    if api_key:
        return api_key

    # 2. System keychain
    api_key = SecretsService.get_api_key()
    if api_key:
        return api_key

    # 3. Legacy JSON (with migration)
    api_key = self._migrate_from_json()
    if api_key:
        return api_key

    return None
```

### User Experience

**First Time Setup:**
1. User enters API key in settings
2. Key stored in system keychain
3. Success notification shown
4. No visible change to user workflow

**Existing Users:**
1. App detects old JSON config
2. Automatic migration on next start
3. Notification: "API key secured in system keychain"
4. No action required

**Key Verification:**
```
Settings Screen:
┌────────────────────────────────┐
│ API Key: ••••••••••••••••••5a2f│  ← Show last 4 chars
│ [Change Key] [Remove Key]      │
│                                │
│ ✓ Stored securely in:          │
│   macOS Keychain               │
└────────────────────────────────┘
```

## Consequences

### Positive

**Security:**
- API keys encrypted at rest
- Platform-native security (hardware-backed on supported systems)
- Automatic encryption key management
- Follows OWASP secure storage guidelines

**Compliance:**
- Meets PCI-DSS requirements
- SOC 2 compliant
- GDPR-friendly (proper data protection)
- Audit-friendly (can track access)

**User Experience:**
- Seamless for most users (automatic migration)
- Works like password managers
- No additional steps required
- Cross-platform consistency

**Maintainability:**
- Less code than custom encryption
- Battle-tested library
- Active maintenance
- Good documentation

### Negative

**Dependency:**
- New required dependency (`keyring`)
- Platform-specific backends
- Potential compatibility issues
- ~500KB install size

**Complexity:**
- More complex than JSON file
- Platform-specific behavior
- Debugging harder (can't cat file)
- Testing requires mocking

**Migration Risk:**
- Could fail on some systems
- User data migration always risky
- Need good error handling
- Rollback strategy required

**Limited Environments:**
- Headless servers (no keyring daemon)
- Docker containers (no system keychain)
- CI/CD pipelines (need workaround)

### Risks

**Risk 1: Keyring Unavailable**
- **Impact:** High - app can't store keys
- **Mitigation:**
  - Detect at startup
  - Show clear error message
  - Offer encrypted file fallback
  - Document environment requirements

**Risk 2: Migration Failure**
- **Impact:** Medium - user loses API key
- **Mitigation:**
  - Keep backup of JSON during migration
  - Extensive error logging
  - Retry mechanism
  - Manual recovery instructions

**Risk 3: Platform-Specific Bugs**
- **Impact:** Medium - works on some systems, not others
- **Mitigation:**
  - Test on all platforms (macOS, Linux, Windows)
  - Document known issues
  - Provide workarounds
  - Monitor issue reports

**Risk 4: Keyring Permission Errors**
- **Impact:** Low - user can't access keychain
- **Mitigation:**
  - Clear error messages
  - Link to platform docs
  - Fallback to environment variables
  - Sudo requirements documented

### Neutral

**Testing:**
- Need platform-specific tests
- Mock keyring in unit tests
- Integration tests on real keychain
- CI/CD needs special handling

**Documentation:**
- Update security docs
- Platform-specific setup guides
- Migration FAQ
- Troubleshooting section

## Alternatives Considered

### Alternative 1: Custom Encryption

Encrypt JSON file with user password or machine ID.

**Pros:**
- No external dependencies
- Works everywhere
- Full control

**Cons:**
- Need to manage encryption keys
- Password prompts annoy users
- Machine ID not always unique
- Reinventing the wheel
- Not as secure as platform keychain

**Why Rejected:** Platform keychain is more secure and better UX.

### Alternative 2: Environment Variables Only

Force users to use `GOOGLE_API_KEY` environment variable.

**Pros:**
- No storage needed
- Already supported
- Standard practice

**Cons:**
- Poor UX (must export every session)
- Visible in process list
- Shell history exposure
- Not persistent

**Why Rejected:** Too cumbersome for daily use.

### Alternative 3: Encrypted SQLite Database

Store credentials in encrypted SQLite database.

**Pros:**
- Can store multiple secrets
- Better than JSON
- Cross-platform

**Cons:**
- Still need to manage encryption key
- More complex than keyring
- Not leveraging platform security
- Overkill for single API key

**Why Rejected:** Keyring is simpler and more secure.

### Alternative 4: OAuth 2.0 Flow

Use OAuth instead of API keys.

**Pros:**
- More secure (scoped, revocable)
- Industry standard
- Token refresh

**Cons:**
- Google doesn't support OAuth for Gemini API
- Requires web server
- Complex setup
- Not applicable to current API

**Why Rejected:** Not supported by Gemini API.

## Implementation Notes

### Dependencies

**Add to requirements.txt:**
```
keyring>=24.0.0
```

**Optional backends:**
```
# Linux
secretstorage>=3.3.0  # For GNOME Keyring

# Windows (included in keyring)
pywin32-ctypes>=0.2.0
```

### File Structure

```
adh_cli/
  services/
    secrets_service.py      # New: 100 LOC

tests/
  services/
    test_secrets_service.py # New: 150 LOC
```

### Modified Files

```
adh_cli/
  app.py                    # Update: _load_api_key()
  screens/
    settings_screen.py      # Update: Use SecretsService
    settings_modal.py       # Update: Use SecretsService
```

### Migration Script

```python
# adh_cli/migrations/001_keychain_migration.py
def run_migration():
    """Run one-time migration to keychain."""
    config_path = Path.home() / ".adh-cli" / "settings.json"
    backup_path = config_path.with_suffix(".json.backup")

    # Create backup
    if config_path.exists():
        shutil.copy(config_path, backup_path)

    try:
        # Migrate
        migrate_api_key_to_keychain()

        # Verify
        if SecretsService.get_api_key():
            # Remove backup
            backup_path.unlink()
            return True
    except Exception as e:
        # Restore backup
        if backup_path.exists():
            shutil.copy(backup_path, config_path)
        raise
```

### Testing Strategy

**Unit Tests:**
```python
def test_store_and_retrieve_api_key():
    SecretsService.store_api_key("test_key_123")
    assert SecretsService.get_api_key() == "test_key_123"
    SecretsService.delete_api_key()
    assert SecretsService.get_api_key() is None

def test_delete_nonexistent_key():
    # Should not raise
    SecretsService.delete_api_key()
```

**Integration Tests:**
```python
@pytest.mark.integration
def test_migration_from_json():
    # Create old-style JSON
    config = {"api_key": "old_key_123"}
    config_path.write_text(json.dumps(config))

    # Run migration
    migrate_api_key_to_keychain()

    # Verify in keychain
    assert SecretsService.get_api_key() == "old_key_123"

    # Verify removed from JSON
    new_config = json.loads(config_path.read_text())
    assert "api_key" not in new_config
```

**Platform Tests:**
- macOS: Test with Keychain Access
- Linux: Test with GNOME Keyring, KWallet
- Windows: Test with Credential Manager

### Documentation Updates

**Security Guide** (`docs/security.md`):
```markdown
## API Key Storage

ADH CLI stores API keys securely using your system's keychain:

- **macOS**: Keychain Access
- **Linux**: GNOME Keyring or KWallet
- **Windows**: Windows Credential Manager

Keys are encrypted at rest and only accessible to your user account.

### Troubleshooting

**Linux: No keyring available**
Install gnome-keyring or kwallet:
```bash
# Ubuntu/Debian
sudo apt install gnome-keyring

# Fedora
sudo dnf install gnome-keyring
```

**Permission denied**
Ensure your user has access to the keychain service.
```

### Rollout Plan

**Version X.X.0:**
- Add SecretsService
- Automatic migration
- Keep JSON fallback
- Deprecation warning

**Version X.X+1:**
- Default to keychain only
- JSON read-only (no write)
- Migration prompt if JSON detected

**Version X.X+2:**
- Remove JSON support
- Keychain required
- Clear error if unavailable

## References

**Security Standards:**
- [OWASP Secure Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [Google API Key Best Practices](https://cloud.google.com/docs/authentication/api-keys)

**Libraries:**
- [keyring Documentation](https://pypi.org/project/keyring/)
- [Python Keyring Backends](https://github.com/jaraco/keyring#backend-integration)

**Platform Docs:**
- [macOS Keychain](https://support.apple.com/guide/keychain-access/welcome/mac)
- [GNOME Keyring](https://wiki.gnome.org/Projects/GnomeKeyring)
- [Windows Credential Manager](https://support.microsoft.com/en-us/windows/accessing-credential-manager-1b5c916a-6a16-889f-8581-fc16e8165ac0)

**Related ADRs:**
- ADR-001: Policy-Aware Architecture
- ADR-005: Error Handling Improvements (dependency)

**Code Examples:**
- [keyring Usage Examples](https://github.com/jaraco/keyring#usage)
- Similar implementations in other CLIs

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-09-30 | Initial proposal | Project Team |
