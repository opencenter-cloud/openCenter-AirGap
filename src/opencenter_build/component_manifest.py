"""Component manifest management for declarative artifact specification.

This module provides data models and operations for managing the component
manifest (config/components.yaml), which declares what artifacts to collect
for the air-gap package.
"""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

from opencenter_build.exceptions import ConfigError


@dataclass
class KubernetesComponent:
    """Kubernetes binaries specification.

    Attributes:
        version: Kubernetes version
        binaries: List of binary specifications with name, url, checksum_url
    """

    version: str
    binaries: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ToolComponent:
    """CLI tool specification.

    Attributes:
        name: Tool name
        version: Tool version
        url: Download URL (supports {{version}} template)
        checksum_url: Optional checksum URL
        extract: Whether to extract archive
        binary: Path to binary within archive (if extract=True)
    """

    name: str
    version: str
    url: str
    checksum_url: str | None = None
    extract: bool = False
    binary: str | None = None


@dataclass
class RepositoryComponent:
    """Git repository specification.

    Attributes:
        name: Repository name
        url: Git clone URL
        ref: Git ref (branch, tag, or commit)
        type: Repository type (always 'git')
    """

    name: str
    url: str
    ref: str
    type: str = "git"


@dataclass
class ImageDiscovery:
    """Image auto-discovery configuration.

    Attributes:
        source: Source repository reference (e.g., 'repositories.kubespray')
        patterns: File patterns to scan for images
    """

    source: str
    patterns: list[str] = field(default_factory=list)


@dataclass
class ImagesComponent:
    """Container images specification.

    Attributes:
        auto_discover: List of auto-discovery configurations
        additional: List of explicit image references
    """

    auto_discover: list[ImageDiscovery] = field(default_factory=list)
    additional: list[str] = field(default_factory=list)


@dataclass
class ChartComponent:
    """Helm chart specification.

    Attributes:
        name: Chart name
        repo: Helm repository URL or Git URL
        version: Chart version
        path: Path within Git repo (for Git-based charts)
        ref: Git ref (for Git-based charts)
    """

    name: str
    repo: str
    version: str
    path: str | None = None
    ref: str | None = None


@dataclass
class OSPackagesComponent:
    """OS packages specification.

    Attributes:
        source: Source for packages ('kubespray-offline')
        additional: Additional packages to include
    """

    source: str = "kubespray-offline"
    additional: list[str] = field(default_factory=list)


@dataclass
class PythonPackagesComponent:
    """Python packages specification.

    Attributes:
        source: Source for packages ('kubespray-offline')
        additional: Additional packages with versions
    """

    source: str = "kubespray-offline"
    additional: list[str] = field(default_factory=list)


@dataclass
class TerraformProviderComponent:
    """Terraform provider specification.

    Attributes:
        name: Provider name
        source: Provider source (e.g., 'hashicorp/local')
        version: Provider version
    """

    name: str
    source: str
    version: str


