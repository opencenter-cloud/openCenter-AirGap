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
class RepoSpec:
    """Repository specification for extraction from versions.env.

    Attributes:
        name: Repository name
        url: Git clone URL
        ref: Git ref (branch, tag, or commit)
    """

    name: str
    url: str
    ref: str

    def __post_init__(self) -> None:
        """Validate required fields."""
        if not self.name:
            raise ValueError("Repository name is required")
        if not self.url:
            raise ValueError("Repository URL is required")
        if not self.ref:
            raise ValueError("Repository ref is required")


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
        _generated: Generation metadata (preserved on round-trip)
    """

    kubernetes: KubernetesComponent | None = None
    tools: list[ToolComponent] = field(default_factory=list)
    repositories: list[RepositoryComponent] = field(default_factory=list)
    images: ImagesComponent = field(default_factory=ImagesComponent)
    charts: list[ChartComponent] = field(default_factory=list)
    os_packages: OSPackagesComponent = field(default_factory=OSPackagesComponent)
    python_packages: PythonPackagesComponent = field(default_factory=PythonPackagesComponent)
    terraform_providers: list[TerraformProviderComponent] = field(default_factory=list)
    _generated: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary for YAML serialization.

        Includes generation metadata if present.

        Returns:
            Dictionary representation
        """
        data = {}

        # Include metadata if present
        if self._generated:
            data["_generated"] = self._generated

        if self.kubernetes:
            data["kubernetes"] = asdict(self.kubernetes)

        if self.tools:
            data["tools"] = [asdict(tool) for tool in self.tools]

        if self.repositories:
            data["repositories"] = [asdict(repo) for repo in self.repositories]

        if self.images.auto_discover or self.images.additional:
            images_data = {}
            if self.images.auto_discover:
                images_data["auto_discover"] = [asdict(disc) for disc in self.images.auto_discover]
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

        Preserves generation metadata if present.

        Args:
            data: Dictionary with manifest data

        Returns:
            ComponentManifest instance
        """
        manifest = cls()

        # Preserve metadata if present
        if "_generated" in data:
            manifest._generated = data["_generated"]

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
            manifest.repositories = [RepositoryComponent(**repo) for repo in data["repositories"]]

        # Images
        if "images" in data:
            images_data = data["images"]
            auto_discover = []
            if "auto_discover" in images_data:
                auto_discover = [ImageDiscovery(**disc) for disc in images_data["auto_discover"]]
            additional = images_data.get("additional", [])
            manifest.images = ImagesComponent(auto_discover=auto_discover, additional=additional)

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
                TerraformProviderComponent(**provider) for provider in data["terraform_providers"]
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


def create_default_manifest(
    template: str = "baremetal", versions_env: Path | None = None
) -> ComponentManifest:
    """Create default component manifest from versions.env.

    Generates component manifest by parsing versions.env and extracting
    component definitions. This ensures single source of truth for versions.

    Args:
        template: Template name ('baremetal' or 'openstack')
        versions_env: Path to versions.env file (default: config/versions.env)

    Returns:
        ComponentManifest with components from versions.env

    Raises:
        ConfigError: If versions.env not found or invalid
    """
    from opencenter_build.config import parse_versions_env

    # Load versions.env
    if versions_env is None:
        versions_env = Path("config/versions.env")

    if not versions_env.exists():
        raise ConfigError(
            f"versions.env not found: {versions_env}\n"
            "Create config/versions.env with component versions first"
        )

    versions = parse_versions_env(versions_env)

    manifest = ComponentManifest()

    # Kubernetes binaries
    k8s_version = versions.get("KUBERNETES_VERSION", "v1.34.3").lstrip("v")
    manifest.kubernetes = KubernetesComponent(
        version=k8s_version,
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

    # CLI tools from versions.env
    if "HELM_VERSION" in versions:
        manifest.add_tool(
            name="helm",
            version=versions["HELM_VERSION"].lstrip("v"),
            url="https://get.helm.sh/helm-v{{version}}-linux-amd64.tar.gz",
            extract=True,
            binary="linux-amd64/helm",
        )

    if "K9S_VERSION" in versions:
        manifest.add_tool(
            name="k9s",
            version=versions["K9S_VERSION"].lstrip("v"),
            url="https://github.com/derailed/k9s/releases/download/v{{version}}/k9s_Linux_amd64.tar.gz",
            extract=True,
            binary="k9s",
        )

    if "STERN_VERSION" in versions:
        manifest.add_tool(
            name="stern",
            version=versions["STERN_VERSION"].lstrip("v"),
            url="https://github.com/stern/stern/releases/download/v{{version}}/stern_{{version}}_linux_amd64.tar.gz",
            extract=True,
            binary="stern",
        )

    if "YQ_VERSION" in versions:
        manifest.add_tool(
            name="yq",
            version=versions["YQ_VERSION"].lstrip("v"),
            url="https://github.com/mikefarah/yq/releases/download/v{{version}}/yq_linux_amd64",
            extract=False,
        )

    if "JQ_VERSION" in versions:
        manifest.add_tool(
            name="jq",
            version=versions["JQ_VERSION"].lstrip("v"),
            url="https://github.com/jqlang/jq/releases/download/jq-{{version}}/jq-linux-amd64",
            extract=False,
        )

    # Git repositories from versions.env
    if "KUBESPRAY_VERSION" in versions:
        manifest.add_repository(
            name="kubespray",
            url="https://github.com/kubernetes-sigs/kubespray.git",
            ref=versions["KUBESPRAY_VERSION"],
        )

    if "OPENCENTER_GITOPS_BASE_REPO" in versions:
        # Extract repository name from URL to preserve case sensitivity
        url = versions["OPENCENTER_GITOPS_BASE_REPO"]
        repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
        manifest.add_repository(
            name=repo_name,
            url=url,
            ref=versions.get("OPENCENTER_GITOPS_BASE_VERSION", "main"),
        )

    # Image auto-discovery from repositories
    if manifest.repositories:
        for repo in manifest.repositories:
            if repo.name == "kubespray":
                manifest.images.auto_discover.append(
                    ImageDiscovery(
                        source=f"repositories.{repo.name}",
                        patterns=[
                            "roles/*/defaults/main.yml",
                            "inventory/*/group_vars/*.yml",
                        ],
                    )
                )

    # Helm charts from versions.env
    if "CERT_MANAGER_VERSION" in versions:
        manifest.add_chart(
            name="cert-manager",
            repo="https://charts.jetstack.io",
            version=versions["CERT_MANAGER_VERSION"],
        )

    if "INGRESS_NGINX_VERSION" in versions:
        manifest.add_chart(
            name="ingress-nginx",
            repo="https://kubernetes.github.io/ingress-nginx",
            version=versions["INGRESS_NGINX_VERSION"],
        )

    # Terraform providers (OpenStack only)
    if template == "openstack":
        if "OPENSTACK_PROVIDER_VERSION" in versions:
            manifest.terraform_providers.append(
                TerraformProviderComponent(
                    name="openstack",
                    source="terraform-provider-openstack/openstack",
                    version=versions["OPENSTACK_PROVIDER_VERSION"],
                )
            )
        if "LOCAL_PROVIDER_VERSION" in versions:
            manifest.terraform_providers.append(
                TerraformProviderComponent(
                    name="local",
                    source="hashicorp/local",
                    version=versions["LOCAL_PROVIDER_VERSION"],
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
    """Write component manifest to YAML file with metadata.

    Adds generation metadata and header comment explaining auto-generation.
    Manual edits are preserved during regeneration via merge strategy.

    Args:
        manifest: ComponentManifest to write
        path: Output path

    Raises:
        ConfigError: If write fails
    """
    from datetime import datetime, timezone

    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        data = manifest.to_dict()

        # Add generation metadata
        metadata = {
            "_generated": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "config/versions.env",
                "tool": "opencenter-airgap",
                "note": "This file is auto-generated. Manual edits are preserved during regeneration.",
            }
        }

        # Merge metadata at the beginning
        data = {**metadata, **data}

        # Header comment explaining auto-generation
        header = """# Component Manifest
