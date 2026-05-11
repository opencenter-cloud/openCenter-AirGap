"""Property-based tests for artifact manifest generation.

Tests universal correctness properties for manifest completeness,
consistency, serialization, and export functionality.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

from hypothesis import given, strategies as st
from hypothesis import assume

from opencenter_build.manifest import ArtifactManifest, ManifestGenerator


# Strategies for generating test data
@st.composite
def artifact_manifest_strategy(draw):
    """Generate arbitrary ArtifactManifest instances."""
    build_id = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "P", "S"), blacklist_characters="\r\n")))
    timestamp = datetime.now()

    # Generate images
    images = draw(st.lists(st.text(min_size=1, max_size=100), max_size=20))
    image_count = len(images)
    image_total_size = draw(st.integers(min_value=0, max_value=10**10))

    # Generate charts
    chart_count = draw(st.integers(min_value=0, max_value=50))
    charts = [
        {"name": f"chart-{i}", "version": "1.0.0", "url": f"https://example.com/chart-{i}.tgz"}
        for i in range(chart_count)
    ]

    # Generate repos
    repo_count = draw(st.integers(min_value=0, max_value=20))
    repos = [
        {
            "url": f"https://github.com/org/repo-{i}.git",
            "ref": "main",
            "size": draw(st.integers(min_value=0, max_value=10**9)),
        }
        for i in range(repo_count)
    ]

    # Generate binaries
    binary_count = draw(st.integers(min_value=0, max_value=30))
    binary_total_size = draw(st.integers(min_value=0, max_value=10**10))
    binaries = [
        {
            "name": f"binary-{i}",
            "version": "1.0.0",
            "path": f"/path/to/binary-{i}",
            "size": draw(st.integers(min_value=0, max_value=10**8)),
            "sha256": draw(st.text(min_size=64, max_size=64, alphabet="0123456789abcdef")),
        }
        for i in range(binary_count)
    ]

    # Generate OS packages
    os_package_count = draw(st.integers(min_value=0, max_value=100))
    os_package_total_size = draw(st.integers(min_value=0, max_value=10**10))
    os_packages = [
        {"name": f"package-{i}", "version": "1.0.0", "arch": "amd64"}
        for i in range(os_package_count)
    ]

    # Generate PyPI packages
    pypi_package_count = draw(st.integers(min_value=0, max_value=100))
    pypi_package_total_size = draw(st.integers(min_value=0, max_value=10**10))
    pypi_packages = [
        {
            "name": f"pypi-package-{i}",
            "version": "1.0.0",
            "type": draw(st.sampled_from(["wheel", "source"])),
        }
        for i in range(pypi_package_count)
    ]

    # Generate Terraform providers
    terraform_provider_count = draw(st.integers(min_value=0, max_value=20))
    terraform_providers = [
        {"name": f"provider-{i}", "version": "1.0.0", "platform": "linux_amd64"}
        for i in range(terraform_provider_count)
    ]

    manifest = ArtifactManifest(
        build_id=build_id,
        timestamp=timestamp,
        images=images,
        image_count=image_count,
        image_total_size=image_total_size,
        charts=charts,
        chart_count=chart_count,
        repos=repos,
        repo_count=repo_count,
        binaries=binaries,
        binary_count=binary_count,
        binary_total_size=binary_total_size,
        os_packages=os_packages,
        os_package_count=os_package_count,
        os_package_total_size=os_package_total_size,
        pypi_packages=pypi_packages,
        pypi_package_count=pypi_package_count,
        pypi_package_total_size=pypi_package_total_size,
        terraform_providers=terraform_providers,
        terraform_provider_count=terraform_provider_count,
    )

    manifest.calculate_totals()
    return manifest


@given(manifest=artifact_manifest_strategy())
def test_property_manifest_completeness(manifest):
    """Property 8: Manifest Completeness.

    For any artifact manifest, it should contain complete information for all
    artifact types: images, charts, repos, binaries, OS packages, PyPI packages,
    and Terraform providers.

    **Validates: Requirements 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8**
    """
    # Images should have names and counts
    assert isinstance(manifest.images, list)
    assert manifest.image_count == len(manifest.images)
    assert manifest.image_total_size >= 0

    # Charts should have metadata
    assert isinstance(manifest.charts, list)
    assert manifest.chart_count == len(manifest.charts)
    for chart in manifest.charts:
        assert "name" in chart

    # Repos should have metadata
    assert isinstance(manifest.repos, list)
    assert manifest.repo_count == len(manifest.repos)
    for repo in manifest.repos:
        assert "url" in repo

    # Binaries should have complete metadata
    assert isinstance(manifest.binaries, list)
    assert manifest.binary_count == len(manifest.binaries)
    assert manifest.binary_total_size >= 0
    for binary in manifest.binaries:
        assert "name" in binary
        assert "path" in binary
        assert "size" in binary
        assert "sha256" in binary

    # OS packages should have metadata
    assert isinstance(manifest.os_packages, list)
    assert manifest.os_package_count == len(manifest.os_packages)
    assert manifest.os_package_total_size >= 0
    for pkg in manifest.os_packages:
        assert "name" in pkg
        assert "version" in pkg
        assert "arch" in pkg

    # PyPI packages should have metadata
    assert isinstance(manifest.pypi_packages, list)
    assert manifest.pypi_package_count == len(manifest.pypi_packages)
    assert manifest.pypi_package_total_size >= 0
    for pkg in manifest.pypi_packages:
        assert "name" in pkg
        assert "version" in pkg
        assert "type" in pkg
        assert pkg["type"] in ["wheel", "source"]

    # Terraform providers should have metadata
    assert isinstance(manifest.terraform_providers, list)
    assert manifest.terraform_provider_count == len(manifest.terraform_providers)
    for provider in manifest.terraform_providers:
        assert "name" in provider
        assert "version" in provider
        assert "platform" in provider


@given(manifest=artifact_manifest_strategy())
def test_property_manifest_total_consistency(manifest):
    """Property 9: Manifest Total Consistency.

    For any artifact manifest, the total artifact count should equal the sum
    of individual type counts, and the total size should equal the sum of
    individual type sizes.

    **Validates: Requirements 6.9**
    """
    # Total count should equal sum of individual counts
    expected_count = (
        manifest.image_count
        + manifest.chart_count
        + manifest.repo_count
        + manifest.binary_count
        + manifest.os_package_count
        + manifest.pypi_package_count
        + manifest.terraform_provider_count
    )
    assert manifest.total_artifacts == expected_count

    # Total size should equal sum of individual sizes
    expected_size = (
        manifest.image_total_size
        + manifest.binary_total_size
        + manifest.os_package_total_size
        + manifest.pypi_package_total_size
    )
    assert manifest.total_size == expected_size


@given(manifest=artifact_manifest_strategy())
def test_property_manifest_serialization_round_trip(manifest):
    """Property 10: Manifest Serialization Round Trip.

    For any artifact manifest, serializing to JSON and deserializing back
    should produce an equivalent manifest with all fields preserved.

    **Validates: Requirements 6.10**
    """
    # Serialize to dict
    manifest_dict = manifest.to_dict()

    # Verify it's JSON-serializable
    json_str = json.dumps(manifest_dict)
    assert isinstance(json_str, str)

    # Deserialize back
    restored_dict = json.loads(json_str)
    restored_manifest = ArtifactManifest.from_dict(restored_dict)

    # Verify all fields are preserved
    assert restored_manifest.build_id == manifest.build_id
    assert restored_manifest.timestamp == manifest.timestamp
    assert restored_manifest.images == manifest.images
    assert restored_manifest.image_count == manifest.image_count
    assert restored_manifest.image_total_size == manifest.image_total_size
    assert restored_manifest.charts == manifest.charts
    assert restored_manifest.chart_count == manifest.chart_count
    assert restored_manifest.repos == manifest.repos
    assert restored_manifest.repo_count == manifest.repo_count
    assert restored_manifest.binaries == manifest.binaries
    assert restored_manifest.binary_count == manifest.binary_count
    assert restored_manifest.binary_total_size == manifest.binary_total_size
    assert restored_manifest.os_packages == manifest.os_packages
    assert restored_manifest.os_package_count == manifest.os_package_count
    assert restored_manifest.os_package_total_size == manifest.os_package_total_size
    assert restored_manifest.pypi_packages == manifest.pypi_packages
    assert restored_manifest.pypi_package_count == manifest.pypi_package_count
    assert restored_manifest.pypi_package_total_size == manifest.pypi_package_total_size
    assert restored_manifest.terraform_providers == manifest.terraform_providers
    assert restored_manifest.terraform_provider_count == manifest.terraform_provider_count
    assert restored_manifest.total_artifacts == manifest.total_artifacts
    assert restored_manifest.total_size == manifest.total_size


@given(manifest=artifact_manifest_strategy())
def test_property_markdown_export_completeness(manifest):
    """Property 11: Markdown Export Completeness.

    For any artifact manifest, the Markdown export should contain sections
    for all artifact types and include the summary table with counts and sizes.

    **Validates: Requirements 6.11**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "manifest.md"
        generator = ManifestGenerator(Path(tmpdir))
        generator.export_markdown(manifest, output_path)

        # Verify file was created
        assert output_path.exists()

        # Read content
        content = output_path.read_text()

        # Verify header with build ID
        assert manifest.build_id in content

        # Verify summary table exists
        assert "## Summary" in content
        assert "| Artifact Type | Count | Total Size |" in content

        # Verify all artifact types are mentioned in summary
        assert "Container Images" in content
        assert "Helm Charts" in content
        assert "Git Repositories" in content
        assert "Binaries" in content
        assert "OS Packages" in content
        assert "PyPI Packages" in content
        assert "Terraform Providers" in content
        assert "Total" in content

        # Verify counts appear in content
        assert str(manifest.image_count) in content
        assert str(manifest.chart_count) in content
        assert str(manifest.repo_count) in content
        assert str(manifest.binary_count) in content
        assert str(manifest.os_package_count) in content
        assert str(manifest.pypi_package_count) in content
        assert str(manifest.terraform_provider_count) in content
        assert str(manifest.total_artifacts) in content

        # If there are images, verify images section exists
        if manifest.images:
            assert "## Container Images" in content

        # If there are charts, verify charts section exists
        if manifest.charts:
            assert "## Helm Charts" in content

        # If there are binaries, verify binaries section exists
        if manifest.binaries:
            assert "## Binaries" in content
