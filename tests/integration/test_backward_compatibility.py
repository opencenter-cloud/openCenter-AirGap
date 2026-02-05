"""Integration tests for backward compatibility.

Tests that existing components.yaml files work correctly and that
the build system handles stale manifests appropriately.
"""

import time
from pathlib import Path

import pytest

from opencenter_build.cli import app
from typer.testing import CliRunner


runner = CliRunner()


def create_complete_versions_env(path: Path) -> None:
    """Create a complete versions.env file with all required fields."""
    path.write_text(
        """
KUBESPRAY_VERSION=master
KUBESPRAY_COMMIT_SHA=HEAD
KUBERNETES_VERSION=v1.34.3
UBUNTU_VERSION=24.04
CONTAINER_RUNTIME=containerd
CNI_PLUGIN=calico
TERRAFORM_VERSION=1.14.0
FLUXCD_VERSION=v2.7.5
GITEA_VERSION=v1.25.4
CERT_MANAGER_VERSION=v1.16.2
INGRESS_NGINX_VERSION=v1.9.0
KEYCLOAK_VERSION=26.0.7
PROMETHEUS_VERSION=v3.0.1
GRAFANA_VERSION=11.4.0
OPENCENTER_GITOPS_BASE_REPO=https://github.com/rackerlabs/openCenter-gitops-base
OPENCENTER_GITOPS_BASE_VERSION=main
OPENCENTER_GITOPS_BASE_COMMIT_SHA=HEAD
OPENCENTER_CONTAINER_REGISTRY=ghcr.io/opencenter-cloud
TARGET_ARCH=amd64
PYTHON_VERSION=3.10
HELM_VERSION=v4.0.5
"""
    )


class TestExistingManifestWorks:
    """Test that existing components.yaml files work without versions.env."""

    def test_build_with_existing_manifest_no_versions_env(self, tmp_path, monkeypatch):
        """Test building with existing manifest when versions.env doesn't exist."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Create directory structure
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create existing components.yaml (no versions.env)
        manifest_path = config_dir / "components.yaml"
        manifest_path.write_text(
            """
kubernetes:
  version: 1.34.3
  binaries:
    - name: kubectl
      url: https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubectl
      checksum_url: https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubectl.sha256

tools:
  - name: helm
    version: 4.0.5
    url: https://get.helm.sh/helm-v{{version}}-linux-amd64.tar.gz
    extract: true
    binary: linux-amd64/helm

images:
  additional:
    - nginx:1.21
    - redis:7.0
"""
        )

        # Create build and dist directories
        (tmp_path / "build").mkdir()
        (tmp_path / "dist").mkdir()

        # Run build command - should work with existing manifest
        # Note: This will fail at orchestrator stage, but we're testing manifest loading
        result = runner.invoke(app, ["build", "--config", "config/versions.env"])

        # Should fail because versions.env doesn't exist
        assert result.exit_code == 1
        assert (
            "Configuration not found" in result.stdout or "versions.env not found" in result.stdout
        )

    def test_build_with_existing_manifest_and_versions_env(self, tmp_path, monkeypatch):
        """Test building with existing manifest when both files exist."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Create directory structure
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create versions.env first
        versions_env = config_dir / "versions.env"
        create_complete_versions_env(versions_env)

        time.sleep(0.01)  # Ensure different mtime

        # Create existing components.yaml (newer than versions.env)
        manifest_path = config_dir / "components.yaml"
        manifest_path.write_text(
            """
kubernetes:
  version: 1.34.3
  binaries:
    - name: kubectl
      url: https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubectl
      checksum_url: https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubectl.sha256

tools:
  - name: helm
    version: 4.0.5
    url: https://get.helm.sh/helm-v{{version}}-linux-amd64.tar.gz
    extract: true
    binary: linux-amd64/helm

images:
  additional:
    - nginx:1.21
    - redis:7.0
"""
        )

        # Create build and dist directories
        (tmp_path / "build").mkdir()
        (tmp_path / "dist").mkdir()

        # Verify manifest is newer
        assert manifest_path.stat().st_mtime > versions_env.stat().st_mtime

        # Run build command - should use existing manifest without regeneration
        # Note: This will fail at orchestrator stage, but we're testing manifest handling
        result = runner.invoke(app, ["build"])

        # Should not regenerate manifest (no "Generating components.yaml" message)
        assert "Generating components.yaml from versions.env" not in result.stdout

    def test_manifest_not_regenerated_when_newer(self, tmp_path, monkeypatch):
        """Test that manifest is not regenerated when it's newer than versions.env."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Create directory structure
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create versions.env first
        versions_env = config_dir / "versions.env"
        create_complete_versions_env(versions_env)

        time.sleep(0.01)  # Ensure different mtime

        # Create manifest after (newer)
        manifest_path = config_dir / "components.yaml"
        manifest_path.write_text(
            """
