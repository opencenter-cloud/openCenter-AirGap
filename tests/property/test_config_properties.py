#!/usr/bin/env python3
"""
Property-Based Tests: BuildConfig Parsing

Property 16: Backward Compatible Configuration Parsing

Validates: Requirements 12.1
"""

from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from opencenter_build.config import BuildConfig, parse_versions_env
from opencenter_build.exceptions import ConfigError

# Test configuration
MIN_EXAMPLES = 100
MAX_EXAMPLES = 200


# Hypothesis strategies
version_strategy = st.one_of(
    st.just("v1.34.3"),
    st.just("v2.24.0"),
    st.just("1.6.6"),
    st.just("v2.2.0"),
    st.just("1.21.0"),
    st.just("v1.13.0"),
    st.just("v1.9.0"),
    st.just("21.1.1"),
    st.just("v2.48.0"),
    st.just("10.2.0"),
    st.builds(
        lambda major, minor, patch: f"v{major}.{minor}.{patch}",
        major=st.integers(min_value=1, max_value=3),
        minor=st.integers(min_value=0, max_value=99),
        patch=st.integers(min_value=0, max_value=99),
    ),
)

url_strategy = st.one_of(
    st.just("https://github.com/rackerlabs/opencenter-gitops-base"),
    st.just("https://github.com/kubernetes-sigs/kubespray"),
    st.just("ghcr.io/opencenter-cloud"),
    st.just("docker.io/library"),
    st.builds(
        lambda org, repo: f"https://github.com/{org}/{repo}",
        org=st.text(
            alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=3, max_size=20
        ),
        repo=st.text(
            alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=3, max_size=20
        ),
    ),
)

sha_strategy = st.text(alphabet="0123456789abcdef", min_size=40, max_size=40)


def valid_versions_env_strategy() -> st.SearchStrategy[dict[str, str]]:
    """Strategy for generating valid versions.env content."""
    return st.fixed_dictionaries(
        {
            "KUBERNETES_VERSION": version_strategy,
            "KUBESPRAY_VERSION": version_strategy,
            "KUBESPRAY_COMMIT_SHA": sha_strategy,
            "UBUNTU_VERSION": st.sampled_from(["20.04", "22.04", "24.04"]),
            "CONTAINER_RUNTIME": st.sampled_from(["containerd", "docker"]),
            "CNI_PLUGIN": st.sampled_from(["calico", "flannel", "weave"]),
            "TERRAFORM_VERSION": version_strategy,
            "FLUXCD_VERSION": version_strategy,
            "GITEA_VERSION": version_strategy,
            "CERT_MANAGER_VERSION": version_strategy,
            "INGRESS_NGINX_VERSION": version_strategy,
            "KEYCLOAK_VERSION": version_strategy,
            "PROMETHEUS_VERSION": version_strategy,
            "GRAFANA_VERSION": version_strategy,
            "OPENCENTER_GITOPS_BASE_REPO": url_strategy,
            "OPENCENTER_GITOPS_BASE_VERSION": version_strategy,
            "OPENCENTER_GITOPS_BASE_COMMIT_SHA": sha_strategy,
            "OPENCENTER_CONTAINER_REGISTRY": url_strategy,
            "TARGET_ARCH": st.sampled_from(["amd64", "arm64"]),
            "PYTHON_VERSION": st.sampled_from(["3.10", "3.11", "3.12"]),
        }
    )


def write_versions_env(path: Path, config: dict[str, str]) -> None:
    """Write versions.env file with given configuration."""
    lines = ["# Generated test configuration\n"]
    for key, value in config.items():
        # Quote values with spaces or special characters
        if " " in value or "#" in value:
            lines.append(f'{key}="{value}"\n')
        else:
            lines.append(f"{key}={value}\n")
    path.write_text("".join(lines))


# Property 16: Backward Compatible Configuration Parsing
@given(config_data=valid_versions_env_strategy())
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_16_backward_compatible_config_parsing(
    config_data: dict[str, str], tmp_path: Path
) -> None:
    """
    Property 16: Backward Compatible Configuration Parsing

    For any valid versions.env file from the bash-based system, the Python
    system should parse it successfully without modification and extract all
    required fields.

    **Validates: Requirements 12.1**
    """
    # Write versions.env file
    config_file = tmp_path / "versions.env"
    write_versions_env(config_file, config_data)

    # Parse with BuildConfig
    config = BuildConfig.from_env_file(config_file)

    # Verify all required fields are present
    assert config.kubernetes_version == config_data["KUBERNETES_VERSION"]
    assert config.kubespray_version == config_data["KUBESPRAY_VERSION"]
    assert config.kubespray_commit_sha == config_data["KUBESPRAY_COMMIT_SHA"]
    assert config.ubuntu_version == config_data["UBUNTU_VERSION"]
    assert config.container_runtime == config_data["CONTAINER_RUNTIME"]
    assert config.cni_plugin == config_data["CNI_PLUGIN"]
    assert config.terraform_version == config_data["TERRAFORM_VERSION"]
    assert config.fluxcd_version == config_data["FLUXCD_VERSION"]
    assert config.gitea_version == config_data["GITEA_VERSION"]
    assert config.cert_manager_version == config_data["CERT_MANAGER_VERSION"]
    assert config.ingress_nginx_version == config_data["INGRESS_NGINX_VERSION"]
    assert config.keycloak_version == config_data["KEYCLOAK_VERSION"]
    assert config.prometheus_version == config_data["PROMETHEUS_VERSION"]
    assert config.grafana_version == config_data["GRAFANA_VERSION"]
    assert config.opencenter_gitops_base_repo == config_data["OPENCENTER_GITOPS_BASE_REPO"]
    assert config.opencenter_gitops_base_version == config_data["OPENCENTER_GITOPS_BASE_VERSION"]
    assert (
        config.opencenter_gitops_base_commit_sha == config_data["OPENCENTER_GITOPS_BASE_COMMIT_SHA"]
    )
    assert config.opencenter_container_registry == config_data["OPENCENTER_CONTAINER_REGISTRY"]
    assert config.target_arch == config_data["TARGET_ARCH"]
    assert config.python_version == config_data["PYTHON_VERSION"]

    # Verify raw_config contains all fields
    assert len(config.raw_config) >= len(config_data)
    for key in config_data:
        assert key in config.raw_config


