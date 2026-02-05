#!/usr/bin/env python3
"""Validate openCenter AirGap configuration files.

This script validates all configuration files against JSON schemas before
the build process begins. It catches configuration errors early and provides
clear error messages.

Usage:
    python scripts/build/validate_config.py
    python scripts/build/validate_config.py --config-dir config
    python scripts/build/validate_config.py --versions-only

Exit codes:
    0: All validations passed
    1: Validation failed
    2: Configuration file not found
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Any

import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from opencenter_build.validation import ConfigValidator
from opencenter_build.exceptions import ValidationError


def parse_versions_env(file_path: Path) -> Dict[str, str]:
    """Parse versions.env file into dictionary.

    Args:
        file_path: Path to versions.env file

    Returns:
        Dictionary of KEY=value pairs

    Raises:
        FileNotFoundError: If file does not exist
    """
    if not file_path.exists():
        raise FileNotFoundError(f"versions.env not found: {file_path}")

    versions = {}
    for line in file_path.read_text().splitlines():
        line = line.strip()
        # Skip comments and empty lines
        if not line or line.startswith("#"):
            continue
        # Parse KEY=value (handle quoted values and inline comments)
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            # Remove quotes
            if value.startswith('"') and '"' in value[1:]:
                # Find closing quote and ignore everything after
                closing_quote = value.index('"', 1)
                value = value[1:closing_quote]
            elif value.startswith("'") and "'" in value[1:]:
                # Find closing quote and ignore everything after
                closing_quote = value.index("'", 1)
                value = value[1:closing_quote]
            else:
                # No quotes, remove inline comments
                if "#" in value:
                    value = value.split("#")[0].strip()

            versions[key] = value

    return versions


def validate_versions(config_dir: Path, validator: ConfigValidator) -> bool:
    """Validate versions.env configuration.

    Args:
        config_dir: Configuration directory path
        validator: ConfigValidator instance

    Returns:
        True if validation passed, False otherwise
    """
    versions_file = config_dir / "versions.env"
    print(f"Validating {versions_file}...")

    try:
        versions = parse_versions_env(versions_file)
        validator.validate_versions_env(versions)
        print(f"✓ versions.env is valid ({len(versions)} variables)")
        return True
    except FileNotFoundError as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        return False
    except ValidationError as e:
        print(f"✗ Validation failed:\n{e}", file=sys.stderr)
        return False


def validate_nodes(examples_dir: Path, validator: ConfigValidator) -> bool:
    """Validate example node inventory files.

    Args:
        examples_dir: Examples directory path
        validator: ConfigValidator instance

    Returns:
        True if all validations passed, False otherwise
    """
    node_files = list(examples_dir.glob("nodes-*.yaml"))
    if not node_files:
        print("⚠ No node inventory files found in examples/")
        return True

    all_valid = True
    for node_file in node_files:
        print(f"Validating {node_file}...")
        try:
            nodes = yaml.safe_load(node_file.read_text())
            validator.validate_nodes_file(nodes)
            print(f"✓ {node_file.name} is valid")
        except yaml.YAMLError as e:
            print(f"✗ Invalid YAML in {node_file.name}: {e}", file=sys.stderr)
            all_valid = False
        except ValidationError as e:
            print(f"✗ Validation failed for {node_file.name}:\n{e}", file=sys.stderr)
            all_valid = False

    return all_valid


def validate_openstack(examples_dir: Path, validator: ConfigValidator) -> bool:
    """Validate example OpenStack configuration files.

    Args:
        examples_dir: Examples directory path
        validator: ConfigValidator instance

    Returns:
        True if all validations passed, False otherwise
    """
    openstack_files = list(examples_dir.glob("openstack-*.yaml"))
    if not openstack_files:
        print("⚠ No OpenStack configuration files found in examples/")
        return True

    all_valid = True
    for openstack_file in openstack_files:
        print(f"Validating {openstack_file}...")
        try:
            openstack_config = yaml.safe_load(openstack_file.read_text())
            validator.validate_openstack_config(openstack_config)
            print(f"✓ {openstack_file.name} is valid")
        except yaml.YAMLError as e:
            print(f"✗ Invalid YAML in {openstack_file.name}: {e}", file=sys.stderr)
            all_valid = False
        except ValidationError as e:
            print(f"✗ Validation failed for {openstack_file.name}:\n{e}", file=sys.stderr)
            all_valid = False

    return all_valid


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(description="Validate openCenter AirGap configuration files")
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("config"),
        help="Configuration directory (default: config)",
    )
    parser.add_argument(
        "--examples-dir",
        type=Path,
        default=Path("examples"),
        help="Examples directory (default: examples)",
    )
    parser.add_argument(
        "--schema-dir",
        type=Path,
        default=Path("config/schemas"),
        help="Schema directory (default: config/schemas)",
    )
    parser.add_argument(
        "--versions-only",
        action="store_true",
        help="Only validate versions.env",
    )

    args = parser.parse_args()

    # Initialize validator
    try:
        validator = ConfigValidator(args.schema_dir)
    except ValidationError as e:
        print(f"✗ Failed to initialize validator: {e}", file=sys.stderr)
        return 2

    print("=" * 60)
    print("openCenter AirGap Configuration Validation")
    print("=" * 60)
    print()

    # Validate versions.env (required)
    versions_valid = validate_versions(args.config_dir, validator)

    if args.versions_only:
        return 0 if versions_valid else 1

    print()

    # Validate example node files (optional)
    nodes_valid = validate_nodes(args.examples_dir, validator)

    print()

    # Validate example OpenStack files (optional)
    openstack_valid = validate_openstack(args.examples_dir, validator)

    print()
    print("=" * 60)

    if versions_valid and nodes_valid and openstack_valid:
        print("✓ All validations passed")
        return 0
    else:
        print("✗ Some validations failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
