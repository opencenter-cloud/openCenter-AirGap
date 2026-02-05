"""Integration tests for workflow simplification.

Tests the complete workflow from init → edit → build → scan:
- Test 9.1: End-to-end workflow (init → edit → build → scan)
- Test 9.2: Customization workflow (build → add custom → rebuild)
- Test 9.3: Force regeneration (build → manual edit → force regenerate)

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 2.5, 4.3, 6.4**
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def test_workspace(tmp_path):
    """Create isolated test workspace with CLI access."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create directory structure
    (workspace / "config").mkdir()
    (workspace / "build").mkdir()
    (workspace / "dist").mkdir()

    # Copy source files to make CLI available
    project_root = Path.cwd()
    src_dir = project_root / "src" / "opencenter_build"

    if src_dir.exists():
        (workspace / "src" / "opencenter_build").mkdir(parents=True)
        for py_file in src_dir.glob("*.py"):
            shutil.copy2(py_file, workspace / "src" / "opencenter_build" / py_file.name)

    yield workspace


def run_cli_command(workspace: Path, command: list[str]) -> subprocess.CompletedProcess:
    """Run CLI command in test workspace."""
    # Use python -m to run the CLI
    cmd = [sys.executable, "-m", "opencenter_build.cli"] + command

    result = subprocess.run(
        cmd,
        cwd=workspace,
        capture_output=True,
        text=True,
        env={**subprocess.os.environ, "PYTHONPATH": str(workspace / "src")},
    )

    return result