_generated:
  timestamp: "2026-02-04T10:00:00Z"
  source: config/versions.env
  tool: opencenter-airgap

kubernetes:
  version: 1.34.3

tools:
  - name: helm
    version: 4.0.5
    url: https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz
"""
        )

        # Store original content
        original_content = manifest_path.read_text()

        # Create build and dist directories
        (tmp_path / "build").mkdir()
        (tmp_path / "dist").mkdir()

        # Run build command
        result = runner.invoke(app, ["build"])

        # Manifest should not be regenerated
        assert manifest_path.read_text() == original_content
        assert "Generating components.yaml from versions.env" not in result.stdout


class TestStaleManifestWarning:
    """Test warning for stale manifests."""

    def test_warning_when_versions_env_newer(self, tmp_path, monkeypatch):
        """Test that warning is displayed when versions.env is newer than manifest."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Create directory structure
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create manifest first
        manifest_path = config_dir / "components.yaml"
        manifest_path.write_text(
            """
kubernetes:
  version: 1.34.3

tools:
  - name: helm
    version: 4.0.5
    url: https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz
"""
        )

        time.sleep(0.01)  # Ensure different mtime

        # Create versions.env after (newer)
        versions_env = config_dir / "versions.env"
        create_complete_versions_env(versions_env)

        # Create build and dist directories
        (tmp_path / "build").mkdir()
        (tmp_path / "dist").mkdir()

        # Verify versions.env is newer
        assert versions_env.stat().st_mtime > manifest_path.stat().st_mtime

        # Run build command
        result = runner.invoke(app, ["build"])

        # Should regenerate manifest and show message
        assert "Generating components.yaml from versions.env" in result.stdout

    def test_no_warning_when_manifest_newer(self, tmp_path, monkeypatch):
        """Test that no warning is displayed when manifest is newer."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Create directory structure
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create versions.env first
        versions_env = config_dir / "versions.env"
        create_complete_versions_env(versions_env)

        time.sleep(0.01)  # Ensure different mtime

        # Create manifest after (newer)
        manifest_path = config_dir / "components.yaml"
        manifest_path.write_text(
            """
kubernetes:
  version: 1.34.3

tools:
  - name: helm
    version: 4.0.5
    url: https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz
"""
        )

        # Create build and dist directories
        (tmp_path / "build").mkdir()
        (tmp_path / "dist").mkdir()

        # Verify manifest is newer
        assert manifest_path.stat().st_mtime > versions_env.stat().st_mtime

        # Run build command
        result = runner.invoke(app, ["build"])

        # Should not regenerate or show warning
        assert "Generating components.yaml from versions.env" not in result.stdout


class TestManualEditsPreserved:
    """Test that manual edits to components.yaml are preserved."""

    def test_manual_images_preserved_on_regeneration(self, tmp_path, monkeypatch):
        """Test that manually added images are preserved when manifest is regenerated."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Create directory structure
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create manifest with manual additions
        manifest_path = config_dir / "components.yaml"
        manifest_path.write_text(
            """
kubernetes:
  version: 1.34.3

tools:
  - name: helm
    version: 4.0.5
    url: https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz

images:
  additional:
    - custom-image:1.0
    - another-custom:2.0
"""
        )

        time.sleep(0.01)  # Ensure different mtime

        # Create versions.env after (newer) - triggers regeneration
        versions_env = config_dir / "versions.env"
        create_complete_versions_env(versions_env)

        # Create build and dist directories
        (tmp_path / "build").mkdir()
        (tmp_path / "dist").mkdir()

        # Run build command
        result = runner.invoke(app, ["build"])

        # Should regenerate manifest
        assert "Generating components.yaml from versions.env" in result.stdout

        # Read regenerated manifest
        from opencenter_build.component_manifest import read_manifest

        manifest = read_manifest(manifest_path)

        # Verify custom images are preserved
        assert "custom-image:1.0" in manifest.images.additional
        assert "another-custom:2.0" in manifest.images.additional

    def test_manual_charts_preserved_on_regeneration(self, tmp_path, monkeypatch):
        """Test that manually added charts are preserved when manifest is regenerated."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Create directory structure
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create manifest with manual chart additions
        manifest_path = config_dir / "components.yaml"
        manifest_path.write_text(
            """
