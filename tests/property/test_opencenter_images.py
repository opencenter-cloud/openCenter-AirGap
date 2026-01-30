#!/usr/bin/env python3
"""
Property-Based Test: openCenter Platform Service Images Available

Property 15: openCenter Platform Service Images Available

For any openCenter platform service image in the package (20+ services including
FluxCD, Gitea, cert-manager, ingress-nginx, Gateway API, Keycloak, Prometheus,
Grafana, Loki, Tempo, OpenTelemetry, Mimir, Longhorn, vSphere CSI, OpenStack CSI,
Kyverno, OLM, RBAC Manager, Velero, Harbor, Headlamp, Weave GitOps, MetalLB,
Sealed Secrets, Postgres Operator, Strimzi Kafka), the image should be available
in the bastion registry and pullable.

Validates: Requirements 5.13, 5.14, 5.15

Note: This property validates image availability, not service deployment.
Service deployment is handled by the openCenter platform (gitops-base).
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Tuple, Set
from hypothesis import given, strategies as st, settings, HealthCheck
import pytest

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    requests = None  # type: ignore


# Test configuration
BASTION_IP = os.getenv("BASTION_IP", "localhost")
REGISTRY_PORT = os.getenv("REGISTRY_PORT", "35000")
REGISTRY_URL = f"http://{BASTION_IP}:{REGISTRY_PORT}"
PROJECT_ROOT = Path(__file__).parent.parent.parent
OPENCENTER_IMAGES_FILE = PROJECT_ROOT / "config" / "opencenter-images.txt"


def load_opencenter_images() -> List[str]:
    """Load openCenter platform service images from config file."""
    if not OPENCENTER_IMAGES_FILE.exists():
        pytest.skip(f"openCenter images file not found: {OPENCENTER_IMAGES_FILE}")

    images = []
    with open(OPENCENTER_IMAGES_FILE, "r") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if line and not line.startswith("#"):
                images.append(line)

    return images


def check_registry_connectivity() -> bool:
    """Check if bastion registry is accessible."""
    if not HAS_REQUESTS:
        return False
    try:
        response = requests.get(f"{REGISTRY_URL}/v2/", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


def strip_registry_prefix(image: str) -> str:
    """
    Strip common registry prefixes to match bastion registry format.
    kubespray-offline strips these prefixes when pushing to local registry.
    """
    prefixes = [
        "registry.k8s.io/",
        "gcr.io/",
        "ghcr.io/",
        "docker.io/",
        "quay.io/",
        "registry.opensource.zalan.do/",
        "longhornio/",
    ]

    for prefix in prefixes:
        if image.startswith(prefix):
            return image[len(prefix) :]

    return image


def parse_image(image: str) -> Tuple[str, str]:
    """Parse image into repository and tag."""
    if ":" in image:
        repo, tag = image.rsplit(":", 1)
    else:
        repo = image
        tag = "latest"

    return repo, tag


def check_image_in_registry(image: str) -> Tuple[bool, str]:
    """
    Check if image exists in bastion registry.
    Returns (exists, error_message).
    """
    try:
        # Parse image
        repo, tag = parse_image(image)

        # Strip registry prefix
        stripped_repo = strip_registry_prefix(repo)

        # Query registry for tags
        tags_url = f"{REGISTRY_URL}/v2/{stripped_repo}/tags/list"
        response = requests.get(tags_url, timeout=10)

        if response.status_code == 404:
            return False, f"Repository not found: {stripped_repo}"

        if response.status_code != 200:
            return False, f"Registry error: HTTP {response.status_code}"

        # Check if tag exists
        data = response.json()
        tags = data.get("tags", [])

        if tag in tags:
            return True, ""
        else:
            return (
                False,
                f"Tag '{tag}' not found in repository '{stripped_repo}' (available: {tags[:5]})",
            )

    except requests.RequestException as e:
        return False, f"Network error: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def is_image_pullable(image: str) -> Tuple[bool, str]:
    """
    Check if image can be pulled from bastion registry.
    Returns (pullable, error_message).
    """
    try:
        # Parse image
        repo, tag = parse_image(image)

        # Strip registry prefix and construct bastion image reference
        stripped_repo = strip_registry_prefix(repo)
        bastion_image = f"{BASTION_IP}:{REGISTRY_PORT}/{stripped_repo}:{tag}"

        # Try to pull image using podman/docker
        container_runtime = (
            "podman"
            if subprocess.run(["which", "podman"], capture_output=True).returncode == 0
            else "docker"
        )

        result = subprocess.run(
            [container_runtime, "pull", bastion_image], capture_output=True, text=True, timeout=60
        )

        if result.returncode == 0:
            return True, ""
        else:
            return False, f"Pull failed: {result.stderr[:200]}"

    except subprocess.TimeoutExpired:
        return False, "Pull timeout (60s)"
    except Exception as e:
        return False, f"Error: {str(e)}"


# ============================================================================
# Property Tests
# ============================================================================


class TestOpenCenterImageAvailability:
    """Property-based tests for openCenter platform service image availability."""

    @pytest.fixture(scope="class", autouse=True)
    def check_registry(self):
        """Check registry connectivity before running tests."""
        if not HAS_REQUESTS:
            pytest.skip("requests library not available - install with: pip install requests")
        if not check_registry_connectivity():
            pytest.skip(f"Bastion registry not accessible at {REGISTRY_URL}")

    @pytest.fixture(scope="class")
    def opencenter_images(self):
        """Load openCenter images once for all tests."""
        return load_opencenter_images()

    def test_opencenter_images_loaded(self, opencenter_images):
        """Verify openCenter images file is loaded and contains images."""
        assert len(opencenter_images) > 0, "No openCenter images found"
        assert len(opencenter_images) >= 50, f"Expected 50+ images, found {len(opencenter_images)}"

        print(f"\nLoaded {len(opencenter_images)} openCenter platform service images")

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    @given(st.data())
    def test_property_15_opencenter_images_available_in_registry(self, opencenter_images, data):
        """
        Property 15: openCenter Platform Service Images Available

        For any openCenter platform service image, the image should be
        available in the bastion registry.

        Validates: Requirements 5.13, 5.14, 5.15
        """
        # Select a random image from the list
        if not opencenter_images:
            pytest.skip("No openCenter images to test")

        image = data.draw(st.sampled_from(opencenter_images))

        # Check if image exists in registry
        exists, error = check_image_in_registry(image)

        assert exists, (
            f"openCenter image not available in bastion registry:\n"
            f"  Image: {image}\n"
            f"  Registry: {REGISTRY_URL}\n"
            f"  Error: {error}\n"
            f"\n"
            f"This violates Property 15: openCenter Platform Service Images Available\n"
            f"All openCenter platform service images must be available in the bastion registry."
        )

    @pytest.mark.slow
    @settings(
        max_examples=10,  # Limit to 10 pulls (slow operation)
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    @given(st.data())
    def test_property_15_opencenter_images_pullable(self, opencenter_images, data):
        """
        Property 15 (Extended): openCenter Platform Service Images Pullable

        For any openCenter platform service image, the image should be
        pullable from the bastion registry.

        Validates: Requirements 5.13, 5.14, 5.15

        Note: This test is slow as it actually pulls images.
        """
        # Select a random image from the list
        if not opencenter_images:
            pytest.skip("No openCenter images to test")

        image = data.draw(st.sampled_from(opencenter_images))

        # Check if image is pullable
        pullable, error = is_image_pullable(image)

        assert pullable, (
            f"openCenter image not pullable from bastion registry:\n"
            f"  Image: {image}\n"
            f"  Registry: {REGISTRY_URL}\n"
            f"  Error: {error}\n"
            f"\n"
            f"This violates Property 15: openCenter Platform Service Images Available\n"
            f"All openCenter platform service images must be pullable from the bastion registry."
        )

    def test_all_opencenter_images_present(self, opencenter_images):
        """
        Comprehensive test: Check all openCenter images are in registry.

        This is not a property test, but a comprehensive check of all images.
        """
        missing_images = []

        for image in opencenter_images:
            exists, error = check_image_in_registry(image)
            if not exists:
                missing_images.append((image, error))

        if missing_images:
            error_report = "\n".join([f"  - {img}: {err}" for img, err in missing_images[:10]])
            if len(missing_images) > 10:
                error_report += f"\n  ... and {len(missing_images) - 10} more"

            pytest.fail(
                f"{len(missing_images)} openCenter images missing from registry:\n"
                f"{error_report}\n"
                f"\n"
                f"Total images checked: {len(opencenter_images)}\n"
                f"Missing: {len(missing_images)}\n"
                f"Coverage: {(len(opencenter_images) - len(missing_images)) * 100 // len(opencenter_images)}%"
            )

        print(f"\n✓ All {len(opencenter_images)} openCenter images available in registry")


# ============================================================================
# Test Execution
# ============================================================================

if __name__ == "__main__":
    """Run tests directly with pytest."""
    pytest.main([__file__, "-v", "--tb=short"])
