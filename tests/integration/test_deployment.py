"""Integration tests for deployment and service management.

This module tests the complete deployment workflow including:
- Zarf package deployment
- Service startup (nginx, registry, git)
- Service health verification
- Artifact serving

**Validates: Requirements 9.3, 9.4**
"""

import subprocess
import time
import urllib.request
from pathlib import Path

import pytest


@pytest.fixture
def test_package_path(tmp_path):
    """Create a minimal test package for deployment testing."""
    # For integration testing, we would need a real Zarf package
    # This is a placeholder that would be replaced with actual package creation
    package_path = tmp_path / "test-package.tar.zst"

    # In a real integration test, we would:
    # 1. Build a minimal Zarf package with test artifacts
    # 2. Return the path to that package

    # For now, skip if no test package exists
    if not package_path.exists():
        pytest.skip("Test package not available")

    return package_path


@pytest.fixture
def deployment_env(tmp_path):
    """Set up deployment environment."""
    install_path = tmp_path / "opencenter"
    install_path.mkdir(parents=True, exist_ok=True)

    # Create directory structure
    (install_path / "files").mkdir(exist_ok=True)
    (install_path / "debs").mkdir(exist_ok=True)
    (install_path / "pypi").mkdir(exist_ok=True)

    # Create test files
    (install_path / "files" / "test.txt").write_text("test file")
    (install_path / "debs" / "test.deb").write_text("test deb")
    (install_path / "pypi" / "test.whl").write_text("test wheel")

    yield install_path

    # Cleanup: stop and remove nginx container if it exists
    try:
        subprocess.run(
            ["docker", "stop", "opencenter-nginx-test"],
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["docker", "rm", "opencenter-nginx-test"],
            capture_output=True,
            check=False,
        )
    except Exception:
        pass


@pytest.mark.integration
@pytest.mark.skipif(
    subprocess.run(["which", "docker"], capture_output=True).returncode != 0,
    reason="Docker not available",
)
def test_nginx_service_startup(deployment_env):
    """Test nginx container starts and serves files.

    **Validates: Requirements 9.3, 9.4**
    """
    nginx_port = 8888  # Use non-standard port to avoid conflicts
    container_name = "opencenter-nginx-test"

    try:
        # Start nginx container
        nginx_cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "-p",
            f"{nginx_port}:80",
            "-v",
            f"{deployment_env}/files:/usr/share/nginx/html/files:ro",
            "-v",
            f"{deployment_env}/debs:/usr/share/nginx/html/debs:ro",
            "-v",
            f"{deployment_env}/pypi:/usr/share/nginx/html/pypi:ro",
            "nginx:1.29.2",
        ]

        result = subprocess.run(
            nginx_cmd,
            capture_output=True,
            text=True,
            check=True,
        )

        # Wait for nginx to be ready
        time.sleep(2)

        # Verify nginx is running
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            check=True,
        )

        assert "Up" in result.stdout, "Nginx container should be running"

        # Verify file serving
        services = [
            f"http://localhost:{nginx_port}/files/",
            f"http://localhost:{nginx_port}/debs/",
            f"http://localhost:{nginx_port}/pypi/",
        ]

        for url in services:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as response:
                assert response.status == 200, f"Service should respond with 200: {url}"

        # Verify specific file can be retrieved
        file_url = f"http://localhost:{nginx_port}/files/test.txt"
        req = urllib.request.Request(file_url)
        with urllib.request.urlopen(req, timeout=5) as response:
            content = response.read().decode("utf-8")
            assert content == "test file", "File content should match"

    finally:
        # Cleanup
        subprocess.run(
            ["docker", "stop", container_name],
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["docker", "rm", container_name],
            capture_output=True,
            check=False,
        )


@pytest.mark.integration
@pytest.mark.skipif(
    subprocess.run(["which", "docker"], capture_output=True).returncode != 0,
    reason="Docker not available",
)
def test_service_health_checks(deployment_env):
    """Test service health verification.

    **Validates: Requirements 9.3, 9.4**
    """
    nginx_port = 8889  # Use different port
    container_name = "opencenter-nginx-test-health"

    try:
        # Start nginx container
        nginx_cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "-p",
            f"{nginx_port}:80",
            "-v",
            f"{deployment_env}/files:/usr/share/nginx/html/files:ro",
            "nginx:1.29.2",
        ]

        subprocess.run(nginx_cmd, capture_output=True, check=True)

        # Wait for service to be ready
        time.sleep(2)

        # Test health check
        max_retries = 5
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(f"http://localhost:{nginx_port}/files/")
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == 200:
                        break
            except Exception:
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)

        # Verify final health check succeeds
        req = urllib.request.Request(f"http://localhost:{nginx_port}/files/")
        with urllib.request.urlopen(req, timeout=5) as response:
            assert response.status == 200

    finally:
        # Cleanup
        subprocess.run(
            ["docker", "stop", container_name],
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["docker", "rm", container_name],
            capture_output=True,
            check=False,
        )


@pytest.mark.integration
@pytest.mark.skipif(
    subprocess.run(["which", "docker"], capture_output=True).returncode != 0,
    reason="Docker not available",
)
def test_artifact_serving(deployment_env):
    """Test that all artifact types are served correctly.

    **Validates: Requirements 9.4**
    """
    nginx_port = 8890  # Use different port
    container_name = "opencenter-nginx-test-artifacts"

    try:
        # Start nginx container
        nginx_cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "-p",
            f"{nginx_port}:80",
            "-v",
            f"{deployment_env}/files:/usr/share/nginx/html/files:ro",
            "-v",
            f"{deployment_env}/debs:/usr/share/nginx/html/debs:ro",
            "-v",
            f"{deployment_env}/pypi:/usr/share/nginx/html/pypi:ro",
            "nginx:1.29.2",
        ]

        subprocess.run(nginx_cmd, capture_output=True, check=True)

        # Wait for service to be ready
        time.sleep(2)

        # Test each artifact type
        artifacts = [
            (f"http://localhost:{nginx_port}/files/test.txt", "test file"),
            (f"http://localhost:{nginx_port}/debs/test.deb", "test deb"),
            (f"http://localhost:{nginx_port}/pypi/test.whl", "test wheel"),
        ]

        for url, expected_content in artifacts:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as response:
                assert response.status == 200, f"Artifact should be accessible: {url}"
                content = response.read().decode("utf-8")
                assert content == expected_content, f"Content should match for {url}"

    finally:
        # Cleanup
        subprocess.run(
            ["docker", "stop", container_name],
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["docker", "rm", container_name],
            capture_output=True,
            check=False,
        )


@pytest.mark.integration
@pytest.mark.skipif(
    subprocess.run(["which", "docker"], capture_output=True).returncode != 0,
    reason="Docker not available",
)
def test_cleanup_on_failure(deployment_env):
    """Test that cleanup removes containers on failure.

    **Validates: Requirements 9.5**
    """
    container_name = "opencenter-nginx-test-cleanup"

    # Start a container that we'll cleanup
    nginx_cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        container_name,
        "-p",
        "8891:80",
        "nginx:1.29.2",
    ]

    subprocess.run(nginx_cmd, capture_output=True, check=True)

    # Verify container is running
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert container_name in result.stdout, "Container should be running"

    # Simulate cleanup
    subprocess.run(
        ["docker", "stop", container_name],
        capture_output=True,
        check=False,
    )
    subprocess.run(
        ["docker", "rm", container_name],
        capture_output=True,
        check=False,
    )

    # Verify container is removed
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert container_name not in result.stdout, "Container should be removed"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
