"""Configuration loading and parsing utilities.

This module provides functions for loading and parsing configuration files
used in the build system, including versions.env and YAML configurations.
"""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from opencenter_build.exceptions import ConfigError


def parse_versions_env(config_file: Path) -> dict[str, str]:
    """Parse versions.env file into dictionary.

    Parses shell variable assignments from versions.env, ignoring comments
    and empty lines. Supports quoted and unquoted values.

    Args:
        config_file: Path to versions.env file

    Returns:
        Dictionary mapping variable names to values

    Raises:
        ConfigError: If file cannot be read or parsed

    Example:
        >>> versions = parse_versions_env(Path("config/versions.env"))
        >>> print(versions["KUBERNETES_VERSION"])
        v1.34.3
    """
    if not config_file.exists():
        raise ConfigError(f"Configuration file not found: {config_file}")

    versions: dict[str, str] = {}

    try:
        content = config_file.read_text()
    except Exception as exc:
        raise ConfigError(f"Failed to read {config_file}: {exc}") from exc

    for line in content.splitlines():
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith("#"):
            continue

        # Parse KEY=VALUE or KEY="VALUE"
        match = re.match(r"^([A-Z_][A-Z0-9_]*)=(.+)$", line)
        if not match:
            continue

        key, value = match.groups()

        # Remove quotes if present
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]

        versions[key] = value

    return versions


def load_versions_env(config_file: Path) -> dict[str, str]:
    """Load versions.env file into dictionary.

    Alias for parse_versions_env for backward compatibility.

    Args:
        config_file: Path to versions.env file

    Returns:
        Dictionary mapping variable names to values

    Raises:
        ConfigError: If file cannot be read or parsed
    """
    return parse_versions_env(config_file)


def load_yaml_config(config_file: Path) -> dict[str, Any]:
    """Load YAML configuration file.

    Args:
        config_file: Path to YAML file

    Returns:
        Parsed YAML content as dictionary

    Raises:
        ConfigError: If file cannot be read or parsed

    Example:
        >>> nodes = load_yaml_config(Path("config/nodes.yaml"))
        >>> print(nodes["control_plane"])
    """
    if not config_file.exists():
        raise ConfigError(f"Configuration file not found: {config_file}")

    try:
        content = config_file.read_text()
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            raise ConfigError(f"Expected YAML dict, got {type(data).__name__}")
        return data
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse YAML in {config_file}: {exc}") from exc
    except Exception as exc:
        raise ConfigError(f"Failed to read {config_file}: {exc}") from exc


def write_yaml_config(config_file: Path, data: dict[str, Any]) -> None:
    """Write configuration to YAML file.

    Args:
        config_file: Path to output YAML file
        data: Dictionary to write as YAML

    Raises:
        ConfigError: If file cannot be written
    """
    try:
        config_file.parent.mkdir(parents=True, exist_ok=True)
        content = yaml.safe_dump(data, default_flow_style=False, sort_keys=False)
        config_file.write_text(content)
    except Exception as exc:
        raise ConfigError(f"Failed to write {config_file}: {exc}") from exc