# Property 16: Configuration Hash Determinism
@given(config_data=valid_versions_env_strategy())
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_16_config_hash_determinism(config_data: dict[str, str], tmp_path: Path) -> None:
    """
    Property 16: Configuration Hash Determinism

    For any configuration, the hash should be deterministic - parsing the
    same configuration multiple times should produce the same hash.

    **Validates: Requirements 12.1**
    """
    # Write versions.env file
    config_file = tmp_path / "versions.env"
    write_versions_env(config_file, config_data)

    # Parse multiple times
    config1 = BuildConfig.from_env_file(config_file)
    config2 = BuildConfig.from_env_file(config_file)

    # Verify hashes are identical
    hash1 = config1.hash()
    hash2 = config2.hash()

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hex digest length


# Property 16: Configuration with Comments and Empty Lines
@given(
    config_data=valid_versions_env_strategy(),
    num_comments=st.integers(min_value=0, max_value=10),
    num_empty_lines=st.integers(min_value=0, max_value=10),
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_16_config_with_comments_and_empty_lines(
    config_data: dict[str, str], num_comments: int, num_empty_lines: int, tmp_path: Path
) -> None:
    """
    Property 16: Configuration with Comments and Empty Lines

    For any configuration with comments and empty lines (common in bash
    scripts), parsing should ignore them and extract only variable assignments.

    **Validates: Requirements 12.1**
    """
    # Write versions.env file with comments and empty lines
    config_file = tmp_path / "versions.env"
    lines = ["# Generated test configuration\n"]

    # Add some comments
    for i in range(num_comments):
        lines.append(f"# Comment line {i}\n")

    # Add some empty lines
    for _ in range(num_empty_lines):
        lines.append("\n")

    # Add configuration
    for key, value in config_data.items():
        if " " in value or "#" in value:
            lines.append(f'{key}="{value}"\n')
        else:
            lines.append(f"{key}={value}\n")

    config_file.write_text("".join(lines))

    # Parse with BuildConfig
    config = BuildConfig.from_env_file(config_file)

    # Verify all required fields are present (comments/empty lines ignored)
    assert config.kubernetes_version == config_data["KUBERNETES_VERSION"]
    assert config.kubespray_version == config_data["KUBESPRAY_VERSION"]


# Property 16: Configuration with Quoted Values
@given(config_data=valid_versions_env_strategy())
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_16_config_with_quoted_values(config_data: dict[str, str], tmp_path: Path) -> None:
    """
    Property 16: Configuration with Quoted Values

    For any configuration with quoted values (common in bash scripts),
    parsing should correctly strip quotes and extract the value.

    **Validates: Requirements 12.1**
    """
    # Write versions.env file with all values quoted
    config_file = tmp_path / "versions.env"
    lines = ["# Generated test configuration\n"]
    for key, value in config_data.items():
        lines.append(f'{key}="{value}"\n')
    config_file.write_text("".join(lines))

    # Parse with BuildConfig
    config = BuildConfig.from_env_file(config_file)

    # Verify values are correctly unquoted
    assert config.kubernetes_version == config_data["KUBERNETES_VERSION"]
    assert config.kubespray_version == config_data["KUBESPRAY_VERSION"]

    # Verify no quotes in parsed values
    assert '"' not in config.kubernetes_version
    assert "'" not in config.kubernetes_version


# Property 16: Missing Required Fields Detection
@given(
    config_data=valid_versions_env_strategy(),
    field_to_remove=st.sampled_from(
        ["KUBERNETES_VERSION", "KUBESPRAY_VERSION", "TERRAFORM_VERSION", "FLUXCD_VERSION"]
    ),
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_16_missing_required_fields_detection(
    config_data: dict[str, str], field_to_remove: str, tmp_path: Path
) -> None:
    """
    Property 16: Missing Required Fields Detection

    For any configuration missing a required field, parsing should raise
    ConfigError with a clear message indicating which field is missing.

    **Validates: Requirements 12.1**
    """
    # Remove one required field
    incomplete_config = config_data.copy()
    del incomplete_config[field_to_remove]

    # Write incomplete versions.env file
    config_file = tmp_path / "versions.env"
    write_versions_env(config_file, incomplete_config)

    # Attempt to parse - should raise ConfigError
    with pytest.raises(ConfigError) as exc_info:
        BuildConfig.from_env_file(config_file)

    # Verify error message mentions the missing field
    assert field_to_remove in str(exc_info.value)
    assert "Missing required fields" in str(exc_info.value)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