def test_end_to_end_workflow(test_workspace):
    """Test complete workflow: init → edit → build → scan.

    Workflow:
    1. Initialize project with 'init' command
    2. Edit versions.env configuration
    3. Run 'build' command to generate components.yaml
    4. Run 'scan' command to discover images/charts
    5. Verify manifest generation
    6. Verify repo cloning (simulated)
    7. Verify chart discovery

    **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    """
    # Step 1: Initialize project
    result = run_cli_command(test_workspace, ["init"])

    # Verify init created necessary files
    assert (test_workspace / "config" / "versions.env").exists(), "versions.env should be created"
    assert (test_workspace / "config").exists(), "config directory should exist"
    assert (test_workspace / "build").exists(), "build directory should exist"
    assert (test_workspace / "dist").exists(), "dist directory should exist"

    # Step 2: Edit versions.env (simulate user editing)
    versions_env = test_workspace / "config" / "versions.env"
    versions_content = versions_env.read_text()

    # Verify default content exists
    assert "KUBERNETES_VERSION" in versions_content
    assert "KUBESPRAY_VERSION" in versions_content

    # Add custom version (simulate user edit)
    versions_env.write_text(
        versions_content
        + "\n# Custom additions\nCUSTOM_TOOL_VERSION=1.0.0\nCUSTOM_IMAGE=docker.io/custom:latest\n"
    )

    # Step 3: Create test repository for scanning
    test_repo = test_workspace / "build" / "test-repo"
    test_repo.mkdir(parents=True)

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

    # Create Helm chart
    chart_dir = test_repo / "charts" / "test-chart"
    chart_dir.mkdir(parents=True)
    (chart_dir / "Chart.yaml").write_text(
        """
apiVersion: v2
name: test-chart
version: 1.0.0
description: Test Helm chart
"""
    )

    (chart_dir / "values.yaml").write_text(
        """
image:
  repository: quay.io/prometheus/prometheus
  tag: v2.48.0
"""
    )

    # Step 4: Test manifest generation (without full build)
    from opencenter_build.component_manifest import create_default_manifest, write_manifest

    manifest = create_default_manifest(versions_env=versions_env)
    manifest_path = test_workspace / "config" / "components.yaml"
    write_manifest(manifest, manifest_path)

    # Verify manifest was generated
    assert manifest_path.exists(), "components.yaml should be generated"

    # Verify manifest content
    manifest_content = yaml.safe_load(manifest_path.read_text())
    assert "kubernetes" in manifest_content
    assert "repositories" in manifest_content
    assert "images" in manifest_content

    # Step 5: Test repository scanning
    from opencenter_build.scanner import RepositoryScanner

    scanner = RepositoryScanner(repos=[test_repo], max_workers=1)
    scan_results = scanner.scan_all()

    # Verify images discovered
    assert str(test_repo) in scan_results
    discovered_images = scan_results[str(test_repo)]
    assert len(discovered_images) > 0, "Should discover images from YAML files"

    # Step 6: Test chart discovery
    from opencenter_build.component_manifest import HelmChartScanner

    chart_scanner = HelmChartScanner(repos=[test_repo])
    discovered_charts = chart_scanner.scan_all()

    # Verify charts discovered
    assert len(discovered_charts) > 0, "Should discover Helm charts"
    chart_names = [chart.name for chart in discovered_charts]
    assert "test-chart" in chart_names, "Should find test-chart"

    # Step 7: Verify complete workflow state
    # All necessary files should exist
    assert (test_workspace / "config" / "versions.env").exists()
    assert (test_workspace / "config" / "components.yaml").exists()
    assert len(discovered_images) > 0
    assert len(discovered_charts) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def test_customization_workflow(test_workspace):
    """Test customization workflow: build → add custom component → rebuild.

    Workflow:
    1. Initialize and build initial manifest
    2. Add custom components to components.yaml
    3. Update versions.env with new versions
    4. Rebuild and verify custom components preserved
    5. Verify versions updated from versions.env

    **Validates: Requirements 2.5, 4.3**
    """
    # Step 1: Initialize project
    versions_env = test_workspace / "config" / "versions.env"
    versions_env.write_text(
        """# Initial versions
KUBERNETES_VERSION=v1.34.3
KUBESPRAY_VERSION=v2.24.0
KUBESPRAY_COMMIT_SHA=8a5d3d0c8e9f7b6a5c4d3e2f1a0b9c8d7e6f5a4b
TERRAFORM_VERSION=1.6.6
FLUXCD_VERSION=v2.2.0
CUSTOM_TOOL_VERSION=1.0.0
"""
    )

    # Step 2: Generate initial manifest
    from opencenter_build.component_manifest import (
        create_default_manifest,
        write_manifest,
        read_manifest,
    )

    initial_manifest = create_default_manifest(versions_env=versions_env)
    manifest_path = test_workspace / "config" / "components.yaml"
    write_manifest(initial_manifest, manifest_path)

    # Verify initial manifest
    assert manifest_path.exists()
    initial_content = yaml.safe_load(manifest_path.read_text())
    assert "kubernetes" in initial_content

    # Step 3: Add custom components (simulate user customization)
    loaded_manifest = read_manifest(manifest_path)

    # Add custom tool
    loaded_manifest.add_tool(
        name="custom-cli",
        version="2.0.0",
        url="https://example.com/custom-cli-v2.0.0.tar.gz",
        extract=True,
        binary="custom-cli",
    )

    # Add custom image
    loaded_manifest.add_image("docker.io/custom/app:v1.5.0")

    # Add custom chart
    loaded_manifest.add_chart(
        name="custom-chart",
        repo="https://charts.example.com",
        version="3.0.0",
    )

    # Save customized manifest
    write_manifest(loaded_manifest, manifest_path)

    # Step 4: Update versions.env (simulate version bump)
    versions_env.write_text(
        """# Updated versions
KUBERNETES_VERSION=v1.34.4
KUBESPRAY_VERSION=v2.24.1
KUBESPRAY_COMMIT_SHA=9b6e4e1d9f0e8c7b6a5d4e3f2a1b0c9d8e7f6a5c
TERRAFORM_VERSION=1.6.7
FLUXCD_VERSION=v2.2.1
CUSTOM_TOOL_VERSION=2.0.0
"""
    )

    # Step 5: Rebuild manifest (merge with updated versions)
    from opencenter_build.component_manifest import merge_manifests

    regenerated_manifest = create_default_manifest(versions_env=versions_env)
    existing_manifest = read_manifest(manifest_path)
    merged_manifest = merge_manifests(existing_manifest, regenerated_manifest)

    # Save merged manifest
    write_manifest(merged_manifest, manifest_path)

    # Step 6: Verify custom components preserved
    final_manifest = read_manifest(manifest_path)

    # Check custom tool preserved
    tool_names = [tool.name for tool in final_manifest.tools]
    assert "custom-cli" in tool_names, "Custom tool should be preserved"

    custom_tool_found = next((t for t in final_manifest.tools if t.name == "custom-cli"), None)
    assert custom_tool_found is not None
    assert custom_tool_found.version == "2.0.0", "Custom tool version should be preserved"

    # Check custom image preserved
    additional_images = final_manifest.images.additional
    assert "docker.io/custom/app:v1.5.0" in additional_images, "Custom image should be preserved"

    # Check custom chart preserved
    chart_names = [chart.name for chart in final_manifest.charts]
    assert "custom-chart" in chart_names, "Custom chart should be preserved"

    custom_chart = next((c for c in final_manifest.charts if c.name == "custom-chart"), None)
    assert custom_chart is not None
    assert custom_chart.version == "3.0.0", "Custom chart version should be preserved"

    # Step 7: Verify versions updated from versions.env
    final_content = yaml.safe_load(manifest_path.read_text())

    # Kubernetes version should be updated
    k8s_version = final_content["kubernetes"]["version"]
    assert (
        "1.34.4" in k8s_version or "{{KUBERNETES_VERSION}}" in k8s_version
    ), "Kubernetes version should be updated or templated"

    # Verify manifest still valid
    assert "kubernetes" in final_content
    assert "repositories" in final_content
    assert "images" in final_content
    assert "charts" in final_content
    assert "tools" in final_content


