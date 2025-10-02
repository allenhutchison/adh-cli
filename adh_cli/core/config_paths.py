"""Centralized configuration path management for ADH CLI.

This module provides a single source of truth for all configuration and data
file paths, following XDG Base Directory specification.
"""

import shutil
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ConfigPaths:
    """Centralized configuration path management.

    All ADH CLI configuration and data files are stored in ~/.config/adh-cli/
    following XDG Base Directory specification.

    Legacy location (~/.adh-cli/) is supported with automatic migration.
    """

    # XDG-compliant base directory
    BASE_DIR = Path.home() / ".config" / "adh-cli"

    # Legacy directory for backward compatibility
    LEGACY_DIR = Path.home() / ".adh-cli"

    # Migration marker file
    _MIGRATION_MARKER = LEGACY_DIR / ".migrated"

    @classmethod
    def get_base_dir(cls) -> Path:
        """Get base configuration directory, creating if needed.

        Returns:
            Path to ~/.config/adh-cli/
        """
        cls.BASE_DIR.mkdir(parents=True, exist_ok=True)
        return cls.BASE_DIR

    @classmethod
    def get_config_file(cls) -> Path:
        """Get path to main configuration file.

        Returns:
            Path to config.json
        """
        cls.get_base_dir()  # Ensure directory exists
        return cls.BASE_DIR / "config.json"

    @classmethod
    def get_policies_dir(cls) -> Path:
        """Get path to policies directory.

        Returns:
            Path to policies/
        """
        policies_dir = cls.BASE_DIR / "policies"
        policies_dir.mkdir(parents=True, exist_ok=True)
        return policies_dir

    @classmethod
    def get_audit_log(cls) -> Path:
        """Get path to audit log file.

        Returns:
            Path to audit.log
        """
        cls.get_base_dir()  # Ensure directory exists
        return cls.BASE_DIR / "audit.log"

    @classmethod
    def get_backups_dir(cls) -> Path:
        """Get path to backups directory.

        Returns:
            Path to backups/
        """
        backups_dir = cls.BASE_DIR / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        return backups_dir

    @classmethod
    def get_policy_preferences(cls) -> Path:
        """Get path to policy preferences file.

        Returns:
            Path to policy_preferences.yaml
        """
        cls.get_base_dir()  # Ensure directory exists
        return cls.BASE_DIR / "policy_preferences.yaml"

    @classmethod
    def migrate_if_needed(cls) -> tuple[bool, Optional[str]]:
        """Migrate configuration from legacy location if needed.

        Checks if legacy directory (~/.adh-cli/) exists and new directory
        is empty or missing. If so, copies all files to new location.

        Migration is only performed once. A marker file (.migrated) is
        created in the legacy directory to prevent repeated migrations.

        Returns:
            Tuple of (migration_performed, error_message)
            - (True, None) if migration was successful
            - (False, None) if migration was not needed
            - (False, error_msg) if migration failed
        """
        # Check if migration already performed
        if cls._MIGRATION_MARKER.exists():
            logger.debug("Migration already performed (marker file exists)")
            return False, None

        # Check if legacy directory exists
        if not cls.LEGACY_DIR.exists():
            logger.debug("No legacy directory found, no migration needed")
            return False, None

        # Check if legacy directory is empty
        legacy_contents = list(cls.LEGACY_DIR.iterdir())
        if not legacy_contents:
            logger.debug("Legacy directory is empty, no migration needed")
            return False, None

        # Check if new directory already has content (manual setup)
        if cls.BASE_DIR.exists():
            new_contents = list(cls.BASE_DIR.iterdir())
            if new_contents:
                logger.info(
                    f"New config directory already exists with content, "
                    f"skipping migration"
                )
                # Create marker to prevent future migration attempts
                try:
                    cls._MIGRATION_MARKER.touch()
                except Exception as e:
                    logger.warning(f"Could not create migration marker: {e}")
                return False, None

        # Perform migration
        logger.info(f"Migrating configuration from {cls.LEGACY_DIR} to {cls.BASE_DIR}")

        try:
            # Create new base directory
            cls.BASE_DIR.mkdir(parents=True, exist_ok=True)

            # Track what was migrated for logging
            migrated_items = []

            # Copy all items from legacy directory
            for item in legacy_contents:
                # Skip the migration marker if it somehow exists
                if item.name == ".migrated":
                    continue

                dest = cls.BASE_DIR / item.name

                try:
                    if item.is_dir():
                        shutil.copytree(item, dest, dirs_exist_ok=True)
                        migrated_items.append(f"{item.name}/ (directory)")
                    else:
                        shutil.copy2(item, dest)
                        migrated_items.append(item.name)

                    logger.debug(f"Migrated: {item.name}")

                except Exception as e:
                    logger.error(f"Failed to migrate {item.name}: {e}")
                    # Continue with other items rather than failing completely

            # Create migration marker
            try:
                cls._MIGRATION_MARKER.touch()
                logger.info("Created migration marker file")
            except Exception as e:
                logger.warning(f"Could not create migration marker: {e}")

            logger.info(
                f"Migration completed successfully. Migrated {len(migrated_items)} items"
            )
            logger.debug(f"Migrated items: {', '.join(migrated_items)}")

            return True, None

        except Exception as e:
            error_msg = f"Migration failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    @classmethod
    def get_legacy_dir(cls) -> Path:
        """Get legacy directory path.

        Returns:
            Path to ~/.adh-cli/

        Note:
            This is provided for backward compatibility and testing.
            New code should not use this.
        """
        return cls.LEGACY_DIR

    @classmethod
    def is_migrated(cls) -> bool:
        """Check if migration has been performed.

        Returns:
            True if migration marker exists
        """
        return cls._MIGRATION_MARKER.exists()
