"""Unit tests for component manifest module."""

import time
from pathlib import Path

import pytest

from opencenter_build.component_manifest import (
    ComponentManifest,
    ImagesComponent,
    ToolComponent,
    ChartComponent,
    RepositoryComponent,
    RepoSpec,
    should_regenerate_manifest,
    merge_manifests,
    create_default_manifest,
    read_manifest,
    write_manifest,
    extract_repos_from_versions,
    clone_repository,
    HelmChartScanner,
)
from opencenter_build.exceptions import ConfigError


class TestShouldRegenerateManifest:
    """Test should_regenerate_manifest function."""

    def test_force_regenerate_returns_true(self, tmp_path):
        """Test that force=True always returns True."""
        versions_env = tmp_path / "versions.env"
        manifest = tmp_path / "components.yaml"

        # Create both files
        versions_env.write_text("KUBERNETES_VERSION=v1.34.3\n")
        manifest.write_text("kubernetes:\n  version: 1.34.3\n")

        assert should_regenerate_manifest(versions_env, manifest, force=True) is True

    def test_manifest_missing_returns_true(self, tmp_path):
        """Test that missing manifest returns True."""
        versions_env = tmp_path / "versions.env"
        manifest = tmp_path / "components.yaml"

        versions_env.write_text("KUBERNETES_VERSION=v1.34.3\n")

        assert should_regenerate_manifest(versions_env, manifest, force=False) is True

    def test_versions_env_missing_returns_false(self, tmp_path):
        """Test that missing versions.env returns False."""
        versions_env = tmp_path / "versions.env"
        manifest = tmp_path / "components.yaml"

        manifest.write_text("kubernetes:\n  version: 1.34.3\n")

        assert should_regenerate_manifest(versions_env, manifest, force=False) is False

    def test_versions_env_newer_returns_true(self, tmp_path):
        """Test that newer versions.env returns True."""
        versions_env = tmp_path / "versions.env"
        manifest = tmp_path / "components.yaml"

        # Create manifest first
        manifest.write_text("kubernetes:\n  version: 1.34.3\n")
        time.sleep(0.01)  # Ensure different mtime

        # Create versions.env after (newer)
        versions_env.write_text("KUBERNETES_VERSION=v1.34.3\n")

        assert should_regenerate_manifest(versions_env, manifest, force=False) is True

    def test_manifest_newer_returns_false(self, tmp_path):
        """Test that newer manifest returns False."""
        versions_env = tmp_path / "versions.env"
        manifest = tmp_path / "components.yaml"

        # Create versions.env first
        versions_env.write_text("KUBERNETES_VERSION=v1.34.3\n")
        time.sleep(0.01)  # Ensure different mtime

        # Create manifest after (newer)
        manifest.write_text("kubernetes:\n  version: 1.34.3\n")

        assert should_regenerate_manifest(versions_env, manifest, force=False) is False


