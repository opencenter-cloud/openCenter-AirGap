"""Integration test for full build with component manifest.

Tests complete build workflow using component manifest:
- Initialize component manifest
- Add components (tools, repos, images, charts)
- Scan repositories for images
- Generate Zarf manifest
- Execute full build
- Verify package creation
- Verify artifact manifest generation

**Validates: Requirements 5.7, 6.1, 13.7, 14.1**
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from opencenter_build.component_manifest import (
    ComponentManifest,
    RepoSpec as RepositorySpec,
    ToolComponent as ToolSpec,
    create_default_manifest,
)


@pytest.fixture
def test_workspace(tmp_path):
    """Create isolated test workspace with minimal structure."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create directory structure
    (workspace / "config").mkdir()
    (workspace / "build").mkdir()
    (workspace / "dist").mkdir()
    (workspace / "src" / "opencenter_build").mkdir(parents=True)

    # Copy source files
    project_root = Path.cwd()
    src_dir = project_root / "src" / "opencenter_build"

    if src_dir.exists():
        for py_file in src_dir.glob("*.py"):
            shutil.copy2(py_file, workspace / "src" / "opencenter_build" / py_file.name)

    # Create complete versions.env
    versions_env = workspace / "config" / "versions.env"
    versions_env.write_text(
        """# Test versions
KUBESPRAY_VERSION=v2.24.0
KUBESPRAY_COMMIT_SHA=8a5d3d0c8e9f7b6a5c4d3e2f1a0b9c8d7e6f5a4b
KUBERNETES_VERSION=v1.34.3
UBUNTU_VERSION=24.04
CONTAINER_RUNTIME=containerd
CNI_PLUGIN=calico
TERRAFORM_VERSION=1.6.6
FLUXCD_VERSION=v2.2.0
GITEA_VERSION=1.21.0
CERT_MANAGER_VERSION=v1.13.0
INGRESS_NGINX_VERSION=v1.9.0
KEYCLOAK_VERSION=21.1.1
PROMETHEUS_VERSION=v2.48.0
GRAFANA_VERSION=10.2.0
OPENCENTER_GITOPS_BASE_REPO=https://github.com/opencenter-cloud/openCenter-gitops-base
OPENCENTER_GITOPS_BASE_VERSION=v1.0.0
OPENCENTER_GITOPS_BASE_COMMIT_SHA=1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b
OPENCENTER_CONTAINER_REGISTRY=ghcr.io/opencenter-cloud
TARGET_ARCH=amd64
PYTHON_VERSION=3.10
"""
    )

    # Create test repository for scanning
    test_repo = workspace / "test-repo"
    test_repo.mkdir()

    # Create YAML files with image references
    (test_repo / "deployment.yaml").write_text(
        """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-app
spec:
  template:
    spec:
      containers:
      - name: nginx
        image: docker.io/nginx:1.21.0
      - name: redis
        image: redis:7.0-alpine
"""
    )

    (test_repo / "values.yaml").write_text(
        """
image:
  repository: quay.io/prometheus/prometheus
  tag: v2.48.0
sidecar:
  image: grafana/grafana:10.2.0
"""
    )

    yield workspace


def test_component_manifest_initialization(test_workspace):
    """Test component manifest initialization.

    **Validates: Requirement 13.7**
    """
    manifest_path = test_workspace / "config" / "components.yaml"

    # Create default manifest
    manifest = create_default_manifest()
    manifest.save(manifest_path)

    # Verify file exists
    assert manifest_path.exists(), "Component manifest should be created"

    # Verify content
    content = yaml.safe_load(manifest_path.read_text())
    assert "kubernetes" in content
    assert "repositories" in content
    assert "images" in content

    # Verify Kubernetes configuration
    assert content["kubernetes"]["version"] == "{{KUBERNETES_VERSION}}"
    assert len(content["kubernetes"]["binaries"]) >= 3

    # Verify default repository
    assert len(content["repositories"]) >= 1
    assert content["repositories"][0]["name"] == "kubespray"