# Auto-generated from config/versions.env
# Manual edits are preserved during regeneration
# To regenerate: python3 -m opencenter_build.cli build --force-regenerate

"""

        with open(path, "w") as f:
            f.write(header)
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    except Exception as exc:
        raise ConfigError(f"Failed to write component manifest: {exc}") from exc


def should_regenerate_manifest(versions_env: Path, manifest: Path, force: bool = False) -> bool:
    """Determine if components.yaml should be regenerated.

    Args:
        versions_env: Path to versions.env file
        manifest: Path to components.yaml file
        force: Force regeneration regardless of other conditions

    Returns:
        True if manifest should be regenerated, False otherwise
    """
    if force:
        return True

    if not manifest.exists():
        return True

    if not versions_env.exists():
        return False

    # Compare modification times
    versions_mtime = versions_env.stat().st_mtime
    manifest_mtime = manifest.stat().st_mtime

    return versions_mtime > manifest_mtime


def merge_manifests(existing: ComponentManifest, generated: ComponentManifest) -> ComponentManifest:
    """Merge existing manual edits with generated manifest.

    Strategy:
    - Use generated versions for all components
    - Preserve additional images from existing
    - Preserve additional charts from existing
    - Preserve custom tools not in generated
    - Preserve metadata from existing

    Args:
        existing: Existing manifest with potential manual edits
        generated: Newly generated manifest from versions.env

    Returns:
        Merged ComponentManifest
    """
    # Start with generated manifest
    merged = ComponentManifest()

    # Preserve metadata from existing manifest
    merged._generated = existing._generated

    # Copy generated components (these have updated versions)
    merged.kubernetes = generated.kubernetes
    merged.tools = generated.tools.copy()
    merged.repositories = generated.repositories.copy()
    merged.os_packages = generated.os_packages
    merged.python_packages = generated.python_packages
    merged.terraform_providers = generated.terraform_providers.copy()

    # Merge images - preserve additional images from existing
    merged.images = ImagesComponent(
        auto_discover=generated.images.auto_discover.copy(),
        additional=generated.images.additional.copy(),
    )

    existing_images = set(existing.images.additional)
    generated_images = set(generated.images.additional)
    additional_images = existing_images - generated_images

    merged.images.additional.extend(sorted(additional_images))

    # Merge charts - preserve charts not in generated
    merged.charts = generated.charts.copy()

    existing_chart_names = {c.name for c in existing.charts}
    generated_chart_names = {c.name for c in generated.charts}

    for chart in existing.charts:
        if chart.name not in generated_chart_names:
            merged.charts.append(chart)

    # Merge tools - preserve custom tools not in generated
    existing_tool_names = {t.name for t in existing.tools}
    generated_tool_names = {t.name for t in generated.tools}

    for tool in existing.tools:
        if tool.name not in generated_tool_names:
            merged.tools.append(tool)

    return merged


def extract_repos_from_versions(versions: dict[str, str]) -> list[RepoSpec]:
    """Extract repository specifications from versions.env.

    Looks for patterns:
    - KUBESPRAY_VERSION + KUBESPRAY_COMMIT_SHA
    - OPENCENTER_GITOPS_BASE_REPO + OPENCENTER_GITOPS_BASE_VERSION

    Args:
        versions: Dictionary of version variables from versions.env

    Returns:
        List of RepoSpec objects for repositories found in versions.env
    """
    repos = []

    # Kubespray repository
    if "KUBESPRAY_VERSION" in versions:
        repos.append(
            RepoSpec(
                name="kubespray",
                url="https://github.com/kubernetes-sigs/kubespray.git",
                ref=versions["KUBESPRAY_VERSION"],
            )
        )

    # openCenter GitOps Base repository
    if "OPENCENTER_GITOPS_BASE_REPO" in versions:
        # Extract repository name from URL to preserve case sensitivity
        url = versions["OPENCENTER_GITOPS_BASE_REPO"]
        repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
        repos.append(
            RepoSpec(
                name=repo_name,
                url=url,
                ref=versions.get("OPENCENTER_GITOPS_BASE_VERSION", "main"),
            )
        )

    return repos


def clone_repository(repo_spec: RepoSpec, build_dir: Path | None = None) -> Path:
    """Clone repository to build/ directory.

    Checks if repository already exists before cloning. Uses shallow clone
    with depth 1 for efficiency.

    Args:
        repo_spec: Repository specification with name, url, and ref
        build_dir: Build directory (default: build/)

    Returns:
        Path to cloned repository

    Raises:
        ConfigError: If clone fails
    """
    import subprocess
    from rich.console import Console

    console = Console()

    if build_dir is None:
        build_dir = Path("build")

    repo_path = build_dir / repo_spec.name

    # Check if repository already exists
    if repo_path.exists():
        console.print(f"[cyan]Repository already exists:[/cyan] {repo_path}")
        return repo_path

    # Create build directory if needed
    build_dir.mkdir(parents=True, exist_ok=True)

    # Clone repository
    console.print(f"[cyan]Cloning {repo_spec.name}...[/cyan]")
    console.print(f"  URL: {repo_spec.url}")
    console.print(f"  Ref: {repo_spec.ref}")

    try:
        result = subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                repo_spec.ref,
                repo_spec.url,
                str(repo_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        console.print(f"[green]✓[/green] Cloned to: {repo_path}")
        return repo_path

    except subprocess.CalledProcessError as exc:
        error_msg = f"Failed to clone repository {repo_spec.name}: {exc.stderr}"
        console.print(f"[red]✗[/red] {error_msg}")
        raise ConfigError(error_msg) from exc
    except FileNotFoundError:
        error_msg = "git command not found. Please install git."
        console.print(f"[red]✗[/red] {error_msg}")
        raise ConfigError(error_msg)


class HelmChartScanner:
    """Scanner for discovering Helm charts in repositories.

    Scans repositories for Chart.yaml files and extracts chart metadata
    (name, version). Returns ChartComponent objects with local paths.
    """

    def __init__(self, repos: list[Path]):
        """Initialize scanner with repository paths.

        Args:
            repos: List of repository paths to scan
        """
        self.repos = repos

    def scan_all(self) -> list[ChartComponent]:
        """Scan all repositories for Helm charts.

        Looks for Chart.yaml files, parses metadata, and creates
        ChartComponent objects with local paths.

        Returns:
            List of discovered ChartComponent objects
        """
        charts = []

        for repo in self.repos:
            if not repo.exists():
                continue

            # Find all Chart.yaml files in repository
            for chart_yaml in repo.rglob("Chart.yaml"):
                chart = self._parse_chart_yaml(chart_yaml, repo)
                if chart:
                    charts.append(chart)

        return charts

    def _parse_chart_yaml(self, chart_path: Path, repo_root: Path) -> ChartComponent | None:
        """Parse Chart.yaml and extract metadata.

        Args:
            chart_path: Path to Chart.yaml file
            repo_root: Root path of repository

        Returns:
            ChartComponent with extracted metadata, or None if parse fails
        """
        try:
            with open(chart_path) as f:
                data = yaml.safe_load(f)

            if not data:
                return None

            # Extract required fields
            name = data.get("name")
            version = data.get("version")

            if not name or not version:
                return None

            # Calculate relative path from repo root
            chart_dir = chart_path.parent
            try:
                relative_path = chart_dir.relative_to(repo_root)
            except ValueError:
                # If chart_dir is not relative to repo_root, use absolute path
                relative_path = chart_dir

            # Create ChartComponent with local path
            return ChartComponent(
                name=name,
                version=version,
                repo=str(repo_root),  # Local repository path
                path=str(relative_path),
            )

        except yaml.YAMLError:
            # Invalid YAML - skip this chart
            return None
        except Exception:
            # Any other error - skip this chart
            return None