class TestMergeManifests:
    """Test merge_manifests function."""

    def test_preserves_additional_images(self):
        """Test that additional images from existing manifest are preserved."""
        existing = ComponentManifest()
        existing.images.additional = ["custom-image:1.0", "another-image:2.0"]

        generated = ComponentManifest()
        generated.images.additional = ["standard-image:1.0"]

        merged = merge_manifests(existing, generated)

        assert "standard-image:1.0" in merged.images.additional
        assert "custom-image:1.0" in merged.images.additional
        assert "another-image:2.0" in merged.images.additional
        assert len(merged.images.additional) == 3

    def test_avoids_duplicate_images(self):
        """Test that duplicate images are not added."""
        existing = ComponentManifest()
        existing.images.additional = ["shared-image:1.0", "custom-image:1.0"]

        generated = ComponentManifest()
        generated.images.additional = ["shared-image:1.0", "new-image:1.0"]

        merged = merge_manifests(existing, generated)

        # Count occurrences of shared-image
        shared_count = merged.images.additional.count("shared-image:1.0")
        assert shared_count == 1
        assert "custom-image:1.0" in merged.images.additional
        assert "new-image:1.0" in merged.images.additional

    def test_preserves_custom_charts(self):
        """Test that custom charts from existing manifest are preserved."""
        existing = ComponentManifest()
        existing.charts = [
            ChartComponent(name="custom-chart", repo="https://custom.io", version="1.0.0"),
            ChartComponent(
                name="cert-manager", repo="https://charts.jetstack.io", version="v1.13.0"
            ),
        ]

        generated = ComponentManifest()
        generated.charts = [
            ChartComponent(
                name="cert-manager", repo="https://charts.jetstack.io", version="v1.16.2"
            ),
        ]

        merged = merge_manifests(existing, generated)

        chart_names = [c.name for c in merged.charts]
        assert "cert-manager" in chart_names
        assert "custom-chart" in chart_names

        # Verify cert-manager uses generated version
        cert_manager = next(c for c in merged.charts if c.name == "cert-manager")
        assert cert_manager.version == "v1.16.2"

    def test_preserves_custom_tools(self):
        """Test that custom tools from existing manifest are preserved."""
        existing = ComponentManifest()
        existing.tools = [
            ToolComponent(name="custom-tool", version="1.0.0", url="https://custom.io/tool"),
            ToolComponent(
                name="helm",
                version="3.14.0",
                url="https://get.helm.sh/helm-v3.14.0-linux-amd64.tar.gz",
            ),
        ]

        generated = ComponentManifest()
        generated.tools = [
            ToolComponent(
                name="helm",
                version="4.0.5",
                url="https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz",
            ),
        ]

        merged = merge_manifests(existing, generated)

        tool_names = [t.name for t in merged.tools]
        assert "helm" in tool_names
        assert "custom-tool" in tool_names

        # Verify helm uses generated version
        helm = next(t for t in merged.tools if t.name == "helm")
        assert helm.version == "4.0.5"

    def test_uses_generated_versions(self):
        """Test that generated versions override existing versions."""
        existing = ComponentManifest()
        existing.tools = [
            ToolComponent(
                name="helm",
                version="3.14.0",
                url="https://get.helm.sh/helm-v3.14.0-linux-amd64.tar.gz",
            ),
        ]

        generated = ComponentManifest()
        generated.tools = [
            ToolComponent(
                name="helm",
                version="4.0.5",
                url="https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz",
            ),
        ]

        merged = merge_manifests(existing, generated)

        helm = next(t for t in merged.tools if t.name == "helm")
        assert helm.version == "4.0.5"
        assert "4.0.5" in helm.url

    def test_empty_existing_manifest(self):
        """Test merging with empty existing manifest."""
        existing = ComponentManifest()

        generated = ComponentManifest()
        generated.images.additional = ["image:1.0"]
        generated.tools = [
            ToolComponent(
                name="helm",
                version="4.0.5",
                url="https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz",
            ),
        ]

        merged = merge_manifests(existing, generated)

        assert len(merged.images.additional) == 1
        assert len(merged.tools) == 1

    def test_empty_generated_manifest(self):
        """Test merging with empty generated manifest."""
        existing = ComponentManifest()
        existing.images.additional = ["custom-image:1.0"]
        existing.tools = [
            ToolComponent(name="custom-tool", version="1.0.0", url="https://custom.io/tool"),
        ]

        generated = ComponentManifest()

        merged = merge_manifests(existing, generated)

        assert "custom-image:1.0" in merged.images.additional
        assert len(merged.tools) == 1
        assert merged.tools[0].name == "custom-tool"


