"""Test that package modules can be imported and used."""

import pytest


def test_import_image_utils():
    """Test importing image_utils module."""
    from opencenter_build.image_utils import (
        parse_image_reference,
        normalize_image_reference,
        validate_image_tag,
        parse_image_list,
        generate_yaml_block,
        validate_images,
    )

    # Verify functions are callable
    assert callable(parse_image_reference)
    assert callable(normalize_image_reference)
    assert callable(validate_image_tag)
    assert callable(parse_image_list)
    assert callable(generate_yaml_block)
    assert callable(validate_images)


def test_import_version_utils():
    """Test importing version_utils module."""
    from opencenter_build.version_utils import (
        validate_semver,
        validate_kubernetes_version,
        validate_commit_sha,
        parse_version_components,
        compare_versions,
        VersionType,
        VersionSpec,
        VersionParser,
        VersionValidator,
    )

    # Verify functions and classes are available
    assert callable(validate_semver)
    assert callable(validate_kubernetes_version)
    assert callable(validate_commit_sha)
    assert callable(parse_version_components)
    assert callable(compare_versions)
    assert VersionType is not None
    assert VersionSpec is not None
    assert VersionParser is not None
    assert VersionValidator is not None


def test_import_zarf_utils():
    """Test importing zarf_utils module."""
    from opencenter_build.zarf_utils import (
        generate_zarf_component,
        generate_zarf_metadata,
        write_zarf_yaml,
        read_zarf_yaml,
        validate_zarf_structure,
        generate_images_block,
        generate_zarf_yaml_from_template,
    )

    # Verify functions are callable
    assert callable(generate_zarf_component)
    assert callable(generate_zarf_metadata)
    assert callable(write_zarf_yaml)
    assert callable(read_zarf_yaml)
    assert callable(validate_zarf_structure)
    assert callable(generate_images_block)
    assert callable(generate_zarf_yaml_from_template)


def test_version_parser_integration():
    """Test VersionParser can classify versions."""
    from opencenter_build.version_utils import VersionParser, VersionType

    assert VersionParser.classify_version("v1.34.3") == VersionType.PINNED
    assert VersionParser.classify_version("master") == VersionType.MUTABLE
    assert VersionParser.classify_version("a" * 40) == VersionType.COMMIT_SHA


def test_version_validator_integration():
    """Test VersionValidator can validate specs."""
    from opencenter_build.version_utils import (
        VersionValidator,
        VersionSpec,
        VersionType,
    )

    validator = VersionValidator(allow_mutable=False)

    # Valid pinned version
    spec = VersionSpec(
        file_path="test.env",
        line_number=1,
        variable_name="VERSION",
        value="v1.34.3",
        version_type=VersionType.PINNED,
    )
    assert validator.validate_spec(spec) is True

    # Invalid mutable version
    spec_mutable = VersionSpec(
        file_path="test.env",
        line_number=2,
        variable_name="VERSION",
        value="master",
        version_type=VersionType.MUTABLE,
    )
    assert validator.validate_spec(spec_mutable) is False
    assert len(validator.errors) > 0
