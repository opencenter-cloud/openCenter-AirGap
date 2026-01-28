"""Version validation and comparison utilities.

This module provides functions for validating version strings and
comparing semantic versions.
"""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from opencenter_build.exceptions import ValidationError


class VersionType(Enum):
    """Types of version specifications."""

    PINNED = "pinned"  # Exact version: v1.34.3, 1.6.6
    COMMIT_SHA = "commit_sha"  # Git commit SHA: abc123...
    MUTABLE = "mutable"  # Mutable reference: master, main, latest
    UNKNOWN = "unknown"  # Cannot determine type


@dataclass
class VersionSpec:
    """Represents a version specification found in a file."""

    file_path: str
    line_number: int
    variable_name: str
    value: str
    version_type: VersionType


class VersionParser:
    """Parse and classify version specifications."""

    @staticmethod
    def classify_version(value: str) -> VersionType:
        """Classify version string by type.

        Args:
            value: Version string to classify

        Returns:
            VersionType enum value

        Example:
            >>> VersionParser.classify_version("v1.34.3")
            <VersionType.PINNED: 'pinned'>
            >>> VersionParser.classify_version("master")
            <VersionType.MUTABLE: 'mutable'>
        """
        if not value or not value.strip():
            return VersionType.UNKNOWN

        value = value.strip()

        # Check for commit SHA (40 hex chars)
        if validate_commit_sha(value):
            return VersionType.COMMIT_SHA

        # Check for mutable references
        mutable_refs = {"master", "main", "latest", "stable", "edge", "dev", "develop"}
        if value.lower() in mutable_refs:
            return VersionType.MUTABLE

        # Check for semantic version (with or without 'v' prefix)
        if validate_semver(value.lstrip("v")):
            return VersionType.PINNED

        # Check for Kubernetes version
        if validate_kubernetes_version(value):
            return VersionType.PINNED

        return VersionType.UNKNOWN

    @staticmethod
    def parse_env_file(file_path: Path) -> list[VersionSpec]:
        """Parse version specifications from shell environment file.

        Args:
            file_path: Path to .env or versions.env file

        Returns:
            List of VersionSpec objects

        Raises:
            ValidationError: If file cannot be read

        Example:
            >>> specs = VersionParser.parse_env_file(Path("config/versions.env"))
            >>> for spec in specs:
            ...     print(f"{spec.variable_name}={spec.value}")
        """
        if not file_path.exists():
            raise ValidationError(f"File not found: {file_path}")

        specs: list[VersionSpec] = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()

                    # Skip comments and empty lines
                    if not line or line.startswith("#"):
                        continue

                    # Parse VAR=value format
                    if "=" in line:
                        var_name, value = line.split("=", 1)
                        var_name = var_name.strip()
                        value = value.strip().strip('"').strip("'")

                        version_type = VersionParser.classify_version(value)

                        specs.append(
                            VersionSpec(
                                file_path=str(file_path),
                                line_number=line_num,
                                variable_name=var_name,
                                value=value,
                                version_type=version_type,
                            )
                        )
        except Exception as exc:
            raise ValidationError(f"Failed to parse {file_path}: {exc}") from exc

        return specs


class VersionValidator:
    """Validate version pinning across configuration files."""

    def __init__(self, allow_mutable: bool = False):
        """Initialize validator.

        Args:
            allow_mutable: If True, allow mutable version references (default False)
        """
        self.allow_mutable = allow_mutable
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate_spec(self, spec: VersionSpec) -> bool:
        """Validate a single version specification.

        Args:
            spec: VersionSpec to validate

        Returns:
            True if valid, False otherwise (errors added to self.errors)

        Example:
            >>> validator = VersionValidator()
            >>> spec = VersionSpec(
            ...     file_path="config/versions.env",
            ...     line_number=10,
            ...     variable_name="KUBERNETES_VERSION",
            ...     value="master",
            ...     version_type=VersionType.MUTABLE
            ... )
            >>> validator.validate_spec(spec)
            False
        """
        if spec.version_type == VersionType.UNKNOWN:
            self.errors.append(
                f"{spec.file_path}:{spec.line_number} - "
                f"Unknown version format for {spec.variable_name}={spec.value}"
            )
            return False

        if spec.version_type == VersionType.MUTABLE and not self.allow_mutable:
            self.errors.append(
                f"{spec.file_path}:{spec.line_number} - "
                f"Mutable version reference not allowed: {spec.variable_name}={spec.value}"
            )
            return False

        if spec.version_type == VersionType.MUTABLE and self.allow_mutable:
            self.warnings.append(
                f"{spec.file_path}:{spec.line_number} - "
                f"Mutable version reference: {spec.variable_name}={spec.value}"
            )

        return True

    def validate_file(self, file_path: Path) -> bool:
        """Validate all version specifications in a file.

        Args:
            file_path: Path to configuration file

        Returns:
            True if all specs valid, False otherwise

        Example:
            >>> validator = VersionValidator()
            >>> validator.validate_file(Path("config/versions.env"))
            True
        """
        try:
            specs = VersionParser.parse_env_file(file_path)
            all_valid = True

            for spec in specs:
                if not self.validate_spec(spec):
                    all_valid = False

            return all_valid
        except ValidationError as exc:
            self.errors.append(str(exc))
            return False

    def get_report(self) -> str:
        """Generate validation report.

        Returns:
            Formatted report string with errors and warnings

        Example:
            >>> validator = VersionValidator()
            >>> validator.validate_file(Path("config/versions.env"))
            >>> print(validator.get_report())
        """
        lines = []

        if self.errors:
            lines.append("ERRORS:")
            for error in self.errors:
                lines.append(f"  - {error}")

        if self.warnings:
            if lines:
                lines.append("")
            lines.append("WARNINGS:")
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        if not lines:
            lines.append("All version specifications valid.")

        return "\n".join(lines)