class TestCreateDefaultManifest:
    """Test create_default_manifest function."""

    def test_creates_manifest_from_versions_env(self, tmp_path):
        """Test creating manifest from versions.env."""
        versions_env = tmp_path / "versions.env"
        versions_env.write_text(
            """
KUBERNETES_VERSION=v1.34.3
HELM_VERSION=v4.0.5
K9S_VERSION=v0.50.9
KUBESPRAY_VERSION=master
OPENCENTER_GITOPS_BASE_REPO=https://github.com/rackerlabs/openCenter-gitops-base
OPENCENTER_GITOPS_BASE_VERSION=main
CERT_MANAGER_VERSION=v1.16.2
"""
        )

        manifest = create_default_manifest(versions_env=versions_env)

        # Check Kubernetes
        assert manifest.kubernetes is not None
        assert manifest.kubernetes.version == "1.34.3"

        # Check tools
        tool_names = [t.name for t in manifest.tools]
        assert "helm" in tool_names
        assert "k9s" in tool_names

        helm = next(t for t in manifest.tools if t.name == "helm")
        assert helm.version == "4.0.5"

        # Check repositories
        repo_names = [r.name for r in manifest.repositories]
        assert "kubespray" in repo_names
        assert "opencenter-gitops-base" in repo_names

        # Check charts
        chart_names = [c.name for c in manifest.charts]
        assert "cert-manager" in chart_names

    def test_raises_error_if_versions_env_missing(self, tmp_path):
        """Test that missing versions.env raises ConfigError."""
        versions_env = tmp_path / "versions.env"

        with pytest.raises(ConfigError, match="versions.env not found"):
            create_default_manifest(versions_env=versions_env)


class TestReadWriteManifest:
    """Test read_manifest and write_manifest functions."""

    def test_write_and_read_manifest(self, tmp_path):
        """Test writing and reading manifest."""
        manifest_path = tmp_path / "components.yaml"

        # Create manifest
        manifest = ComponentManifest()
        manifest.images.additional = ["nginx:1.21", "redis:7.0"]
        manifest.tools = [
            ToolComponent(
                name="helm",
                version="4.0.5",
                url="https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz",
            ),
        ]

        # Write manifest
        write_manifest(manifest, manifest_path)

        assert manifest_path.exists()

        # Read manifest
        loaded = read_manifest(manifest_path)

        assert len(loaded.images.additional) == 2
        assert "nginx:1.21" in loaded.images.additional
        assert len(loaded.tools) == 1
        assert loaded.tools[0].name == "helm"

    def test_read_nonexistent_manifest_raises_error(self, tmp_path):
        """Test that reading nonexistent manifest raises ConfigError."""
        manifest_path = tmp_path / "components.yaml"

        with pytest.raises(ConfigError, match="Component manifest not found"):
            read_manifest(manifest_path)


