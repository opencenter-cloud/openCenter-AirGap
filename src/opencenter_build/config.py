"""Configuration loading and parsing utilities.

This module provides functions for loading and parsing configuration files
used in the build system, including versions.env and YAML configurations.
"""

import re
from pathlib import Path
from typing import Any

import yaml

from opencenter_build.exceptions import ConfigError


def parse_versions_env(config_file: Path) -> dict[str, str]:
    """Parse versions.env file into dictionary.

    Parses shell variable assignments from versions.env, ignoring comments
    and empty lines. Supports quoted and unquoted values.

    Args:
        config_file: Path to versions.env file

    Returns:
        Dictionary mapping variable names to values

    Raises:
        ConfigError: If file cannot be read or parsed

    Example:
        >>> versions = parse_versions_env(Path("config/versions.env"))
        >>> print(versions["KUBERNETES_VERSION"])
        v1.34.3
    """
    if not config_file.exists():
        raise ConfigError(f"Configuration file not found: {config_file}")

    versions: dict[str, str] = {}

    try:
        content = config_file.read_text()
    except Exception as exc:
        raise ConfigError(f"Failed to read {config_file}: {exc}") from exc

    for line in content.splitlines():
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith("#"):
            continue

        # Parse KEY=VALUE or KEY="VALUE"
        match = re.match(r"^([A-Z_][A-Z0-9_]*)=(.+)$", line)
        if not match:
            continue

        key, value = match.groups()

        # Remove quotes if present
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]

        versions[key] = value

    return versions


def load_versions_env(config_file: Path) -> dict[str, str]:
    """Load versions.env file into dictionary.

    Alias for parse_versions_env for backward compatibility.

    Args:
        config_file: Path to versions.env file

    Returns:
        Dictionary mapping variable names to values

    Raises:
        ConfigError: If file cannot be read or parsed
    """
    return parse_versions_env(config_file)


def load_yaml_config(config_file: Path) -> dict[str, Any]:
    """Load YAML configuration file.

    Args:
        config_file: Path to YAML file

    Returns:
        Parsed YAML content as dictionary

    Raises:
        ConfigError: If file cannot be read or parsed

    Example:
        >>> nodes = load_yaml_config(Path("config/nodes.yaml"))
        >>> print(nodes["control_plane"])
    """
    if not config_file.exists():
        raise ConfigError(f"Configuration file not found: {config_file}")

    try:
        content = config_file.read_text()
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            raise ConfigError(f"Expected YAML dict, got {type(data).__name__}")
        return data
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse YAML in {config_file}: {exc}") from exc
    except Exception as exc:
        raise ConfigError(f"Failed to read {config_file}: {exc}") from exc


def write_yaml_config(config_file: Path, data: dict[str, Any]) -> None:
    """Write configuration to YAML file.

    Args:
        config_file: Path to output YAML file
        data: Dictionary to write as YAML

    Raises:
        ConfigError: If file cannot be written
    """
    try:
        config_file.parent.mkdir(parents=True, exist_ok=True)
        content = yaml.safe_dump(data, default_flow_style=False, sort_keys=False)
        config_file.write_text(content)
    except Exception as exc:
        raise ConfigError(f"Failed to write {config_file}: {exc}") from exc
