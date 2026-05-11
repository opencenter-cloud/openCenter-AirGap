"""Centralized download module with provenance tracking.

Every download performed through this module is recorded in a structured
provenance log (NDJSON format) at build/provenance/downloads.ndjson.

Each record captures:
- Original and resolved (post-redirect) URLs
- SHA256 checksum of the downloaded content
- File size, HTTP status, response headers
- Timestamp and verification status

This provides a complete audit trail linking every artifact in the
air-gap package back to its exact download source.
"""

import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from opencenter_build.exceptions import AssetCollectionError, NetworkError


@dataclass
class DownloadRecord:
    """Single download provenance record.

    Attributes:
        artifact: Human-readable artifact name
        url: Original request URL
        resolved_url: Final URL after redirects
        dest_path: Local filesystem path where artifact was saved
        sha256: SHA256 hex digest of downloaded content
        size_bytes: File size in bytes
        http_status: HTTP response status code
        checksum_url: URL used for checksum verification (if any)
        checksum_verified: Whether checksum was verified against upstream
        success: Whether the download completed successfully
        timestamp: ISO 8601 UTC timestamp of download
        headers: Selected response headers (Content-Type, ETag, Last-Modified)
    """

    artifact: str
    url: str
    resolved_url: str
    dest_path: str
    sha256: str
    size_bytes: int
    http_status: int
    checksum_url: str | None = None
    checksum_verified: bool = False
    success: bool = True
    timestamp: str = ""
    headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Set timestamp if not provided."""
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_json_line(self) -> str:
        """Serialize to a single JSON line for NDJSON output."""
        return json.dumps(asdict(self), separators=(",", ":"))


class ProvenanceLog:
    """Append-only provenance log in NDJSON format.

    Writes download records to build/provenance/downloads.ndjson.
    Thread-safe for sequential writes (not concurrent).
    """

    def __init__(self, provenance_dir: Path | None = None) -> None:
        """Initialize provenance log.

        Args:
            provenance_dir: Directory for provenance files.
                Defaults to build/provenance/.
        """
        if provenance_dir is None:
            provenance_dir = Path("build/provenance")
        self.provenance_dir = provenance_dir
        self.log_file = provenance_dir / "downloads.ndjson"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Create provenance directory if it doesn't exist."""
        self.provenance_dir.mkdir(parents=True, exist_ok=True)

    def append(self, record: DownloadRecord) -> None:
        """Append a download record to the log.

        Args:
            record: Download record to persist
        """
        self._ensure_dir()
        with open(self.log_file, "a") as f:
            f.write(record.to_json_line() + "\n")

    def read_all(self) -> list[DownloadRecord]:
        """Read all records from the provenance log.

        Returns:
            List of DownloadRecord objects
        """
        records: list[DownloadRecord] = []
        if not self.log_file.exists():
            return records

        with open(self.log_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                records.append(DownloadRecord(**data))

        return records

    def get_url_for_artifact(self, artifact_name: str) -> str | None:
        """Look up the source URL for a named artifact.

        Args:
            artifact_name: Artifact name to search for

        Returns:
            Source URL if found, None otherwise
        """
        for record in reversed(self.read_all()):
            if record.artifact == artifact_name and record.success:
                return record.url
        return None

    def get_url_for_file(self, file_path: str | Path) -> str | None:
        """Look up the source URL for a file by its destination path.

        Args:
            file_path: Destination path to search for

        Returns:
            Source URL if found, None otherwise
        """
        file_path_str = str(file_path)
        for record in reversed(self.read_all()):
            if record.dest_path == file_path_str and record.success:
                return record.url
        return None


class Downloader:
    """Centralized artifact downloader with provenance tracking.

    All downloads go through this class to ensure every artifact
    has a recorded source URL, checksum, and metadata.
    """

    def __init__(
        self,
        provenance_dir: Path | None = None,
        verify_checksums: bool = True,
    ) -> None:
        """Initialize downloader.

        Args:
            provenance_dir: Directory for provenance log.
                Defaults to build/provenance/.
            verify_checksums: Whether to verify checksums when checksum_url
                is provided. Defaults to True.
        """
        self.log = ProvenanceLog(provenance_dir)
        self.verify_checksums = verify_checksums

    def download(
        self,
        url: str,
        dest: Path,
        artifact_name: str | None = None,
        checksum_url: str | None = None,
    ) -> DownloadRecord:
        """Download a file and record provenance.

        Args:
            url: URL to download
            dest: Destination file path
            artifact_name: Human-readable name (defaults to filename)
            checksum_url: Optional URL containing expected SHA256

        Returns:
            DownloadRecord with download metadata

        Raises:
            NetworkError: If download fails
            AssetCollectionError: If checksum verification fails
        """
        if artifact_name is None:
            artifact_name = dest.name

        dest.parent.mkdir(parents=True, exist_ok=True)

        # Download with curl to capture HTTP metadata
        record = self._curl_download(url, dest, artifact_name, checksum_url)

        # Verify checksum if URL provided
        if checksum_url and self.verify_checksums and record.success:
            self._verify_checksum(record, checksum_url)

        # Persist provenance
        self.log.append(record)

        if not record.success:
            raise NetworkError(
                f"Download failed: {url}",
                operation="download",
                details={"url": url, "http_status": record.http_status},
            )

        return record

    def download_and_extract(
        self,
        url: str,
        dest_dir: Path,
        artifact_name: str | None = None,
        checksum_url: str | None = None,
        extract_members: list[str] | None = None,
        strip_components: int = 0,
    ) -> DownloadRecord:
        """Download a tar archive, extract it, and record provenance.

        Args:
            url: URL to download
            dest_dir: Directory to extract into
            artifact_name: Human-readable name (defaults to URL basename)
            checksum_url: Optional URL containing expected SHA256
            extract_members: Specific members to extract (None = all)
            strip_components: Number of leading path components to strip

        Returns:
            DownloadRecord with download metadata

        Raises:
            NetworkError: If download fails
            AssetCollectionError: If extraction or checksum verification fails
        """
        if artifact_name is None:
            artifact_name = Path(urlparse(url).path).name

        dest_dir.mkdir(parents=True, exist_ok=True)

        # Download to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as tmp:
            tmp_path = Path(tmp.name)

        try:
            record = self._curl_download(url, tmp_path, artifact_name, checksum_url)
            record.dest_path = str(dest_dir)

            if not record.success:
                self.log.append(record)
                raise NetworkError(
                    f"Download failed: {url}",
                    operation="download_and_extract",
                    details={"url": url, "http_status": record.http_status},
                )

            # Verify checksum
            if checksum_url and self.verify_checksums:
                self._verify_checksum(record, checksum_url)

            # Extract
            self._extract_tar(tmp_path, dest_dir, extract_members, strip_components)

            self.log.append(record)
            return record

        finally:
            tmp_path.unlink(missing_ok=True)

    def _curl_download(
        self,
        url: str,
        dest: Path,
        artifact_name: str,
        checksum_url: str | None,
    ) -> DownloadRecord:
        """Execute curl download and build record.

        Args:
            url: URL to download
            dest: Destination path
            artifact_name: Artifact name for the record
            checksum_url: Checksum URL (stored in record)

        Returns:
            DownloadRecord (success may be False)
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Use curl with write-out to capture metadata
        write_out = json.dumps({
            "http_code": "%{http_code}",
            "url_effective": "%{url_effective}",
            "content_type": "%{content_type}",
            "size_download": "%{size_download}",
        })

        try:
            result = subprocess.run(
                [
                    "curl",
                    "-fsSL",
                    "-o", str(dest),
                    "-w", write_out,
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=600,
            )

            if result.returncode != 0:
                return DownloadRecord(
                    artifact=artifact_name,
                    url=url,
                    resolved_url=url,
                    dest_path=str(dest),
                    sha256="",
                    size_bytes=0,
                    http_status=0,
                    checksum_url=checksum_url,
                    checksum_verified=False,
                    success=False,
                    timestamp=timestamp,
                )

            # Parse curl write-out
            curl_meta = json.loads(result.stdout)
            http_status = int(curl_meta.get("http_code", "0"))
            resolved_url = curl_meta.get("url_effective", url)

            # Calculate SHA256
            sha256 = self._sha256(dest)
            size_bytes = dest.stat().st_size if dest.exists() else 0

            return DownloadRecord(
                artifact=artifact_name,
                url=url,
                resolved_url=resolved_url,
                dest_path=str(dest),
                sha256=sha256,
                size_bytes=size_bytes,
                http_status=http_status,
                checksum_url=checksum_url,
                checksum_verified=False,
                success=True,
                timestamp=timestamp,
                headers={"content_type": curl_meta.get("content_type", "")},
            )

        except subprocess.TimeoutExpired:
            return DownloadRecord(
                artifact=artifact_name,
                url=url,
                resolved_url=url,
                dest_path=str(dest),
                sha256="",
                size_bytes=0,
                http_status=0,
                checksum_url=checksum_url,
                checksum_verified=False,
                success=False,
                timestamp=timestamp,
            )

    def _verify_checksum(self, record: DownloadRecord, checksum_url: str) -> None:
        """Verify downloaded file against upstream checksum.

        Args:
            record: Download record to update
            checksum_url: URL containing expected checksum

        Raises:
            AssetCollectionError: If checksum doesn't match
        """
        try:
            result = subprocess.run(
                ["curl", "-fsSL", checksum_url],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return  # Can't verify, leave checksum_verified=False

            # Parse checksum (handle both "hash" and "hash  filename" formats)
            expected = result.stdout.strip().split()[0]

            if expected == record.sha256:
                record.checksum_verified = True
            else:
                record.checksum_verified = False
                record.success = False
                raise AssetCollectionError(
                    f"Checksum mismatch for {record.artifact}",
                    operation="checksum_verification",
                    details={
                        "expected": expected,
                        "actual": record.sha256,
                        "url": record.url,
                        "checksum_url": checksum_url,
                    },
                )

        except subprocess.TimeoutExpired:
            pass  # Can't verify, leave checksum_verified=False
        except AssetCollectionError:
            raise
        except Exception:
            pass  # Non-fatal: can't verify

    def _extract_tar(
        self,
        archive: Path,
        dest_dir: Path,
        members: list[str] | None,
        strip_components: int,
    ) -> None:
        """Extract tar archive.

        Args:
            archive: Path to tar archive
            dest_dir: Extraction destination
            members: Specific members to extract
            strip_components: Leading path components to strip

        Raises:
            AssetCollectionError: If extraction fails
        """
        try:
            with tarfile.open(archive, "r:gz") as tar:
                if members:
                    tar_members = [
                        m for m in tar.getmembers()
                        if any(m.name == member or m.name.endswith("/" + member) for member in members)
                    ]
                else:
                    tar_members = tar.getmembers()

                if strip_components > 0:
                    for member in tar_members:
                        parts = member.name.split("/")
                        if len(parts) > strip_components:
                            member.name = "/".join(parts[strip_components:])
                        else:
                            continue

                tar.extractall(path=dest_dir, members=tar_members)

        except (tarfile.TarError, OSError) as exc:
            raise AssetCollectionError(
                f"Failed to extract archive: {archive}",
                operation="extract",
                details={"archive": str(archive), "dest": str(dest_dir)},
            ) from exc

    @staticmethod
    def _sha256(file_path: Path) -> str:
        """Calculate SHA256 of a file.

        Args:
            file_path: Path to file

        Returns:
            Hex-encoded SHA256 digest
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