class TestManifestMetadata:
    """Test manifest metadata functionality."""

    def test_write_manifest_includes_metadata(self, tmp_path):
        """Test that write_manifest adds generation metadata."""
        manifest_path = tmp_path / "components.yaml"

        manifest = ComponentManifest()
        manifest.images.additional = ["nginx:1.21"]

        write_manifest(manifest, manifest_path)

        # Read raw YAML to check metadata
        content = manifest_path.read_text()

        # Check header comment
        assert "# Component Manifest" in content
        assert "# Auto-generated from config/versions.env" in content
        assert "# Manual edits are preserved during regeneration" in content
        assert (
            "# To regenerate: python3 -m opencenter_build.cli build --force-regenerate" in content
        )

        # Check metadata section
        assert "_generated:" in content
        assert "timestamp:" in content
        assert "source: config/versions.env" in content
        assert "tool: opencenter-airgap" in content
        assert "note: This file is auto-generated" in content

    def test_metadata_preserved_on_round_trip(self, tmp_path):
        """Test that metadata is preserved when reading and writing."""
        manifest_path = tmp_path / "components.yaml"

        # Create and write manifest
        manifest = ComponentManifest()
        manifest.images.additional = ["nginx:1.21"]

        write_manifest(manifest, manifest_path)

        # Read manifest
        loaded = read_manifest(manifest_path)

        # Verify metadata was loaded
        assert loaded._generated is not None
        assert "timestamp" in loaded._generated
        assert loaded._generated["source"] == "config/versions.env"
        assert loaded._generated["tool"] == "opencenter-airgap"

        # Write again
        manifest_path2 = tmp_path / "components2.yaml"
        write_manifest(loaded, manifest_path2)

        # Read again
        loaded2 = read_manifest(manifest_path2)

        # Verify metadata still present
        assert loaded2._generated is not None
        assert loaded2._generated["timestamp"] == loaded._generated["timestamp"]
        assert loaded2._generated["source"] == loaded._generated["source"]

    def test_to_dict_includes_metadata(self):
        """Test that to_dict includes metadata if present."""
        manifest = ComponentManifest()
        manifest._generated = {
            "timestamp": "2026-02-04T12:00:00Z",
            "source": "config/versions.env",
            "tool": "opencenter-airgap",
        }
        manifest.images.additional = ["nginx:1.21"]

        data = manifest.to_dict()

        assert "_generated" in data
        assert data["_generated"]["timestamp"] == "2026-02-04T12:00:00Z"
        assert data["_generated"]["source"] == "config/versions.env"

    def test_from_dict_preserves_metadata(self):
        """Test that from_dict preserves metadata."""
        data = {
            "_generated": {
                "timestamp": "2026-02-04T12:00:00Z",
                "source": "config/versions.env",
                "tool": "opencenter-airgap",
            },
            "images": {"additional": ["nginx:1.21"]},
        }

        manifest = ComponentManifest.from_dict(data)

        assert manifest._generated is not None
        assert manifest._generated["timestamp"] == "2026-02-04T12:00:00Z"
        assert manifest._generated["source"] == "config/versions.env"

    def test_merge_preserves_existing_metadata(self):
        """Test that merge_manifests preserves metadata from existing manifest."""
        existing = ComponentManifest()
        existing._generated = {
            "timestamp": "2026-02-04T10:00:00Z",
            "source": "config/versions.env",
            "tool": "opencenter-airgap",
        }
        existing.images.additional = ["custom-image:1.0"]

        generated = ComponentManifest()
        generated.images.additional = ["standard-image:1.0"]

        merged = merge_manifests(existing, generated)

        # Verify metadata from existing is preserved
        assert merged._generated is not None
        assert merged._generated["timestamp"] == "2026-02-04T10:00:00Z"
        assert merged._generated["source"] == "config/versions.env"

    def test_manifest_without_metadata_works(self, tmp_path):
        """Test that manifests without metadata still work."""
        manifest_path = tmp_path / "components.yaml"

        # Write manifest without metadata (old format)
        manifest_path.write_text(
            """
images:
  additional:
    - nginx:1.21
"""
        )

        # Should load without error
        loaded = read_manifest(manifest_path)

        assert loaded._generated is None
        assert len(loaded.images.additional) == 1
        assert "nginx:1.21" in loaded.images.additional


class TestRepoSpec:
    """Test RepoSpec dataclass."""

    def test_creates_valid_repo_spec(self):
        """Test creating a valid RepoSpec."""
        repo = RepoSpec(
            name="kubespray", url="https://github.com/kubernetes-sigs/kubespray.git", ref="v2.24.0"
        )

        assert repo.name == "kubespray"
        assert repo.url == "https://github.com/kubernetes-sigs/kubespray.git"
        assert repo.ref == "v2.24.0"

    def test_validates_required_name(self):
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="Repository name is required"):
            RepoSpec(name="", url="https://github.com/kubernetes-sigs/kubespray.git", ref="v2.24.0")

    def test_validates_required_url(self):
        """Test that empty url raises ValueError."""
        with pytest.raises(ValueError, match="Repository URL is required"):
            RepoSpec(name="kubespray", url="", ref="v2.24.0")

    def test_validates_required_ref(self):
        """Test that empty ref raises ValueError."""
        with pytest.raises(ValueError, match="Repository ref is required"):
            RepoSpec(
                name="kubespray", url="https://github.com/kubernetes-sigs/kubespray.git", ref=""
            )


