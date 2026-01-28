"""Unit tests for exception hierarchy.

Tests exception hierarchy, error chaining, and error context.
"""

import time
from datetime import datetime

import pytest

from opencenter_build.exceptions import (
    AssetCollectionError,
    BuildError,
    ConfigError,
    DeploymentError,
    NetworkError,
    OpenCenterError,
    PackageError,
    SecretsError,
    StateError,
    ValidationError,
)


class TestExceptionHierarchy:
    """Test exception inheritance and hierarchy."""

    def test_all_exceptions_inherit_from_base(self) -> None:
        """All custom exceptions inherit from OpenCenterError."""
        exceptions = [
            BuildError,
            AssetCollectionError,
            PackageError,
            ValidationError,
            StateError,
            SecretsError,
            DeploymentError,
            NetworkError,
            ConfigError,
        ]

        for exc_class in exceptions:
            assert issubclass(exc_class, OpenCenterError)
            assert issubclass(exc_class, Exception)

    def test_build_error_hierarchy(self) -> None:
        """Build-related exceptions inherit from BuildError."""
        assert issubclass(AssetCollectionError, BuildError)
        assert issubclass(PackageError, BuildError)

    def test_exception_can_be_caught_by_base(self) -> None:
        """Specific exceptions can be caught by base class."""
        with pytest.raises(OpenCenterError):
            raise ValidationError("Test error")

        with pytest.raises(BuildError):
            raise AssetCollectionError("Test error")


class TestErrorContext:
    """Test error context attributes."""

    def test_basic_error_message(self) -> None:
        """Exception can be created with just a message."""
        error = OpenCenterError("Something went wrong")
        assert str(error).startswith("Something went wrong")
        assert error.operation is None
        assert error.details == {}
        assert isinstance(error.timestamp, datetime)

    def test_error_with_operation(self) -> None:
        """Exception includes operation context."""
        error = OpenCenterError("Failed to collect assets", operation="asset_collection")
        error_str = str(error)
        assert "Failed to collect assets" in error_str
        assert "Operation: asset_collection" in error_str

    def test_error_with_details(self) -> None:
        """Exception includes detail context."""
        error = OpenCenterError(
            "Download failed",
            operation="download",
            details={"url": "https://example.com", "status_code": 404},
        )
        error_str = str(error)
        assert "Download failed" in error_str
        assert "Operation: download" in error_str
        assert "url=https://example.com" in error_str
        assert "status_code=404" in error_str

    def test_error_timestamp_captured(self) -> None:
        """Exception captures timestamp when created."""
        before = datetime.now()
        time.sleep(0.001)  # Ensure time passes
        error = OpenCenterError("Test error")
        time.sleep(0.001)
        after = datetime.now()

        assert before < error.timestamp < after
        assert error.timestamp.isoformat() in str(error)

    def test_error_details_empty_by_default(self) -> None:
        """Exception details default to empty dict."""
        error = OpenCenterError("Test error")
        assert error.details == {}
        assert isinstance(error.details, dict)

    def test_error_context_preserved_in_subclasses(self) -> None:
        """Subclass exceptions preserve context attributes."""
        error = ValidationError(
            "Invalid config",
            operation="config_validation",
            details={"field": "KUBERNETES_VERSION", "value": "invalid"},
        )

        assert error.operation == "config_validation"
        assert error.details["field"] == "KUBERNETES_VERSION"
        assert error.details["value"] == "invalid"
        assert isinstance(error.timestamp, datetime)


class TestErrorChaining:
    """Test exception chaining with 'from' clause."""

    def test_error_chaining_preserves_cause(self) -> None:
        """Exception chaining preserves original exception."""
        original = ValueError("Original error")

        try:
            try:
                raise original
            except ValueError as e:
                raise ValidationError("Validation failed") from e
        except ValidationError as caught:
            assert caught.__cause__ is original
            assert isinstance(caught.__cause__, ValueError)
            assert str(caught.__cause__) == "Original error"

    def test_error_chaining_with_context(self) -> None:
        """Exception chaining works with context attributes."""
        original = IOError("File not found")

        try:
            try:
                raise original
            except IOError as e:
                raise StateError(
                    "Failed to read state",
                    operation="state_read",
                    details={"file": "/path/to/state.json"},
                ) from e
        except StateError as caught:
            assert caught.__cause__ is original
            assert caught.operation == "state_read"
            assert caught.details["file"] == "/path/to/state.json"

    def test_nested_error_chaining(self) -> None:
        """Multiple levels of exception chaining work correctly."""
        level1 = IOError("Disk error")
        level2 = StateError("State read failed")
        level3 = BuildError("Build failed")

        try:
            try:
                try:
                    raise level1
                except IOError as e:
                    raise level2 from e
            except StateError as e:
                raise level3 from e
        except BuildError as caught:
            assert caught.__cause__ is level2
            assert caught.__cause__.__cause__ is level1


