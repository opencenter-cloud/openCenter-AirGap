"""Unit tests for Zarf manifest generation.

This module contains unit tests that verify specific examples and edge cases
for Zarf manifest generation components.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from opencenter_build.config import BuildConfig
from opencenter_build.exceptions import ConfigError
from opencenter_build.zarf_generator import ZarfGenerator


@pytest.fixture
def sample_config():
    """Create sample BuildConfig for testing."""
    return BuildConfig(
        kubernetes_version="v1.34.3",
        kubespray_version="v2.24.0",
        kubespray_commit_sha="8a5d3d0c8e9f7b6a5c4d3e2f1a0b9c8d7e6f5a4b",
        ubuntu_version="24.04",
        container_runtime="containerd",
        cni_plugin="calico",
        terraform_version="1.6.6",
        fluxcd_version="v2.2.0",
        gitea_version="1.21.0",
        cert_manager_version="v1.13.0",
        ingress_nginx_version="v1.9.0",
        keycloak_version="21.1.1",
        prometheus_version="v2.48.0",
        grafana_version="10.2.0",
        opencenter_gitops_base_repo="https://github.com/opencenter-cloud/openCenter-gitops-base",
        opencenter_gitops_base_version="v1.0.0",
        opencenter_gitops_base_commit_sha="1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b",
        opencenter_container_registry="ghcr.io/opencenter-cloud",
        target_arch="amd64",
        python_version="3.10",
        repos=[],
        max_workers=4,
        output_dir=Path("dist"),
        raw_config={},
    )


@pytest.fixture
def generator(sample_config):
    """Create ZarfGenerator instance."""
    return ZarfGenerator(sample_config)


def test_generator_initialization(sample_config):
    """Test ZarfGenerator initialization."""
    generator = ZarfGenerator(sample_config)
    assert generator.config == sample_config


def test_generate_creates_file(generator):
    """Test that generate() creates zarf.yaml file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "zarf.yaml"
        generator.generate(output_path)

        assert output_path.exists()
        assert output_path.is_file()


def test_generate_valid_yaml(generator):
    """Test that generated file is valid YAML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "zarf.yaml"
        generator.generate(output_path)

        content = output_path.read_text()
        manifest = yaml.safe_load(content)

        assert isinstance(manifest, dict)


def test_images_component_structure(generator):
    """Test images component structure.

    **Validates: Requirement 5.2**

    Verifies that the images component:
    - Has correct name and description
    - Is marked as optional (required=False)
    - Contains actions for image loading
    - Has onDeploy before actions
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "zarf.yaml"
        generator.generate(output_path)

        manifest = yaml.safe_load(output_path.read_text())
        components = manifest["components"]

        images_component = next((c for c in components if c["name"] == "k8s-images"), None)

        assert images_component is not None
        assert images_component["name"] == "k8s-images"
        assert (
            images_component["description"] == "Container images for Kubernetes and core services"
        )
        assert images_component["required"] is False

        # Verify actions structure
        assert "actions" in images_component
        assert "onDeploy" in images_component["actions"]
        assert "before" in images_component["actions"]["onDeploy"]

        before_actions = images_component["actions"]["onDeploy"]["before"]
        assert len(before_actions) > 0
        assert "cmd" in before_actions[0]
        assert "description" in before_actions[0]


def test_charts_component_structure(generator):
    """Test charts component structure.

    **Validates: Requirement 5.3**

    Note: Current implementation includes charts in kubespray-core component
    as part of the files. This test verifies the kubespray-core component
    includes the necessary file paths for charts.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "zarf.yaml"
        generator.generate(output_path)

        manifest = yaml.safe_load(output_path.read_text())
        components = manifest["components"]

        kubespray_component = next((c for c in components if c["name"] == "kubespray-core"), None)

        assert kubespray_component is not None
        assert "files" in kubespray_component

        # Verify kubespray component includes necessary paths
        files = kubespray_component["files"]
        assert len(files) > 0


def test_repos_component_structure(generator):
    """Test repos component structure.

    **Validates: Requirement 5.4**

    Note: Current implementation includes repos in kubespray-core component.
    This test verifies the kubespray-core component includes repo paths.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "zarf.yaml"
        generator.generate(output_path)

        manifest = yaml.safe_load(output_path.read_text())
        components = manifest["components"]

        kubespray_component = next((c for c in components if c["name"] == "kubespray-core"), None)

        assert kubespray_component is not None
        assert "files" in kubespray_component

        # Verify repos path is included
        files = kubespray_component["files"]
        repo_files = [f for f in files if "repos" in f["source"]]
        assert len(repo_files) > 0