class TestExtractReposFromVersions:
    """Test extract_repos_from_versions function."""

    def test_extracts_kubespray_repo(self):
        """Test extracting kubespray repository."""
        versions = {
            "KUBESPRAY_VERSION": "v2.24.0",
            "KUBESPRAY_COMMIT_SHA": "8a5d3d0c8e9f7b6a5c4d3e2f1a0b9c8d7e6f5a4b",
        }

        repos = extract_repos_from_versions(versions)

        assert len(repos) == 1
        assert repos[0].name == "kubespray"
        assert repos[0].url == "https://github.com/kubernetes-sigs/kubespray.git"
        assert repos[0].ref == "v2.24.0"

    def test_extracts_opencenter_gitops_repo(self):
        """Test extracting openCenter GitOps repository."""
        versions = {
            "OPENCENTER_GITOPS_BASE_REPO": "https://github.com/rackerlabs/openCenter-gitops-base",
            "OPENCENTER_GITOPS_BASE_VERSION": "v1.0.0",
        }

        repos = extract_repos_from_versions(versions)

        assert len(repos) == 1
        assert repos[0].name == "opencenter-gitops-base"
        assert repos[0].url == "https://github.com/rackerlabs/openCenter-gitops-base"
        assert repos[0].ref == "v1.0.0"

    def test_extracts_multiple_repos(self):
        """Test extracting multiple repositories."""
        versions = {
            "KUBESPRAY_VERSION": "v2.24.0",
            "OPENCENTER_GITOPS_BASE_REPO": "https://github.com/rackerlabs/openCenter-gitops-base",
            "OPENCENTER_GITOPS_BASE_VERSION": "v1.0.0",
        }

        repos = extract_repos_from_versions(versions)

        assert len(repos) == 2

        repo_names = [r.name for r in repos]
        assert "kubespray" in repo_names
        assert "opencenter-gitops-base" in repo_names

    def test_handles_missing_kubespray_version(self):
        """Test handling missing KUBESPRAY_VERSION."""
        versions = {
            "OPENCENTER_GITOPS_BASE_REPO": "https://github.com/rackerlabs/openCenter-gitops-base",
            "OPENCENTER_GITOPS_BASE_VERSION": "v1.0.0",
        }

        repos = extract_repos_from_versions(versions)

        assert len(repos) == 1
        assert repos[0].name == "opencenter-gitops-base"

    def test_handles_missing_opencenter_repo(self):
        """Test handling missing OPENCENTER_GITOPS_BASE_REPO."""
        versions = {
            "KUBESPRAY_VERSION": "v2.24.0",
        }

        repos = extract_repos_from_versions(versions)

        assert len(repos) == 1
        assert repos[0].name == "kubespray"

    def test_handles_empty_versions(self):
        """Test handling empty versions dictionary."""
        versions = {}

        repos = extract_repos_from_versions(versions)

        assert len(repos) == 0

    def test_defaults_to_main_when_version_missing(self):
        """Test that missing OPENCENTER_GITOPS_BASE_VERSION defaults to 'main'."""
        versions = {
            "OPENCENTER_GITOPS_BASE_REPO": "https://github.com/rackerlabs/openCenter-gitops-base",
        }

        repos = extract_repos_from_versions(versions)

        assert len(repos) == 1
        assert repos[0].ref == "main"


