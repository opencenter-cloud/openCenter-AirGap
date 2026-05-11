"""Unit tests for SLSA provenance attestation generator."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from opencenter_build.provenance import (
    ProvenanceSubject,
    ResolvedDependency,
    BuildMetadata,
    SLSAProvenance,
    ProvenanceGenerator,
    INTOTO_STATEMENT_TYPE,
    SLSA_PROVENANCE_TYPE,
    BUILD_TYPE,
    BUILDER_ID,
)
from opencenter_build.downloader import DownloadRecord, ProvenanceLog


class TestProvenanceSubject:
    """Test ProvenanceSubject serialization."""

    def test_to_dict_with_sha256_only(self):
        """Test subject with SHA256 digest."""
        subject = ProvenanceSubject(
            name="zarf-package-openCenter-airgap-amd64-1.0.0.tar.zst",
            sha256="abc123def456",
        )
        result = subject.to_dict()
        assert result["name"] == "zarf-package-openCenter-airgap-amd64-1.0.0.tar.zst"
        assert result["digest"] == {"sha256": "abc123def456"}

    def test_to_dict_with_both_digests(self):
        """Test subject with SHA256 and SHA512."""
        subject = ProvenanceSubject(
            name="package.tar.zst",
            sha256="abc",
            sha512="def",
        )
        result = subject.to_dict()
        assert result["digest"] == {"sha256": "abc", "sha512": "def"}


class TestResolvedDependency:
    """Test ResolvedDependency serialization."""

    def test_to_dict_minimal(self):
        """Test dependency with required fields only."""
        dep = ResolvedDependency(
            uri="https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
            digest={"sha256": "abc123"},
            name="kubectl",
        )
        result = dep.to_dict()
        assert result["uri"] == "https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl"
        assert result["digest"] == {"sha256": "abc123"}
        assert result["name"] == "kubectl"
        assert "downloadLocation" not in result

    def test_to_dict_with_download_location(self):
        """Test dependency with download location."""
        dep = ResolvedDependency(
            uri="https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
            digest={"sha256": "abc123"},
            name="kubectl",
            download_location="https://cdn.dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
        )
        result = dep.to_dict()
        assert result["downloadLocation"] == "https://cdn.dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl"


class TestBuildMetadata:
    """Test BuildMetadata serialization."""

    def test_to_dict_full(self):
        """Test metadata with all fields."""
        meta = BuildMetadata(
            invocation_id="build-20260508-143000",
            started_on="2026-05-08T14:30:00Z",
            finished_on="2026-05-08T15:45:00Z",
        )
        result = meta.to_dict()
        assert result["invocationId"] == "build-20260508-143000"
        assert result["startedOn"] == "2026-05-08T14:30:00Z"
        assert result["finishedOn"] == "2026-05-08T15:45:00Z"

    def test_to_dict_minimal(self):
        """Test metadata with only invocation ID."""
        meta = BuildMetadata(invocation_id="build-123")
        result = meta.to_dict()
        assert result["invocationId"] == "build-123"
        assert "startedOn" not in result


class TestSLSAProvenance:
    """Test SLSAProvenance attestation structure."""

    def test_to_dict_produces_valid_intoto_statement(self):
        """Test that output conforms to in-toto Statement v1."""
        provenance = SLSAProvenance(
            subjects=[
                ProvenanceSubject(name="package.tar.zst", sha256="abc123")
            ],
            dependencies=[
                ResolvedDependency(
                    uri="https://example.com/binary",
                    digest={"sha256": "def456"},
                    name="binary",
                )
            ],
            build_metadata=BuildMetadata(
                invocation_id="build-001",
                started_on="2026-05-08T14:30:00Z",
                finished_on="2026-05-08T15:00:00Z",
            ),
            build_config={"versions": {"KUBERNETES_VERSION": "v1.34.3"}},
            builder_version="1.0.0",
        )

        result = provenance.to_dict()

        # Verify top-level structure
        assert result["_type"] == INTOTO_STATEMENT_TYPE
        assert result["predicateType"] == SLSA_PROVENANCE_TYPE
        assert len(result["subject"]) == 1
        assert result["subject"][0]["name"] == "package.tar.zst"

        # Verify predicate structure
        predicate = result["predicate"]
        assert predicate["buildDefinition"]["buildType"] == BUILD_TYPE
        assert len(predicate["buildDefinition"]["resolvedDependencies"]) == 1
        assert predicate["runDetails"]["builder"]["id"] == BUILDER_ID
        assert predicate["runDetails"]["metadata"]["invocationId"] == "build-001"

    def test_to_dict_empty_provenance(self):
        """Test empty provenance still produces valid structure."""
        provenance = SLSAProvenance()
        result = provenance.to_dict()

        assert result["_type"] == INTOTO_STATEMENT_TYPE
        assert result["subject"] == []
        assert result["predicate"]["buildDefinition"]["resolvedDependencies"] == []


class TestProvenanceGenerator:
    """Test ProvenanceGenerator end-to-end."""

    def test_generate_creates_attestation(self, tmp_path):
        """Test generating provenance from a package and log."""
        # Create a fake package
        package = tmp_path / "dist" / "zarf-package-test-amd64-1.0.0.tar.zst"
        package.parent.mkdir(parents=True)
        package.write_bytes(b"fake package content")

        # Create provenance log with some records
        provenance_dir = tmp_path / "provenance"
        provenance_dir.mkdir()
        log = ProvenanceLog(provenance_dir)

        log.append(DownloadRecord(
            artifact="kubectl",
            url="https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
            resolved_url="https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
            dest_path="/tmp/kubectl",
            sha256="aaa111",
            size_bytes=50_000_000,
            http_status=200,
            success=True,
            timestamp="2026-05-08T10:00:00Z",
        ))
        log.append(DownloadRecord(
            artifact="helm",
            url="https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz",
            resolved_url="https://get.helm.sh/helm-v4.0.5-linux-amd64.tar.gz",
            dest_path="/tmp/helm.tar.gz",
            sha256="bbb222",
            size_bytes=20_000_000,
            http_status=200,
            success=True,
            timestamp="2026-05-08T10:01:00Z",
        ))

        # Generate
        generator = ProvenanceGenerator(
            provenance_dir=provenance_dir,
            project_root=tmp_path,
        )

        provenance = generator.generate(
            package_path=package,
            build_id="test-build-001",
            started_on="2026-05-08T10:00:00Z",
            versions_env={"KUBERNETES_VERSION": "v1.34.3"},
        )

        assert len(provenance.subjects) == 1
        assert provenance.subjects[0].name == "zarf-package-test-amd64-1.0.0.tar.zst"
        assert provenance.subjects[0].sha256 != ""
        assert len(provenance.dependencies) == 2
        assert provenance.build_metadata.invocation_id == "test-build-001"

    def test_export_writes_valid_json(self, tmp_path):
        """Test export produces valid JSON file."""
        package = tmp_path / "package.tar.zst"
        package.write_bytes(b"content")

        provenance_dir = tmp_path / "provenance"
        provenance_dir.mkdir()

        generator = ProvenanceGenerator(
            provenance_dir=provenance_dir,
            project_root=tmp_path,
        )

        provenance = generator.generate(
            package_path=package,
            build_id="export-test",
        )

        output = tmp_path / "output" / "provenance.json"
        written = generator.export(provenance, output)

        assert written.exists()
        data = json.loads(written.read_text())
        assert data["_type"] == INTOTO_STATEMENT_TYPE
        assert data["predicateType"] == SLSA_PROVENANCE_TYPE

    def test_deduplicates_dependencies(self, tmp_path):
        """Test that duplicate URLs are deduplicated."""
        package = tmp_path / "package.tar.zst"
        package.write_bytes(b"content")

        provenance_dir = tmp_path / "provenance"
        provenance_dir.mkdir()
        log = ProvenanceLog(provenance_dir)

        # Same URL downloaded twice (e.g., retry)
        for _ in range(2):
            log.append(DownloadRecord(
                artifact="kubectl",
                url="https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
                resolved_url="https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl",
                dest_path="/tmp/kubectl",
                sha256="aaa111",
                size_bytes=50_000_000,
                http_status=200,
                success=True,
                timestamp="2026-05-08T10:00:00Z",
            ))

        generator = ProvenanceGenerator(
            provenance_dir=provenance_dir,
            project_root=tmp_path,
        )

        provenance = generator.generate(package_path=package, build_id="dedup-test")
        assert len(provenance.dependencies) == 1

    def test_skips_failed_downloads(self, tmp_path):
        """Test that failed downloads are excluded from dependencies."""
        package = tmp_path / "package.tar.zst"
        package.write_bytes(b"content")

        provenance_dir = tmp_path / "provenance"
        provenance_dir.mkdir()
        log = ProvenanceLog(provenance_dir)

        log.append(DownloadRecord(
            artifact="good",
            url="https://example.com/good",
            resolved_url="https://example.com/good",
            dest_path="/tmp/good",
            sha256="aaa",
            size_bytes=100,
            http_status=200,
            success=True,
            timestamp="2026-05-08T10:00:00Z",
        ))
        log.append(DownloadRecord(
            artifact="bad",
            url="https://example.com/bad",
            resolved_url="https://example.com/bad",
            dest_path="/tmp/bad",
            sha256="",
            size_bytes=0,
            http_status=404,
            success=False,
            timestamp="2026-05-08T10:01:00Z",
        ))

        generator = ProvenanceGenerator(
            provenance_dir=provenance_dir,
            project_root=tmp_path,
        )

        provenance = generator.generate(package_path=package, build_id="filter-test")
        assert len(provenance.dependencies) == 1
        assert provenance.dependencies[0].name == "good"
