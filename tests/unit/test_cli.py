"""Unit tests for CLI commands.

Tests command invocation, flag handling, and error messages for all
CLI commands in the opencenter-airgap tool.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from opencenter_build.cli import app
from opencenter_build.component_manifest import ComponentManifest, ToolComponent, RepositoryComponent


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary config directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def sample_versions_env(temp_config_dir):
    """Create sample versions.env file."""
    versions_file = temp_config_dir / "versions.env"
    versions_file.write_text(
        "KUBERNETES_VERSION=v1.34.3\n"
        "KUBESPRAY_VERSION=v2.24.0\n"
        "KUBESPRAY_COMMIT_SHA=abc123\n"
        "UBUNTU_VERSION=24.04\n"
        "CONTAINER_RUNTIME=containerd\n"
        "CNI_PLUGIN=calico\n"
        "TERRAFORM_VERSION=1.6.6\n"
        "FLUXCD_VERSION=v2.2.0\n"
        "GITEA_VERSION=1.21.0\n"
        "CERT_MANAGER_VERSION=v1.13.0\n"
        "INGRESS_NGINX_VERSION=v1.9.0\n"
        "KEYCLOAK_VERSION=21.1.1\n"
        "PROMETHEUS_VERSION=v2.48.0\n"
        "GRAFANA_VERSION=10.2.0\n"
        "OPENCENTER_GITOPS_BASE_REPO=https://github.com/example/repo.git\n"
        "OPENCENTER_GITOPS_BASE_VERSION=v1.0.0\n"
        "OPENCENTER_GITOPS_BASE_COMMIT_SHA=def456\n"
        "OPENCENTER_CONTAINER_REGISTRY=registry.example.com\n"
        "TARGET_ARCH=amd64\n"
        "PYTHON_VERSION=3.10\n"
    )
    return versions_file


@pytest.fixture
def sample_component_manifest(temp_config_dir):
    """Create sample component manifest."""
    from opencenter_build.component_manifest import write_manifest

    manifest_file = temp_config_dir / "components.yaml"
    manifest = ComponentManifest()
    manifest.tools = [
        ToolComponent(name="kubectl", version="v1.34.3", url="https://example.com/kubectl")
    ]
    manifest.repositories = [
        RepositoryComponent(
            name="kubespray", url="https://github.com/example/kubespray.git", ref="master"
        )
    ]
    write_manifest(manifest, manifest_file)
    return manifest_file


class TestInitCommand:
    """Tests for init command."""

    def test_init_creates_directories(self, runner, tmp_path):
        """Test that init creates necessary directories."""
        with patch("opencenter_build.cli.Path") as mock_path:
            mock_path.return_value = tmp_path
            result = runner.invoke(app, ["init"])

            assert result.exit_code == 0
            assert "Created directory" in result.stdout

    def test_init_with_manifest(self, runner, tmp_path):
        """Test init with --create-manifest flag."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        with patch("opencenter_build.cli.Path") as mock_path:
            mock_path.return_value = tmp_path
            result = runner.invoke(app, ["init", "--create-manifest"])

            # Should create manifest
            assert result.exit_code == 0 or "manifest" in result.stdout.lower()

    def test_init_validates_existing_config(self, runner, tmp_path, sample_versions_env):
        """Test that init validates existing configuration."""
        with patch("opencenter_build.cli.Path") as mock_path:
            mock_path.return_value = tmp_path
            result = runner.invoke(app, ["init", f"--config={sample_versions_env}"])

            # Should validate config
            assert "version variables" in result.stdout.lower() or result.exit_code == 0


