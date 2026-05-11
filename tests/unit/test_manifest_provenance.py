"""Unit tests for ArtifactManifest source_url integration with provenance log."""

import json
from pathlib import Path

import pytest

from opencenter_build.manifest import ManifestGenerator, ArtifactManifest


class TestManifestGeneratorProvenanceIndex:
    """Test provenance index loading and lookup."""

    def test_loads_provenance_index_from_ndjson(self, tmp_path):
        """Test that provenance index is built from downloads.ndjson."""
        # Create provenance log
        provenance_dir = tmp_path / "provenance"
        provenance_dir.mkdir()
        ndjson = provenance_dir / "downloads.ndjson"
        ndjson.write_text(
            json.dumps({
                "artifact": "kubectl",
                "url": "https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
                "resolved_url": "https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
                "dest_path": "/tmp/kubectl",
                "sha256": "abc123",
                "size_bytes": 50000000,
                "http_status": 200,
                "success": True,
                "timestamp": "2026-05-08T10:00:00Z",
            }) + "\n"
        )

        generator = ManifestGenerator(tmp_path)
        url = generator._lookup_source_url(sha256="abc123")
        assert url == "https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl"

    def test_lookup_by_artifact_name(self, tmp_path):
        """Test lookup falls back to artifact name."""
        provenance_dir = tmp_path / "provenance"
        provenance_dir.mkdir()
        ndjson = provenance_dir / "downloads.ndjson"
        ndjson.write_text(
            json.dumps({
                "artifact": "helm",
                "url": "https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz",
                "resolved_url": "https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz",
                "dest_path": "/tmp/helm.tar.gz",
                "sha256": "deadbeef",
                "size_bytes": 2048,
                "http_status": 200,
                "success": True,
                "timestamp": "2026-05-08T10:00:00Z",
            }) + "\n"
        )

        generator = ManifestGenerator(tmp_path)
        url = generator._lookup_source_url(name="helm")
        assert url == "https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz"

    def test_lookup_by_path_basename(self, tmp_path):
        """Test lookup falls back to dest path basename."""
        provenance_dir = tmp_path / "provenance"
        provenance_dir.mkdir()
        ndjson = provenance_dir / "downloads.ndjson"
        ndjson.write_text(
            json.dumps({
                "artifact": "stern",
                "url": "https://github.com/stern/stern/releases/download/v1.33.1/stern_1.33.1_linux_amd64.tar.gz",
                "resolved_url": "https://github.com/stern/stern/releases/download/v1.33.1/stern_1.33.1_linux_amd64.tar.gz",
                "dest_path": "/opt/tools/stern",
                "sha256": "fff000",
                "size_bytes": 1024,
                "http_status": 200,
                "success": True,
                "timestamp": "2026-05-08T10:00:00Z",
            }) + "\n"
        )

        generator = ManifestGenerator(tmp_path)
        url = generator._lookup_source_url(path_name="stern")
        assert "stern" in url

    def test_lookup_returns_empty_for_unknown(self, tmp_path):
        """Test that unknown artifacts return empty string."""
        provenance_dir = tmp_path / "provenance"
        provenance_dir.mkdir()
        (provenance_dir / "downloads.ndjson").write_text("")

        generator = ManifestGenerator(tmp_path)
        url = generator._lookup_source_url(sha256="nonexistent")
        assert url == ""

    def test_skips_failed_records(self, tmp_path):
        """Test that failed downloads are not indexed."""
        provenance_dir = tmp_path / "provenance"
        provenance_dir.mkdir()
        ndjson = provenance_dir / "downloads.ndjson"
        ndjson.write_text(
            json.dumps({
                "artifact": "bad-download",
                "url": "https://example.com/bad",
                "resolved_url": "https://example.com/bad",
                "dest_path": "/tmp/bad",
                "sha256": "bad_sha",
                "size_bytes": 0,
                "http_status": 404,
                "success": False,
                "timestamp": "2026-05-08T10:00:00Z",
            }) + "\n"
        )

        generator = ManifestGenerator(tmp_path)
        url = generator._lookup_source_url(sha256="bad_sha")
        assert url == ""