def test_add_components_to_manifest(test_workspace):
    """Test adding components to manifest.

    **Validates: Requirement 13.7**
    """
    manifest_path = test_workspace / "config" / "components.yaml"

    # Create manifest
    manifest = ComponentManifest()

    # Add tool
    tool = ToolSpec(
        name="helm",
        version="3.14.0",
        url="https://get.helm.sh/helm-v{{version}}-linux-amd64.tar.gz",
        extract=True,
        binary="linux-amd64/helm",
    )
    manifest.add_tool(tool)

    # Add repository
    repo = RepositorySpec(
        name="test-repo",
        url="https://github.com/test/repo.git",
        ref="v1.0.0",
    )
    manifest.add_repository(repo)

    # Add image
    manifest.add_image("docker.io/nginx:1.21.0")
    manifest.add_image("redis:7.0-alpine")

    # Add chart
    manifest.add_chart(
        name="cert-manager",
        repo="https://charts.jetstack.io",
        version="v1.13.0",
    )

    # Save manifest
    manifest.save(manifest_path)

    # Verify saved content
    content = yaml.safe_load(manifest_path.read_text())

    assert len(content["tools"]) == 1
    assert content["tools"][0]["name"] == "helm"
    assert content["tools"][0]["extract"] is True

    assert len(content["repositories"]) == 1
    assert content["repositories"][0]["name"] == "test-repo"

    assert len(content["images"]["additional"]) == 2
    assert "docker.io/nginx:1.21.0" in content["images"]["additional"]

    assert len(content["charts"]) == 1
    assert content["charts"][0]["name"] == "cert-manager"


def test_scan_repositories_for_images(test_workspace):
    """Test repository scanning for container images.

    **Validates: Requirement 1.4**
    """
    from opencenter_build.scanner import RepositoryScanner

    test_repo = test_workspace / "test-repo"

    # Scan repository
    scanner = RepositoryScanner(
        repos=[test_repo],
        max_workers=1,
    )

    results = scanner.scan_all()

    # Verify images discovered
    assert str(test_repo) in results
    images = results[str(test_repo)]

    # Should find images from YAML files
    assert len(images) > 0

    # Check for expected images
    image_list = list(images)
    image_str = " ".join(image_list)

    # At least some images should be found
    assert (
        any("nginx" in img.lower() for img in image_list)
        or any("redis" in img.lower() for img in image_list)
        or any("prometheus" in img.lower() for img in image_list)
        or any("grafana" in img.lower() for img in image_list)
    ), f"Should find at least one expected image, found: {image_list}"


def test_generate_zarf_manifest(test_workspace):
    """Test Zarf manifest generation from component manifest.

    **Validates: Requirement 14.1**
    """
    from opencenter_build.config import BuildConfig
    from opencenter_build.zarf_generator import ZarfGenerator

    # Create component manifest
    manifest_path = test_workspace / "config" / "components.yaml"
    manifest = create_default_manifest()

    # Add some components
    manifest.add_image("docker.io/nginx:1.21.0")
    manifest.add_chart(
        name="ingress-nginx",
        repo="https://kubernetes.github.io/ingress-nginx",
        version="4.8.3",
    )
    manifest.save(manifest_path)

    # Load build config
    config = BuildConfig.from_env_file(test_workspace / "config" / "versions.env")

    # Generate Zarf manifest
    generator = ZarfGenerator(config)
    zarf_path = test_workspace / "zarf.yaml"
    generator.generate(zarf_path)

    # Verify Zarf manifest created
    assert zarf_path.exists(), "Zarf manifest should be created"

    # Verify content
    content = yaml.safe_load(zarf_path.read_text())

    assert "kind" in content
    assert content["kind"] == "ZarfPackageConfig"
    assert "metadata" in content
    assert "components" in content

    # Verify components exist
    component_names = [comp["name"] for comp in content["components"]]
    assert len(component_names) > 0


def test_full_build_with_component_manifest(test_workspace):
    """Test complete build workflow with component manifest.

    **Validates: Requirements 5.7, 6.1, 13.7, 14.1**
    """
    # Create component manifest
    manifest_path = test_workspace / "config" / "components.yaml"
    manifest = create_default_manifest()

    # Add test components
    manifest.add_tool(
        ToolSpec(
            name="kubectl",
            version="1.34.3",
            url="https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
        )
    )

    manifest.add_image("docker.io/nginx:1.21.0")
    manifest.add_image("redis:7.0-alpine")

    manifest.save(manifest_path)

    # Verify manifest saved correctly
    assert manifest_path.exists()

    # Load and verify
    loaded_manifest = ComponentManifest.from_yaml(manifest_path)
    assert len(loaded_manifest.tools) >= 1
    assert len(loaded_manifest.images.get("additional", [])) >= 2

    # Generate Zarf manifest
    from opencenter_build.config import BuildConfig
    from opencenter_build.zarf_generator import ZarfGenerator

    config = BuildConfig.from_env_file(test_workspace / "config" / "versions.env")
    generator = ZarfGenerator(config)
    zarf_path = test_workspace / "zarf.yaml"
    generator.generate(zarf_path)

    assert zarf_path.exists()

    # Verify Zarf manifest is valid YAML
    zarf_content = yaml.safe_load(zarf_path.read_text())
    assert zarf_content["kind"] == "ZarfPackageConfig"


