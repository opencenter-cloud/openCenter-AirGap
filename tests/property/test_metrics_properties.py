"""Property-based tests for build metrics.

Tests Property 13: Metrics Completeness
Validates: Requirements 8.2, 8.3, 8.4, 8.5
"""

from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from hypothesis import given, strategies as st

from opencenter_build.metrics import BuildMetrics


@given(
    build_id=st.text(min_size=1, max_size=50),
    duration=st.floats(min_value=0.1, max_value=10000.0),
    steps_completed=st.integers(min_value=0, max_value=100),
    steps_failed=st.integers(min_value=0, max_value=10),
    success=st.booleans(),
    image_count=st.integers(min_value=0, max_value=1000),
    chart_count=st.integers(min_value=0, max_value=100),
    repo_count=st.integers(min_value=0, max_value=50),
    binary_count=st.integers(min_value=0, max_value=100),
    os_package_count=st.integers(min_value=0, max_value=5000),
    pypi_package_count=st.integers(min_value=0, max_value=1000),
    terraform_provider_count=st.integers(min_value=0, max_value=50),
)
def test_metrics_completeness_property(
    build_id: str,
    duration: float,
    steps_completed: int,
    steps_failed: int,
    success: bool,
    image_count: int,
    chart_count: int,
    repo_count: int,
    binary_count: int,
    os_package_count: int,
    pypi_package_count: int,
    terraform_provider_count: int,
):
    """Property 13: Metrics Completeness.

    **Validates: Requirements 8.2, 8.3, 8.4, 8.5**

    For any completed build, the exported metrics should include:
    - Build duration (8.2)
    - Build success/failure status (8.3)
    - Per-step durations (8.4)
    - Artifact counts by type (8.5)
    """
    # Create metrics
    start_time = datetime.now()
    metrics = BuildMetrics(
        build_id=build_id,
        start_time=start_time,
        steps_completed=steps_completed,
        steps_failed=steps_failed,
        image_count=image_count,
        chart_count=chart_count,
        repo_count=repo_count,
        binary_count=binary_count,
        os_package_count=os_package_count,
        pypi_package_count=pypi_package_count,
        terraform_provider_count=terraform_provider_count,
    )

    # Simulate step durations
    step_names = [f"step_{i}" for i in range(steps_completed)]
    for step_name in step_names:
        metrics.record_step_duration(step_name, duration / max(steps_completed, 1))

    # Complete the build
    metrics.end_time = start_time + timedelta(seconds=duration)
    metrics.duration_seconds = duration
    metrics.success = success

    # Export to Prometheus format
    prom_output = metrics.to_prometheus()

    # Verify build duration is present (Requirement 8.2)
    assert "opencenter_build_duration_seconds" in prom_output, "Metrics must include build duration"
    assert f'build_id="{build_id}"' in prom_output, "Metrics must include build_id label"

    # Verify success/failure status is present (Requirement 8.3)
    assert "opencenter_build_success" in prom_output, "Metrics must include build success status"
    expected_success_value = "1" if success else "0"
    assert (
        f'opencenter_build_success{{build_id="{build_id}"}} {expected_success_value}' in prom_output
    ), "Metrics must correctly report success/failure status"

    # Verify per-step durations are present (Requirement 8.4)
    if steps_completed > 0:
        assert (
            "opencenter_build_step_duration_seconds" in prom_output
        ), "Metrics must include per-step durations when steps are completed"
        for step_name in step_names:
            assert (
                f'step="{step_name}"' in prom_output
            ), f"Metrics must include duration for step {step_name}"

    # Verify artifact counts by type are present (Requirement 8.5)
    assert "opencenter_build_artifact_count" in prom_output, "Metrics must include artifact counts"

    artifact_types = [
        ("images", image_count),
        ("charts", chart_count),
        ("repos", repo_count),
        ("binaries", binary_count),
        ("os_packages", os_package_count),
        ("pypi_packages", pypi_package_count),
        ("terraform_providers", terraform_provider_count),
    ]

    for artifact_type, count in artifact_types:
        assert (
            f'type="{artifact_type}"' in prom_output
        ), f"Metrics must include count for artifact type {artifact_type}"
        assert (
            f"}} {count}" in prom_output
        ), f"Metrics must include correct count for {artifact_type}"


