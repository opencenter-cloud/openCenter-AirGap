"""Unit tests for repository scanner.

Tests specific edge cases and error conditions for the RepositoryScanner.
"""

import tempfile
from pathlib import Path

import pytest

from opencenter_build.scanner import RepositoryScanner


class TestRepositoryScannerEdgeCases:
    """Test edge cases for RepositoryScanner."""

    def test_empty_repository(self):
        """Test scanning an empty repository.

        **Validates: Requirements 1.4**

        An empty repository should return an empty set of images.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            scanner = RepositoryScanner(repos=[repo_path])
            results = scanner.scan_all()

            assert str(repo_path) in results
            assert len(results[str(repo_path)]) == 0

    def test_repository_with_no_images(self):
        """Test scanning a repository with no image references.

        **Validates: Requirements 1.4**

        A repository with YAML files but no image references should
        return an empty set.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create YAML files without image references
            (repo_path / "config.yaml").write_text(
                """
                apiVersion: v1
                kind: ConfigMap
                metadata:
                  name: my-config
                data:
                  key: value
                """
            )

            (repo_path / "service.yaml").write_text(
                """
                apiVersion: v1
                kind: Service
                metadata:
                  name: my-service
                spec:
                  ports:
                  - port: 80
                """
            )

            scanner = RepositoryScanner(repos=[repo_path])
            results = scanner.scan_all()

            assert str(repo_path) in results
            assert len(results[str(repo_path)]) == 0

    def test_nonexistent_repository(self):
        """Test scanning a nonexistent repository path.

        **Validates: Requirements 1.4**

        A nonexistent repository should return an empty set without crashing.
        """
        nonexistent_path = Path("/nonexistent/path/to/repo")

        scanner = RepositoryScanner(repos=[nonexistent_path])
        results = scanner.scan_all()

        assert str(nonexistent_path) in results
        assert len(results[str(nonexistent_path)]) == 0

    def test_invalid_file_path(self):
        """Test scanning with invalid file paths in repository.

        **Validates: Requirements 2.3**

        Invalid file paths (e.g., broken symlinks) should be handled
        gracefully without crashing.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create a valid YAML file
            (repo_path / "valid.yaml").write_text(
                """
                apiVersion: v1
                kind: Pod
                spec:
                  containers:
                  - name: nginx
                    image: nginx:latest
                """
            )

            # Create a broken symlink
            broken_link = repo_path / "broken.yaml"
            broken_link.symlink_to(Path("/nonexistent/file.yaml"))

            scanner = RepositoryScanner(repos=[repo_path])
            results = scanner.scan_all()

            # Should find the valid image despite broken symlink
            discovered_images = results[str(repo_path)]
            assert any("nginx" in img for img in discovered_images)

    def test_repository_with_subdirectories(self):
        """Test scanning repository with nested subdirectories.

        **Validates: Requirements 1.4**

        Scanner should recursively scan subdirectories.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create nested directory structure
            (repo_path / "apps" / "frontend").mkdir(parents=True)
            (repo_path / "apps" / "backend").mkdir(parents=True)

            # Add YAML files in different directories
            (repo_path / "apps" / "frontend" / "deployment.yaml").write_text(
                """
                apiVersion: apps/v1
                kind: Deployment
                spec:
                  template:
                    spec:
                      containers:
                      - name: frontend
                        image: myapp/frontend:v1.0.0
                """
            )

            (repo_path / "apps" / "backend" / "deployment.yaml").write_text(
                """
                apiVersion: apps/v1
                kind: Deployment
                spec:
                  template:
                    spec:
                      containers:
                      - name: backend
                        image: myapp/backend:v2.0.0
                """
            )

            scanner = RepositoryScanner(repos=[repo_path])
            results = scanner.scan_all()

            discovered_images = results[str(repo_path)]

            # Should find images from both subdirectories
            assert any("frontend" in img for img in discovered_images)
            assert any("backend" in img for img in discovered_images)

    def test_multiple_repositories(self):
        """Test scanning multiple repositories concurrently.

        **Validates: Requirements 1.2, 1.3**

        Scanner should handle multiple repositories and return
        separate results for each.
        """
        with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
            repo1 = Path(tmpdir1)
            repo2 = Path(tmpdir2)

            # Add different images to each repo
            (repo1 / "app1.yaml").write_text(
                """
                apiVersion: v1
                kind: Pod
                spec:
                  containers:
                  - name: app1
                    image: app1:v1
                """
            )

            (repo2 / "app2.yaml").write_text(
                """
                apiVersion: v1
                kind: Pod
                spec:
                  containers:
                  - name: app2
                    image: app2:v2
                """
            )

            scanner = RepositoryScanner(repos=[repo1, repo2])
            results = scanner.scan_all()

            # Should have results for both repos
            assert str(repo1) in results
            assert str(repo2) in results

            # Each repo should have its own images
            images1 = results[str(repo1)]
            images2 = results[str(repo2)]

            assert any("app1" in img for img in images1)
            assert any("app2" in img for img in images2)

    def test_scan_repo_single_method(self):
        """Test scan_repo method for single repository.

        **Validates: Requirements 1.4**

        The scan_repo convenience method should work for single repos.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            (repo_path / "pod.yaml").write_text(
                """
                apiVersion: v1
                kind: Pod
                spec:
                  containers:
                  - name: redis
                    image: redis:7.0
                """
            )

            scanner = RepositoryScanner(repos=[])
            images = scanner.scan_repo(repo_path)

            assert any("redis" in img for img in images)

    def test_custom_patterns(self):
        """Test scanner with custom regex patterns.

        **Validates: Requirements 1.4**

        Scanner should support custom patterns for image detection.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create file with custom format
            (repo_path / "custom.yaml").write_text(
                """
                container_image: "custom/myapp:v1.0.0"
                """
            )

            # Use custom pattern
            custom_patterns = [r'container_image:\s*"([^"]+)"']

            scanner = RepositoryScanner(repos=[repo_path], patterns=custom_patterns)
            results = scanner.scan_all()

            discovered_images = results[str(repo_path)]

            assert "custom/myapp:v1.0.0" in discovered_images

    def test_file_extension_filtering(self):
        """Test that only relevant file extensions are scanned.

        **Validates: Requirements 1.4**

        Scanner should only scan files with relevant extensions
        (yaml, yml, json, etc.) and skip others.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create YAML file with image
            (repo_path / "deployment.yaml").write_text(
                """
                apiVersion: v1
                kind: Pod
                spec:
                  containers:
                  - name: app
                    image: myapp:v1
                """
            )

            # Create Python file with image reference (should be skipped)
            (repo_path / "script.py").write_text(
                """
                # This should not be scanned
                image: "should-not-find:latest"
                """
            )

            # Create binary file (should be skipped)
            (repo_path / "binary.bin").write_bytes(b"\x00\x01\x02\x03")

            scanner = RepositoryScanner(repos=[repo_path])
            results = scanner.scan_all()

            discovered_images = results[str(repo_path)]

            # Should find image from YAML but not from Python or binary
            assert any("myapp" in img for img in discovered_images)
            assert not any("should-not-find" in img for img in discovered_images)

    def test_max_workers_configuration(self):
        """Test scanner with different max_workers settings.

        **Validates: Requirements 1.3**

        Scanner should respect max_workers configuration.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            (repo_path / "pod.yaml").write_text(
                """
                apiVersion: v1
                kind: Pod
                spec:
                  containers:
                  - name: nginx
                    image: nginx:latest
                """
            )

            # Test with explicit worker count
            scanner = RepositoryScanner(repos=[repo_path], max_workers=2)
            assert scanner.max_workers == 2

            results = scanner.scan_all()
            discovered_images = results[str(repo_path)]

            assert any("nginx" in img for img in discovered_images)

    def test_empty_yaml_file(self):
        """Test scanning empty YAML file.

        **Validates: Requirements 2.3**

        Empty YAML files should be handled gracefully.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create empty YAML file
            (repo_path / "empty.yaml").write_text("")

            # Create valid YAML file
            (repo_path / "valid.yaml").write_text(
                """
                apiVersion: v1
                kind: Pod
                spec:
                  containers:
                  - name: app
                    image: app:v1
                """
            )

            scanner = RepositoryScanner(repos=[repo_path])
            results = scanner.scan_all()

            discovered_images = results[str(repo_path)]

            # Should find image from valid file
            assert any("app" in img for img in discovered_images)
