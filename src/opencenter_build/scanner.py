"""Repository scanner for container image and GitOps resource discovery.

This module provides concurrent repository scanning to discover:
- Container images from YAML/JSON manifests
- Helm charts from HelmRelease resources
- Helm repositories from HelmRepository resources

Uses ProcessPoolExecutor for parallel processing and memory-mapped I/O for large files.
"""

import mmap
import multiprocessing
import re
import yaml
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Pattern

from opencenter_build.exceptions import ScanError


@dataclass
class HelmRepositorySpec:
    """Helm repository specification from HelmRepository resource."""

    name: str
    url: str


@dataclass
class HelmReleaseSpec:
    """Helm release specification from HelmRelease resource."""

    chart: str
    source_ref: str
    version: str | None = None


# Default regex patterns for container image detection
DEFAULT_IMAGE_PATTERNS = [
    # Full image with digest: registry/repo:tag@sha256:hash
    r"(?:image|Image|IMAGE):\s*['\"]?([a-zA-Z0-9._-]+(?:[:/][a-zA-Z0-9._/-]+)+:[a-zA-Z0-9._-]+@sha256:[a-f0-9]+)['\"]?",
    # Full image references: registry/repo:tag or registry/namespace/repo:tag
    r"(?:image|Image|IMAGE):\s*['\"]?([a-zA-Z0-9._-]+(?:[:/][a-zA-Z0-9._/-]+)+:[a-zA-Z0-9._-]+)['\"]?",
    # Docker Hub shorthand: namespace/image:tag
    r"(?:image|Image|IMAGE):\s*['\"]?([a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+:[a-zA-Z0-9._-]+)['\"]?",
    # Simple image:tag format (e.g., nginx:latest)
    r"(?:image|Image|IMAGE):\s+([a-zA-Z0-9._-]+:[a-zA-Z0-9._-]+)",
    # Helm values repository (full path only, not bare tags)
    r"repository:\s*['\"]?([a-zA-Z0-9._-]+(?:[:/][a-zA-Z0-9._/-]+)+)['\"]?",
]

# File extensions to scan
SCANNABLE_EXTENSIONS = {
    ".yaml",
    ".yml",
    ".json",
    ".tf",
    ".hcl",
    ".toml",
    ".md",
    ".txt",
}

# Memory-mapped I/O threshold (1MB)
MMAP_THRESHOLD = 1024 * 1024


@lru_cache(maxsize=1)
def _compile_patterns(patterns: tuple[str, ...]) -> list[Pattern[str]]:
    """Compile and cache regex patterns.

    Uses lru_cache to compile patterns once and reuse across worker processes.
    Patterns are passed as tuple for hashability.

    Args:
        patterns: Tuple of regex pattern strings

    Returns:
        List of compiled regex patterns
    """
    return [re.compile(pattern) for pattern in patterns]


def _scan_file(file_path: Path, patterns: tuple[str, ...]) -> set[str]:
    """Scan single file for container images.

    Uses memory-mapped I/O for files larger than 1MB. Handles encoding
    errors gracefully by trying multiple encodings.

    Args:
        file_path: Path to file to scan
        patterns: Tuple of regex pattern strings

    Returns:
        Set of discovered image references (validated)
    """
    compiled_patterns = _compile_patterns(patterns)
    images: set[str] = set()

    try:
        file_size = file_path.stat().st_size

        # Use memory-mapped I/O for large files
        if file_size > MMAP_THRESHOLD:
            with open(file_path, "r+b") as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmapped:
                    content = _decode_content(mmapped, file_path)
        else:
            content = _read_file_with_fallback(file_path)

        # Apply all patterns
        for pattern in compiled_patterns:
            matches = pattern.findall(content)
            # Filter out invalid matches (bare tags, None, etc.)
            for match in matches:
                if match and _is_valid_image_reference(match):
                    images.add(match)

    except (OSError, IOError) as exc:
        # Log but don't fail on individual file errors
        pass
    except Exception:
        # Gracefully handle any other errors
        pass

    return images


