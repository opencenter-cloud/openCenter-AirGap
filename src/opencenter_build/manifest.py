"""Artifact manifest generation for openCenter AirGap builds.

This module provides data models and generation logic for creating comprehensive
artifact inventories with checksums and metadata.
"""

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ArtifactManifest:
    """Complete artifact inventory with checksums and metadata.

    Attributes:
        build_id: Unique identifier for this build
        timestamp: When the manifest was generated
        images: List of container image references
        image_count: Total number of images
        image_total_size: Total size of all images in bytes
        charts: List of Helm chart metadata dicts
        chart_count: Total number of charts
        repos: List of Git repository metadata dicts
        repo_count: Total number of repositories
        binaries: List of binary file metadata dicts
        binary_count: Total number of binaries
        binary_total_size: Total size of all binaries in bytes
        os_packages: List of OS package metadata dicts
        os_package_count: Total number of OS packages
        os_package_total_size: Total size of all OS packages in bytes
        pypi_packages: List of PyPI package metadata dicts
        pypi_package_count: Total number of PyPI packages
        pypi_package_total_size: Total size of all PyPI packages in bytes
        terraform_providers: List of Terraform provider metadata dicts
        terraform_provider_count: Total number of Terraform providers
        total_artifacts: Sum of all artifact counts
        total_size: Sum of all artifact sizes in bytes
    """

    build_id: str
    timestamp: datetime

    # Container images
    images: list[str] = field(default_factory=list)
    image_count: int = 0
    image_total_size: int = 0

    # Helm charts
    charts: list[dict[str, Any]] = field(default_factory=list)
    chart_count: int = 0

    # Git repositories
    repos: list[dict[str, Any]] = field(default_factory=list)
    repo_count: int = 0

    # Binaries (kubectl, kubelet, etc.)
    binaries: list[dict[str, Any]] = field(default_factory=list)
    binary_count: int = 0
    binary_total_size: int = 0

    # OS packages (debs)
    os_packages: list[dict[str, Any]] = field(default_factory=list)
    os_package_count: int = 0
    os_package_total_size: int = 0

    # PyPI packages
    pypi_packages: list[dict[str, Any]] = field(default_factory=list)
    pypi_package_count: int = 0
    pypi_package_total_size: int = 0

    # Terraform providers
    terraform_providers: list[dict[str, Any]] = field(default_factory=list)
    terraform_provider_count: int = 0

    # Totals
    total_artifacts: int = 0
    total_size: int = 0

    def calculate_totals(self) -> None:
        """Calculate total artifact count and size from individual collections."""
        self.total_artifacts = (
            self.image_count
            + self.chart_count
            + self.repo_count
            + self.binary_count
            + self.os_package_count
            + self.pypi_package_count
            + self.terraform_provider_count
        )

        self.total_size = (
            self.image_total_size
            + self.binary_total_size
            + self.os_package_total_size
            + self.pypi_package_total_size
        )

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Format byte size as human-readable string.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted string (e.g., "1.5 GB", "256 MB")
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes / (1024 ** 2):.1f} MB"
        else:
            return f"{size_bytes / (1024 ** 3):.2f} GB"

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary for serialization.

        Returns:
            Dictionary representation with ISO timestamp
        """
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArtifactManifest":
        """Create manifest from dictionary.

        Args:
            data: Dictionary with manifest data

        Returns:
            ArtifactManifest instance
        """
        data = data.copy()
        if isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class ManifestGenerator:
    """Generates artifact manifests from build directories.

    Scans build output directories to inventory all collected artifacts,
    calculate checksums, and export manifests in JSON and Markdown formats.
    """

    def __init__(self, build_dir: Path):
        """Initialize generator.

        Args:
            build_dir: Root build directory containing artifacts
        """
        self.build_dir = Path(build_dir)

    def generate(self, build_id: str | None = None) -> ArtifactManifest:
        """Generate complete artifact manifest from build directory.

        Args:
            build_id: Optional build identifier (generated if not provided)

        Returns:
            Complete artifact manifest
        """
        if build_id is None:
            build_id = datetime.now().strftime("%Y%m%d-%H%M%S")

        manifest = ArtifactManifest(build_id=build_id, timestamp=datetime.now())

        # Scan for each artifact type
        self._scan_images(manifest)
        self._scan_charts(manifest)
        self._scan_repos(manifest)
        self._scan_binaries(manifest)
        self._scan_os_packages(manifest)
        self._scan_pypi_packages(manifest)
        self._scan_terraform_providers(manifest)

        # Calculate totals
        manifest.calculate_totals()

        return manifest

    def _scan_images(self, manifest: ArtifactManifest) -> None:
        """Scan for container images.

        Args:
            manifest: Manifest to populate
        """
        images_file = self.build_dir / "config" / "all-images.txt"
        if images_file.exists():
            with open(images_file) as f:
                manifest.images = [line.strip() for line in f if line.strip()]
            manifest.image_count = len(manifest.images)

        # Try to get image sizes from kubespray-offline outputs
        images_dir = self.build_dir / "kubespray-offline" / "outputs" / "images"
        if images_dir.exists():
            total_size = 0
            for img_file in images_dir.rglob("*.tar.gz"):
                total_size += img_file.stat().st_size
            manifest.image_total_size = total_size

    def _scan_charts(self, manifest: ArtifactManifest) -> None:
        """Scan for Helm charts.

        Args:
            manifest: Manifest to populate
        """
        charts_dir = self.build_dir / "assets" / "charts"
        if not charts_dir.exists():
            return

        for chart_file in charts_dir.glob("*.tgz"):
            chart_info = {
                "name": chart_file.stem,
                "path": str(chart_file.relative_to(self.build_dir)),
                "size": chart_file.stat().st_size,
                "sha256": self._calculate_sha256(chart_file),
            }
            manifest.charts.append(chart_info)

        manifest.chart_count = len(manifest.charts)

    def _scan_repos(self, manifest: ArtifactManifest) -> None:
        """Scan for Git repositories.

        Args:
            manifest: Manifest to populate
        """
        repos_file = self.build_dir / "config" / "git-repositories.json"
        if repos_file.exists():
            with open(repos_file) as f:
                repos_data = json.load(f)
                manifest.repos = repos_data if isinstance(repos_data, list) else []
                manifest.repo_count = len(manifest.repos)

    def _scan_binaries(self, manifest: ArtifactManifest) -> None:
        """Scan for binary files (kubectl, kubelet, etc.).

        Args:
            manifest: Manifest to populate
        """
        files_dir = self.build_dir / "kubespray-offline" / "outputs" / "files"
        if not files_dir.exists():
            return

        total_size = 0
        for binary_file in files_dir.rglob("*"):
            if binary_file.is_file():
                size = binary_file.stat().st_size
                binary_info = {
                    "name": binary_file.name,
                    "path": str(binary_file.relative_to(self.build_dir)),
                    "size": size,
                    "sha256": self._calculate_sha256(binary_file),
                }
                manifest.binaries.append(binary_info)
                total_size += size

        manifest.binary_count = len(manifest.binaries)
        manifest.binary_total_size = total_size

    def _scan_os_packages(self, manifest: ArtifactManifest) -> None:
        """Scan for OS packages (debs).

        Args:
            manifest: Manifest to populate
        """
        debs_dir = self.build_dir / "kubespray-offline" / "outputs" / "debs"
        if not debs_dir.exists():
            return

        total_size = 0
        for deb_file in debs_dir.rglob("*.deb"):
            size = deb_file.stat().st_size
            pkg_info = {
                "name": deb_file.name,
                "path": str(deb_file.relative_to(self.build_dir)),
                "size": size,
                "sha256": self._calculate_sha256(deb_file),
            }
            manifest.os_packages.append(pkg_info)
            total_size += size

        manifest.os_package_count = len(manifest.os_packages)
        manifest.os_package_total_size = total_size

    def _scan_pypi_packages(self, manifest: ArtifactManifest) -> None:
        """Scan for PyPI packages.

        Args:
            manifest: Manifest to populate
        """
        pypi_dir = self.build_dir / "kubespray-offline" / "outputs" / "pypi"
        if not pypi_dir.exists():
            return

        total_size = 0
        for pkg_file in pypi_dir.rglob("*"):
            if pkg_file.is_file() and (pkg_file.suffix in [".whl", ".tar.gz", ".zip"]):
                size = pkg_file.stat().st_size
                pkg_info = {
                    "name": pkg_file.name,
                    "type": "wheel" if pkg_file.suffix == ".whl" else "source",
                    "path": str(pkg_file.relative_to(self.build_dir)),
                    "size": size,
                    "sha256": self._calculate_sha256(pkg_file),
                }
                manifest.pypi_packages.append(pkg_info)
                total_size += size

        manifest.pypi_package_count = len(manifest.pypi_packages)
        manifest.pypi_package_total_size = total_size

    def _scan_terraform_providers(self, manifest: ArtifactManifest) -> None:
        """Scan for Terraform providers.

        Args:
            manifest: Manifest to populate
        """
        tf_dir = self.build_dir / "assets" / "terraform-mirror"
        if not tf_dir.exists():
            return

        for provider_file in tf_dir.rglob("*.zip"):
            provider_info = {
                "name": provider_file.stem,
                "path": str(provider_file.relative_to(self.build_dir)),
                "size": provider_file.stat().st_size,
                "sha256": self._calculate_sha256(provider_file),
            }
            manifest.terraform_providers.append(provider_info)

        manifest.terraform_provider_count = len(manifest.terraform_providers)

    def _calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file.

        Args:
            file_path: Path to file

        Returns:
            Hex-encoded SHA256 checksum
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def export_json(self, manifest: ArtifactManifest, output: Path) -> None:
        """Export manifest as JSON.

        Args:
            manifest: Manifest to export
            output: Output file path
        """
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            json.dump(manifest.to_dict(), f, indent=2)

    def export_markdown(self, manifest: ArtifactManifest, output: Path) -> None:
        """Export manifest as Markdown with tables.

        Args:
            manifest: Manifest to export
            output: Output file path
        """
        output.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            f"# Artifact Manifest: {manifest.build_id}",
            "",
            f"**Generated:** {manifest.timestamp.isoformat()}",
            "",
            "## Summary",
            "",
            "| Artifact Type | Count | Total Size |",
            "|--------------|-------|------------|",
            f"| Container Images | {manifest.image_count} | {manifest.format_size(manifest.image_total_size)} |",
            f"| Helm Charts | {manifest.chart_count} | - |",
            f"| Git Repositories | {manifest.repo_count} | - |",
            f"| Binaries | {manifest.binary_count} | {manifest.format_size(manifest.binary_total_size)} |",
            f"| OS Packages | {manifest.os_package_count} | {manifest.format_size(manifest.os_package_total_size)} |",
            f"| PyPI Packages | {manifest.pypi_package_count} | {manifest.format_size(manifest.pypi_package_total_size)} |",
            f"| Terraform Providers | {manifest.terraform_provider_count} | - |",
            f"| **Total** | **{manifest.total_artifacts}** | **{manifest.format_size(manifest.total_size)}** |",
            "",
        ]

        # Container Images section
        if manifest.images:
            lines.extend(["## Container Images", "", f"Total: {manifest.image_count} images", ""])
            for img in manifest.images[:10]:  # Show first 10
                lines.append(f"- {img}")
            if len(manifest.images) > 10:
                lines.append(f"- ... and {len(manifest.images) - 10} more")
            lines.append("")

        # Helm Charts section
        if manifest.charts:
            lines.extend(
                ["## Helm Charts", "", "| Name | Size | SHA256 |", "|------|------|--------|"]
            )
            for chart in manifest.charts:
                size_str = manifest.format_size(chart["size"]) if "size" in chart else "-"
                sha_str = f"`{chart['sha256'][:16]}...`" if "sha256" in chart else "-"
                lines.append(f"| {chart['name']} | {size_str} | {sha_str} |")
            lines.append("")

        # Binaries section
        if manifest.binaries:
            lines.extend(
                [
                    "## Binaries",
                    "",
                    f"Total: {manifest.binary_count} files ({manifest.format_size(manifest.binary_total_size)})",
                    "",
                    "| Name | Size | SHA256 |",
                    "|------|------|--------|",
                ]
            )
            for binary in manifest.binaries[:20]:  # Show first 20
                lines.append(
                    f"| {binary['name']} | {manifest.format_size(binary['size'])} | "
                    f"`{binary['sha256'][:16]}...` |"
                )
            if len(manifest.binaries) > 20:
                lines.append(f"| ... and {len(manifest.binaries) - 20} more | | |")
            lines.append("")

        # OS Packages section
        if manifest.os_packages:
            lines.extend(
                [
                    "## OS Packages",
                    "",
                    f"Total: {manifest.os_package_count} packages ({manifest.format_size(manifest.os_package_total_size)})",
                    "",
                ]
            )

        # PyPI Packages section
        if manifest.pypi_packages:
            lines.extend(
                [
                    "## PyPI Packages",
                    "",
                    f"Total: {manifest.pypi_package_count} packages ({manifest.format_size(manifest.pypi_package_total_size)})",
                    "",
                ]
            )

        # Terraform Providers section
        if manifest.terraform_providers:
            lines.extend(
                [
                    "## Terraform Providers",
                    "",
                    f"Total: {manifest.terraform_provider_count} providers",
                    "",
                ]
            )

        with open(output, "w") as f:
            f.write("\n".join(lines))
