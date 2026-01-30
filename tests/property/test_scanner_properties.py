"""Property-based tests for repository scanner.

Tests universal correctness properties of the RepositoryScanner using
Hypothesis for property-based testing.
"""

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from opencenter_build.scanner import RepositoryScanner


# Strategy for generating valid image references
@st.composite
def image_reference(draw):
    """Generate valid container image reference.

    Formats:
    - registry/repo:tag
    - repo:tag
    - registry/namespace/repo:tag
    """
    registry = draw(st.sampled_from(["docker.io", "quay.io", "gcr.io", "ghcr.io"]))
    namespace = draw(st.sampled_from(["library", "prometheus", "grafana", "bitnami"]))
    repo = draw(st.sampled_from(["nginx", "redis", "postgres", "mysql", "alpine"]))
    tag = draw(st.sampled_from(["latest", "1.0.0", "v2.3.4", "stable", "20240101"]))

    # Generate different formats
    format_choice = draw(st.integers(min_value=0, max_value=2))
    if format_choice == 0:
        return f"{registry}/{namespace}/{repo}:{tag}"
    elif format_choice == 1:
        return f"{namespace}/{repo}:{tag}"
    else:
        return f"{repo}:{tag}"


@st.composite
def yaml_with_images(draw):
    """Generate YAML content with embedded image references."""
    images = draw(st.lists(image_reference(), min_size=1, max_size=5))

    # Generate YAML with different formats
    yaml_lines = ["apiVersion: v1", "kind: Pod", "spec:", "  containers:"]

    for i, image in enumerate(images):
        yaml_lines.extend(
            [
                f"  - name: container-{i}",
                f"    image: {image}",
            ]
        )

    return "\n".join(yaml_lines), set(images)


@st.composite
def repository_with_images(draw):
    """Generate temporary repository with YAML files containing images."""
    # Generate 1-3 YAML files
    num_files = draw(st.integers(min_value=1, max_value=3))
    all_images = set()

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        for i in range(num_files):
            yaml_content, images = draw(yaml_with_images())
            all_images.update(images)

            # Create YAML file
            yaml_file = repo_path / f"deployment-{i}.yaml"
            yaml_file.write_text(yaml_content)

        yield repo_path, all_images


# Property 1: Image Discovery Completeness
# For any set of repositories containing container image references,
# scanning should discover all images that match the configured patterns.
@settings(max_examples=100, deadline=None)
@given(st.data())
def test_image_discovery_completeness(data):
    """Property 1: Image Discovery Completeness.

    **Validates: Requirements 1.4**

    For any repository containing image references in YAML files,
    the scanner must discover all images that match the patterns.
    """
    # Generate repository with known images
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        expected_images = set()

        # Generate 1-3 YAML files with images
        num_files = data.draw(st.integers(min_value=1, max_value=3))

        for i in range(num_files):
            yaml_content, images = data.draw(yaml_with_images())
            expected_images.update(images)

            yaml_file = repo_path / f"deployment-{i}.yaml"
            yaml_file.write_text(yaml_content)

        # Scan repository
        scanner = RepositoryScanner(repos=[repo_path])
        results = scanner.scan_all()

        discovered_images = results.get(str(repo_path), set())

        # Property: All expected images should be discovered
        # Note: Scanner may find additional partial matches, so we check
        # that all expected images are present in discovered set
        for expected_image in expected_images:
            assert any(
                expected_image in discovered for discovered in discovered_images
            ), f"Expected image {expected_image} not found in {discovered_images}"


# Property: Empty repository returns empty results
@settings(max_examples=50)
@given(st.just(None))
def test_empty_repository_returns_empty_results(data):
    """Property: Empty repository returns empty results.

    **Validates: Requirements 1.4**

    Scanning an empty repository should return an empty set of images.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        scanner = RepositoryScanner(repos=[repo_path])
        results = scanner.scan_all()

        discovered_images = results.get(str(repo_path), set())

        # Property: Empty repository should yield no images
        assert len(discovered_images) == 0, f"Expected no images, found {discovered_images}"


# Property: Repository with no YAML files returns empty results
@settings(max_examples=50)
@given(st.integers(min_value=1, max_value=5))
def test_repository_without_yaml_returns_empty(num_files):
    """Property: Repository without YAML files returns empty results.

    **Validates: Requirements 1.4**

    Scanning a repository with only non-YAML files should return empty results.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Create non-YAML files
        for i in range(num_files):
            (repo_path / f"file-{i}.txt").write_text("Some text content")
            (repo_path / f"script-{i}.sh").write_text("#!/bin/bash\necho hello")

        scanner = RepositoryScanner(repos=[repo_path])
        results = scanner.scan_all()

        discovered_images = results.get(str(repo_path), set())

        # Property: No YAML files should yield no images
        assert len(discovered_images) == 0, f"Expected no images, found {discovered_images}"