kubernetes:
  version: 1.34.3

tools:
  - name: helm
    version: 4.0.5
    url: https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz

charts:
  - name: custom-chart
    repo: https://custom.io
    version: 1.0.0
  - name: cert-manager
    repo: https://charts.jetstack.io
    version: v1.13.0
"""
        )

        time.sleep(0.01)  # Ensure different mtime

        # Create versions.env with updated cert-manager version
        versions_env = config_dir / "versions.env"
        create_complete_versions_env(versions_env)

        # Create build and dist directories
        (tmp_path / "build").mkdir()
        (tmp_path / "dist").mkdir()

        # Run build command
        result = runner.invoke(app, ["build"])

        # Should regenerate manifest
        assert "Generating components.yaml from versions.env" in result.stdout

        # Read regenerated manifest
        from opencenter_build.component_manifest import read_manifest

        manifest = read_manifest(manifest_path)

        # Verify custom chart is preserved
        chart_names = [c.name for c in manifest.charts]
        assert "custom-chart" in chart_names

        # Verify cert-manager version is updated from versions.env
        cert_manager = next(c for c in manifest.charts if c.name == "cert-manager")
        assert cert_manager.version == "v1.16.2"

    def test_manual_tools_preserved_on_regeneration(self, tmp_path, monkeypatch):
        """Test that manually added tools are preserved when manifest is regenerated."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Create directory structure
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create manifest with manual tool additions
        manifest_path = config_dir / "components.yaml"
        manifest_path.write_text(
            """
kubernetes:
  version: 1.34.3

tools:
  - name: helm
    version: 4.0.5
    url: https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz
  - name: custom-tool
    version: 1.0.0
    url: https://custom.io/tool-v1.0.0.tar.gz
"""
        )

        time.sleep(0.01)  # Ensure different mtime

        # Create versions.env after (newer)
        versions_env = config_dir / "versions.env"
        create_complete_versions_env(versions_env)

        # Create build and dist directories
        (tmp_path / "build").mkdir()
        (tmp_path / "dist").mkdir()

        # Run build command
        result = runner.invoke(app, ["build"])

        # Should regenerate manifest
        assert "Generating components.yaml from versions.env" in result.stdout

        # Read regenerated manifest
        from opencenter_build.component_manifest import read_manifest

        manifest = read_manifest(manifest_path)

        # Verify custom tool is preserved
        tool_names = [t.name for t in manifest.tools]
        assert "custom-tool" in tool_names
        assert "helm" in tool_names

        # Verify helm version is from versions.env
        helm = next(t for t in manifest.tools if t.name == "helm")
        assert helm.version == "4.0.5"

    def test_force_regenerate_preserves_manual_edits(self, tmp_path, monkeypatch):
        """Test that --force-regenerate still preserves manual edits via merge."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Create directory structure
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create versions.env
        versions_env = config_dir / "versions.env"
        create_complete_versions_env(versions_env)

        # Create manifest with manual additions (newer than versions.env)
        time.sleep(0.01)
        manifest_path = config_dir / "components.yaml"
        manifest_path.write_text(
            """
kubernetes:
  version: 1.34.3

tools:
  - name: helm
    version: 4.0.5
    url: https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz

images:
  additional:
    - custom-image:1.0
"""
        )

        # Create build and dist directories
        (tmp_path / "build").mkdir()
        (tmp_path / "dist").mkdir()

        # Run build with --force-regenerate
        result = runner.invoke(app, ["build", "--force-regenerate"])

        # Should regenerate manifest
        assert (
            "Generating components.yaml from versions.env" in result.stdout
            or "Regenerated and merged manual edits" in result.stdout
        )

        # Read regenerated manifest
        from opencenter_build.component_manifest import read_manifest

        manifest = read_manifest(manifest_path)

        # Verify custom image is still preserved
        assert "custom-image:1.0" in manifest.images.additional

        # Read regenerated manifest
        from opencenter_build.component_manifest import read_manifest

        manifest = read_manifest(manifest_path)

        # Verify custom image is still preserved
        assert "custom-image:1.0" in manifest.images.additional
