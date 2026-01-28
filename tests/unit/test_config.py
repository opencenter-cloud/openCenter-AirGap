"""Unit tests for configuration loading module."""

import tempfile
from pathlib import Path

import pytest

from opencenter_build.config import load_yaml_config, parse_versions_env
from opencenter_build.exceptions import ConfigError


class TestParseVersionsEnv:
    """Test parsing versions.env files."""

    def test_parse_valid_versions_env(self, tmp_path):
        """Test parsing valid versions.env file."""
        versions_file = tmp_path / "versions.env"
        versions_file.write_text(
            """
# Kubernetes versions
KUBERNETES_VERSION=v1.34.3
TERRAFORM_VERSION=1.6.6

# Container runtime
CONTAINER_RUNTIME=runc
RUNC_VERSION=1.3.4
"""
        )

        versions = parse_versions_env(versions_file)

        assert versions["KUBERNETES_VERSION"] == "v1.34.3"
        assert versions["TERRAFORM_VERSION"] == "1.6.6"
        assert versions["CONTAINER_RUNTIME"] == "runc"
        assert versions["RUNC_VERSION"] == "1.3.4"

    def test_parse_versions_env_with_quotes(self, tmp_path):
        """Test parsing versions with quotes."""
        versions_file = tmp_path / "versions.env"
        versions_file.write_text(
            """
KUBERNETES_VERSION="v1.34.3"
TERRAFORM_VERSION='1.6.6'
"""
        )

        versions = parse_versions_env(versions_file)

        assert versions["KUBERNETES_VERSION"] == "v1.34.3"
        assert versions["TERRAFORM_VERSION"] == "1.6.6"

    def test_parse_versions_env_ignores_comments(self, tmp_path):
        """Test that comments are ignored."""
        versions_file = tmp_path / "versions.env"
        versions_file.write_text(
            """
# This is a comment
KUBERNETES_VERSION=v1.34.3
# Another comment
# COMMENTED_OUT=value
TERRAFORM_VERSION=1.6.6
"""
        )

        versions = parse_versions_env(versions_file)

        assert "KUBERNETES_VERSION" in versions
        assert "TERRAFORM_VERSION" in versions
        assert "COMMENTED_OUT" not in versions

    def test_parse_versions_env_ignores_empty_lines(self, tmp_path):
        """Test that empty lines are ignored."""
        versions_file = tmp_path / "versions.env"
        versions_file.write_text(
            """

KUBERNETES_VERSION=v1.34.3


TERRAFORM_VERSION=1.6.6

"""
        )

        versions = parse_versions_env(versions_file)

        assert len(versions) == 2

    def test_parse_versions_env_file_not_found(self, tmp_path):
        """Test error when file doesn't exist."""
        versions_file = tmp_path / "nonexistent.env"

        with pytest.raises(ConfigError):
            parse_versions_env(versions_file)


class TestLoadYamlConfig:
    """Test loading YAML configuration files."""

    def test_load_valid_yaml(self, tmp_path):
        """Test loading valid YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
control_plane:
  - hostname: master-1
    ip: 192.168.1.10
workers:
  - hostname: worker-1
    ip: 192.168.1.20
"""
        )

        config = load_yaml_config(config_file)

        assert "control_plane" in config
        assert "workers" in config
        assert len(config["control_plane"]) == 1
        assert config["control_plane"][0]["hostname"] == "master-1"

    def test_load_yaml_file_not_found(self, tmp_path):
        """Test error when YAML file doesn't exist."""
        config_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(ConfigError):
            load_yaml_config(config_file)

    def test_load_invalid_yaml(self, tmp_path):
        """Test error with invalid YAML syntax."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text(
            """
invalid: yaml: syntax:
  - missing
    proper: indentation
"""
        )

        with pytest.raises(ConfigError):
            load_yaml_config(config_file)

    def test_load_yaml_with_comments(self, tmp_path):
        """Test loading YAML with comments."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
# Configuration file
control_plane:
  # Master nodes
  - hostname: master-1
    ip: 192.168.1.10
"""
        )

        config = load_yaml_config(config_file)

        assert "control_plane" in config
        assert len(config["control_plane"]) == 1

    def test_load_yaml_with_nested_structure(self, tmp_path):
        """Test loading YAML with nested structures."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
cluster:
  name: production
  nodes:
    control_plane:
      count: 3
    workers:
      count: 5
"""
        )

        config = load_yaml_config(config_file)

        assert config["cluster"]["name"] == "production"
        assert config["cluster"]["nodes"]["control_plane"]["count"] == 3
        assert config["cluster"]["nodes"]["workers"]["count"] == 5
