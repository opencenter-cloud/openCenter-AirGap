"""Component manifest management for declarative build specifications.

This module provides classes for managing component manifests that declare
what artifacts to collect for air-gap packages. Component manifests are
version-controlled YAML files that specify tools, repositories, images,
charts, and other dependencies.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from opencenter_build.exceptions import ConfigError


@dataclass
class ToolSpec:
    """CLI tool specification.

    Attributes:
        name: Tool name (e.g., "kubectl", "helm")
        version: Tool version
        url: Download URL (supports {{version}} template)
        extract: Whether to extract archive
        binary: Binary path within archive (if extract=True)
        checksum_url: Optional checksum file URL
    """

    name: str
    version: str
    url: str
    extract: bool = False
    binary: str | None = None
    checksum_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result: dict[str, Any] = {
            "name": self.name,
            "version": self.version,
            "url": self.url,
        }
        if self.extract:
            result["extract"] = self.extract
        if self.binary:
            result["binary"] = self.binary
        if self.checksum_url:
            result["checksum_url"] = self.checksum_url
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolSpec":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            version=data["version"],
            url=data["url"],
            extract=data.get("extract", False),
            binary=data.get("binary"),
            checksum_url=data.get("checksum_url"),
        )


@dataclass
class RepositorySpec:
    """Git repository specification.

    Attributes:
        name: Repository name
        url: Git repository URL
        ref: Git ref (branch, tag, or commit SHA)
        type: Repository type (default: "git")
    """

    name: str
    url: str
    ref: str
    type: str = "git"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "name": self.name,
            "url": self.url,
            "ref": self.ref,
            "type": self.type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepositorySpec":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            url=data["url"],
            ref=data["ref"],
            type=data.get("type", "git"),
        )


@dataclass
class ImageDiscoverySpec:
    """Image auto-discovery specification.

    Attributes:
        source: Source reference (e.g., "repositories.kubespray")
        patterns: File patterns to scan for images
    """

    source: str
    patterns: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "source": self.source,
            "patterns": self.patterns,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageDiscoverySpec":
        """Create from dictionary."""
        return cls(
            source=data["source"],
            patterns=data["patterns"],
        )


@dataclass
class ComponentManifest:
    """Complete component manifest.

    Attributes:
        kubernetes: Kubernetes configuration (version, binaries)
        tools: List of CLI tools to collect
        repositories: List of Git repositories
        images: Image configuration (auto_discover, additional)
        charts: List of Helm charts
        os_packages: OS package configuration
        python_packages: Python package configuration
        terraform_providers: List of Terraform providers
    """

    kubernetes: dict[str, Any] = field(default_factory=dict)
    tools: list[ToolSpec] = field(default_factory=list)
    repositories: list[RepositorySpec] = field(default_factory=list)
    images: dict[str, Any] = field(default_factory=dict)
    charts: list[dict[str, Any]] = field(default_factory=list)
    os_packages: dict[str, Any] = field(default_factory=dict)
    python_packages: dict[str, Any] = field(default_factory=dict)
    terraform_providers: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path) -> "ComponentManifest":
        """Load from YAML file.

        Args:
            path: Path to components.yaml

        Returns:
            ComponentManifest instance

        Raises:
            ConfigError: If file cannot be read or parsed
        """
        if not path.exists():
            raise ConfigError(f"Component manifest not found: {path}")

        try:
            content = path.read_text()
            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                raise ConfigError(f"Expected YAML dict, got {type(data).__name__}")

            # Parse tools
            tools = [ToolSpec.from_dict(tool_data) for tool_data in data.get("tools", [])]

            # Parse repositories
            repositories = [
                RepositorySpec.from_dict(repo_data) for repo_data in data.get("repositories", [])
            ]

            return cls(
                kubernetes=data.get("kubernetes", {}),
                tools=tools,
                repositories=repositories,
                images=data.get("images", {}),
                charts=data.get("charts", []),
                os_packages=data.get("os_packages", {}),
                python_packages=data.get("python_packages", {}),
                terraform_providers=data.get("terraform_providers", []),
            )
        except yaml.YAMLError as exc:
            raise ConfigError(f"Failed to parse YAML in {path}: {exc}") from exc
        except Exception as exc:
            raise ConfigError(f"Failed to read {path}: {exc}") from exc

    def add_tool(self, tool: ToolSpec) -> None:
        """Add tool to manifest.

        Args:
            tool: Tool specification to add
        """
        self.tools.append(tool)

    def add_repository(self, repo: RepositorySpec) -> None:
        """Add repository to manifest.

        Args:
            repo: Repository specification to add
        """
        self.repositories.append(repo)

    def add_image(self, image: str) -> None:
        """Add explicit image to manifest.

        Args:
            image: Image reference (e.g., "docker.io/nginx:1.21")
        """
        if "additional" not in self.images:
            self.images["additional"] = []
        self.images["additional"].append(image)

    def add_chart(self, name: str, repo: str, version: str) -> None:
        """Add Helm chart to manifest.

        Args:
            name: Chart name
            repo: Helm repository URL
            version: Chart version
        """
        self.charts.append(
            {
                "name": name,
                "repo": repo,
                "version": version,
            }
        )

    def save(self, path: Path) -> None:
        """Save manifest to YAML file.

        Args:
            path: Output path for components.yaml

        Raises:
            ConfigError: If file cannot be written
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            # Convert to dictionary
            data: dict[str, Any] = {}

            if self.kubernetes:
                data["kubernetes"] = self.kubernetes

            if self.tools:
                data["tools"] = [tool.to_dict() for tool in self.tools]

            if self.repositories:
                data["repositories"] = [repo.to_dict() for repo in self.repositories]

            if self.images:
                data["images"] = self.images

            if self.charts:
                data["charts"] = self.charts

            if self.os_packages:
                data["os_packages"] = self.os_packages

            if self.python_packages:
                data["python_packages"] = self.python_packages

            if self.terraform_providers:
                data["terraform_providers"] = self.terraform_providers

            # Write YAML
            content = yaml.safe_dump(data, default_flow_style=False, sort_keys=False)
            path.write_text(content)
        except Exception as exc:
            raise ConfigError(f"Failed to write {path}: {exc}") from exc


def create_default_manifest() -> ComponentManifest:
    """Create default component manifest with common components.

    Returns:
        ComponentManifest with default configuration
    """
    manifest = ComponentManifest()

    # Kubernetes configuration
    manifest.kubernetes = {
        "version": "{{KUBERNETES_VERSION}}",
        "binaries": [
            {
                "name": "kubectl",
                "url": "https://dl.k8s.io/{{KUBERNETES_VERSION}}/bin/linux/amd64/kubectl",
            },
            {
                "name": "kubelet",
                "url": "https://dl.k8s.io/{{KUBERNETES_VERSION}}/bin/linux/amd64/kubelet",
            },
            {
                "name": "kubeadm",
                "url": "https://dl.k8s.io/{{KUBERNETES_VERSION}}/bin/linux/amd64/kubeadm",
            },
        ],
    }

    # Default repositories
    manifest.repositories = [
        RepositorySpec(
            name="kubespray",
            url="https://github.com/kubernetes-sigs/kubespray.git",
            ref="master",
        ),
    ]

    # Image discovery configuration
    manifest.images = {
        "auto_discover": [
            {
                "source": "repositories.kubespray",
                "patterns": [
                    "roles/*/defaults/main.yml",
                    "inventory/*/group_vars/*.yml",
                ],
            },
        ],
        "additional": [],
    }

    return manifest
