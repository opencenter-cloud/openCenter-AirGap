#!/usr/bin/env python3
"""
Property-Based Tests: Configuration Validation

Property 15: Configuration Validation Completeness

Validates: Requirements 10.2, 10.4
"""

from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck, assume

from opencenter_build.validation import ComprehensiveConfigValidator, ValidationResult
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


# Property 15: Configuration Validation Completeness
# For any configuration with missing required variables or invalid repository paths,
# validation should detect and report all issues.


@given(
    valid_config=valid_versions_env_strategy(),
    missing_vars=st.lists(
        st.sampled_from(ComprehensiveConfigValidator.REQUIRED_VARIABLES),
        min_size=1,
        max_size=5,
        unique=True,
    ),
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_15_missing_variables_detected(
    tmp_path: Path, valid_config: dict[str, str], missing_vars: list[str]
) -> None:
    """
    **Property 15: Configuration Validation Completeness**
    **Validates: Requirements 10.2**

    For any configuration with missing required variables,
    validation should detect and report all missing variables.
    """
    # Remove specified variables
    incomplete_config = {k: v for k, v in valid_config.items() if k not in missing_vars}

    # Write to file
    config_file = tmp_path / "versions.env"
    write_versions_env(config_file, incomplete_config)

    # Validate
    validator = ComprehensiveConfigValidator(config_file=config_file)
    result = validator.validate_all(
        check_repos=False, check_dependencies=False, check_component_manifest=False
    )

    # Property: Validation should fail
    assert not result.passed, "Validation should fail for missing variables"

    # Property: All missing variables should be detected
    error_text = " ".join(result.errors)
    for var in missing_vars:
        assert var in error_text, f"Missing variable {var} should be reported in errors"


@given(valid_config=valid_versions_env_strategy())
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_15_valid_config_passes(tmp_path: Path, valid_config: dict[str, str]) -> None:
    """
    **Property 15: Configuration Validation Completeness**
    **Validates: Requirements 10.2**

    For any valid configuration with all required variables,
    validation should pass without errors.
    """
    # Write to file
    config_file = tmp_path / "versions.env"
    write_versions_env(config_file, valid_config)

    # Validate
    validator = ComprehensiveConfigValidator(config_file=config_file)
    result = validator.validate_all(
        check_repos=False, check_dependencies=False, check_component_manifest=False
    )

    # Property: Validation should pass
    assert result.passed, f"Validation should pass for valid config. Errors: {result.errors}"


@given(
    valid_config=valid_versions_env_strategy(),
    empty_vars=st.lists(
        st.sampled_from(ComprehensiveConfigValidator.REQUIRED_VARIABLES),
        min_size=1,
        max_size=3,
        unique=True,
    ),
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_15_empty_values_treated_as_missing(
    tmp_path: Path, valid_config: dict[str, str], empty_vars: list[str]
) -> None:
    """
    **Property 15: Configuration Validation Completeness**
    **Validates: Requirements 10.2**

    For any configuration with empty variable values,
    validation should treat them as missing (errors).

    Note: The parse_versions_env function skips lines with empty values
    (KEY= or KEY=""), so they are effectively missing variables.
    """
    # Set specified variables to empty
    config_with_empty = valid_config.copy()
    for var in empty_vars:
        config_with_empty[var] = ""

    # Write to file
    config_file = tmp_path / "versions.env"
    write_versions_env(config_file, config_with_empty)

    # Validate
    validator = ComprehensiveConfigValidator(config_file=config_file)
    result = validator.validate_all(
        check_repos=False, check_dependencies=False, check_component_manifest=False
    )

    # Property: Should fail validation (empty values treated as missing)
    assert not result.passed, "Validation should fail for empty values"

    # Property: All empty variables should be mentioned in errors
    error_text = " ".join(result.errors)
    for var in empty_vars:
        assert var in error_text, f"Empty variable {var} should be mentioned in errors"


def test_property_15_missing_file_detected(tmp_path: Path) -> None:
    """
    **Property 15: Configuration Validation Completeness**
    **Validates: Requirements 10.1**

    For any missing configuration file,
    validation should detect and report the error.
    """
    # Use non-existent file
    config_file = tmp_path / "nonexistent.env"

    # Validate
    validator = ComprehensiveConfigValidator(config_file=config_file)
    result = validator.validate_all(
        check_repos=False, check_dependencies=False, check_component_manifest=False
    )

    # Property: Validation should fail
    assert not result.passed, "Validation should fail for missing file"

    # Property: Error should mention the missing file
    error_text = " ".join(result.errors)
    assert "not found" in error_text.lower(), "Error should mention file not found"


@given(valid_config=valid_versions_env_strategy(), num_repos=st.integers(min_value=1, max_value=5))
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_15_missing_repos_warned(
    tmp_path: Path, valid_config: dict[str, str], num_repos: int
) -> None:
    """
    **Property 15: Configuration Validation Completeness**
    **Validates: Requirements 10.4**

    For any configuration with missing repository paths,
    validation should detect and warn about missing repositories.
    """
    # Write valid config
    config_file = tmp_path / "versions.env"
    write_versions_env(config_file, valid_config)

    # Create component manifest with repositories
    component_manifest = tmp_path / "components.yaml"
    repos = []
    for i in range(num_repos):
        repos.append(
            f"  - name: repo{i}\n    url: https://github.com/test/repo{i}\n    ref: main\n"
        )

    manifest_content = "repositories:\n" + "".join(repos)
    component_manifest.write_text(manifest_content)

    # Validate (repositories don't exist in build/ directory)
    validator = ComprehensiveConfigValidator(config_file=config_file)
    result = validator.validate_all(
        check_repos=True,
        check_dependencies=False,
        check_component_manifest=True,
        component_manifest_path=component_manifest,
    )

    # Property: Should have warnings for missing repositories
    assert result.has_warnings, "Validation should warn about missing repositories"

    # Property: All missing repositories should be mentioned
    warning_text = " ".join(result.warnings)
    for i in range(num_repos):
        assert (
            f"repo{i}" in warning_text
        ), f"Missing repository repo{i} should be mentioned in warnings"


@given(valid_config=valid_versions_env_strategy(), num_repos=st.integers(min_value=1, max_value=3))
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_15_existing_repos_pass(
    tmp_path: Path, valid_config: dict[str, str], num_repos: int
) -> None:
    """
    **Property 15: Configuration Validation Completeness**
    **Validates: Requirements 10.4**

    For any configuration with existing repository paths,
    validation should not warn about those repositories.
    """
    # Write valid config
    config_file = tmp_path / "versions.env"
    write_versions_env(config_file, valid_config)

    # Create component manifest with repositories
    component_manifest = tmp_path / "components.yaml"
    repos = []
    for i in range(num_repos):
        repos.append(
            f"  - name: repo{i}\n    url: https://github.com/test/repo{i}\n    ref: main\n"
        )
        # Create the repository directory with .git
        repo_path = tmp_path / "build" / f"repo{i}"
        repo_path.mkdir(parents=True, exist_ok=True)
        (repo_path / ".git").mkdir(exist_ok=True)

    manifest_content = "repositories:\n" + "".join(repos)
    component_manifest.write_text(manifest_content)

    # Change to tmp_path so relative paths work
    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        # Validate
        validator = ComprehensiveConfigValidator(config_file=config_file)
        result = validator.validate_all(
            check_repos=True,
            check_dependencies=False,
            check_component_manifest=True,
            component_manifest_path=component_manifest,
        )

        # Property: Should not have warnings about existing repositories
        warning_text = " ".join(result.warnings)
        for i in range(num_repos):
            assert (
                f"repo{i}" not in warning_text or "not cloned" not in warning_text.lower()
            ), f"Should not warn about existing repository repo{i}"

    finally:
        os.chdir(original_cwd)


def test_property_15_validation_result_consistency() -> None:
    """
    **Property 15: Configuration Validation Completeness**

    ValidationResult should have consistent state:
    - passed is True when errors is empty
    - passed is False when errors is not empty
    - has_warnings is True when warnings is not empty
    """
    # Test with no errors or warnings
    result1 = ValidationResult(errors=[], warnings=[])
    assert result1.passed is True
    assert result1.has_warnings is False

    # Test with errors only
    result2 = ValidationResult(errors=["error1"], warnings=[])
    assert result2.passed is False
    assert result2.has_warnings is False

    # Test with warnings only
    result3 = ValidationResult(errors=[], warnings=["warning1"])
    assert result3.passed is True
    assert result3.has_warnings is True

    # Test with both errors and warnings
    result4 = ValidationResult(errors=["error1"], warnings=["warning1"])
    assert result4.passed is False
    assert result4.has_warnings is True