class TestCloneRepository:
    """Test clone_repository function."""

    def test_clones_repository_successfully(self, tmp_path, monkeypatch):
        """Test successful repository clone."""
        from unittest.mock import Mock, patch
        from opencenter_build.component_manifest import clone_repository

        build_dir = tmp_path / "build"
        repo_spec = RepoSpec(name="test-repo", url="https://github.com/test/repo.git", ref="main")

        # Mock subprocess.run to simulate successful clone
        mock_run = Mock()
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""

        with patch("subprocess.run", mock_run):
            result = clone_repository(repo_spec, build_dir)

        # Verify result
        assert result == build_dir / "test-repo"

        # Verify subprocess.run was called with correct arguments
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "git"
        assert call_args[1] == "clone"
        assert call_args[2] == "--depth"
        assert call_args[3] == "1"
        assert call_args[4] == "--branch"
        assert call_args[5] == "main"
        assert call_args[6] == "https://github.com/test/repo.git"
        assert str(build_dir / "test-repo") in call_args[7]

    def test_skips_if_repository_exists(self, tmp_path):
        """Test that existing repository is not cloned again."""
        from unittest.mock import Mock, patch
        from opencenter_build.component_manifest import clone_repository

        build_dir = tmp_path / "build"
        repo_path = build_dir / "test-repo"
        repo_path.mkdir(parents=True)

        repo_spec = RepoSpec(name="test-repo", url="https://github.com/test/repo.git", ref="main")

        # Mock subprocess.run - should not be called
        mock_run = Mock()

        with patch("subprocess.run", mock_run):
            result = clone_repository(repo_spec, build_dir)

        # Verify result
        assert result == repo_path

        # Verify subprocess.run was NOT called
        mock_run.assert_not_called()

    def test_handles_clone_error(self, tmp_path):
        """Test handling of git clone errors."""
        from unittest.mock import Mock, patch
        from subprocess import CalledProcessError
        from opencenter_build.component_manifest import clone_repository

        build_dir = tmp_path / "build"
        repo_spec = RepoSpec(
            name="test-repo", url="https://github.com/test/repo.git", ref="invalid-ref"
        )

        # Mock subprocess.run to simulate clone failure
        mock_run = Mock()
        mock_run.side_effect = CalledProcessError(
            returncode=128,
            cmd=["git", "clone"],
            stderr="fatal: Remote branch invalid-ref not found",
        )

        with patch("subprocess.run", mock_run):
            with pytest.raises(ConfigError, match="Failed to clone repository"):
                clone_repository(repo_spec, build_dir)

    def test_handles_git_not_found(self, tmp_path):
        """Test handling when git command is not found."""
        from unittest.mock import Mock, patch
        from opencenter_build.component_manifest import clone_repository

        build_dir = tmp_path / "build"
        repo_spec = RepoSpec(name="test-repo", url="https://github.com/test/repo.git", ref="main")

        # Mock subprocess.run to simulate git not found
        mock_run = Mock()
        mock_run.side_effect = FileNotFoundError("git command not found")

        with patch("subprocess.run", mock_run):
            with pytest.raises(ConfigError, match="git command not found"):
                clone_repository(repo_spec, build_dir)

    def test_creates_build_directory_if_missing(self, tmp_path):
        """Test that build directory is created if it doesn't exist."""
        from unittest.mock import Mock, patch
        from opencenter_build.component_manifest import clone_repository

        build_dir = tmp_path / "build"
        # Don't create build_dir - let clone_repository create it

        repo_spec = RepoSpec(name="test-repo", url="https://github.com/test/repo.git", ref="main")

        # Mock subprocess.run to simulate successful clone
        mock_run = Mock()
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""

        with patch("subprocess.run", mock_run):
            clone_repository(repo_spec, build_dir)

        # Verify build directory was created
        assert build_dir.exists()

    def test_uses_default_build_directory(self, tmp_path, monkeypatch):
        """Test that default build/ directory is used when not specified."""
        from unittest.mock import Mock, patch
        from opencenter_build.component_manifest import clone_repository

        # Change to tmp_path so default build/ is created there
        monkeypatch.chdir(tmp_path)

        repo_spec = RepoSpec(name="test-repo", url="https://github.com/test/repo.git", ref="main")

        # Mock subprocess.run to simulate successful clone
        mock_run = Mock()
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""

        with patch("subprocess.run", mock_run):
            result = clone_repository(repo_spec)

        # Verify default build/ directory was used
        assert result == Path("build") / "test-repo"


