"""Post-hoc URL reconstruction for kubespray-offline artifacts.

kubespray-offline's download-all.sh is an opaque process — it downloads
hundreds of artifacts without emitting a structured provenance log.

This module reconstructs source URLs after the fact by:
1. Parsing kubespray-offline's config files (which contain URL templates)
2. Matching downloaded filenames against known URL patterns
3. Producing provenance records compatible with the main downloads.ndjson

This is a best-effort reconstruction. Some artifacts (especially those
downloaded by nested scripts) may not have reconstructable URLs.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opencenter_build.downloader import DownloadRecord, ProvenanceLog


@dataclass
class KubesprayOfflineConfig:
    """Parsed kubespray-offline configuration.

    Attributes:
        versions: Key-value pairs from config files
        image_urls: Container image references
        file_urls: Binary/file download URL templates
        deb_repos: APT repository URLs
        pypi_index: PyPI mirror URL
    """

    versions: dict[str, str] = field(default_factory=dict)
    image_urls: list[str] = field(default_factory=list)
    file_urls: dict[str, str] = field(default_factory=dict)
    deb_repos: list[str] = field(default_factory=list)
    pypi_index: str = ""


# Known URL patterns for kubespray-offline artifacts.
# Maps filename patterns to URL templates.
KNOWN_URL_PATTERNS: dict[str, str] = {
    # Kubernetes binaries (version includes 'v' prefix)
    r"^kubectl$": "https://dl.k8s.io/v{version}/bin/linux/amd64/kubectl",
    r"^kubelet$": "https://dl.k8s.io/v{version}/bin/linux/amd64/kubelet",
    r"^kubeadm$": "https://dl.k8s.io/v{version}/bin/linux/amd64/kubeadm",
    # Container runtime
    r"^containerd-(\d+\.\d+\.\d+)-linux-amd64\.tar\.gz$": "https://github.com/containerd/containerd/releases/download/v{version}/containerd-{version}-linux-amd64.tar.gz",
    r"^runc\.amd64$": "https://github.com/opencontainers/runc/releases/download/v{version}/runc.amd64",
    r"^runc$": "https://github.com/opencontainers/runc/releases/download/v{version}/runc.amd64",
    # CNI plugins
    r"^cni-plugins-linux-amd64-v(\d+\.\d+\.\d+)\.tgz$": "https://github.com/containernetworking/plugins/releases/download/v{version}/cni-plugins-linux-amd64-v{version}.tgz",
    # crictl
    r"^crictl-v(\d+\.\d+\.\d+)-linux-amd64\.tar\.gz$": "https://github.com/kubernetes-sigs/cri-tools/releases/download/v{version}/crictl-v{version}-linux-amd64.tar.gz",
    # etcd
    r"^etcd-v(\d+\.\d+\.\d+)-linux-amd64\.tar\.gz$": "https://github.com/etcd-io/etcd/releases/download/v{version}/etcd-v{version}-linux-amd64.tar.gz",
    # Calico
    r"^calicoctl-linux-amd64$": "https://github.com/projectcalico/calico/releases/download/v{version}/calicoctl-linux-amd64",
    # nerdctl
    r"^nerdctl-(\d+\.\d+\.\d+)-linux-amd64\.tar\.gz$": "https://github.com/containerd/nerdctl/releases/download/v{version}/nerdctl-{version}-linux-amd64.tar.gz",
}


def parse_kubespray_offline_config(kubespray_offline_dir: Path) -> KubesprayOfflineConfig:
    """Parse kubespray-offline configuration files.

    Reads config/versions.env and other config files from the
    kubespray-offline directory to extract version information
    and URL templates.

    Args:
        kubespray_offline_dir: Path to kubespray-offline clone

    Returns:
        Parsed configuration
    """
    config = KubesprayOfflineConfig()

    # Parse config files
    config_dir = kubespray_offline_dir / "config"
    if not config_dir.exists():
        return config

    # Read all .env and .sh config files
    for config_file in config_dir.iterdir():
        if config_file.suffix in (".env", ".sh", ""):
            _parse_env_file(config_file, config.versions)

    # Read download URL lists if they exist
    for url_file in config_dir.glob("*url*"):
        if url_file.is_file():
            with open(url_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        config.file_urls[Path(line).name] = line

    # Read image lists
    for image_file in config_dir.glob("*image*"):
        if image_file.is_file():
            with open(image_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        config.image_urls.append(line)

    return config


def _parse_env_file(path: Path, versions: dict[str, str]) -> None:
    """Parse a shell-style env file into key-value pairs.

    Args:
        path: Path to env file
        versions: Dictionary to populate
    """
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Handle export VAR=value and VAR=value
                line = line.removeprefix("export ")
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        versions[key] = value
    except (OSError, UnicodeDecodeError):
        pass


def reconstruct_urls(
    kubespray_offline_dir: Path,
    versions_env: dict[str, str] | None = None,
) -> list[DownloadRecord]:
    """Reconstruct source URLs for kubespray-offline artifacts.

    Scans the outputs directory and attempts to match each file
    against known URL patterns using version information from config.

    Args:
        kubespray_offline_dir: Path to kubespray-offline clone
        versions_env: Optional project-level versions (from config/versions.env)

    Returns:
        List of reconstructed DownloadRecord objects
    """
    records: list[DownloadRecord] = []
    outputs_dir = kubespray_offline_dir / "outputs"

    if not outputs_dir.exists():
        return records

    # Parse kubespray-offline config
    config = parse_kubespray_offline_config(kubespray_offline_dir)

    # Merge project versions if provided
    all_versions = {**config.versions}
    if versions_env:
        all_versions.update(versions_env)

    timestamp = datetime.now(timezone.utc).isoformat()

    # Scan files directory
    files_dir = outputs_dir / "files"
    if files_dir.exists():
        for file_path in files_dir.rglob("*"):
            if file_path.is_file():
                record = _reconstruct_file_url(
                    file_path, all_versions, config, timestamp
                )
                records.append(record)

    # Scan images directory
    images_dir = outputs_dir / "images"
    if images_dir.exists():
        for image_file in images_dir.rglob("*.tar.gz"):
            record = _reconstruct_image_url(image_file, config, timestamp)
            records.append(record)

    return records


def _reconstruct_file_url(
    file_path: Path,
    versions: dict[str, str],
    config: KubesprayOfflineConfig,
    timestamp: str,
) -> DownloadRecord:
    """Attempt to reconstruct the download URL for a binary file.

    Args:
        file_path: Path to the downloaded file
        versions: Merged version information
        config: Parsed kubespray-offline config
        timestamp: Reconstruction timestamp

    Returns:
        DownloadRecord with reconstructed URL (or empty URL if unknown)
    """
    filename = file_path.name
    reconstructed_url = ""

    # Check explicit URL mappings from config
    if filename in config.file_urls:
        reconstructed_url = config.file_urls[filename]
    else:
        # Try pattern matching
        for pattern, url_template in KNOWN_URL_PATTERNS.items():
            match = re.match(pattern, filename)
            if match:
                # Extract version from filename or config
                version = _find_version_for_pattern(
                    pattern, filename, match, versions
                )
                if version:
                    reconstructed_url = url_template.format(version=version)
                break

    # Calculate checksum
    sha256 = _sha256(file_path)
    size_bytes = file_path.stat().st_size

    return DownloadRecord(
        artifact=filename,
        url=reconstructed_url,
        resolved_url=reconstructed_url,
        dest_path=str(file_path),
        sha256=sha256,
        size_bytes=size_bytes,
        http_status=200 if reconstructed_url else 0,
        checksum_verified=False,
        success=bool(reconstructed_url),
        timestamp=timestamp,
        headers={"reconstruction": "post-hoc", "source": "kubespray-offline"},
    )


def _reconstruct_image_url(
    image_file: Path,
    config: KubesprayOfflineConfig,
    timestamp: str,
) -> DownloadRecord:
    """Attempt to reconstruct the registry URL for a container image.

    Args:
        image_file: Path to the image tar.gz
        config: Parsed kubespray-offline config
        timestamp: Reconstruction timestamp

    Returns:
        DownloadRecord with image reference as URL
    """
    # Image filenames are typically: registry_org_name_tag.tar.gz
    # Try to match against known image list
    filename = image_file.stem  # Remove .tar.gz
    if filename.endswith(".tar"):
        filename = filename[:-4]  # Remove .tar from .tar.gz

    reconstructed_url = ""

    # Try matching against image list from config
    # Image files use underscores/dashes where the reference uses slashes/colons
    filename_normalized = filename.replace("__", "/").replace("_", "/")

    for image_ref in config.image_urls:
        # Normalize image reference for comparison
        ref_normalized = image_ref.replace("/", "/").replace(":", "/")
        if filename_normalized in ref_normalized or ref_normalized in filename_normalized:
            reconstructed_url = f"docker://{image_ref}"
            break

    sha256 = _sha256(image_file)
    size_bytes = image_file.stat().st_size

    return DownloadRecord(
        artifact=image_file.name,
        url=reconstructed_url,
        resolved_url=reconstructed_url,
        dest_path=str(image_file),
        sha256=sha256,
        size_bytes=size_bytes,
        http_status=200 if reconstructed_url else 0,
        checksum_verified=False,
        success=bool(reconstructed_url),
        timestamp=timestamp,
        headers={"reconstruction": "post-hoc", "source": "kubespray-offline"},
    )


def _find_version_for_pattern(
    pattern: str,
    filename: str,
    match: re.Match,
    versions: dict[str, str],
) -> str:
    """Find the version string for a matched pattern.

    Tries to extract version from:
    1. Regex capture group in the filename
    2. Known version keys in the versions dict

    Args:
        pattern: Regex pattern that matched
        filename: The filename
        match: Regex match object
        versions: Version dictionary

    Returns:
        Version string, or empty string if not found
    """
    # Try capture group first
    if match.groups():
        return match.group(1)

    # Map patterns to version keys
    version_key_map: dict[str, list[str]] = {
        r"^kubectl$": ["KUBERNETES_VERSION", "kube_version"],
        r"^kubelet$": ["KUBERNETES_VERSION", "kube_version"],
        r"^kubeadm$": ["KUBERNETES_VERSION", "kube_version"],
        r"^runc\.amd64$": ["RUNC_VERSION", "runc_version"],
        r"^runc$": ["RUNC_VERSION", "runc_version"],
        r"^calicoctl-linux-amd64$": ["CALICO_VERSION", "calico_version"],
    }

    keys = version_key_map.get(pattern, [])
    for key in keys:
        if key in versions:
            return versions[key].lstrip("v")

    return ""


def _sha256(file_path: Path) -> str:
    """Calculate SHA256 of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def generate_kubespray_provenance(
    kubespray_offline_dir: Path,
    provenance_dir: Path | None = None,
    versions_env: dict[str, str] | None = None,
) -> Path:
    """Generate provenance file for kubespray-offline artifacts.

    Reconstructs URLs and writes to build/provenance/kubespray-offline-urls.json.

    Args:
        kubespray_offline_dir: Path to kubespray-offline clone
        provenance_dir: Output directory (defaults to build/provenance/)
        versions_env: Optional project-level versions

    Returns:
        Path to generated provenance file
    """
    if provenance_dir is None:
        provenance_dir = Path("build/provenance")

    provenance_dir.mkdir(parents=True, exist_ok=True)
    output_file = provenance_dir / "kubespray-offline-urls.json"

    records = reconstruct_urls(kubespray_offline_dir, versions_env)

    # Also append to main provenance log
    log = ProvenanceLog(provenance_dir)
    for record in records:
        log.append(record)

    # Write dedicated kubespray-offline provenance file
    output_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(kubespray_offline_dir),
        "total_artifacts": len(records),
        "reconstructed_urls": sum(1 for r in records if r.url),
        "unknown_urls": sum(1 for r in records if not r.url),
        "artifacts": [
            {
                "artifact": r.artifact,
                "url": r.url or "UNKNOWN",
                "sha256": r.sha256,
                "size_bytes": r.size_bytes,
                "dest_path": r.dest_path,
            }
            for r in records
        ],
    }

    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    return output_file
