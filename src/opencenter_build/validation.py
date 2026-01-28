"""Configuration validation using JSON schemas.

This module provides schema-based validation for all openCenter AirGap
configuration files. Validation catches errors early in the build process
before asset collection begins.

Classes:
    ConfigValidator: Validates configuration files against JSON schemas
"""

import json
from pathlib import Path
from typing import Any, Dict

import jsonschema
from jsonschema import Draft7Validator

from opencenter_build.exceptions import ValidationError


class ConfigValidator:
    """Validate configuration files against JSON schemas.

    This class loads JSON schemas from a directory and validates configuration
    dictionaries against them. It provides clear error messages with field paths
    when validation fails.

    Attributes:
        schema_dir: Path to directory containing JSON schema files
    """

    def __init__(self, schema_dir: Path) -> None:
        """Initialize validator with schema directory.

        Args:
            schema_dir: Path to directory containing .schema.json files

        Raises:
            ValidationError: If schema directory does not exist
        """
        self.schema_dir = schema_dir
        if not self.schema_dir.exists():
            raise ValidationError(
                f"Schema directory not found: {schema_dir}\n" f"Expected location: config/schemas/"
            )

    def _load_schema(self, schema_name: str) -> Dict[str, Any]:
        """Load JSON schema from file.

        Args:
            schema_name: Name of schema file (e.g., "versions.schema.json")

        Returns:
            Parsed JSON schema as dictionary

        Raises:
            ValidationError: If schema file not found or invalid JSON
        """
        schema_path = self.schema_dir / schema_name
        if not schema_path.exists():
            raise ValidationError(
                f"Schema not found: {schema_name}\n"
                f"Expected path: {schema_path}\n"
                f"Available schemas: {', '.join(f.name for f in self.schema_dir.glob('*.json'))}"
            )

        try:
            schema_dict: Dict[str, Any] = json.loads(schema_path.read_text())
            return schema_dict
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON in schema {schema_name}: {e}") from e

    def _validate_against_schema(
        self, config: Dict[str, Any], schema: Dict[str, Any], config_name: str
    ) -> None:
        """Validate configuration against schema.

        Args:
            config: Configuration dictionary to validate
            schema: JSON schema dictionary
            config_name: Name of configuration (for error messages)

        Raises:
            ValidationError: If validation fails with detailed error message
        """
        try:
            validator = Draft7Validator(schema)
            errors = sorted(validator.iter_errors(config), key=lambda e: e.path)

            if errors:
                error_messages = []
                for error in errors:
                    path = ".".join(str(p) for p in error.path) if error.path else "root"
                    error_messages.append(f"  - {path}: {error.message}")

                raise ValidationError(
                    f"Validation failed for {config_name}:\n" + "\n".join(error_messages)
                )

        except jsonschema.SchemaError as e:
            raise ValidationError(f"Invalid schema for {config_name}: {e.message}") from e

    def validate_versions_env(self, config: Dict[str, str]) -> None:
        """Validate versions.env configuration.

        Validates version pins for all components. Ensures required fields exist
        and version strings match expected patterns (semantic versioning).

        Args:
            config: Dictionary of version variables (KEY=value pairs)

        Raises:
            ValidationError: If validation fails with specific field errors

        Example:
            >>> validator = ConfigValidator(Path("config/schemas"))
            >>> versions = {"KUBERNETES_VERSION": "v1.34.3", ...}
            >>> validator.validate_versions_env(versions)
        """
        schema = self._load_schema("versions.schema.json")
        self._validate_against_schema(config, schema, "versions.env")

    def validate_nodes_file(self, config: Dict[str, Any]) -> None:
        """Validate node inventory configuration.

        Validates node definitions for Kubespray deployment. Checks control plane
        and worker node specifications including hostnames, IPs, and optional fields.

        Args:
            config: Node inventory dictionary (YAML parsed to dict)

        Raises:
            ValidationError: If validation fails (invalid IPs, hostnames, etc.)

        Example:
            >>> validator = ConfigValidator(Path("config/schemas"))
            >>> nodes = yaml.safe_load(Path("nodes.yaml").read_text())
            >>> validator.validate_nodes_file(nodes)
        """
        schema = self._load_schema("nodes.schema.json")
        self._validate_against_schema(config, schema, "nodes configuration")

    def validate_openstack_config(self, config: Dict[str, Any]) -> None:
        """Validate OpenStack configuration.

        Validates OpenStack credentials and VM configuration for Terraform
        provisioning. Ensures all required fields exist and values are valid.

        Args:
            config: OpenStack configuration dictionary

        Raises:
            ValidationError: If validation fails (missing credentials, invalid URLs, etc.)

        Example:
            >>> validator = ConfigValidator(Path("config/schemas"))
            >>> openstack = yaml.safe_load(Path("openstack-config.yaml").read_text())
            >>> validator.validate_openstack_config(openstack)
        """
        schema = self._load_schema("openstack-config.schema.json")
        self._validate_against_schema(config, schema, "OpenStack configuration")

    def validate_zarf_variables(self, config: Dict[str, Any]) -> None:
        """Validate Zarf package variables.

        Validates variable overrides for Zarf package deployment. Checks paths,
        ports, network CIDRs, and boolean flags.

        Args:
            config: Zarf variables dictionary

        Raises:
            ValidationError: If validation fails (invalid paths, ports, CIDRs, etc.)

        Example:
            >>> validator = ConfigValidator(Path("config/schemas"))
            >>> zarf_vars = {"install_path": "/opt/opencenter", "registry_port": 5000}
            >>> validator.validate_zarf_variables(zarf_vars)
        """
        schema = self._load_schema("zarf-variables.schema.json")
        self._validate_against_schema(config, schema, "Zarf variables")