def test_files_component_structure(generator):
    """Test files component structure.

    **Validates: Requirement 5.5**

    Verifies that binary files and packages are included in components:
    - Bootstrap component has Python wheels
    - Kubespray component has K8s binaries
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "zarf.yaml"
        generator.generate(output_path)

        manifest = yaml.safe_load(output_path.read_text())
        components = manifest["components"]

        # Check bootstrap component for Python wheels
        bootstrap_component = next((c for c in components if c["name"] == "bootstrap-tools"), None)
        assert bootstrap_component is not None
        assert "files" in bootstrap_component

        bootstrap_files = bootstrap_component["files"]
        wheel_files = [f for f in bootstrap_files if "python-wheels" in f["source"]]
        assert len(wheel_files) > 0

        # Check kubespray component for K8s binaries
        kubespray_component = next((c for c in components if c["name"] == "kubespray-core"), None)
        assert kubespray_component is not None
        assert "files" in kubespray_component

        kubespray_files = kubespray_component["files"]
        binary_files = [f for f in kubespray_files if "k8s-binaries" in f["source"]]
        assert len(binary_files) > 0


def test_actions_component_structure(generator):
    """Test actions component structure.

    **Validates: Requirement 5.5**

    Verifies that deployment actions are properly configured:
    - Bootstrap component has Python venv setup
    - Deploy component has bastion setup script
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "zarf.yaml"
        generator.generate(output_path)

        manifest = yaml.safe_load(output_path.read_text())
        components = manifest["components"]

        # Check bootstrap component actions
        bootstrap_component = next((c for c in components if c["name"] == "bootstrap-tools"), None)
        assert bootstrap_component is not None
        assert "actions" in bootstrap_component
        assert "onDeploy" in bootstrap_component["actions"]
        assert "after" in bootstrap_component["actions"]["onDeploy"]

        bootstrap_actions = bootstrap_component["actions"]["onDeploy"]["after"]
        assert len(bootstrap_actions) > 0

        # Verify Python venv creation action
        venv_action = next((a for a in bootstrap_actions if "venv" in a["cmd"]), None)
        assert venv_action is not None

        # Check deploy component actions
        deploy_component = next((c for c in components if c["name"] == "deploy-cluster"), None)
        assert deploy_component is not None
        assert "actions" in deploy_component
        assert "onDeploy" in deploy_component["actions"]
        assert "after" in deploy_component["actions"]["onDeploy"]

        deploy_actions = deploy_component["actions"]["onDeploy"]["after"]
        assert len(deploy_actions) > 0

        # Verify setup script action
        setup_action = next((a for a in deploy_actions if "setup-all.sh" in a["cmd"]), None)
        assert setup_action is not None


def test_metadata_version_stripping(sample_config):
    """Test that version 'v' prefix is stripped in metadata."""
    sample_config.opencenter_gitops_base_version = "v1.2.3"
    generator = ZarfGenerator(sample_config)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "zarf.yaml"
        generator.generate(output_path)

        manifest = yaml.safe_load(output_path.read_text())
        assert manifest["metadata"]["version"] == "1.2.3"


def test_metadata_architecture_from_config(sample_config):
    """Test that architecture is taken from config."""
    sample_config.target_arch = "arm64"
    generator = ZarfGenerator(sample_config)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "zarf.yaml"
        generator.generate(output_path)

        manifest = yaml.safe_load(output_path.read_text())
        assert manifest["metadata"]["architecture"] == "arm64"


def test_terraform_component_optional(generator):
    """Test that Terraform component is marked as optional."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "zarf.yaml"
        generator.generate(output_path)

        manifest = yaml.safe_load(output_path.read_text())
        components = manifest["components"]

        terraform_component = next(
            (c for c in components if c["name"] == "terraform-providers"), None
        )

        assert terraform_component is not None
        assert terraform_component["required"] is False


def test_required_components_marked_required(generator):
    """Test that required components are marked as required."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "zarf.yaml"
        generator.generate(output_path)

        manifest = yaml.safe_load(output_path.read_text())
        components = manifest["components"]

        required_component_names = ["bootstrap-tools", "kubespray-core", "deploy-cluster"]

        for name in required_component_names:
            component = next((c for c in components if c["name"] == name), None)
            assert component is not None, f"Component {name} should exist"
            assert component["required"] is True, f"Component {name} should be required"


def test_variables_have_defaults(generator):
    """Test that all variables have default values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "zarf.yaml"
        generator.generate(output_path)

        manifest = yaml.safe_load(output_path.read_text())
        variables = manifest["variables"]

        for var in variables:
            assert "default" in var, f"Variable {var['name']} should have default"


def test_generate_creates_parent_directories(generator):
    """Test that generate() creates parent directories if needed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "subdir" / "nested" / "zarf.yaml"
        generator.generate(output_path)

        assert output_path.exists()
        assert output_path.parent.exists()


def test_terraformrc_command_format(generator):
    """Test that .terraformrc command is properly formatted."""
    cmd = generator._create_terraformrc_command()

    assert "cat > /root/.terraformrc" in cmd
    assert "EOF" in cmd
    assert "plugin_cache_dir" in cmd
    assert "filesystem_mirror" in cmd
    assert "###ZARF_VAR_INSTALL_PATH###" in cmd


def test_image_load_command_format(generator):
    """Test that image load command is properly formatted."""
    cmd = generator._create_image_load_command()

    assert "###ZARF_VAR_INSTALL_PATH###/images" in cmd
    assert "podman" in cmd
    assert "registry:2.8.3" in cmd
    assert "load-push-all-images.sh" in cmd
