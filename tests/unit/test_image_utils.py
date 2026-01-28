"""Unit tests for image utilities."""

import tempfile
from pathlib import Path

import pytest

from opencenter_build.exceptions import ValidationError
from opencenter_build.image_utils import (
    generate_yaml_block,
    normalize_image_reference,
    parse_image_list,
    parse_image_reference,
    validate_image_tag,
    validate_images,
)


def test_parse_image_reference_short_form() -> None:
    """Test parsing short-form image references."""
    ref = parse_image_reference("nginx:1.21")
    assert ref.registry == "docker.io"
    assert ref.repository == "library/nginx"
    assert ref.tag == "1.21"
    assert ref.digest is None


def test_parse_image_reference_with_registry() -> None:
    """Test parsing image references with registry."""
    ref = parse_image_reference("gcr.io/project/image:v1.0.0")
    assert ref.registry == "gcr.io"
    assert ref.repository == "project/image"
    assert ref.tag == "v1.0.0"


def test_parse_image_reference_with_digest() -> None:
    """Test parsing image references with digest."""
    ref = parse_image_reference("nginx:1.21@sha256:abc123")
    assert ref.registry == "docker.io"
    assert ref.repository == "library/nginx"
    assert ref.tag == "1.21"
    assert ref.digest == "sha256:abc123"


def test_parse_image_reference_no_tag() -> None:
    """Test parsing image references without tag (defaults to latest)."""
    ref = parse_image_reference("nginx")
    assert ref.registry == "docker.io"
    assert ref.repository == "library/nginx"
    assert ref.tag == "latest"


def test_parse_image_reference_org_repo() -> None:
    """Test parsing org/repo format."""
    ref = parse_image_reference("bitnami/postgresql:14")
    assert ref.registry == "docker.io"
    assert ref.repository == "bitnami/postgresql"
    assert ref.tag == "14"


def test_parse_image_reference_localhost() -> None:
    """Test parsing localhost registry."""
    ref = parse_image_reference("localhost:5000/myimage:v1")
    assert ref.registry == "localhost:5000"
    assert ref.repository == "myimage"
    assert ref.tag == "v1"


def test_parse_image_reference_empty() -> None:
    """Test parsing empty image reference."""
    with pytest.raises(ValidationError, match="cannot be empty"):
        parse_image_reference("")


def test_parse_image_reference_invalid_digest() -> None:
    """Test parsing image reference with invalid digest."""
    with pytest.raises(ValidationError, match="Invalid digest format"):
        parse_image_reference("nginx:1.21@md5:invalid")


def test_normalize_image_reference() -> None:
    """Test image reference normalization."""
    assert normalize_image_reference("nginx:1.21") == "docker.io/library/nginx:1.21"
    assert normalize_image_reference("gcr.io/project/image:v1") == "gcr.io/project/image:v1"


def test_validate_image_tag_valid() -> None:
    """Test image tag validation with valid tags."""
    assert validate_image_tag("v1.21.0")
    assert validate_image_tag("latest")
    assert validate_image_tag("1.21.0-rc.1")
    assert validate_image_tag("sha-abc123")
    assert validate_image_tag("v1_2_3")


def test_validate_image_tag_invalid() -> None:
    """Test image tag validation with invalid tags."""
    assert not validate_image_tag(".invalid")
    assert not validate_image_tag("-invalid")
    assert not validate_image_tag("")
    assert not validate_image_tag("a" * 129)


class TestParseImageList:
    """Test parse_image_list function."""

    def test_parse_valid_image_list(self, tmp_path):
        """Test parsing valid image list file."""
        image_file = tmp_path / "images.txt"
        image_file.write_text(
            """
# Container images for deployment
nginx:1.29.2
registry:2.8.3
postgres:14.5

# Additional images
redis:7.0
"""
        )

        images = parse_image_list(image_file)

        assert len(images) == 4
        assert "nginx:1.29.2" in images
        assert "registry:2.8.3" in images
        assert "postgres:14.5" in images
        assert "redis:7.0" in images

    def test_parse_image_list_ignores_comments(self, tmp_path):
        """Test that comments are ignored."""
        image_file = tmp_path / "images.txt"
        image_file.write_text(
            """
# This is a comment
nginx:1.29.2
# Another comment
registry:2.8.3
"""
        )

        images = parse_image_list(image_file)

        assert len(images) == 2
        assert "nginx:1.29.2" in images
        assert "registry:2.8.3" in images

    def test_parse_image_list_ignores_empty_lines(self, tmp_path):
        """Test that empty lines are ignored."""
        image_file = tmp_path / "images.txt"
        image_file.write_text(
            """

nginx:1.29.2


registry:2.8.3

"""
        )

        images = parse_image_list(image_file)

        assert len(images) == 2

    def test_parse_image_list_file_not_found(self, tmp_path):
        """Test error when file doesn't exist."""
        image_file = tmp_path / "nonexistent.txt"

        with pytest.raises(ValidationError, match="not found"):
            parse_image_list(image_file)

    def test_parse_image_list_with_path_object(self, tmp_path):
        """Test parsing with Path object."""
        image_file = tmp_path / "images.txt"
        image_file.write_text("nginx:1.29.2\nregistry:2.8.3")

        images = parse_image_list(Path(image_file))

        assert len(images) == 2

    def test_parse_image_list_with_string_path(self, tmp_path):
        """Test parsing with string path."""
        image_file = tmp_path / "images.txt"
        image_file.write_text("nginx:1.29.2\nregistry:2.8.3")

        images = parse_image_list(str(image_file))

        assert len(images) == 2

    def test_parse_empty_image_list(self, tmp_path):
        """Test parsing empty image list."""
        image_file = tmp_path / "images.txt"
        image_file.write_text("")

        images = parse_image_list(image_file)

        assert len(images) == 0

    def test_parse_image_list_only_comments(self, tmp_path):
        """Test parsing file with only comments."""
        image_file = tmp_path / "images.txt"
        image_file.write_text(
            """
# Comment 1
# Comment 2
# Comment 3
"""
        )

        images = parse_image_list(image_file)

        assert len(images) == 0


