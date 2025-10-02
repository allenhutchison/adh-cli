"""Centralized configuration path management for ADH CLI.

This module provides a single source of truth for all configuration and data
file paths, following XDG Base Directory specification.
"""

from pathlib import Path


class ConfigPaths:
    """Centralized configuration path management.

    All ADH CLI configuration and data files are stored in ~/.config/adh-cli/
    following XDG Base Directory specification.
    """

    # XDG-compliant base directory
    BASE_DIR = Path.home() / ".config" / "adh-cli"

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