class TestHelmChartScanner:
    """Test HelmChartScanner class."""

    def test_scans_valid_chart_yaml(self, tmp_path):
        """Test scanning a valid Chart.yaml file."""
        # Create a repository with a valid Chart.yaml
        repo_path = tmp_path / "test-repo"
        chart_path = repo_path / "charts" / "my-chart"
        chart_path.mkdir(parents=True)

        chart_yaml = chart_path / "Chart.yaml"
        chart_yaml.write_text(
            """
name: my-chart
version: 1.0.0
description: A test chart
"""
        )

        scanner = HelmChartScanner(repos=[repo_path])
        charts = scanner.scan_all()

        assert len(charts) == 1
        assert charts[0].name == "my-chart"
        assert charts[0].version == "1.0.0"
        assert charts[0].repo == str(repo_path)
        assert charts[0].path == "charts/my-chart"

    def test_scans_multiple_charts_in_repo(self, tmp_path):
        """Test scanning multiple charts in a repository."""
        repo_path = tmp_path / "test-repo"

        # Create first chart
        chart1_path = repo_path / "charts" / "chart1"
        chart1_path.mkdir(parents=True)
        (chart1_path / "Chart.yaml").write_text(
            """
name: chart1
version: 1.0.0
"""
        )

        # Create second chart
        chart2_path = repo_path / "charts" / "chart2"
        chart2_path.mkdir(parents=True)
        (chart2_path / "Chart.yaml").write_text(
            """
name: chart2
version: 2.0.0
"""
        )

        scanner = HelmChartScanner(repos=[repo_path])
        charts = scanner.scan_all()

        assert len(charts) == 2

        chart_names = [c.name for c in charts]
        assert "chart1" in chart_names
        assert "chart2" in chart_names

    def test_handles_invalid_yaml(self, tmp_path):
        """Test handling of invalid YAML in Chart.yaml."""
        repo_path = tmp_path / "test-repo"
        chart_path = repo_path / "charts" / "bad-chart"
        chart_path.mkdir(parents=True)

        chart_yaml = chart_path / "Chart.yaml"
        chart_yaml.write_text(
            """
name: bad-chart
version: 1.0.0
invalid yaml: [unclosed bracket
"""
        )

        scanner = HelmChartScanner(repos=[repo_path])
        charts = scanner.scan_all()

        # Invalid YAML should be skipped
        assert len(charts) == 0

    def test_handles_missing_name_field(self, tmp_path):
        """Test handling of Chart.yaml with missing name field."""
        repo_path = tmp_path / "test-repo"
        chart_path = repo_path / "charts" / "no-name"
        chart_path.mkdir(parents=True)

        chart_yaml = chart_path / "Chart.yaml"
        chart_yaml.write_text(
            """
version: 1.0.0
description: Chart without name
"""
        )

        scanner = HelmChartScanner(repos=[repo_path])
        charts = scanner.scan_all()

        # Chart without name should be skipped
        assert len(charts) == 0

    def test_handles_missing_version_field(self, tmp_path):
        """Test handling of Chart.yaml with missing version field."""
        repo_path = tmp_path / "test-repo"
        chart_path = repo_path / "charts" / "no-version"
        chart_path.mkdir(parents=True)

        chart_yaml = chart_path / "Chart.yaml"
        chart_yaml.write_text(
            """
name: no-version
description: Chart without version
"""
        )

        scanner = HelmChartScanner(repos=[repo_path])
        charts = scanner.scan_all()

        # Chart without version should be skipped
        assert len(charts) == 0

    def test_handles_empty_chart_yaml(self, tmp_path):
        """Test handling of empty Chart.yaml file."""
        repo_path = tmp_path / "test-repo"
        chart_path = repo_path / "charts" / "empty-chart"
        chart_path.mkdir(parents=True)

        chart_yaml = chart_path / "Chart.yaml"
        chart_yaml.write_text("")

        scanner = HelmChartScanner(repos=[repo_path])
        charts = scanner.scan_all()

        # Empty Chart.yaml should be skipped
        assert len(charts) == 0

    def test_handles_nonexistent_repo(self, tmp_path):
        """Test handling of nonexistent repository path."""
        repo_path = tmp_path / "nonexistent-repo"

        scanner = HelmChartScanner(repos=[repo_path])
        charts = scanner.scan_all()

        # Should return empty list without error
        assert len(charts) == 0

    def test_scans_multiple_repos(self, tmp_path):
        """Test scanning multiple repositories."""
        # Create first repo with chart
        repo1_path = tmp_path / "repo1"
        chart1_path = repo1_path / "charts" / "chart1"
        chart1_path.mkdir(parents=True)
        (chart1_path / "Chart.yaml").write_text(
            """
name: chart1
version: 1.0.0
"""
        )

        # Create second repo with chart
        repo2_path = tmp_path / "repo2"
        chart2_path = repo2_path / "charts" / "chart2"
        chart2_path.mkdir(parents=True)
        (chart2_path / "Chart.yaml").write_text(
            """
name: chart2
version: 2.0.0
"""
        )

        scanner = HelmChartScanner(repos=[repo1_path, repo2_path])
        charts = scanner.scan_all()

        assert len(charts) == 2

        chart_names = [c.name for c in charts]
        assert "chart1" in chart_names
        assert "chart2" in chart_names

    def test_handles_nested_charts(self, tmp_path):
        """Test scanning nested chart directories."""
        repo_path = tmp_path / "test-repo"

        # Create nested chart structure
        nested_chart_path = repo_path / "deploy" / "helm" / "charts" / "nested-chart"
        nested_chart_path.mkdir(parents=True)
        (nested_chart_path / "Chart.yaml").write_text(
            """
name: nested-chart
version: 1.0.0
"""
        )

        scanner = HelmChartScanner(repos=[repo_path])
        charts = scanner.scan_all()

        assert len(charts) == 1
        assert charts[0].name == "nested-chart"
        assert charts[0].path == "deploy/helm/charts/nested-chart"

    def test_handles_chart_with_additional_fields(self, tmp_path):
        """Test scanning Chart.yaml with additional fields."""
        repo_path = tmp_path / "test-repo"
        chart_path = repo_path / "charts" / "full-chart"
        chart_path.mkdir(parents=True)

        chart_yaml = chart_path / "Chart.yaml"
        chart_yaml.write_text(
            """
apiVersion: v2
name: full-chart
version: 1.0.0
description: A full-featured chart
type: application
appVersion: "1.0"
keywords:
  - test
  - example
maintainers:
  - name: Test Maintainer
    email: test@example.com
"""
        )

        scanner = HelmChartScanner(repos=[repo_path])
        charts = scanner.scan_all()

        assert len(charts) == 1
        assert charts[0].name == "full-chart"
        assert charts[0].version == "1.0.0"

    def test_handles_parse_errors_gracefully(self, tmp_path):
        """Test that parse errors don't crash the scanner."""
        repo_path = tmp_path / "test-repo"

        # Create a valid chart
        valid_chart_path = repo_path / "charts" / "valid-chart"
        valid_chart_path.mkdir(parents=True)
        (valid_chart_path / "Chart.yaml").write_text(
            """
name: valid-chart
version: 1.0.0
"""
        )

        # Create an invalid chart
        invalid_chart_path = repo_path / "charts" / "invalid-chart"
        invalid_chart_path.mkdir(parents=True)
        (invalid_chart_path / "Chart.yaml").write_text("invalid: yaml: [")

        scanner = HelmChartScanner(repos=[repo_path])
        charts = scanner.scan_all()

        # Should only return the valid chart
        assert len(charts) == 1
        assert charts[0].name == "valid-chart"

    def test_empty_repo_list(self):
        """Test scanner with empty repository list."""
        scanner = HelmChartScanner(repos=[])
        charts = scanner.scan_all()

        assert len(charts) == 0
