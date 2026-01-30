"""Configuration validation using JSON schemas.

This module provides schema-based validation for all openCenter AirGap
configuration files. Validation catches errors early in the build process
before asset collection begins.

Classes:
    ConfigValidator: Validates configuration files against JSON schemas
    ComprehensiveConfigValidator: Validates complete build configuration
"""

import json
import shutil
import subprocess
from dataclasses import dataclass
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


@dataclass
class ValidationResult:
    """Result of configuration validation.

    Attributes:
        errors: List of validation errors (critical issues)
        warnings: List of validation warnings (non-critical issues)
        passed: Whether validation passed (no errors)
    """

    errors: list[str]
    warnings: list[str]

    @property
    def passed(self) -> bool:
        """Check if validation passed (no errors)."""
        return len(self.errors) == 0

    @property
    def has_warnings(self) -> bool:
        """Check if validation has warnings."""
        return len(self.warnings) > 0


class ComprehensiveConfigValidator:
    """Comprehensive configuration validator for build system.

    Validates all aspects of build configuration including:
    - versions.env file existence and required variables
    - Repository paths
    - External dependencies (Zarf, Docker)
    - Component manifest (if present)

    This validator implements Requirements 10.1, 10.2, 10.4, 10.5.
    """

    # Required variables in versions.env
    REQUIRED_VARIABLES = [
        "KUBERNETES_VERSION",
        "KUBESPRAY_VERSION",
        "KUBESPRAY_COMMIT_SHA",
        "UBUNTU_VERSION",
        "CONTAINER_RUNTIME",
        "CNI_PLUGIN",
        "TERRAFORM_VERSION",
        "FLUXCD_VERSION",
        "GITEA_VERSION",
        "CERT_MANAGER_VERSION",
        "INGRESS_NGINX_VERSION",
        "KEYCLOAK_VERSION",
        "PROMETHEUS_VERSION",
        "GRAFANA_VERSION",
        "OPENCENTER_GITOPS_BASE_REPO",
        "OPENCENTER_GITOPS_BASE_VERSION",
        "OPENCENTER_GITOPS_BASE_COMMIT_SHA",
        "OPENCENTER_CONTAINER_REGISTRY",
        "TARGET_ARCH",
        "PYTHON_VERSION",
    ]

    def __init__(self, config_file: Path = Path("config/versions.env")):
        """Initialize validator.

        Args:
            config_file: Path to versions.env configuration file
        """
        self.config_file = config_file

    def validate_all(
        self,
        check_repos: bool = True,
        check_dependencies: bool = True,
        check_component_manifest: bool = True,
        component_manifest_path: Path | None = None,
    ) -> ValidationResult:
        """Validate all configuration aspects.

        Args:
            check_repos: Check repository paths exist
            check_dependencies: Check external dependencies (Zarf, Docker)
            check_component_manifest: Check component manifest if present
            component_manifest_path: Path to component manifest (default: config/components.yaml)

        Returns:
            ValidationResult with errors and warnings

        Example:
            >>> validator = ComprehensiveConfigValidator()
            >>> result = validator.validate_all()
            >>> if not result.passed:
            ...     print(f"Validation failed: {result.errors}")
        """
        errors: list[str] = []
        warnings: list[str] = []

        # 1. Validate versions.env exists (Requirement 10.1)
        versions_result = self._validate_versions_env()
        errors.extend(versions_result.errors)
        warnings.extend(versions_result.warnings)

        # 2. Check repository paths if requested
        if check_repos and component_manifest_path:
            repos_result = self._validate_repository_paths(component_manifest_path)
            errors.extend(repos_result.errors)
            warnings.extend(repos_result.warnings)

        # 3. Check external dependencies (Requirement 10.5)
        if check_dependencies:
            deps_result = self._validate_external_dependencies()
            errors.extend(deps_result.errors)
            warnings.extend(deps_result.warnings)

        # 4. Check component manifest if requested
        if check_component_manifest and component_manifest_path:
            manifest_result = self._validate_component_manifest(component_manifest_path)
            errors.extend(manifest_result.errors)
            warnings.extend(manifest_result.warnings)

        return ValidationResult(errors=errors, warnings=warnings)

    def _validate_versions_env(self) -> ValidationResult:
        """Validate versions.env file.

        Checks:
        - File exists (Requirement 10.1)
        - All required variables are defined (Requirement 10.2)

        Returns:
            ValidationResult with errors and warnings
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check file exists
        if not self.config_file.exists():
            errors.append(f"Configuration file not found: {self.config_file}")
            return ValidationResult(errors=errors, warnings=warnings)

        # Parse file
        try:
            from opencenter_build.config import parse_versions_env

            versions = parse_versions_env(self.config_file)
        except Exception as exc:
            errors.append(f"Failed to parse {self.config_file}: {exc}")
            return ValidationResult(errors=errors, warnings=warnings)

        # Check required variables (Requirement 10.2)
        missing_vars = [var for var in self.REQUIRED_VARIABLES if var not in versions]
        if missing_vars:
            errors.append(
                f"Missing required variables in {self.config_file}: " f"{', '.join(missing_vars)}"
            )

        # Check for empty values
        empty_vars = [var for var, value in versions.items() if not value.strip()]
        if empty_vars:
            warnings.append(f"Empty values for variables: {', '.join(empty_vars)}")

        return ValidationResult(errors=errors, warnings=warnings)

    def _validate_repository_paths(self, component_manifest_path: Path) -> ValidationResult:
        """Validate repository paths exist.

        Checks that repositories specified in component manifest have been
        cloned to build/ directory (Requirement 10.4).

        Args:
            component_manifest_path: Path to component manifest

        Returns:
            ValidationResult with errors and warnings
        """
        errors: list[str] = []
        warnings: list[str] = []

        if not component_manifest_path.exists():
            # Not an error - component manifest is optional
            return ValidationResult(errors=errors, warnings=warnings)

        try:
            from opencenter_build.component_manifest import read_manifest

            manifest = read_manifest(component_manifest_path)

            # Check each repository
            for repo_spec in manifest.repositories:
                repo_path = Path("build") / repo_spec.name
                if not repo_path.exists():
                    warnings.append(
                        f"Repository not cloned: {repo_path} " f"(from {repo_spec.url})"
                    )
                elif not (repo_path / ".git").exists():
                    warnings.append(f"Directory exists but is not a git repository: {repo_path}")

        except Exception as exc:
            errors.append(f"Failed to validate repository paths: {exc}")

        return ValidationResult(errors=errors, warnings=warnings)

    def _validate_external_dependencies(self) -> ValidationResult:
        """Validate external dependencies are installed.

        Checks:
        - Zarf is installed and accessible (Requirement 10.5)
        - Docker/Podman is installed (optional, warning only)

        Returns:
            ValidationResult with errors and warnings
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check Zarf (required)
        zarf_path = shutil.which("zarf")
        if not zarf_path:
            errors.append(
                "Zarf not found in PATH. Install from: "
                "https://docs.zarf.dev/getting-started/install/"
            )
        else:
            # Try to get Zarf version
            try:
                result = subprocess.run(
                    ["zarf", "version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0:
                    # Version check successful
                    pass
                else:
                    warnings.append(f"Zarf found but version check failed: {result.stderr}")
            except subprocess.TimeoutExpired:
                warnings.append("Zarf version check timed out")
            except Exception as exc:
                warnings.append(f"Failed to check Zarf version: {exc}")

        # Check Docker or Podman (optional, warning only)
        docker_path = shutil.which("docker")
        podman_path = shutil.which("podman")

        if not docker_path and not podman_path:
            warnings.append(
                "Neither Docker nor Podman found in PATH. "
                "Container runtime required for some operations."
            )

        return ValidationResult(errors=errors, warnings=warnings)

    def _validate_component_manifest(self, component_manifest_path: Path) -> ValidationResult:
        """Validate component manifest file.

        Checks that component manifest can be loaded and parsed.

        Args:
            component_manifest_path: Path to component manifest

        Returns:
            ValidationResult with errors and warnings
        """
        errors: list[str] = []
        warnings: list[str] = []

        if not component_manifest_path.exists():
            # Not an error - component manifest is optional
            warnings.append(f"Component manifest not found: {component_manifest_path}")
            return ValidationResult(errors=errors, warnings=warnings)

        try:
            from opencenter_build.component_manifest import read_manifest

            manifest = read_manifest(component_manifest_path)

            # Basic sanity checks
            if not manifest.repositories and not manifest.tools:
                warnings.append("Component manifest has no repositories or tools defined")

        except Exception as exc:
            errors.append(f"Failed to load component manifest: {exc}")

        return ValidationResult(errors=errors, warnings=warnings)

    def validate_versions_env_format(self, versions: dict[str, str]) -> ValidationResult:
        """Validate versions.env format and required variables.

        This method validates a parsed versions.env dictionary rather than
        reading from file. Useful for testing and programmatic validation.

        Args:
            versions: Dictionary of version variables

        Returns:
            ValidationResult with errors and warnings

        Example:
            >>> validator = ComprehensiveConfigValidator()
            >>> versions = {"KUBERNETES_VERSION": "v1.34.3", ...}
            >>> result = validator.validate_versions_env_format(versions)
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check required variables (Requirement 10.2)
        missing_vars = [var for var in self.REQUIRED_VARIABLES if var not in versions]
        if missing_vars:
            errors.append(f"Missing required variables: {', '.join(missing_vars)}")

        # Check for empty values
        empty_vars = [var for var, value in versions.items() if not value.strip()]
        if empty_vars:
            warnings.append(f"Empty values for variables: {', '.join(empty_vars)}")

        return ValidationResult(errors=errors, warnings=warnings)