@dataclass
class BuildConfig:
    """Build configuration loaded from versions.env.

    This dataclass represents the complete build configuration parsed from
    versions.env. It validates required fields and provides a configuration
    hash for change detection.

    Attributes:
        kubernetes_version: Kubernetes version (e.g., "v1.34.3")
        kubespray_version: Kubespray version tag
        kubespray_commit_sha: Kubespray commit SHA for reproducibility
        ubuntu_version: Target Ubuntu version
        container_runtime: Container runtime (containerd, docker)
        cni_plugin: CNI plugin (calico, flannel, etc.)
        terraform_version: Terraform version for OpenStack deployments
        fluxcd_version: FluxCD version
        gitea_version: Gitea version
        cert_manager_version: cert-manager version
        ingress_nginx_version: ingress-nginx version
        keycloak_version: Keycloak version
        prometheus_version: Prometheus version
        grafana_version: Grafana version
        opencenter_gitops_base_repo: openCenter GitOps base repository URL
        opencenter_gitops_base_version: openCenter GitOps base version
        opencenter_gitops_base_commit_sha: openCenter GitOps base commit SHA
        opencenter_container_registry: Container registry URL
        target_arch: Target architecture (amd64, arm64)
        python_version: Python version
        repos: List of repository paths to scan
        max_workers: Maximum worker processes for concurrent operations
        output_dir: Output directory for build artifacts
        raw_config: Raw configuration dictionary from versions.env
    """

    # Kubernetes and Kubespray
    kubernetes_version: str
    kubespray_version: str
    kubespray_commit_sha: str

    # Target OS
    ubuntu_version: str

    # Container runtime and CNI
    container_runtime: str
    cni_plugin: str

    # Terraform
    terraform_version: str

    # Core services
    fluxcd_version: str
    gitea_version: str
    cert_manager_version: str
    ingress_nginx_version: str
    keycloak_version: str
    prometheus_version: str
    grafana_version: str

    # openCenter GitOps
    opencenter_gitops_base_repo: str
    opencenter_gitops_base_version: str
    opencenter_gitops_base_commit_sha: str

    # Registry
    opencenter_container_registry: str

    # Build settings
    target_arch: str
    python_version: str

    # Runtime configuration
    repos: list[Path] = field(default_factory=list)
    max_workers: int = 0
    output_dir: Path = field(default_factory=lambda: Path("dist"))

    # Raw configuration for hash calculation
    raw_config: dict[str, str] = field(default_factory=dict, repr=False)

    @classmethod
    def from_env_file(cls, path: Path, **kwargs: Any) -> "BuildConfig":
        """Load configuration from versions.env file.

        Args:
            path: Path to versions.env file
            **kwargs: Additional configuration overrides (repos, max_workers, output_dir)

        Returns:
            BuildConfig instance

        Raises:
            ConfigError: If file cannot be read or required fields are missing

        Example:
            >>> config = BuildConfig.from_env_file(Path("config/versions.env"))
            >>> print(config.kubernetes_version)
            v1.34.3
        """
        raw_config = parse_versions_env(path)

        # Required fields mapping
        required_fields = {
            "KUBERNETES_VERSION": "kubernetes_version",
            "KUBESPRAY_VERSION": "kubespray_version",
            "KUBESPRAY_COMMIT_SHA": "kubespray_commit_sha",
            "UBUNTU_VERSION": "ubuntu_version",
            "CONTAINER_RUNTIME": "container_runtime",
            "CNI_PLUGIN": "cni_plugin",
            "TERRAFORM_VERSION": "terraform_version",
            "FLUXCD_VERSION": "fluxcd_version",
            "GITEA_VERSION": "gitea_version",
            "CERT_MANAGER_VERSION": "cert_manager_version",
            "INGRESS_NGINX_VERSION": "ingress_nginx_version",
            "KEYCLOAK_VERSION": "keycloak_version",
            "PROMETHEUS_VERSION": "prometheus_version",
            "GRAFANA_VERSION": "grafana_version",
            "OPENCENTER_GITOPS_BASE_REPO": "opencenter_gitops_base_repo",
            "OPENCENTER_GITOPS_BASE_VERSION": "opencenter_gitops_base_version",
            "OPENCENTER_GITOPS_BASE_COMMIT_SHA": "opencenter_gitops_base_commit_sha",
            "OPENCENTER_CONTAINER_REGISTRY": "opencenter_container_registry",
            "TARGET_ARCH": "target_arch",
            "PYTHON_VERSION": "python_version",
        }

        # Validate required fields
        missing_fields = [key for key in required_fields if key not in raw_config]
        if missing_fields:
            raise ConfigError(f"Missing required fields in {path}: {', '.join(missing_fields)}")

        # Build kwargs for dataclass
        config_kwargs: dict[str, Any] = {
            field_name: raw_config[env_key] for env_key, field_name in required_fields.items()
        }

        # Add runtime configuration
        config_kwargs["repos"] = kwargs.get("repos", [])
        config_kwargs["max_workers"] = kwargs.get("max_workers", 0)
        config_kwargs["output_dir"] = kwargs.get("output_dir", Path("dist"))
        config_kwargs["raw_config"] = raw_config

        return cls(**config_kwargs)

    def hash(self) -> str:
        """Generate SHA256 hash of configuration.

        The hash is calculated from the raw configuration dictionary to detect
        configuration changes. This enables cache invalidation and rebuild
        detection.

        Returns:
            Hexadecimal SHA256 hash string

        Example:
            >>> config = BuildConfig.from_env_file(Path("config/versions.env"))
            >>> config_hash = config.hash()
            >>> print(len(config_hash))
            64
        """
        # Sort keys for deterministic hash
        sorted_items = sorted(self.raw_config.items())
        config_str = "\n".join(f"{key}={value}" for key, value in sorted_items)
        return hashlib.sha256(config_str.encode("utf-8")).hexdigest()
