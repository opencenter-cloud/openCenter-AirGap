"""Exception hierarchy for openCenter build operations.

This module defines a structured exception hierarchy that provides
context-rich error handling throughout the build system.
"""

from datetime import datetime
from typing import Any, Dict, Optional


class OpenCenterError(Exception):
    """Base exception for all openCenter errors.

    All custom exceptions in the openCenter build system inherit from this
    base class, allowing for broad exception handling when needed.

    Attributes:
        operation: The operation that was being performed when the error occurred
        details: Additional context about the error
        timestamp: When the error occurred
    """

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize exception with context.

        Args:
            message: Human-readable error message
            operation: The operation being performed (e.g., "asset_collection", "state_write")
            details: Additional context as key-value pairs
        """
        super().__init__(message)
        self.operation = operation
        self.details = details or {}
        self.timestamp = datetime.now()

    def __str__(self) -> str:
        """Format error message with context."""
        parts = [super().__str__()]

        if self.operation:
            parts.append(f"Operation: {self.operation}")

        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            parts.append(f"Details: {details_str}")

        parts.append(f"Timestamp: {self.timestamp.isoformat()}")

        return " | ".join(parts)


class BuildError(OpenCenterError):
    """Build operation failed.

    Raised when a build step fails, such as asset collection, package
    creation, or artifact generation.
    """


class AssetCollectionError(BuildError):
    """Asset collection failed.

    Raised when downloading or collecting build assets fails, such as
    Kubernetes binaries, container images, or package repositories.
    """


class PackageError(BuildError):
    """Package creation or manipulation failed.

    Raised when Zarf package operations fail, such as package creation,
    inspection, or deployment.
    """


class ValidationError(OpenCenterError):
    """Configuration validation failed.

    Raised when configuration files fail schema validation or contain
    invalid values.
    """


class StateError(OpenCenterError):
    """State management operation failed.

    Raised when state file operations fail, such as reading, writing,
    or recovering from corruption.
    """


class SecretsError(OpenCenterError):
    """Secrets management operation failed.

    Raised when secret file operations fail, such as missing secrets,
    incorrect permissions, or empty secret files.
    """


class DeploymentError(OpenCenterError):
    """Deployment operation failed.

    Raised when cluster deployment operations fail, such as node
    provisioning, Kubernetes installation, or service deployment.
    """


class NetworkError(OpenCenterError):
    """Network operation failed.

    Raised when network operations fail, such as downloads, API calls,
    or connectivity checks.
    """


class ConfigError(OpenCenterError):
    """Configuration loading or parsing failed.

    Raised when configuration files cannot be loaded, parsed, or contain
    syntax errors.
    """