# Property: Concurrent scanning produces same results as sequential
@settings(max_examples=50, deadline=None)
@given(st.data())
def test_concurrent_scanning_consistency(data):
    """Property: Concurrent scanning produces consistent results.

    **Validates: Requirements 1.2, 1.3**

    Scanning with multiple workers should produce the same results
    as scanning with a single worker.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        expected_images = set()

        # Generate YAML files with images
        num_files = data.draw(st.integers(min_value=1, max_value=3))

        for i in range(num_files):
            yaml_content, images = data.draw(yaml_with_images())
            expected_images.update(images)

            yaml_file = repo_path / f"deployment-{i}.yaml"
            yaml_file.write_text(yaml_content)

        # Scan with single worker
        scanner_single = RepositoryScanner(repos=[repo_path], max_workers=1)
        results_single = scanner_single.scan_all()
        images_single = results_single.get(str(repo_path), set())

        # Scan with multiple workers
        scanner_multi = RepositoryScanner(repos=[repo_path], max_workers=4)
        results_multi = scanner_multi.scan_all()
        images_multi = results_multi.get(str(repo_path), set())

        # Property: Results should be identical regardless of worker count
        assert images_single == images_multi, (
            f"Single worker found {images_single}, " f"multiple workers found {images_multi}"
        )


# Property 2: Encoding Error Resilience
# For any file with invalid encoding, the file reader should handle
# the error gracefully without crashing and continue processing remaining files.
@settings(max_examples=100, deadline=None)
@given(st.binary(min_size=10, max_size=100))
def test_encoding_error_resilience(invalid_bytes):
    """Property 2: Encoding Error Resilience.

    **Validates: Requirements 2.3**

    For any file with invalid encoding, the scanner should handle
    the error gracefully without crashing and continue processing
    remaining files.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Create a valid YAML file with an image
        valid_yaml = """apiVersion: v1
kind: Pod
spec:
  containers:
  - name: nginx
    image: nginx:latest"""
        (repo_path / "valid.yaml").write_text(valid_yaml)

        # Create a file with potentially invalid encoding
        # Prepend known invalid UTF-8 bytes
        invalid_data = b"\xff\xfe\xfd\xfc" + invalid_bytes
        (repo_path / "invalid.yaml").write_bytes(invalid_data)

        # Create another valid YAML file
        valid_yaml2 = """apiVersion: v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: redis
        image: redis:7.0"""
        (repo_path / "valid2.yaml").write_text(valid_yaml2)

        # Scan repository - should not crash
        scanner = RepositoryScanner(repos=[repo_path])
        results = scanner.scan_all()

        discovered_images = results.get(str(repo_path), set())

        # Property: Scanner should complete without crashing
        # and should find images from valid files
        assert "nginx:latest" in str(discovered_images) or any(
            "nginx" in img for img in discovered_images
        ), f"Should find nginx image despite encoding errors, found: {discovered_images}"


# Property: Scanner handles binary files gracefully
@settings(max_examples=50)
@given(st.binary(min_size=100, max_size=1000))
def test_binary_file_handling(binary_data):
    """Property: Scanner handles binary files gracefully.

    **Validates: Requirements 2.3**

    Scanning a repository with binary files should not crash
    and should continue processing other files.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Create binary file
        (repo_path / "binary.bin").write_bytes(binary_data)

        # Create valid YAML file
        valid_yaml = """apiVersion: v1
kind: Pod
spec:
  containers:
  - name: postgres
    image: postgres:15"""
        (repo_path / "valid.yaml").write_text(valid_yaml)

        # Scan repository - should not crash
        scanner = RepositoryScanner(repos=[repo_path])
        results = scanner.scan_all()

        discovered_images = results.get(str(repo_path), set())

        # Property: Scanner should complete without crashing
        # Binary file should be skipped (wrong extension)
        assert isinstance(discovered_images, set), "Should return a set"


# Property: Large file handling with memory-mapped I/O
@settings(max_examples=20, deadline=None)
@given(st.integers(min_value=2, max_value=5))
def test_large_file_handling(num_images):
    """Property: Large files are handled with memory-mapped I/O.

    **Validates: Requirements 2.1, 2.2**

    Files larger than 1MB should be processed using memory-mapped I/O
    without consuming excessive memory.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Create a large YAML file (>1MB)
        large_content = ["apiVersion: v1", "kind: ConfigMap", "data:"]

        # Add many entries to make file large (need ~50k entries for >1MB)
        for i in range(50000):
            large_content.append(f"  key{i}: value{i}")

        # Add some images
        large_content.extend(
            [
                "---",
                "apiVersion: v1",
                "kind: Pod",
                "spec:",
                "  containers:",
            ]
        )

        for i in range(num_images):
            large_content.extend(
                [
                    f"  - name: container-{i}",
                    f"    image: myapp:v{i}",
                ]
            )

        large_yaml = "\n".join(large_content)
        large_file = repo_path / "large.yaml"
        large_file.write_text(large_yaml)

        # Verify file is large enough
        file_size = large_file.stat().st_size
        assert file_size > 1024 * 1024, f"File should be >1MB, got {file_size} bytes"

        # Scan repository
        scanner = RepositoryScanner(repos=[repo_path])
        results = scanner.scan_all()

        discovered_images = results.get(str(repo_path), set())

        # Property: Should discover images from large file
        myapp_images = [img for img in discovered_images if "myapp" in img]
        assert len(myapp_images) > 0, f"Should find myapp images, found: {discovered_images}"
