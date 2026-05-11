"""Property-based tests for Zarf manifest generation.

This module contains property tests that verify the correctness of Zarf
manifest generation across all valid build configurations.
"""

import tempfile
from pathlib import Path

import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from opencenter_build.config import BuildConfig
from opencenter_build.zarf_generator import ZarfGenerator


@st.composite
def build_config_strategy(draw):
    """Generate valid BuildConfig instances for testing.

    Returns:
        Hypothesis strategy for BuildConfig
    """
    # Generate version strings
    k8s_version = draw(st.sampled_from(["v1.34.3", "v1.33.0", "v1.32.5"]))
    kubespray_version = draw(st.sampled_from(["v2.24.0", "v2.23.0", "v2.22.0"]))
    ubuntu_version = draw(st.sampled_from(["24.04", "22.04", "20.04"]))

    # Generate service versions
    fluxcd_version = draw(st.sampled_from(["v2.2.0", "v2.1.0", "v2.0.0"]))
    gitea_version = draw(st.sampled_from(["1.21.0", "1.20.0", "1.19.0"]))
    cert_manager_version = draw(st.sampled_from(["v1.13.0", "v1.12.0", "v1.11.0"]))
    ingress_nginx_version = draw(st.sampled_from(["v1.9.0", "v1.8.0", "v1.7.0"]))
    keycloak_version = draw(st.sampled_from(["21.1.1", "21.0.0", "20.0.0"]))
    prometheus_version = draw(st.sampled_from(["v2.48.0", "v2.47.0", "v2.46.0"]))
    grafana_version = draw(st.sampled_from(["10.2.0", "10.1.0", "10.0.0"]))

    # Generate commit SHAs (40 hex chars)
    kubespray_sha = draw(st.text(alphabet="0123456789abcdef", min_size=40, max_size=40))
    gitops_sha = draw(st.text(alphabet="0123456789abcdef", min_size=40, max_size=40))

    # Generate gitops version
    gitops_version = draw(st.sampled_from(["v1.0.0", "v0.9.0", "v0.8.0"]))

    return BuildConfig(
        kubernetes_version=k8s_version,
        kubespray_version=kubespray_version,
        kubespray_commit_sha=kubespray_sha,
        ubuntu_version=ubuntu_version,
        container_runtime="containerd",
        cni_plugin="calico",
        terraform_version="1.6.6",
        fluxcd_version=fluxcd_version,
        gitea_version=gitea_version,
        cert_manager_version=cert_manager_version,
        ingress_nginx_version=ingress_nginx_version,
        keycloak_version=keycloak_version,
        prometheus_version=prometheus_version,
        grafana_version=grafana_version,
        opencenter_gitops_base_repo="https://github.com/opencenter-cloud/openCenter-gitops-base",
        opencenter_gitops_base_version=gitops_version,
        opencenter_gitops_base_commit_sha=gitops_sha,
        opencenter_container_registry="ghcr.io/opencenter-cloud",
        target_arch="amd64",
        python_version="3.12",
        repos=[],
        max_workers=4,
        output_dir=Path("dist"),
        raw_config={},
    )