@given(
    build_id=st.text(min_size=1, max_size=50),
    step_count=st.integers(min_value=1, max_value=20),
)
def test_step_duration_recording_property(build_id: str, step_count: int):
    """Property: Step durations are correctly recorded and exported.

    **Validates: Requirements 8.4**

    For any set of build steps with durations, all step durations
    should be present in the exported metrics.
    """
    metrics = BuildMetrics(build_id=build_id, start_time=datetime.now())

    # Record step durations
    step_durations = {}
    for i in range(step_count):
        step_name = f"step_{i}"
        duration = float(i + 1) * 10.0
        metrics.record_step_duration(step_name, duration)
        step_durations[step_name] = duration

    # Complete the build
    metrics.complete(success=True)

    # Export to Prometheus
    prom_output = metrics.to_prometheus()

    # Verify all step durations are present
    for step_name, duration in step_durations.items():
        assert f'step="{step_name}"' in prom_output, f"Step {step_name} must be present in metrics"
        assert f"}} {duration}" in prom_output, f"Duration for step {step_name} must be correct"


@given(
    build_id=st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(
            blacklist_categories=("Cc", "Cs"),  # Exclude control and surrogate characters
            blacklist_characters='\r\n\t"\\',  # Exclude problematic characters for Prometheus labels
        ),
    ),
)
def test_metrics_file_export_property(build_id: str):
    """Property: Metrics are correctly saved to files.

    **Validates: Requirements 8.6**

    For any build metrics, saving to a directory should create both
    JSON and Prometheus format files with correct content.
    """
    metrics = BuildMetrics(build_id=build_id, start_time=datetime.now())
    metrics.complete(success=True)

    # Save to temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        metrics.save(output_dir)

        # Verify JSON file exists and is valid
        json_file = output_dir / "metrics.json"
        assert json_file.exists(), "JSON metrics file must be created"

        json_content = json_file.read_text()
        import json

        json_data = json.loads(json_content)
        assert json_data["build_id"] == build_id, "JSON metrics must contain correct build_id"

        # Verify Prometheus file exists and contains metrics
        prom_file = output_dir / "metrics.prom"
        assert prom_file.exists(), "Prometheus metrics file must be created"

        prom_content = prom_file.read_text()
        assert (
            "opencenter_build_duration_seconds" in prom_content
        ), "Prometheus metrics must contain duration metric"
        assert (
            f'build_id="{build_id}"' in prom_content
        ), "Prometheus metrics must contain build_id label"


@given(
    build_id=st.text(min_size=1, max_size=50),
    artifact_counts=st.fixed_dictionaries(
        {
            "image_count": st.integers(min_value=0, max_value=1000),
            "chart_count": st.integers(min_value=0, max_value=100),
            "repo_count": st.integers(min_value=0, max_value=50),
            "binary_count": st.integers(min_value=0, max_value=100),
            "os_package_count": st.integers(min_value=0, max_value=5000),
            "pypi_package_count": st.integers(min_value=0, max_value=1000),
            "terraform_provider_count": st.integers(min_value=0, max_value=50),
        }
    ),
)
def test_artifact_count_completeness_property(
    build_id: str,
    artifact_counts: dict,
):
    """Property: All artifact types are included in metrics.

    **Validates: Requirements 8.5**

    For any set of artifact counts, the metrics should include counts
    for all artifact types: images, charts, repos, binaries, OS packages,
    PyPI packages, and Terraform providers.
    """
    metrics = BuildMetrics(
        build_id=build_id,
        start_time=datetime.now(),
        **artifact_counts,
    )
    metrics.complete(success=True)

    prom_output = metrics.to_prometheus()

    # Verify all artifact types are present
    expected_types = [
        "images",
        "charts",
        "repos",
        "binaries",
        "os_packages",
        "pypi_packages",
        "terraform_providers",
    ]

    for artifact_type in expected_types:
        assert (
            f'type="{artifact_type}"' in prom_output
        ), f"Metrics must include artifact type {artifact_type}"