class TestSpecificExceptions:
    """Test specific exception types."""

    def test_build_error(self) -> None:
        """BuildError can be raised with context."""
        error = BuildError(
            "Build step failed",
            operation="build_package",
            details={"step": "zarf_create", "exit_code": 1},
        )
        assert "Build step failed" in str(error)
        assert error.operation == "build_package"

    def test_asset_collection_error(self) -> None:
        """AssetCollectionError can be raised with context."""
        error = AssetCollectionError(
            "Failed to download asset",
            operation="download_kubespray",
            details={"url": "https://github.com/...", "error": "timeout"},
        )
        assert "Failed to download asset" in str(error)
        assert isinstance(error, BuildError)

    def test_package_error(self) -> None:
        """PackageError can be raised with context."""
        error = PackageError(
            "Zarf package creation failed",
            operation="zarf_create",
            details={"package": "opencenter-airgap", "size_mb": 8192},
        )
        assert "Zarf package creation failed" in str(error)
        assert isinstance(error, BuildError)

    def test_validation_error(self) -> None:
        """ValidationError can be raised with context."""
        error = ValidationError(
            "Schema validation failed",
            operation="validate_versions",
            details={"schema": "versions.schema.json", "field": "KUBERNETES_VERSION"},
        )
        assert "Schema validation failed" in str(error)

    def test_state_error(self) -> None:
        """StateError can be raised with context."""
        error = StateError(
            "State file corrupted",
            operation="state_read",
            details={"file": ".build-state.json", "error": "invalid JSON"},
        )
        assert "State file corrupted" in str(error)

    def test_secrets_error(self) -> None:
        """SecretsError can be raised with context."""
        error = SecretsError(
            "Secret file has insecure permissions",
            operation="read_secret",
            details={"file": ".secrets/github-token", "permissions": "0644"},
        )
        assert "Secret file has insecure permissions" in str(error)

    def test_deployment_error(self) -> None:
        """DeploymentError can be raised with context."""
        error = DeploymentError(
            "Cluster deployment failed",
            operation="deploy_kubernetes",
            details={"node": "control-plane-1", "phase": "kubelet_start"},
        )
        assert "Cluster deployment failed" in str(error)

    def test_network_error(self) -> None:
        """NetworkError can be raised with context."""
        error = NetworkError(
            "Connection timeout",
            operation="download_image",
            details={"url": "https://registry.k8s.io", "timeout_seconds": 30},
        )
        assert "Connection timeout" in str(error)

    def test_config_error(self) -> None:
        """ConfigError can be raised with context."""
        error = ConfigError(
            "Failed to parse config file",
            operation="load_config",
            details={"file": "versions.env", "line": 42},
        )
        assert "Failed to parse config file" in str(error)


class TestErrorMessages:
    """Test error message formatting."""

    def test_error_message_includes_all_context(self) -> None:
        """Error message includes all context information."""
        error = ValidationError(
            "Invalid configuration",
            operation="validate_config",
            details={"file": "versions.env", "field": "KUBERNETES_VERSION"},
        )

        error_str = str(error)
        assert "Invalid configuration" in error_str
        assert "Operation: validate_config" in error_str
        assert "file=versions.env" in error_str
        assert "field=KUBERNETES_VERSION" in error_str
        assert "Timestamp:" in error_str

    def test_error_message_without_operation(self) -> None:
        """Error message works without operation."""
        error = OpenCenterError("Simple error", details={"key": "value"})
        error_str = str(error)
        assert "Simple error" in error_str
        assert "Operation:" not in error_str
        assert "key=value" in error_str

    def test_error_message_without_details(self) -> None:
        """Error message works without details."""
        error = OpenCenterError("Simple error", operation="test_operation")
        error_str = str(error)
        assert "Simple error" in error_str
        assert "Operation: test_operation" in error_str
        assert "Details:" not in error_str

    def test_error_message_minimal(self) -> None:
        """Error message works with just message."""
        error = OpenCenterError("Minimal error")
        error_str = str(error)
        assert "Minimal error" in error_str
        assert "Timestamp:" in error_str


class TestErrorUsagePatterns:
    """Test common error usage patterns."""

    def test_catch_specific_then_reraise_as_general(self) -> None:
        """Catch specific error and reraise as more general error."""
        try:
            try:
                raise IOError("File not found: /path/to/file")
            except IOError as e:
                raise StateError(
                    "Failed to load state",
                    operation="state_load",
                    details={"path": "/path/to/file"},
                ) from e
        except StateError as caught:
            assert "Failed to load state" in str(caught)
            assert isinstance(caught.__cause__, IOError)

    def test_catch_by_category(self) -> None:
        """Catch errors by category (BuildError catches AssetCollectionError)."""
        try:
            raise AssetCollectionError("Download failed")
        except BuildError as caught:
            assert isinstance(caught, AssetCollectionError)
            assert isinstance(caught, BuildError)

    def test_catch_all_opencenter_errors(self) -> None:
        """Catch all openCenter errors with base class."""
        errors_to_test = [
            ValidationError("test"),
            StateError("test"),
            BuildError("test"),
            DeploymentError("test"),
        ]

        for error in errors_to_test:
            try:
                raise error
            except OpenCenterError as caught:
                assert isinstance(caught, OpenCenterError)