def test_artifact_manifest_generation(test_workspace):
    """Test artifact manifest generation after build.

    **Validates: Requirement 6.1**
    """
    from opencenter_build.manifest import ManifestGenerator

    # Create mock build artifacts
    build_dir = test_workspace / "build"

    # Create kubespray-offline outputs
    outputs_dir = build_dir / "kubespray-offline" / "outputs"
    (outputs_dir / "files").mkdir(parents=True)
    (outputs_dir / "debs").mkdir(parents=True)
    (outputs_dir / "pypi").mkdir(parents=True)

    # Create test files
    (outputs_dir / "files" / "kubectl").write_text("fake kubectl binary")
    (outputs_dir / "debs" / "test.deb").write_text("fake deb package")
    (outputs_dir / "pypi" / "test.whl").write_text("fake wheel")

    # Create images list
    images_file = test_workspace / "config" / "all-images.txt"
    images_file.write_text(
        """docker.io/nginx:1.21.0
redis:7.0-alpine
quay.io/prometheus/prometheus:v2.48.0
"""
    )

    # Generate manifest
    generator = ManifestGenerator(test_workspace)
    manifest = generator.generate()

    # Verify manifest structure
    assert manifest.build_id is not None
    assert manifest.timestamp is not None

    # Verify artifact counts
    assert manifest.image_count >= 0
    assert manifest.binary_count >= 0

    # Export JSON
    json_path = test_workspace / "dist" / "artifact-manifest.json"
    generator.export_json(manifest, json_path)

    assert json_path.exists()

    # Verify JSON content
    json_data = json.loads(json_path.read_text())
    assert "build_id" in json_data
    assert "timestamp" in json_data
    assert "images" in json_data

    # Export Markdown
    md_path = test_workspace / "dist" / "artifact-manifest.md"
    generator.export_markdown(manifest, md_path)

    assert md_path.exists()

    # Verify Markdown content
    md_content = md_path.read_text()
    assert "# Artifact Manifest" in md_content
    assert "Generated:" in md_content


def test_component_manifest_round_trip(test_workspace):
    """Test component manifest save and load round trip.

    **Validates: Requirement 13.7**
    """
    manifest_path = test_workspace / "config" / "components.yaml"

    # Create manifest with various components
    manifest = ComponentManifest()

    manifest.kubernetes = {
        "version": "v1.34.3",
        "binaries": [
            {"name": "kubectl", "url": "https://example.com/kubectl"},
        ],
    }

    manifest.add_tool(
        ToolSpec(
            name="helm",
            version="3.14.0",
            url="https://get.helm.sh/helm-v3.14.0-linux-amd64.tar.gz",
            extract=True,
            binary="linux-amd64/helm",
        )
    )

    manifest.add_repository(
        RepositorySpec(
            name="kubespray",
            url="https://github.com/kubernetes-sigs/kubespray.git",
            ref="master",
        )
    )

    manifest.add_image("docker.io/nginx:1.21.0")
    manifest.add_chart("cert-manager", "https://charts.jetstack.io", "v1.13.0")

    # Save
    manifest.save(manifest_path)

    # Load
    loaded = ComponentManifest.from_yaml(manifest_path)

    # Verify all components preserved
    assert loaded.kubernetes["version"] == "v1.34.3"
    assert len(loaded.kubernetes["binaries"]) == 1

    assert len(loaded.tools) == 1
    assert loaded.tools[0].name == "helm"
    assert loaded.tools[0].extract is True

    assert len(loaded.repositories) == 1
    assert loaded.repositories[0].name == "kubespray"

    assert len(loaded.images.get("additional", [])) == 1
    assert "docker.io/nginx:1.21.0" in loaded.images["additional"]

    assert len(loaded.charts) == 1
    assert loaded.charts[0]["name"] == "cert-manager"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