def validate_semver(version: str) -> bool:
    """Validate semantic version format.

    Checks if version string follows semantic versioning (semver) format:
    MAJOR.MINOR.PATCH with optional pre-release and build metadata.

    Args:
        version: Version string to validate

    Returns:
        True if valid semver, False otherwise

    Example:
        >>> validate_semver("1.21.0")
        True
        >>> validate_semver("v1.21.0")
        False
        >>> validate_semver("1.21.0-rc.1")
        True
    """
    # Semver pattern: MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
    pattern = (
        r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
        r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
        r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
        r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
    )
    return bool(re.match(pattern, version))


def validate_kubernetes_version(version: str) -> bool:
    """Validate Kubernetes version format.

    Kubernetes versions follow the format: vMAJOR.MINOR.PATCH

    Args:
        version: Version string to validate (e.g., "v1.34.3")

    Returns:
        True if valid Kubernetes version, False otherwise

    Example:
        >>> validate_kubernetes_version("v1.34.3")
        True
        >>> validate_kubernetes_version("1.34.3")
        False
    """
    pattern = r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"
    return bool(re.match(pattern, version))


def validate_commit_sha(sha: str) -> bool:
    """Validate Git commit SHA format.

    Checks if string is a valid 40-character hexadecimal Git commit SHA.

    Args:
        sha: Commit SHA string to validate

    Returns:
        True if valid commit SHA, False otherwise

    Example:
        >>> validate_commit_sha("a" * 40)
        True
        >>> validate_commit_sha("invalid")
        False
    """
    pattern = r"^[0-9a-f]{40}$"
    return bool(re.match(pattern, sha.lower()))


def parse_version_components(version: str) -> tuple[int, int, int]:
    """Parse version string into major, minor, patch components.

    Handles both semver (1.21.0) and Kubernetes (v1.21.0) formats.

    Args:
        version: Version string to parse

    Returns:
        Tuple of (major, minor, patch) as integers

    Raises:
        ValidationError: If version format is invalid

    Example:
        >>> parse_version_components("v1.34.3")
        (1, 34, 3)
        >>> parse_version_components("2.5.1")
        (2, 5, 1)
    """
    # Remove 'v' prefix if present
    version = version.lstrip("v")

    # Extract MAJOR.MINOR.PATCH (ignore pre-release and build metadata)
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise ValidationError(f"Invalid version format: {version}")

    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def compare_versions(version1: str, version2: str) -> int:
    """Compare two semantic versions.

    Args:
        version1: First version string
        version2: Second version string

    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2

    Raises:
        ValidationError: If either version is invalid

    Example:
        >>> compare_versions("v1.34.3", "v1.34.2")
        1
        >>> compare_versions("1.21.0", "1.21.0")
        0
        >>> compare_versions("v1.20.0", "v1.21.0")
        -1
    """
    v1_parts = parse_version_components(version1)
    v2_parts = parse_version_components(version2)

    if v1_parts < v2_parts:
        return -1
    if v1_parts > v2_parts:
        return 1
    return 0


def strip_version_prefix(version: str) -> str:
    """Remove 'v' prefix from version string if present.

    Args:
        version: Version string

    Returns:
        Version string without 'v' prefix

    Example:
        >>> strip_version_prefix("v1.34.3")
        '1.34.3'
        >>> strip_version_prefix("1.34.3")
        '1.34.3'
    """
    return version.lstrip("v")


def add_version_prefix(version: str) -> str:
    """Add 'v' prefix to version string if not present.

    Args:
        version: Version string

    Returns:
        Version string with 'v' prefix

    Example:
        >>> add_version_prefix("1.34.3")
        'v1.34.3'
        >>> add_version_prefix("v1.34.3")
        'v1.34.3'
    """
    if version.startswith("v"):
        return version
    return f"v{version}"