class TestManifestGeneratorSourceUrl:
    """Test that scan methods populate source_url from provenance."""

    def test_binaries_include_source_url(self, tmp_path):
        """Test that scanned binaries get source_url from provenance."""
        # Create binary
        files_dir = tmp_path / "kubespray-offline" / "outputs" / "files"
        files_dir.mkdir(parents=True)
        kubectl = files_dir / "kubectl"
        kubectl.write_bytes(b"fake kubectl")

        # Calculate its sha256
        import hashlib
        sha256 = hashlib.sha256(b"fake kubectl").hexdigest()

        # Create provenance log with matching sha256
        provenance_dir = tmp_path / "provenance"
        provenance_dir.mkdir()
        ndjson = provenance_dir / "downloads.ndjson"
        ndjson.write_text(
            json.dumps({
                "artifact": "kubectl",
                "url": "https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
                "resolved_url": "https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
                "dest_path": str(kubectl),
                "sha256": sha256,
                "size_bytes": 12,
                "http_status": 200,
                "success": True,
                "timestamp": "2026-05-08T10:00:00Z",
            }) + "\n"
        )

        generator = ManifestGenerator(tmp_path)
        manifest = ArtifactManifest(
            build_id="test", timestamp=__import__("datetime").datetime.now()
        )
        generator._scan_binaries(manifest)

        assert len(manifest.binaries) == 1
        assert manifest.binaries[0]["source_url"] == "https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl"

    def test_binaries_empty_source_url_when_no_provenance(self, tmp_path):
        """Test that binaries get empty source_url when no provenance exists."""
        files_dir = tmp_path / "kubespray-offline" / "outputs" / "files"
        files_dir.mkdir(parents=True)
        (files_dir / "mystery").write_bytes(b"unknown binary")

        generator = ManifestGenerator(tmp_path)
        manifest = ArtifactManifest(
            build_id="test", timestamp=__import__("datetime").datetime.now()
        )
        generator._scan_binaries(manifest)

        assert len(manifest.binaries) == 1
        assert manifest.binaries[0]["source_url"] == ""

    def test_terraform_providers_include_source_url(self, tmp_path):
        """Test that Terraform providers get source_url."""
        tf_dir = tmp_path / "assets" / "terraform-mirror"
        tf_dir.mkdir(parents=True)
        provider = tf_dir / "terraform-provider-openstack_2.1.0_linux_amd64.zip"
        provider.write_bytes(b"fake provider")

        import hashlib
        sha256 = hashlib.sha256(b"fake provider").hexdigest()

        provenance_dir = tmp_path / "provenance"
        provenance_dir.mkdir()
        ndjson = provenance_dir / "downloads.ndjson"
        ndjson.write_text(
            json.dumps({
                "artifact": "terraform-provider-openstack_2.1.0_linux_amd64",
                "url": "https://releases.hashicorp.com/terraform-provider-openstack/2.1.0/terraform-provider-openstack_2.1.0_linux_amd64.zip",
                "resolved_url": "https://releases.hashicorp.com/terraform-provider-openstack/2.1.0/terraform-provider-openstack_2.1.0_linux_amd64.zip",
                "dest_path": str(provider),
                "sha256": sha256,
                "size_bytes": 13,
                "http_status": 200,
                "success": True,
                "timestamp": "2026-05-08T10:00:00Z",
            }) + "\n"
        )

        generator = ManifestGenerator(tmp_path)
        manifest = ArtifactManifest(
            build_id="test", timestamp=__import__("datetime").datetime.now()
        )
        generator._scan_terraform_providers(manifest)

        assert len(manifest.terraform_providers) == 1
        assert "hashicorp.com" in manifest.terraform_providers[0]["source_url"]
