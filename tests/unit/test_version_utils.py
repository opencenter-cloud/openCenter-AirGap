"""Unit tests for version utilities."""

import tempfile
from pathlib import Path

import pytest

from opencenter_build.exceptions import ValidationError
from opencenter_build.version_utils import (
    VersionParser,
    VersionType,
    VersionValidator,
    add_version_prefix,
    compare_versions,
    parse_version_components,
    strip_version_prefix,
    validate_commit_sha,
    validate_kubernetes_version,
    validate_semver,
)


def test_validate_semver_valid() -> None:
    """Test semver validation with valid versions."""
    assert validate_semver("1.21.0")
    assert validate_semver("0.0.1")
    assert validate_semver("1.21.0-rc.1")
    assert validate_semver("1.21.0+build.123")
    assert validate_semver("1.21.0-rc.1+build.123")


def test_validate_semver_invalid() -> None:
    """Test semver validation with invalid versions."""
    assert not validate_semver("v1.21.0")
    assert not validate_semver("1.21")
    assert not validate_semver("1.21.0.0")
    assert not validate_semver("")
    assert not validate_semver("invalid")


def test_validate_kubernetes_version_valid() -> None:
    """Test Kubernetes version validation with valid versions."""
    assert validate_kubernetes_version("v1.34.3")
    assert validate_kubernetes_version("v1.21.0")
    assert validate_kubernetes_version("v0.1.0")


def test_validate_kubernetes_version_invalid() -> None:
    """Test Kubernetes version validation with invalid versions."""
    assert not validate_kubernetes_version("1.34.3")
    assert not validate_kubernetes_version("v1.34")
    assert not validate_kubernetes_version("v1.34.3-rc1")
    assert not validate_kubernetes_version("")


def test_validate_commit_sha_valid() -> None:
    """Test commit SHA validation with valid SHAs."""
    assert validate_commit_sha("a" * 40)
    assert validate_commit_sha("0123456789abcdef" * 2 + "01234567")
    assert validate_commit_sha("ABCDEF0123456789" * 2 + "ABCDEF01")


def test_validate_commit_sha_invalid() -> None:
    """Test commit SHA validation with invalid SHAs."""
    assert not validate_commit_sha("a" * 39)
    assert not validate_commit_sha("a" * 41)
    assert not validate_commit_sha("g" * 40)
    assert not validate_commit_sha("")


def test_parse_version_components_valid() -> None:
    """Test version component parsing with valid versions."""
    assert parse_version_components("v1.34.3") == (1, 34, 3)
    assert parse_version_components("1.21.0") == (1, 21, 0)
    assert parse_version_components("2.5.1-rc.1") == (2, 5, 1)
    assert parse_version_components("v0.0.1") == (0, 0, 1)


def test_parse_version_components_invalid() -> None:
    """Test version component parsing with invalid versions."""
    with pytest.raises(ValidationError):
        parse_version_components("invalid")

    with pytest.raises(ValidationError):
        parse_version_components("1.2")

    with pytest.raises(ValidationError):
        parse_version_components("")


def test_compare_versions() -> None:
    """Test version comparison."""
    assert compare_versions("v1.34.3", "v1.34.2") == 1
    assert compare_versions("v1.34.2", "v1.34.3") == -1
    assert compare_versions("v1.34.3", "v1.34.3") == 0
    assert compare_versions("1.21.0", "1.21.0") == 0
    assert compare_versions("v2.0.0", "v1.99.99") == 1
    assert compare_versions("v1.0.1", "v1.0.0") == 1


def test_strip_version_prefix() -> None:
    """Test version prefix stripping."""
    assert strip_version_prefix("v1.34.3") == "1.34.3"
    assert strip_version_prefix("1.34.3") == "1.34.3"
    assert strip_version_prefix("vvv1.34.3") == "1.34.3"


def test_add_version_prefix() -> None:
    """Test version prefix addition."""
    assert add_version_prefix("1.34.3") == "v1.34.3"
    assert add_version_prefix("v1.34.3") == "v1.34.3"


class TestVersionParser:
    """Test VersionParser class."""

    def test_classify_version_pinned(self):
        """Test classification of pinned versions."""
        assert VersionParser.classify_version("v1.34.3") == VersionType.PINNED
        assert VersionParser.classify_version("1.21.0") == VersionType.PINNED
        assert VersionParser.classify_version("2.5.1") == VersionType.PINNED

    def test_classify_version_commit_sha(self):
        """Test classification of commit SHAs."""
        sha = "a" * 40
        assert VersionParser.classify_version(sha) == VersionType.COMMIT_SHA

    def test_classify_version_mutable(self):
        """Test classification of mutable references."""
        assert VersionParser.classify_version("master") == VersionType.MUTABLE
        assert VersionParser.classify_version("main") == VersionType.MUTABLE
        assert VersionParser.classify_version("latest") == VersionType.MUTABLE
        assert VersionParser.classify_version("stable") == VersionType.MUTABLE

    def test_classify_version_unknown(self):
        """Test classification of unknown versions."""
        assert VersionParser.classify_version("") == VersionType.UNKNOWN
        assert VersionParser.classify_version("invalid") == VersionType.UNKNOWN

    def test_parse_env_file(self, tmp_path):
        """Test parsing environment file."""
        env_file = tmp_path / "versions.env"
        env_file.write_text(
            """
KUBERNETES_VERSION=v1.34.3
TERRAFORM_VERSION=1.6.6
KUBESPRAY_VERSION=master
"""
        )

        specs = VersionParser.parse_env_file(env_file)

        assert len(specs) == 3
        assert specs[0].variable_name == "KUBERNETES_VERSION"
        assert specs[0].value == "v1.34.3"
        assert specs[0].version_type == VersionType.PINNED

    def test_parse_env_file_not_found(self, tmp_path):
        """Test error when file doesn't exist."""
        env_file = tmp_path / "nonexistent.env"

        with pytest.raises(ValidationError):
            VersionParser.parse_env_file(env_file)


class TestVersionValidator:
    """Test VersionValidator class."""

    def test_validate_file(self, tmp_path):
        """Test validating a file."""
        env_file = tmp_path / "versions.env"
        env_file.write_text(
            """
KUBERNETES_VERSION=v1.34.3
TERRAFORM_VERSION=1.6.6
"""
        )

        validator = VersionValidator()
        result = validator.validate_file(env_file)

        assert result is True
        assert len(validator.errors) == 0

    def test_validate_file_with_mutable_refs(self, tmp_path):
        """Test validation fails with mutable references."""
        env_file = tmp_path / "versions.env"
        env_file.write_text(
            """
KUBERNETES_VERSION=v1.34.3
KUBESPRAY_VERSION=master
"""
        )

        validator = VersionValidator()
        result = validator.validate_file(env_file)

        assert result is False
        assert len(validator.errors) > 0

    def test_get_report(self, tmp_path):
        """Test getting validation report."""
        env_file = tmp_path / "versions.env"
        env_file.write_text(
            """
KUBERNETES_VERSION=v1.34.3
KUBESPRAY_VERSION=master
"""
        )

        validator = VersionValidator()
        validator.validate_file(env_file)

        report = validator.get_report()

        assert "KUBESPRAY_VERSION" in report
        assert "master" in report