@dataclass
class ComponentManifest:
    """Complete component manifest specification.

    Attributes:
        kubernetes: Kubernetes binaries configuration
        tools: List of CLI tools
        repositories: List of Git repositories
        images: Container images configuration
        charts: List of Helm charts
        os_packages: OS packages configuration
        python_packages: Python packages configuration
        terraform_providers: List of Terraform providers
    """

    kubernetes: KubernetesComponent | None = None
    tools: list[ToolComponent] = field(default_factory=list)
    repositories: list[RepositoryComponent] = field(default_factory=list)
    images: ImagesComponent = field(default_factory=ImagesComponent)
    charts: list[ChartComponent] = field(default_factory=list)
    os_packages: OSPackagesComponent = field(default_factory=OSPackagesComponent)
    python_packages: PythonPackagesComponent = field(
        default_factory=PythonPackagesComponent
    )
    terraform_providers: list[TerraformProviderComponent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary for YAML serialization.

        Returns:
            Dictionary representation
        """
        data = {}

        if self.kubernetes:
            data["kubernetes"] = asdict(self.kubernetes)

        if self.tools:
            data["tools"] = [asdict(tool) for tool in self.tools]

        if self.repositories:
            data["repositories"] = [asdict(repo) for repo in self.repositories]

        if self.images.auto_discover or self.images.additional:
            images_data = {}
            if self.images.auto_discover:
                images_data["auto_discover"] = [
                    asdict(disc) for disc in self.images.auto_discover
                ]
            if self.images.additional:
                images_data["additional"] = self.images.additional
            data["images"] = images_data

        if self.charts:
            data["charts"] = [asdict(chart) for chart in self.charts]

        if self.os_packages.additional:
            data["os_packages"] = asdict(self.os_packages)

        if self.python_packages.additional:
            data["python_packages"] = asdict(self.python_packages)

        if self.terraform_providers:
            data["terraform_providers"] = [
                asdict(provider) for provider in self.terraform_providers
            ]

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ComponentManifest":
        """Create manifest from dictionary.

        Args:
            data: Dictionary with manifest data

        Returns:
            ComponentManifest instance
        """
        manifest = cls()

        # Kubernetes
        if "kubernetes" in data:
            k8s_data = data["kubernetes"]
            manifest.kubernetes = KubernetesComponent(
                version=k8s_data["version"], binaries=k8s_data.get("binaries", [])
            )

        # Tools
        if "tools" in data:
            manifest.tools = [ToolComponent(**tool) for tool in data["tools"]]

        # Repositories
        if "repositories" in data:
            manifest.repositories = [
                RepositoryComponent(**repo) for repo in data["repositories"]
            ]

        # Images
        if "images" in data:
            images_data = data["images"]
            auto_discover = []
            if "auto_discover" in images_data:
                auto_discover = [
                    ImageDiscovery(**disc) for disc in images_data["auto_discover"]
                ]
            additional = images_data.get("additional", [])
            manifest.images = ImagesComponent(
                auto_discover=auto_discover, additional=additional
            )

        # Charts
        if "charts" in data:
            manifest.charts = [ChartComponent(**chart) for chart in data["charts"]]

        # OS packages
        if "os_packages" in data:
            manifest.os_packages = OSPackagesComponent(**data["os_packages"])

        # Python packages
        if "python_packages" in data:
            manifest.python_packages = PythonPackagesComponent(**data["python_packages"])

        # Terraform providers
        if "terraform_providers" in data:
            manifest.terraform_providers = [
                TerraformProviderComponent(**provider)
                for provider in data["terraform_providers"]
            ]

        return manifest

    def add_tool(
        self,
        name: str,
        version: str,
        url: str,
        checksum_url: str | None = None,
        extract: bool = False,
        binary: str | None = None,
    ) -> None:
        """Add tool to manifest.

        Args:
            name: Tool name
            version: Tool version
            url: Download URL
            checksum_url: Optional checksum URL
            extract: Whether to extract archive
            binary: Path to binary within archive
        """
        tool = ToolComponent(
            name=name,
            version=version,
            url=url,
            checksum_url=checksum_url,
            extract=extract,
            binary=binary,
        )
        self.tools.append(tool)

    def add_repository(self, name: str, url: str, ref: str) -> None:
        """Add repository to manifest.

        Args:
            name: Repository name
            url: Git clone URL
            ref: Git ref (branch, tag, or commit)
        """
        repo = RepositoryComponent(name=name, url=url, ref=ref)
        self.repositories.append(repo)

    def add_image(self, image: str) -> None:
        """Add image to manifest.

        Args:
            image: Container image reference
        """
        if image not in self.images.additional:
            self.images.additional.append(image)

    def add_chart(
        self,
        name: str,
        repo: str,
        version: str,
        path: str | None = None,
        ref: str | None = None,
    ) -> None:
        """Add Helm chart to manifest.

        Args:
            name: Chart name
            repo: Helm repository URL or Git URL
            version: Chart version
            path: Path within Git repo (for Git-based charts)
            ref: Git ref (for Git-based charts)
        """
        chart = ChartComponent(name=name, repo=repo, version=version, path=path, ref=ref)
        self.charts.append(chart)


def create_default_manifest(template: str = "baremetal") -> ComponentManifest:
    """Create default component manifest from template.

    Args:
        template: Template name ('baremetal' or 'openstack')

    Returns:
        ComponentManifest with default components
    """
    manifest = ComponentManifest()

    # Kubernetes binaries
    manifest.kubernetes = KubernetesComponent(
        version="1.34.3",
        binaries=[
            {
                "name": "kubectl",
                "url": "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubectl",
                "checksum_url": "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubectl.sha256",
            },
            {
                "name": "kubelet",
                "url": "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubelet",
                "checksum_url": "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubelet.sha256",
            },
            {
                "name": "kubeadm",
                "url": "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubeadm",
                "checksum_url": "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubeadm.sha256",
            },
        ],
    )

    # CLI tools
    manifest.add_tool(
        name="helm",
        version="3.14.0",
        url="https://get.helm.sh/helm-v{{version}}-linux-amd64.tar.gz",
        extract=True,
        binary="linux-amd64/helm",
    )

    manifest.add_tool(
        name="k9s",
        version="0.32.4",
        url="https://github.com/derailed/k9s/releases/download/v{{version}}/k9s_Linux_amd64.tar.gz",
        extract=True,
        binary="k9s",
    )

    # Git repositories
    manifest.add_repository(
        name="kubespray",
        url="https://github.com/kubernetes-sigs/kubespray.git",
        ref="master",
    )

    manifest.add_repository(
        name="opencenter-gitops-base",
        url="https://github.com/rackerlabs/opencenter-gitops-base.git",
        ref="v1.0.0",
    )

    # Image auto-discovery
    manifest.images.auto_discover.append(
        ImageDiscovery(
            source="repositories.kubespray",
            patterns=[
                "roles/*/defaults/main.yml",
                "inventory/*/group_vars/*.yml",
            ],
        )
    )

    # Helm charts
    manifest.add_chart(
        name="cert-manager",
        repo="https://charts.jetstack.io",
        version="v1.13.0",
    )

    manifest.add_chart(
        name="ingress-nginx",
        repo="https://kubernetes.github.io/ingress-nginx",
        version="4.8.3",
    )

    # Terraform providers (OpenStack only)
    if template == "openstack":
        manifest.terraform_providers.append(
            TerraformProviderComponent(
                name="openstack",
                source="terraform-provider-openstack/openstack",
                version="1.54.1",
            )
        )
        manifest.terraform_providers.append(
            TerraformProviderComponent(
                name="local", source="hashicorp/local", version="2.4.1"
            )
        )

    return manifest


def read_manifest(path: Path) -> ComponentManifest:
    """Read component manifest from YAML file.

    Args:
        path: Path to manifest file

    Returns:
        ComponentManifest instance

    Raises:
        ConfigError: If file doesn't exist or is invalid
    """
    if not path.exists():
        raise ConfigError(f"Component manifest not found: {path}")

    try:
        with open(path) as f:
            data = yaml.safe_load(f)

        if not data:
            return ComponentManifest()

        return ComponentManifest.from_dict(data)

    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in component manifest: {exc}") from exc
    except Exception as exc:
        raise ConfigError(f"Failed to read component manifest: {exc}") from exc


def write_manifest(manifest: ComponentManifest, path: Path) -> None:
    """Write component manifest to YAML file.

    Args:
        manifest: ComponentManifest to write
        path: Output path

    Raises:
        ConfigError: If write fails
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        data = manifest.to_dict()

        with open(path, "w") as f:
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    except Exception as exc:
        raise ConfigError(f"Failed to write component manifest: {exc}") from exc
