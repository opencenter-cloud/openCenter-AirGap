"""Unit tests for kubespray-offline provenance reconstruction."""

import json
from pathlib import Path

import pytest

from opencenter_build.provenance_kubespray import (
    parse_kubespray_offline_config,
    reconstruct_urls,
    generate_kubespray_provenance,
    _parse_env_file,
    KubesprayOfflineConfig,
)


class TestParseEnvFile:
    """Test shell env file parsing."""

    def test_parses_simple_assignments(self, tmp_path):
        """Test parsing VAR=value lines."""
        env_file = tmp_path / "versions.env"
        env_file.write_text(
            'KUBERNETES_VERSION="v1.34.3"\n'
            'RUNC_VERSION="1.3.4"\n'
            "CNI_VERSION=1.8.0\n"
        )

        versions: dict[str, str] = {}
        _parse_env_file(env_file, versions)

        assert versions["KUBERNETES_VERSION"] == "v1.34.3"
        assert versions["RUNC_VERSION"] == "1.3.4"
        assert versions["CNI_VERSION"] == "1.8.0"

    def test_skips_comments_and_empty_lines(self, tmp_path):
        """Test that comments and blanks are ignored."""
        env_file = tmp_path / "config.env"
        env_file.write_text(
            "# This is a comment\n"
            "\n"
            "KEY=value\n"
            "  # indented comment\n"
        )

        versions: dict[str, str] = {}
        _parse_env_file(env_file, versions)

        assert versions == {"KEY": "value"}

    def test_handles_export_prefix(self, tmp_path):
        """Test stripping 'export' prefix."""
        env_file = tmp_path / "env"
        env_file.write_text("export MY_VAR=hello\n")

        versions: dict[str, str] = {}
        _parse_env_file(env_file, versions)

        assert versions["MY_VAR"] == "hello"


class TestParseKubesprayOfflineConfig:
    """Test kubespray-offline config parsing."""

    def test_parses_config_directory(self, tmp_path):
        """Test parsing a config directory with env files."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        (config_dir / "versions.env").write_text(
            'KUBERNETES_VERSION="v1.34.3"\n'
            'CONTAINERD_VERSION="2.1.5"\n'
        )

        config = parse_kubespray_offline_config(tmp_path)
        assert config.versions["KUBERNETES_VERSION"] == "v1.34.3"
        assert config.versions["CONTAINERD_VERSION"] == "2.1.5"

    def test_returns_empty_config_if_no_config_dir(self, tmp_path):
        """Test graceful handling of missing config directory."""
        config = parse_kubespray_offline_config(tmp_path)
        assert config.versions == {}
        assert config.image_urls == []

    def test_reads_image_lists(self, tmp_path):
        """Test reading image list files."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        (config_dir / "images.txt").write_text(
            "registry.k8s.io/kube-apiserver:v1.34.3\n"
            "registry.k8s.io/kube-controller-manager:v1.34.3\n"
            "# comment\n"
        )

        config = parse_kubespray_offline_config(tmp_path)
        assert "registry.k8s.io/kube-apiserver:v1.34.3" in config.image_urls
        assert "registry.k8s.io/kube-controller-manager:v1.34.3" in config.image_urls
        assert len(config.image_urls) == 2  # comment excluded


class TestReconstructUrls:
    """Test URL reconstruction from downloaded artifacts."""

    def test_reconstructs_kubectl_url(self, tmp_path):
        """Test kubectl binary URL reconstruction."""
        # Set up directory structure
        outputs_dir = tmp_path / "outputs" / "files"
        outputs_dir.mkdir(parents=True)
        (outputs_dir / "kubectl").write_bytes(b"fake kubectl binary")

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "versions.env").write_text('KUBERNETES_VERSION="v1.34.3"\n')

        versions = {"KUBERNETES_VERSION": "v1.34.3"}
        records = reconstruct_urls(tmp_path, versions)

        kubectl_records = [r for r in records if r.artifact == "kubectl"]
        assert len(kubectl_records) == 1
        assert "dl.k8s.io" in kubectl_records[0].url
        assert "v1.34.3" in kubectl_records[0].url

    def test_reconstructs_containerd_url(self, tmp_path):
        """Test containerd archive URL reconstruction."""
        outputs_dir = tmp_path / "outputs" / "files"
        outputs_dir.mkdir(parents=True)
        (outputs_dir / "containerd-2.1.5-linux-amd64.tar.gz").write_bytes(b"fake")

        records = reconstruct_urls(tmp_path)

        containerd_records = [r for r in records if "containerd" in r.artifact]
        assert len(containerd_records) == 1
        assert "github.com/containerd" in containerd_records[0].url
        assert "2.1.5" in containerd_records[0].url

    def test_unknown_files_get_empty_url(self, tmp_path):
        """Test that unrecognized files get empty URL."""
        outputs_dir = tmp_path / "outputs" / "files"
        outputs_dir.mkdir(parents=True)
        (outputs_dir / "mystery-binary").write_bytes(b"unknown")

        records = reconstruct_urls(tmp_path)

        mystery_records = [r for r in records if r.artifact == "mystery-binary"]
        assert len(mystery_records) == 1
        assert mystery_records[0].url == ""
        assert mystery_records[0].success is False

    def test_returns_empty_for_missing_outputs(self, tmp_path):
        """Test graceful handling of missing outputs directory."""
        records = reconstruct_urls(tmp_path)
        assert records == []


class TestGenerateKubesprayProvenance:
    """Test full provenance generation."""

    def test_generates_provenance_file(self, tmp_path):
        """Test that provenance JSON file is created."""
        # Set up minimal kubespray-offline structure
        outputs_dir = tmp_path / "kso" / "outputs" / "files"
        outputs_dir.mkdir(parents=True)
        (outputs_dir / "kubectl").write_bytes(b"kubectl binary")
        (outputs_dir / "kubelet").write_bytes(b"kubelet binary")

        config_dir = tmp_path / "kso" / "config"
        config_dir.mkdir()
        (config_dir / "versions.env").write_text('KUBERNETES_VERSION="v1.34.3"\n')

        provenance_dir = tmp_path / "provenance"
        versions = {"KUBERNETES_VERSION": "v1.34.3"}

        output = generate_kubespray_provenance(
            kubespray_offline_dir=tmp_path / "kso",
            provenance_dir=provenance_dir,
            versions_env=versions,
        )

        assert output.exists()
        data = json.loads(output.read_text())
        assert data["total_artifacts"] == 2
        assert data["reconstructed_urls"] >= 1  # At least kubectl should match

    def test_appends_to_main_provenance_log(self, tmp_path):
        """Test that records are also appended to downloads.ndjson."""
        outputs_dir = tmp_path / "kso" / "outputs" / "files"
        outputs_dir.mkdir(parents=True)
        (outputs_dir / "kubectl").write_bytes(b"binary")

        config_dir = tmp_path / "kso" / "config"
        config_dir.mkdir()

        provenance_dir = tmp_path / "provenance"

        generate_kubespray_provenance(
            kubespray_offline_dir=tmp_path / "kso",
            provenance_dir=provenance_dir,
            versions_env={"KUBERNETES_VERSION": "v1.34.3"},
        )

        ndjson = provenance_dir / "downloads.ndjson"
        assert ndjson.exists()
        lines = ndjson.read_text().strip().split("\n")
        assert len(lines) >= 1
