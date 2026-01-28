#!/usr/bin/env python3
"""Unit tests for scan_repository_images.py"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import sys

# Add scripts/build to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "build"))

from scan_repository_images import RepositoryScanner


class TestRepositoryScanner:
    """Test RepositoryScanner class."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository structure."""
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()

        # Create test files
        (repo_path / "values.yaml").write_text(
            """
image:
  repository: docker.io/nginx
  tag: 1.21.0
"""
        )

        (repo_path / "deployment.yaml").write_text(
            """
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: app
        image: quay.io/prometheus/prometheus:v2.30.0
"""
        )

        (repo_path / "script.sh").write_text(
            """
#!/bin/bash
# Download from https://github.com/example/repo/releases/download/v1.0.0/binary.tar.gz
docker pull gcr.io/google-containers/pause:3.5
"""
        )

        # Create directory to skip
        skip_dir = repo_path / ".git"
        skip_dir.mkdir()
        (skip_dir / "config").write_text("should be skipped")

        return repo_path

    def test_scanner_initialization(self, temp_repo):
        """Test scanner initializes correctly."""
        scanner = RepositoryScanner(temp_repo, "test-repo")

        assert scanner.repo_path == temp_repo
        assert scanner.repo_name == "test-repo"
        assert len(scanner.images) == 0
        assert len(scanner.urls) == 0

    def test_scan_finds_images(self, temp_repo):
        """Test scanner finds container images."""
        scanner = RepositoryScanner(temp_repo, "test-repo")
        images, urls = scanner.scan()

        # Should find images from YAML files
        assert len(images) > 0

        # Check specific images
        image_list = list(images)
        assert any("nginx" in img for img in image_list)
        assert any("prometheus" in img for img in image_list)
        assert any("pause" in img for img in image_list)

    def test_scan_finds_urls(self, temp_repo):
        """Test scanner finds URLs."""
        scanner = RepositoryScanner(temp_repo, "test-repo")
        images, urls = scanner.scan()

        # Should find GitHub URL
        assert len(urls) > 0
        assert any("github.com" in url for url in urls)

    def test_skip_git_directory(self, temp_repo):
        """Test scanner skips .git directory."""
        scanner = RepositoryScanner(temp_repo, "test-repo")

        scanned_files = list(scanner._walk_files())

        # Should not include files from .git
        assert not any(".git" in str(f) for f in scanned_files)

    def test_normalize_image_full_format(self, temp_repo):
        """Test image normalization with full registry/repo:tag."""
        scanner = RepositoryScanner(temp_repo, "test-repo")

        import re

        pattern = r"(?P<registry>[\w\-\.]+)/(?P<repo>[\w\-\.]+(?:/[\w\-\.]+)+):(?P<tag>[\w\-\.]+)"
        match = re.match(pattern, "docker.io/library/nginx:1.21.0")

        if match:
            normalized = scanner._normalize_image(match)
            assert normalized == "docker.io/library/nginx:1.21.0"

    def test_normalize_image_docker_hub_shorthand(self, temp_repo):
        """Test image normalization with Docker Hub shorthand."""
        scanner = RepositoryScanner(temp_repo, "test-repo")

        import re

        pattern = r"\b(?P<repo>[\w\-]+/[\w\-]+):(?P<tag>[\w\-\.]+)\b"
        match = re.match(pattern, "nginx/nginx:1.21.0")

        if match:
            normalized = scanner._normalize_image(match)
            # Should add docker.io registry
            assert "docker.io" in normalized or "nginx/nginx:1.21.0" == normalized

    def test_is_valid_image_rejects_false_positives(self, temp_repo):
        """Test image validation rejects false positives."""
        scanner = RepositoryScanner(temp_repo, "test-repo")

        # Should reject
        assert not scanner._is_valid_image("http://example.com")
        assert not scanner._is_valid_image("https://example.com")
        assert not scanner._is_valid_image("localhost:8080")
        assert not scanner._is_valid_image("example.com")
        assert not scanner._is_valid_image("file.yaml")
        assert not scanner._is_valid_image("short")

        # Should accept
        assert scanner._is_valid_image("docker.io/nginx:1.21")
        assert scanner._is_valid_image("quay.io/repo/image:tag")

    def test_is_valid_url_rejects_false_positives(self, temp_repo):
        """Test URL validation rejects false positives."""
        scanner = RepositoryScanner(temp_repo, "test-repo")

        # Should reject
        assert not scanner._is_valid_url("http://localhost")
        assert not scanner._is_valid_url("http://127.0.0.1")
        assert not scanner._is_valid_url("http://example.com")
        assert not scanner._is_valid_url("short")

        # Should accept
        assert scanner._is_valid_url("https://github.com/user/repo")
        assert scanner._is_valid_url("https://releases.example.io/v1.0.0/file.tar.gz")

    def test_export_results(self, temp_repo, tmp_path):
        """Test exporting scan results."""
        scanner = RepositoryScanner(temp_repo, "test-repo")
        scanner.scan()

        output_dir = tmp_path / "output"
        scanner.export_results(output_dir)

        # Check files created
        assert (output_dir / "test-repo-images.txt").exists()
        assert (output_dir / "test-repo-urls.txt").exists()
        assert (output_dir / "test-repo-scan-details.json").exists()

        # Verify content
        images_content = (output_dir / "test-repo-images.txt").read_text()
        assert "# Container Images from test-repo" in images_content
        assert "# Total:" in images_content

    def test_scan_nonexistent_repo(self, tmp_path):
        """Test scanner handles nonexistent repository."""
        nonexistent = tmp_path / "does-not-exist"
        scanner = RepositoryScanner(nonexistent, "missing")

        images, urls = scanner.scan()

        # Should return empty sets without crashing
        assert len(images) == 0
        assert len(urls) == 0

    def test_scan_tracks_sources(self, temp_repo):
        """Test scanner tracks source files for each image."""
        scanner = RepositoryScanner(temp_repo, "test-repo")
        scanner.scan()

        # Should have source tracking
        assert len(scanner.image_sources) > 0

        # Each image should have at least one source file
        for image, sources in scanner.image_sources.items():
            assert len(sources) > 0
            assert all(isinstance(s, str) for s in sources)

    def test_scannable_extensions(self, tmp_path):
        """Test only scannable file extensions are processed."""
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()

        # Create files with different extensions
        (repo_path / "config.yaml").write_text("image: nginx:1.21")
        (repo_path / "script.sh").write_text("docker pull nginx:1.21")
        (repo_path / "binary.bin").write_bytes(b"\x00\x01\x02")  # Binary file
        (repo_path / "image.png").write_bytes(b"\x89PNG")  # Image file

        scanner = RepositoryScanner(repo_path, "test-repo")
        scanned_files = list(scanner._walk_files())

        # Should only include text files
        assert any("config.yaml" in str(f) for f in scanned_files)
        assert any("script.sh" in str(f) for f in scanned_files)
        assert not any("binary.bin" in str(f) for f in scanned_files)
        assert not any("image.png" in str(f) for f in scanned_files)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