def _is_valid_image_reference(image: str) -> bool:
    """Validate image reference format.

    Filters out bare tags, version numbers, and invalid references.

    Args:
        image: Image reference string

    Returns:
        True if valid image reference
    """
    if not image or image == "None":
        return False

    # Must contain at least one slash or be in image:tag format
    if "/" not in image and ":" not in image:
        return False

    # Reject bare version numbers (no registry/repo)
    if ":" in image and "/" not in image:
        # Allow simple docker hub images like nginx:1.21
        parts = image.split(":")
        if len(parts) == 2 and parts[0] and parts[1]:
            # Check if it looks like a valid image name (not just numbers)
            if not parts[0].replace(".", "").replace("-", "").replace("_", "").isdigit():
                return True
        return False

    return True


def _decode_content(data: bytes | mmap.mmap, file_path: Path) -> str:
    """Decode file content with fallback encodings.

    Tries UTF-8 first, then falls back to latin-1 which accepts all byte values.

    Args:
        data: Raw bytes or memory-mapped data
        file_path: Path to file (for error context)

    Returns:
        Decoded string content
    """
    if isinstance(data, mmap.mmap):
        data = data.read()

    # Try UTF-8 first
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass

    # Fall back to latin-1 (accepts all byte values)
    try:
        return data.decode("latin-1")
    except UnicodeDecodeError:
        # If even latin-1 fails, return empty string
        return ""


def _read_file_with_fallback(file_path: Path) -> str:
    """Read file with encoding fallback.

    Args:
        file_path: Path to file

    Returns:
        File content as string
    """
    # Try UTF-8 first
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        pass

    # Fall back to latin-1
    try:
        return file_path.read_text(encoding="latin-1")
    except UnicodeDecodeError:
        return ""


def _scan_repo_worker(repo_path: Path, patterns: tuple[str, ...]) -> tuple[str, set[str]]:
    """Worker function to scan single repository.

    Designed to be executed in worker process via ProcessPoolExecutor.

    Args:
        repo_path: Path to repository directory
        patterns: Tuple of regex pattern strings

    Returns:
        Tuple of (repo_path_str, discovered_images)
    """
    images: set[str] = set()

    if not repo_path.exists() or not repo_path.is_dir():
        return (str(repo_path), images)

    # Walk repository and scan files
    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue

        # Only scan files with relevant extensions
        if file_path.suffix.lower() not in SCANNABLE_EXTENSIONS:
            continue

        file_images = _scan_file(file_path, patterns)
        images.update(file_images)

    return (str(repo_path), images)


class RepositoryScanner:
    """Concurrent repository scanner for container image discovery.

    Scans Git repositories in parallel using ProcessPoolExecutor to discover
    container image references. Optimized for performance with:
    - Concurrent processing across multiple CPU cores
    - Cached regex pattern compilation
    - Memory-mapped I/O for large files
    - Graceful encoding error handling

    Example:
        >>> scanner = RepositoryScanner(
        ...     repos=[Path("kubespray"), Path("opencenter-gitops-base")],
        ...     max_workers=4
        ... )
        >>> results = scanner.scan_all()
        >>> for repo, images in results.items():
        ...     print(f"{repo}: {len(images)} images")
    """

    def __init__(
        self,
        repos: list[Path],
        max_workers: int | None = None,
        patterns: list[str] | None = None,
    ) -> None:
        """Initialize repository scanner.

        Args:
            repos: List of repository paths to scan
            max_workers: Number of worker processes (default: cpu_count)
            patterns: Custom regex patterns for image detection (optional)
        """
        self.repos = repos
        self.max_workers = max_workers or multiprocessing.cpu_count()
        self.patterns = tuple(patterns or DEFAULT_IMAGE_PATTERNS)

    def scan_all(self) -> dict[str, set[str]]:
        """Scan all repositories concurrently.

        Distributes repository scanning across worker processes for parallel
        execution. Returns results as they complete.

        Returns:
            Dictionary mapping repo paths to discovered images

        Raises:
            ScanError: If scanning fails catastrophically

        Example:
            >>> scanner = RepositoryScanner([Path("kubespray")])
            >>> results = scanner.scan_all()
            >>> print(f"Found {len(results['kubespray'])} images")
        """
        results: dict[str, set[str]] = {}

        try:
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all repository scan tasks
                future_to_repo = {
                    executor.submit(_scan_repo_worker, repo, self.patterns): repo
                    for repo in self.repos
                }

                # Collect results as they complete
                for future in as_completed(future_to_repo):
                    repo = future_to_repo[future]
                    try:
                        repo_path_str, images = future.result()
                        results[repo_path_str] = images
                    except Exception as exc:
                        # Log error but continue with other repos
                        results[str(repo)] = set()

        except Exception as exc:
            raise ScanError(f"Repository scanning failed: {exc}") from exc

        return results

    def scan_repo(self, repo: Path) -> set[str]:
        """Scan single repository for images.

        Convenience method for scanning a single repository without
        concurrent execution.

        Args:
            repo: Repository path to scan

        Returns:
            Set of discovered image references

        Example:
            >>> scanner = RepositoryScanner([])
            >>> images = scanner.scan_repo(Path("kubespray"))
            >>> print(f"Found {len(images)} images")
        """
        _, images = _scan_repo_worker(repo, self.patterns)
        return images


