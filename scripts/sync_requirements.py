#!/usr/bin/env python3
"""
Sync requirements files with pyproject.toml dependencies.

This script reads dependencies from pyproject.toml and generates
requirements.txt and requirements-dev.txt files to keep them in sync.
"""

import tomllib
from pathlib import Path


def main():
    """Generate requirements files from pyproject.toml."""
    # Read pyproject.toml
    project_root = Path(__file__).parent.parent
    pyproject_path = project_root / "pyproject.toml"

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    # Extract dependencies
    runtime_deps = data.get("project", {}).get("dependencies", [])
    dev_deps = data.get("project", {}).get("optional-dependencies", {}).get("dev", [])

    # Write requirements.txt
    requirements_path = project_root / "requirements.txt"
    with open(requirements_path, "w") as f:
        for dep in runtime_deps:
            f.write(f"{dep}\n")

    print(f"✅ Updated {requirements_path}")

    # Write requirements-dev.txt
    requirements_dev_path = project_root / "requirements-dev.txt"
    with open(requirements_dev_path, "w") as f:
        # Include runtime requirements
        f.write("-r requirements.txt\n")
        # Add dev dependencies
        for dep in dev_deps:
            f.write(f"{dep}\n")

    print(f"✅ Updated {requirements_dev_path}")

    # Show summary
    print(f"\n📦 Dependencies synced:")
    print(f"  Runtime: {len(runtime_deps)} packages")
    print(f"  Dev: {len(dev_deps)} packages")


if __name__ == "__main__":
    main()