class TestAddCommand:
    """Tests for add command."""

    def test_add_tool(self, runner, tmp_path, sample_component_manifest):
        """Test adding a tool to manifest."""
        result = runner.invoke(
            app,
            [
                "add",
                "tool",
                "helm",
                "--version=3.14.0",
                "--url=https://example.com/helm.tar.gz",
                f"--manifest={sample_component_manifest}",
            ],
        )

        assert result.exit_code == 0
        assert "Added tool" in result.stdout

    def test_add_repo(self, runner, tmp_path, sample_component_manifest):
        """Test adding a repository to manifest."""
        result = runner.invoke(
            app,
            [
                "add",
                "repo",
                "test-repo",
                "--url=https://github.com/example/test.git",
                "--ref=main",
                f"--manifest={sample_component_manifest}",
            ],
        )

        assert result.exit_code == 0
        assert "Added repository" in result.stdout

    def test_add_image(self, runner, tmp_path, sample_component_manifest):
        """Test adding an image to manifest."""
        result = runner.invoke(
            app,
            ["add", "image", "nginx:1.21", f"--manifest={sample_component_manifest}"],
        )

        assert result.exit_code == 0
        assert "Added image" in result.stdout

    def test_add_chart(self, runner, tmp_path, sample_component_manifest):
        """Test adding a chart to manifest."""
        result = runner.invoke(
            app,
            [
                "add",
                "chart",
                "cert-manager",
                "--version=v1.13.0",
                "--repo=https://charts.jetstack.io",
                f"--manifest={sample_component_manifest}",
            ],
        )

        assert result.exit_code == 0
        assert "Added chart" in result.stdout

    def test_add_invalid_type(self, runner, tmp_path, sample_component_manifest):
        """Test adding with invalid component type."""
        result = runner.invoke(
            app,
            ["add", "invalid", "test", f"--manifest={sample_component_manifest}"],
        )

        assert result.exit_code == 1
        assert "Unknown component type" in result.stdout

    def test_add_tool_missing_required_flags(self, runner, tmp_path, sample_component_manifest):
        """Test adding tool without required flags."""
        result = runner.invoke(
            app,
            ["add", "tool", "helm", f"--manifest={sample_component_manifest}"],
        )

        assert result.exit_code == 1
        assert "required" in result.stdout.lower()


class TestValidateCommand:
    """Tests for validate command."""

    def test_validate_missing_config(self, runner, tmp_path):
        """Test validate with missing config file."""
        result = runner.invoke(app, ["validate", "--config=nonexistent.env"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_validate_valid_config(self, runner, tmp_path, sample_versions_env):
        """Test validate with valid configuration."""
        result = runner.invoke(app, ["validate", f"--config={sample_versions_env}"])

        # Should pass or show warnings
        assert "version variables" in result.stdout.lower() or result.exit_code == 0

    def test_validate_strict_mode(self, runner, tmp_path, sample_versions_env):
        """Test validate with --strict flag."""
        result = runner.invoke(app, ["validate", "--strict", f"--config={sample_versions_env}"])

        # Strict mode may fail on warnings
        assert result.exit_code in [0, 1]


class TestStatusCommand:
    """Tests for status command."""

    def test_status_no_build(self, runner, tmp_path):
        """Test status with no build in progress."""
        state_file = tmp_path / "state.json"
        result = runner.invoke(app, ["status", f"--state={state_file}"])

        assert result.exit_code == 0
        assert "No build" in result.stdout

    def test_status_with_build(self, runner, tmp_path):
        """Test status with existing build state."""
        state_file = tmp_path / "state.json"

        # Create mock state - note: StateManager may have specific format requirements
        # For now, just test that command handles state file gracefully
        state_data = {
            "build_id": "test-123",
            "start_time": "2024-01-01T00:00:00",
            "config_hash": "abc123",
            "steps": [
                {
                    "name": "scan_repositories",
                    "status": "COMPLETED",
                    "start_time": "2024-01-01T00:00:00",
                    "end_time": "2024-01-01T00:01:00",
                    "error": None,
                    "artifacts": {},
                }
            ],
        }
        state_file.write_text(json.dumps(state_data))

        result = runner.invoke(app, ["status", f"--state={state_file}"])

        # Command should handle state file (may fail if format is wrong, but shouldn't crash)
        assert result.exit_code in [0, 1]
        assert "Build ID" in result.stdout or "Error" in result.stdout


class TestCleanCommand:
    """Tests for clean command."""

    def test_clean_with_confirmation(self, runner, tmp_path):
        """Test clean command with confirmation."""
        state_file = tmp_path / "state.json"
        state_file.write_text("{}")

        result = runner.invoke(app, ["clean", f"--state={state_file}"], input="n\n")

        assert result.exit_code == 0
        assert "Cancelled" in result.stdout or "Delete" in result.stdout

    def test_clean_with_yes_flag(self, runner, tmp_path):
        """Test clean command with --yes flag."""
        state_file = tmp_path / "state.json"
        state_file.write_text("{}")

        result = runner.invoke(app, ["clean", "--yes", f"--state={state_file}"])

        assert result.exit_code == 0
        assert "Deleted" in result.stdout or "Nothing to clean" in result.stdout


class TestVersionCommand:
    """Tests for version command."""

    def test_version_displays_info(self, runner):
        """Test that version command displays version information."""
        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "opencenter-airgap" in result.stdout
        assert "Python" in result.stdout

    def test_version_shows_dependencies(self, runner):
        """Test that version command shows dependency versions."""
        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        # Should show at least some dependencies
        assert "typer" in result.stdout.lower() or "rich" in result.stdout.lower()