class GitOpsScanner:
    """Scanner for GitOps resources (HelmRepository and HelmRelease).

    Discovers Helm repositories and releases from FluxCD manifests.
    Builds a mapping of Helm repository names to URLs for chart resolution.
    """

    def __init__(self, repos: list[Path]):
        """Initialize GitOps scanner.

        Args:
            repos: List of repository paths to scan
        """
        self.repos = repos
        self.helm_repos: dict[str, str] = {}  # name -> url mapping

    def scan_all(self) -> tuple[dict[str, str], list[HelmReleaseSpec]]:
        """Scan all repositories for GitOps resources.

        Returns:
            Tuple of (helm_repos_dict, helm_releases_list)
            - helm_repos_dict: {name: url} mapping from HelmRepository resources
            - helm_releases_list: List of HelmReleaseSpec from HelmRelease resources
        """
        helm_repos = {}
        helm_releases = []

        for repo in self.repos:
            if not repo.exists():
                continue

            # Scan for HelmRepository resources
            repo_specs = self._scan_helm_repositories(repo)
            helm_repos.update(repo_specs)

            # Scan for HelmRelease resources
            release_specs = self._scan_helm_releases(repo)
            helm_releases.extend(release_specs)

        return helm_repos, helm_releases

    def _scan_helm_repositories(self, repo_path: Path) -> dict[str, str]:
        """Scan repository for HelmRepository resources.

        Finds YAML files with 'kind: HelmRepository' and extracts:
        - metadata.name
        - spec.url

        Args:
            repo_path: Path to repository

        Returns:
            Dictionary mapping repository name to URL
        """
        helm_repos = {}

        for yaml_file in repo_path.rglob("*.yaml"):
            if not yaml_file.is_file():
                continue

            try:
                with open(yaml_file) as f:
                    content = f.read()

                # Quick check before parsing
                if "kind: HelmRepository" not in content:
                    continue

                # Parse YAML (may contain multiple documents)
                for doc in yaml.safe_load_all(content):
                    if not doc or doc.get("kind") != "HelmRepository":
                        continue

                    name = doc.get("metadata", {}).get("name")
                    url = doc.get("spec", {}).get("url")

                    if name and url:
                        helm_repos[name] = url

            except (yaml.YAMLError, OSError, IOError):
                # Skip files that fail to parse
                continue

        # Also check .yml extension
        for yaml_file in repo_path.rglob("*.yml"):
            if not yaml_file.is_file():
                continue

            try:
                with open(yaml_file) as f:
                    content = f.read()

                if "kind: HelmRepository" not in content:
                    continue

                for doc in yaml.safe_load_all(content):
                    if not doc or doc.get("kind") != "HelmRepository":
                        continue

                    name = doc.get("metadata", {}).get("name")
                    url = doc.get("spec", {}).get("url")

                    if name and url:
                        helm_repos[name] = url

            except (yaml.YAMLError, OSError, IOError):
                continue

        return helm_repos

    def _scan_helm_releases(self, repo_path: Path) -> list[HelmReleaseSpec]:
        """Scan repository for HelmRelease resources.

        Finds YAML files with 'kind: HelmRelease' and extracts:
        - spec.chart.spec.chart (chart name)
        - spec.chart.spec.sourceRef.name (repository reference)
        - spec.chart.spec.version (optional version)

        Args:
            repo_path: Path to repository

        Returns:
            List of HelmReleaseSpec objects
        """
        helm_releases = []

        for yaml_file in repo_path.rglob("*.yaml"):
            if not yaml_file.is_file():
                continue

            try:
                with open(yaml_file) as f:
                    content = f.read()

                # Quick check before parsing
                if "kind: HelmRelease" not in content:
                    continue

                # Parse YAML (may contain multiple documents)
                for doc in yaml.safe_load_all(content):
                    if not doc or doc.get("kind") != "HelmRelease":
                        continue

                    chart_spec = doc.get("spec", {}).get("chart", {}).get("spec", {})

                    chart = chart_spec.get("chart")
                    source_ref = chart_spec.get("sourceRef", {}).get("name")
                    version = chart_spec.get("version")

                    if chart and source_ref:
                        helm_releases.append(
                            HelmReleaseSpec(
                                chart=chart,
                                source_ref=source_ref,
                                version=version,
                            )
                        )

            except (yaml.YAMLError, OSError, IOError):
                # Skip files that fail to parse
                continue

        # Also check .yml extension
        for yaml_file in repo_path.rglob("*.yml"):
            if not yaml_file.is_file():
                continue

            try:
                with open(yaml_file) as f:
                    content = f.read()

                if "kind: HelmRelease" not in content:
                    continue

                for doc in yaml.safe_load_all(content):
                    if not doc or doc.get("kind") != "HelmRelease":
                        continue

                    chart_spec = doc.get("spec", {}).get("chart", {}).get("spec", {})

                    chart = chart_spec.get("chart")
                    source_ref = chart_spec.get("sourceRef", {}).get("name")
                    version = chart_spec.get("version")

                    if chart and source_ref:
                        helm_releases.append(
                            HelmReleaseSpec(
                                chart=chart,
                                source_ref=source_ref,
                                version=version,
                            )
                        )

            except (yaml.YAMLError, OSError, IOError):
                continue

        return helm_releases

    def write_helm_repos_file(self, output_path: Path) -> None:
        """Write discovered Helm repositories to file.

        Creates a text file with format:
        name=url

        Args:
            output_path: Path to output file (e.g., config/helm-repos.txt)
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write("# Helm Repositories discovered from GitOps manifests\n")
            f.write("# Format: name=url\n\n")

            for name, url in sorted(self.helm_repos.items()):
                f.write(f"{name}={url}\n")

    @staticmethod
    def read_helm_repos_file(input_path: Path) -> dict[str, str]:
        """Read Helm repositories from file.

        Args:
            input_path: Path to helm-repos.txt file

        Returns:
            Dictionary mapping repository name to URL
        """
        helm_repos = {}

        if not input_path.exists():
            return helm_repos

        with open(input_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if "=" in line:
                    name, url = line.split("=", 1)
                    helm_repos[name.strip()] = url.strip()

        return helm_repos

    @staticmethod
    def resolve_helm_chart_url(release: HelmReleaseSpec, helm_repos: dict[str, str]) -> str | None:
        """Resolve full Helm chart URL from HelmRelease and repository mapping.

        Supports both HTTP/HTTPS and OCI registries.

        Args:
            release: HelmReleaseSpec with chart name and source reference
            helm_repos: Dictionary mapping repository names to URLs

        Returns:
            Full chart URL (http/https/oci) or None if repository not found

        Example:
            >>> release = HelmReleaseSpec(chart="nginx", source_ref="bitnami", version="1.0.0")
            >>> repos = {"bitnami": "https://charts.bitnami.com/bitnami"}
            >>> url = GitOpsScanner.resolve_helm_chart_url(release, repos)
            >>> print(url)
            https://charts.bitnami.com/bitnami/nginx
        """
        repo_url = helm_repos.get(release.source_ref)
        if not repo_url:
            return None

        # OCI registry format: oci://registry/path
        if repo_url.startswith("oci://"):
            # OCI format: oci://registry/path/chart:version
            chart_url = f"{repo_url.rstrip('/')}/{release.chart}"
            if release.version:
                chart_url = f"{chart_url}:{release.version}"
            return chart_url

        # HTTP/HTTPS format: https://repo/path/chart-version.tgz
        chart_url = f"{repo_url.rstrip('/')}/{release.chart}"
        return chart_url
