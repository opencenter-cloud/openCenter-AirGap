"""Unit tests for the centralized downloader with provenance tracking."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

import pytest

from opencenter_build.downloader import (
    DownloadRecord,
    ProvenanceLog,
    Downloader,
)
from opencenter_build.exceptions import AssetCollectionError, NetworkError


class TestDownloadRecord:
    """Test DownloadRecord dataclass."""

    def test_creates_with_required_fields(self):
        """Test record creation with minimal fields."""
        record = DownloadRecord(
            artifact="kubectl",
            url="https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
            resolved_url="https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
            dest_path="/tmp/kubectl",
            sha256="abc123",
            size_bytes=1024,
            http_status=200,
        )
        assert record.artifact == "kubectl"
        assert record.success is True
        assert record.checksum_verified is False

    def test_auto_sets_timestamp(self):
        """Test that timestamp is auto-populated."""
        record = DownloadRecord(
            artifact="test",
            url="https://example.com/file",
            resolved_url="https://example.com/file",
            dest_path="/tmp/file",
            sha256="abc",
            size_bytes=100,
            http_status=200,
        )
        assert record.timestamp != ""
        assert "T" in record.timestamp  # ISO format

    def test_to_json_line_produces_valid_json(self):
        """Test JSON serialization."""
        record = DownloadRecord(
            artifact="helm",
            url="https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz",
            resolved_url="https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz",
            dest_path="/tmp/helm.tar.gz",
            sha256="deadbeef",
            size_bytes=2048,
            http_status=200,
            timestamp="2026-05-08T10:00:00Z",
        )
        line = record.to_json_line()
        parsed = json.loads(line)
        assert parsed["artifact"] == "helm"
        assert parsed["sha256"] == "deadbeef"
        assert parsed["size_bytes"] == 2048
        assert "\n" not in line


class TestProvenanceLog:
    """Test ProvenanceLog append-only log."""

    def test_append_creates_file(self, tmp_path):
        """Test that append creates the ndjson file."""
        log = ProvenanceLog(tmp_path)
        record = DownloadRecord(
            artifact="test",
            url="https://example.com/file",
            resolved_url="https://example.com/file",
            dest_path="/tmp/file",
            sha256="abc123",
            size_bytes=100,
            http_status=200,
            timestamp="2026-05-08T10:00:00Z",
        )
        log.append(record)

        assert (tmp_path / "downloads.ndjson").exists()

    def test_append_is_additive(self, tmp_path):
        """Test that multiple appends produce multiple lines."""
        log = ProvenanceLog(tmp_path)

        for i in range(3):
            record = DownloadRecord(
                artifact=f"artifact-{i}",
                url=f"https://example.com/file-{i}",
                resolved_url=f"https://example.com/file-{i}",
                dest_path=f"/tmp/file-{i}",
                sha256=f"sha-{i}",
                size_bytes=100 * i,
                http_status=200,
                timestamp="2026-05-08T10:00:00Z",
            )
            log.append(record)

        lines = (tmp_path / "downloads.ndjson").read_text().strip().split("\n")
        assert len(lines) == 3

    def test_read_all_returns_records(self, tmp_path):
        """Test reading all records back."""
        log = ProvenanceLog(tmp_path)

        record = DownloadRecord(
            artifact="kubectl",
            url="https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
            resolved_url="https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
            dest_path="/tmp/kubectl",
            sha256="abc123",
            size_bytes=50_000_000,
            http_status=200,
            timestamp="2026-05-08T10:00:00Z",
        )
        log.append(record)

        records = log.read_all()
        assert len(records) == 1
        assert records[0].artifact == "kubectl"
        assert records[0].sha256 == "abc123"

    def test_read_all_empty_file(self, tmp_path):
        """Test reading from empty/nonexistent file."""
        log = ProvenanceLog(tmp_path)
        records = log.read_all()
        assert records == []

    def test_get_url_for_artifact(self, tmp_path):
        """Test URL lookup by artifact name."""
        log = ProvenanceLog(tmp_path)

        record = DownloadRecord(
            artifact="helm",
            url="https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz",
            resolved_url="https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz",
            dest_path="/tmp/helm.tar.gz",
            sha256="deadbeef",
            size_bytes=2048,
            http_status=200,
            success=True,
            timestamp="2026-05-08T10:00:00Z",
        )
        log.append(record)

        url = log.get_url_for_artifact("helm")
        assert url == "https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz"

    def test_get_url_for_artifact_not_found(self, tmp_path):
        """Test URL lookup returns None for unknown artifact."""
        log = ProvenanceLog(tmp_path)
        assert log.get_url_for_artifact("nonexistent") is None

    def test_get_url_for_file(self, tmp_path):
        """Test URL lookup by file path."""
        log = ProvenanceLog(tmp_path)

        record = DownloadRecord(
            artifact="kubectl",
            url="https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
            resolved_url="https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
            dest_path="/opt/tools/kubectl",
            sha256="abc",
            size_bytes=100,
            http_status=200,
            success=True,
            timestamp="2026-05-08T10:00:00Z",
        )
        log.append(record)

        url = log.get_url_for_file("/opt/tools/kubectl")
        assert url == "https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl"


class TestDownloader:
    """Test Downloader class."""

    @patch("opencenter_build.downloader.subprocess.run")
    def test_download_success(self, mock_run, tmp_path):
        """Test successful download records provenance."""
        dest = tmp_path / "kubectl"
        dest.write_bytes(b"fake binary content")

        # Mock curl execution
        curl_output = json.dumps({
            "http_code": "200",
            "url_effective": "https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
            "content_type": "application/octet-stream",
            "size_download": "19",
        })
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=curl_output,
        )

        downloader = Downloader(provenance_dir=tmp_path / "provenance")
        record = downloader.download(
            url="https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
            dest=dest,
            artifact_name="kubectl",
        )

        assert record.success is True
        assert record.artifact == "kubectl"
        assert record.http_status == 200
        assert record.sha256 != ""

        # Verify provenance was written
        log_file = tmp_path / "provenance" / "downloads.ndjson"
        assert log_file.exists()
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 1

    @patch("opencenter_build.downloader.subprocess.run")
    def test_download_failure_raises_network_error(self, mock_run, tmp_path):
        """Test failed download raises NetworkError."""
        mock_run.return_value = MagicMock(returncode=22, stdout="")

        downloader = Downloader(provenance_dir=tmp_path / "provenance")

        with pytest.raises(NetworkError):
            downloader.download(
                url="https://example.com/nonexistent",
                dest=tmp_path / "file",
                artifact_name="test",
            )

        # Provenance should still be recorded for failures
        log_file = tmp_path / "provenance" / "downloads.ndjson"
        assert log_file.exists()

    @patch("opencenter_build.downloader.subprocess.run")
    def test_checksum_verification_success(self, mock_run, tmp_path):
        """Test checksum verification marks record as verified."""
        dest = tmp_path / "binary"
        dest.write_bytes(b"test content")

        import hashlib
        expected_sha = hashlib.sha256(b"test content").hexdigest()

        # First call: download, second call: checksum fetch
        mock_run.side_effect = [
            MagicMock(
                returncode=0,
                stdout=json.dumps({
                    "http_code": "200",
                    "url_effective": "https://example.com/binary",
                    "content_type": "application/octet-stream",
                    "size_download": "12",
                }),
            ),
            MagicMock(
                returncode=0,
                stdout=f"{expected_sha}  binary\n",
            ),
        ]

        downloader = Downloader(provenance_dir=tmp_path / "provenance")
        record = downloader.download(
            url="https://example.com/binary",
            dest=dest,
            artifact_name="binary",
            checksum_url="https://example.com/binary.sha256",
        )

        assert record.checksum_verified is True

    @patch("opencenter_build.downloader.subprocess.run")
    def test_checksum_mismatch_raises_error(self, mock_run, tmp_path):
        """Test checksum mismatch raises AssetCollectionError."""
        dest = tmp_path / "binary"
        dest.write_bytes(b"test content")

        # First call: download, second call: checksum fetch (wrong hash)
        mock_run.side_effect = [
            MagicMock(
                returncode=0,
                stdout=json.dumps({
                    "http_code": "200",
                    "url_effective": "https://example.com/binary",
                    "content_type": "application/octet-stream",
                    "size_download": "12",
                }),
            ),
            MagicMock(
                returncode=0,
                stdout="0000000000000000000000000000000000000000000000000000000000000000  binary\n",
            ),
        ]

        downloader = Downloader(provenance_dir=tmp_path / "provenance")

        with pytest.raises(AssetCollectionError):
            downloader.download(
                url="https://example.com/binary",
                dest=dest,
                artifact_name="binary",
                checksum_url="https://example.com/binary.sha256",
            )