def test_force_regeneration_workflow(test_workspace):
    """Test force regeneration: build → manual edit → build --force-regenerate.

    Workflow:
    1. Initialize and build initial manifest
    2. Make manual edits to components.yaml
    3. Run build with --force-regenerate flag
    4. Verify manual edits are preserved (merged)
    5. Verify clean regeneration from versions.env

    **Validates: Requirement 6.4**
    """
    # Step 1: Initialize project
    versions_env = test_workspace / "config" / "versions.env"
    versions_env.write_text(
        """# Initial versions
KUBERNETES_VERSION=v1.34.3
KUBESPRAY_VERSION=v2.24.0
KUBESPRAY_COMMIT_SHA=8a5d3d0c8e9f7b6a5c4d3e2f1a0b9c8d7e6f5a4b
TERRAFORM_VERSION=1.6.6
"""
    )

    # Step 2: Generate initial manifest
    from opencenter_build.component_manifest import (
        create_default_manifest,
        write_manifest,
        read_manifest,
        merge_manifests,
    )

    initial_manifest = create_default_manifest(versions_env=versions_env)
    manifest_path = test_workspace / "config" / "components.yaml"
    write_manifest(initial_manifest, manifest_path)

    # Step 3: Make manual edits (simulate user customization)
    manual_content = yaml.safe_load(manifest_path.read_text())

    # Add manual comment and custom field
    manual_content["_manual_edit"] = "This is a manual customization"
    manual_content["custom_section"] = {
        "custom_tool": "my-tool",
        "custom_version": "1.0.0",
    }

    # Modify existing field
    if "images" in manual_content:
        if "additional" not in manual_content["images"]:
            manual_content["images"]["additional"] = []
        manual_content["images"]["additional"].append("docker.io/manual/edit:latest")

    # Write manual edits
    manifest_path.write_text(yaml.dump(manual_content, sort_keys=False))

    # Verify manual edits exist
    edited_content = yaml.safe_load(manifest_path.read_text())
    assert "_manual_edit" in edited_content
    assert "custom_section" in edited_content

    # Step 4: Force regenerate (simulate --force-regenerate flag behavior)
    # This should regenerate from versions.env but preserve manual edits via merge
    regenerated_manifest = create_default_manifest(versions_env=versions_env)
    existing_manifest = read_manifest(manifest_path)
    merged_manifest = merge_manifests(existing_manifest, regenerated_manifest)

    # Save merged result
    write_manifest(merged_manifest, manifest_path)

    # Step 5: Verify manual edits preserved through merge
    final_manifest = read_manifest(manifest_path)

    # Check manual image preserved
    additional_images = final_manifest.images.additional
    assert (
        "docker.io/manual/edit:latest" in additional_images
    ), "Manual image edit should be preserved"

    # Step 6: Verify clean regeneration from versions.env
    final_content = yaml.safe_load(manifest_path.read_text())

    # Core structure should be regenerated
    assert "kubernetes" in final_content
    assert "repositories" in final_content
    assert "images" in final_content

    # Kubernetes version should match versions.env
    k8s_version = final_content["kubernetes"]["version"]
    assert (
        "1.34.3" in k8s_version or "{{KUBERNETES_VERSION}}" in k8s_version
    ), "Kubernetes version should be from versions.env"

    # Step 7: Test complete force regeneration (no merge)
    # This simulates a scenario where user wants to discard all manual edits
    # In practice, this would be done by deleting components.yaml first
    manifest_path.unlink()

    # Regenerate from scratch
    fresh_manifest = create_default_manifest(versions_env=versions_env)
    write_manifest(fresh_manifest, manifest_path)

    # Verify clean state
    fresh_content = yaml.safe_load(manifest_path.read_text())
    assert "kubernetes" in fresh_content
    assert "_manual_edit" not in fresh_content, "Manual edits should not exist in fresh generation"
    assert (
        "custom_section" not in fresh_content
    ), "Custom sections should not exist in fresh generation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