@given(config=build_config_strategy())
@settings(max_examples=100, deadline=None)
def test_property_zarf_configuration_generation(config):
    """Property 7: Zarf Configuration Generation.

    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**

    For any valid BuildConfig, generating zarf.yaml should produce a valid
    Zarf package definition that includes all configured components.

    This property verifies:
    1. Generated manifest is valid YAML
    2. Manifest has required top-level keys (kind, metadata, variables, components)
    3. Metadata contains package information
    4. Variables section defines deployment variables
    5. Components section includes all required components
    6. Each component has proper structure
    """
    generator = ZarfGenerator(config)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "zarf.yaml"
        generator.generate(output_path)

        # Verify file was created
        assert output_path.exists(), "zarf.yaml should be created"

        # Load and parse YAML
        content = output_path.read_text()
        manifest = yaml.safe_load(content)

        # Property 1: Valid YAML structure
        assert isinstance(manifest, dict), "Manifest should be a dictionary"

        # Property 2: Required top-level keys
        assert "kind" in manifest, "Manifest should have 'kind' field"
        assert "metadata" in manifest, "Manifest should have 'metadata' field"
        assert "variables" in manifest, "Manifest should have 'variables' field"
        assert "components" in manifest, "Manifest should have 'components' field"

        # Property 3: Kind is ZarfPackageConfig
        assert manifest["kind"] == "ZarfPackageConfig", "Kind should be ZarfPackageConfig"

        # Property 4: Metadata structure (Requirement 5.1)
        metadata = manifest["metadata"]
        assert isinstance(metadata, dict), "Metadata should be a dictionary"
        assert "name" in metadata, "Metadata should have 'name'"
        assert "description" in metadata, "Metadata should have 'description'"
        assert "version" in metadata, "Metadata should have 'version'"
        assert "architecture" in metadata, "Metadata should have 'architecture'"
        assert metadata["name"] == "opencenter-airgap", "Package name should match"
        assert metadata["architecture"] == config.target_arch, "Architecture should match config"

        # Property 5: Variables section
        variables = manifest["variables"]
        assert isinstance(variables, list), "Variables should be a list"
        assert len(variables) > 0, "Variables should not be empty"

        # Verify required variables exist
        var_names = {var["name"] for var in variables}
        required_vars = {
            "DEPLOYMENT_MODE",
            "BASTION_IP",
            "SSH_USER",
            "INSTALL_PATH",
            "REGISTRY_PORT",
            "NGINX_PORT",
        }
        assert required_vars.issubset(
            var_names
        ), f"Missing required variables: {required_vars - var_names}"

        # Property 6: Components section (Requirements 5.2, 5.3, 5.4, 5.5)
        components = manifest["components"]
        assert isinstance(components, list), "Components should be a list"
        assert len(components) > 0, "Components should not be empty"

        # Verify required components exist
        component_names = {comp["name"] for comp in components}
        required_components = {
            "bootstrap-tools",
            "terraform-providers",
            "kubespray-core",
            "k8s-images",
            "deploy-cluster",
        }
        assert required_components.issubset(
            component_names
        ), f"Missing required components: {required_components - component_names}"

        # Property 7: Each component has proper structure
        for component in components:
            assert "name" in component, "Component should have 'name'"
            assert "description" in component, "Component should have 'description'"
            assert "required" in component, "Component should have 'required' field"

            # Verify component has either files, actions, or repos
            has_files = "files" in component and len(component["files"]) > 0
            has_actions = "actions" in component and len(component["actions"]) > 0
            has_repos = "repos" in component
            assert (
                has_files or has_actions or has_repos
            ), f"Component {component['name']} should have files, actions, or repos"

        # Property 8: Bootstrap component structure (Requirement 5.5)
        bootstrap = next((c for c in components if c["name"] == "bootstrap-tools"), None)
        assert bootstrap is not None, "Bootstrap component should exist"
        assert bootstrap["required"] is True, "Bootstrap should be required"
        assert "files" in bootstrap, "Bootstrap should have files"
        assert len(bootstrap["files"]) > 0, "Bootstrap should have file entries"
        assert "actions" in bootstrap, "Bootstrap should have actions"
        assert "onDeploy" in bootstrap["actions"], "Bootstrap should have onDeploy"

        # Property 9: Images component structure (Requirement 5.2)
        images = next((c for c in components if c["name"] == "k8s-images"), None)
        assert images is not None, "Images component should exist"
        assert "actions" in images, "Images component should have actions"

        # Property 10: Kubespray component structure (Requirement 5.3, 5.4)
        kubespray = next((c for c in components if c["name"] == "kubespray-core"), None)
        assert kubespray is not None, "Kubespray component should exist"
        assert kubespray["required"] is True, "Kubespray should be required"
        assert "files" in kubespray, "Kubespray should have files"
        assert len(kubespray["files"]) > 0, "Kubespray should have file entries"

        # Property 11: Terraform component structure (Requirement 5.4)
        terraform = next((c for c in components if c["name"] == "terraform-providers"), None)
        assert terraform is not None, "Terraform component should exist"
        assert terraform["required"] is False, "Terraform should be optional"
        assert "files" in terraform, "Terraform should have files"

        # Property 12: Deploy component structure (Requirement 5.5)
        deploy = next((c for c in components if c["name"] == "deploy-cluster"), None)
        assert deploy is not None, "Deploy component should exist"
        assert deploy["required"] is True, "Deploy should be required"
        assert "actions" in deploy, "Deploy should have actions"
        assert "onDeploy" in deploy["actions"], "Deploy should have onDeploy"
