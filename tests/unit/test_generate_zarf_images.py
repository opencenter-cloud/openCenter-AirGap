#!/usr/bin/env python3
"""Unit tests for Zarf image block generation."""

import sys
import tempfile
from pathlib import Path

import pytest

from opencenter_build.image_utils import (
    parse_image_list,
    generate_yaml_block,
    validate_images,
)


def test_parse_image_list():
    """Test parsing image list with comments and empty lines."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("# Comment line\n")
        f.write("\n")
        f.write("nginx:1.29.2\n")
        f.write("registry:2.8.3\n")
        f.write("# Another comment\n")
        f.write("quay.io/keycloak/keycloak:26.3.0\n")
        f.write("\n")
        temp_file = Path(f.name)

    try:
        images = parse_image_list(temp_file)
        assert len(images) == 3
        assert "nginx:1.29.2" in images
        assert "registry:2.8.3" in images
        assert "quay.io/keycloak/keycloak:26.3.0" in images
    finally:
        temp_file.unlink()


def test_generate_yaml_block():
    """Test YAML block generation."""
    images = ["nginx:1.29.2", "registry:2.8.3", "quay.io/keycloak/keycloak:26.3.0"]

    yaml_block = generate_yaml_block(images, indent=2)

    assert "  images:" in yaml_block
    assert "    - nginx:1.29.2" in yaml_block
    assert "    - registry:2.8.3" in yaml_block
    assert "    - quay.io/keycloak/keycloak:26.3.0" in yaml_block


def test_validate_images_valid():
    """Test validation with valid images."""
    images = ["nginx:1.29.2", "registry:2.8.3", "quay.io/keycloak/keycloak:26.3.0"]

    assert validate_images(images) is True


def test_validate_images_missing_tag():
    """Test validation catches missing tags."""
    images = [
        "nginx:1.29.2",
        "registry",  # Missing tag
    ]

    # Should return False and print warning
    result = validate_images(images)
    assert result is False


def test_validate_images_with_spaces():
    """Test validation catches images with spaces."""
    images = [
        "nginx:1.29.2",
        "bad image:latest",  # Contains space
    ]

    assert validate_images(images) is False


def test_validate_images_latest_tag():
    """Test validation warns about latest tag."""
    images = [
        "nginx:1.29.2",
        "alpine:latest",  # Latest tag
    ]

    # Should return True but print warning
    result = validate_images(images)
    assert result is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