class TestGenerateYamlBlock:
    """Test generate_yaml_block function."""

    def test_generate_yaml_block_basic(self):
        """Test generating basic YAML block."""
        images = ["nginx:1.29.2", "registry:2.8.3"]
        yaml_block = generate_yaml_block(images, indent=2)

        assert "images:" in yaml_block
        assert "- nginx:1.29.2" in yaml_block
        assert "- registry:2.8.3" in yaml_block

    def test_generate_yaml_block_indentation(self):
        """Test YAML block indentation."""
        images = ["nginx:1.29.2"]
        yaml_block = generate_yaml_block(images, indent=2)

        lines = yaml_block.split("\n")
        assert lines[0] == "  images:"
        assert lines[1] == "    - nginx:1.29.2"

    def test_generate_yaml_block_custom_indent(self):
        """Test YAML block with custom indentation."""
        images = ["nginx:1.29.2"]
        yaml_block = generate_yaml_block(images, indent=4)

        lines = yaml_block.split("\n")
        assert lines[0] == "    images:"
        assert lines[1] == "      - nginx:1.29.2"

    def test_generate_yaml_block_multiple_images(self):
        """Test YAML block with multiple images."""
        images = [
            "nginx:1.29.2",
            "registry:2.8.3",
            "postgres:14.5",
            "redis:7.0",
        ]
        yaml_block = generate_yaml_block(images, indent=2)

        lines = yaml_block.split("\n")
        assert len(lines) == 5  # 1 header + 4 images
        assert lines[0] == "  images:"
        assert all(line.startswith("    - ") for line in lines[1:])

    def test_generate_yaml_block_empty_list(self):
        """Test YAML block with empty image list."""
        images = []
        yaml_block = generate_yaml_block(images, indent=2)

        assert yaml_block == ""

    def test_generate_yaml_block_single_image(self):
        """Test YAML block with single image."""
        images = ["nginx:1.29.2"]
        yaml_block = generate_yaml_block(images, indent=2)

        lines = yaml_block.split("\n")
        assert len(lines) == 2
        assert lines[0] == "  images:"
        assert lines[1] == "    - nginx:1.29.2"

    def test_generate_yaml_block_with_full_references(self):
        """Test YAML block with fully qualified image references."""
        images = [
            "docker.io/library/nginx:1.29.2",
            "gcr.io/project/image:v1.0.0",
            "quay.io/org/repo:latest",
        ]
        yaml_block = generate_yaml_block(images, indent=2)

        assert "docker.io/library/nginx:1.29.2" in yaml_block
        assert "gcr.io/project/image:v1.0.0" in yaml_block
        assert "quay.io/org/repo:latest" in yaml_block


class TestValidateImages:
    """Test validate_images function."""

    def test_validate_images_all_valid(self):
        """Test validation with all valid images."""
        images = [
            "nginx:1.29.2",
            "registry:2.8.3",
            "postgres:14.5",
        ]

        result = validate_images(images)

        assert result is True

    def test_validate_images_with_spaces(self, caplog):
        """Test validation fails with images containing spaces."""
        images = ["nginx :1.29.2", "registry:2.8.3"]

        result = validate_images(images)

        assert result is False
        assert "contains spaces" in caplog.text

    def test_validate_images_missing_tag(self, caplog):
        """Test validation warns about missing tags."""
        images = ["nginx", "registry:2.8.3"]

        result = validate_images(images)

        assert result is False
        assert "missing tag" in caplog.text.lower()

    def test_validate_images_latest_tag(self, caplog):
        """Test validation warns about latest tag."""
        images = ["nginx:latest", "registry:2.8.3"]

        result = validate_images(images)

        # Should still return True (just a warning)
        assert result is True
        assert "latest" in caplog.text.lower()

    def test_validate_images_multiple_issues(self, caplog):
        """Test validation with multiple issues."""
        images = [
            "nginx :1.29.2",  # Has space
            "registry",  # Missing tag
            "postgres:latest",  # Latest tag
            "redis:7.0",  # Valid
        ]

        result = validate_images(images)

        assert result is False
        assert "contains spaces" in caplog.text
        assert "missing tag" in caplog.text.lower()

    def test_validate_images_empty_list(self):
        """Test validation with empty list."""
        images = []

        result = validate_images(images)

        assert result is True

    def test_validate_images_all_invalid(self, caplog):
        """Test validation with all invalid images."""
        images = [
            "nginx :1.29.2",
            "registry with spaces:2.8.3",
        ]

        result = validate_images(images)

        assert result is False
        assert caplog.text.count("contains spaces") == 2
