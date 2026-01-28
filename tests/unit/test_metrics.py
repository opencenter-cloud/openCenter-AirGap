"""Unit tests for build metrics collection and export."""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from opencenter_build.metrics import BuildMetrics


class TestBuildMetrics:
    """Test BuildMetrics class."""

    def test_initialization(self):
        """Test BuildMetrics initialization with required fields."""
        build_id = "build-20260127-1430"
        start_time = datetime.now()

        metrics = BuildMetrics(build_id=build_id, start_time=start_time)

        assert metrics.build_id == build_id
        assert metrics.start_time == start_time
        assert metrics.end_time is None
        assert metrics.duration_seconds is None
        assert metrics.steps_completed == 0
        assert metrics.steps_failed == 0
        assert metrics.package_size_bytes is None
        assert metrics.image_count == 0
        assert metrics.success is False

    def test_complete_success(self):
        """Test marking build as successfully completed."""
        start_time = datetime.now()
        metrics = BuildMetrics(build_id="build-test", start_time=start_time)

        metrics.complete(success=True)

        assert metrics.end_time is not None
        assert metrics.duration_seconds is not None
        assert metrics.duration_seconds >= 0
        assert metrics.success is True

    def test_complete_failure(self):
        """Test marking build as failed."""
        start_time = datetime.now()
        metrics = BuildMetrics(build_id="build-test", start_time=start_time)

        metrics.complete(success=False)

        assert metrics.end_time is not None
        assert metrics.duration_seconds is not None
        assert metrics.success is False

    def test_duration_calculation(self):
        """Test duration calculation is accurate."""
        start_time = datetime.now()
        metrics = BuildMetrics(build_id="build-test", start_time=start_time)

        # Simulate some time passing
        import time

        time.sleep(0.1)

        metrics.complete(success=True)

        assert metrics.duration_seconds >= 0.1
        assert metrics.duration_seconds < 1.0  # Should be quick

    def test_step_tracking(self):
        """Test tracking completed and failed steps."""
        metrics = BuildMetrics(build_id="build-test", start_time=datetime.now())

        metrics.steps_completed = 5
        metrics.steps_failed = 2

        assert metrics.steps_completed == 5
        assert metrics.steps_failed == 2

    def test_resource_tracking(self):
        """Test tracking package size and image count."""
        metrics = BuildMetrics(build_id="build-test", start_time=datetime.now())

        metrics.package_size_bytes = 8589934592  # 8GB
        metrics.image_count = 139

        assert metrics.package_size_bytes == 8589934592
        assert metrics.image_count == 139

    def test_to_json_basic(self):
        """Test JSON export with basic metrics."""
        start_time = datetime(2026, 1, 27, 14, 30, 0)
        metrics = BuildMetrics(build_id="build-20260127-1430", start_time=start_time)

        json_str = metrics.to_json()
        data = json.loads(json_str)

        assert data["build_id"] == "build-20260127-1430"
        assert data["start_time"] == "2026-01-27T14:30:00"
        assert data["end_time"] is None
        assert data["duration_seconds"] is None
        assert data["steps_completed"] == 0
        assert data["steps_failed"] == 0
        assert data["success"] is False

    def test_to_json_complete(self):
        """Test JSON export with completed build."""
        start_time = datetime(2026, 1, 27, 14, 30, 0)
        metrics = BuildMetrics(build_id="build-20260127-1430", start_time=start_time)
        metrics.steps_completed = 5
        metrics.steps_failed = 0
        metrics.package_size_bytes = 8589934592
        metrics.image_count = 139
        metrics.complete(success=True)

        json_str = metrics.to_json()
        data = json.loads(json_str)

        assert data["build_id"] == "build-20260127-1430"
        assert data["start_time"] == "2026-01-27T14:30:00"
        assert data["end_time"] is not None
        assert data["duration_seconds"] is not None
        assert data["steps_completed"] == 5
        assert data["steps_failed"] == 0
        assert data["package_size_bytes"] == 8589934592
        assert data["image_count"] == 139
        assert data["success"] is True

    def test_to_prometheus_basic(self):
        """Test Prometheus export format."""
        start_time = datetime.now()
        metrics = BuildMetrics(build_id="build-test", start_time=start_time)

        prom_str = metrics.to_prometheus()

        assert "# HELP opencenter_build_duration_seconds Build duration" in prom_str
        assert "# TYPE opencenter_build_duration_seconds gauge" in prom_str
        assert 'opencenter_build_duration_seconds{build_id="build-test"} 0' in prom_str
        assert "# HELP opencenter_build_success Build success" in prom_str
        assert 'opencenter_build_success{build_id="build-test"} 0' in prom_str
        assert "# HELP opencenter_build_steps_completed Steps completed" in prom_str
        assert 'opencenter_build_steps_completed{build_id="build-test"} 0' in prom_str
        assert "# HELP opencenter_build_steps_failed Steps failed" in prom_str
        assert 'opencenter_build_steps_failed{build_id="build-test"} 0' in prom_str

    def test_to_prometheus_with_values(self):
        """Test Prometheus export with actual values."""
        start_time = datetime.now()
        metrics = BuildMetrics(build_id="build-20260127", start_time=start_time)
        metrics.steps_completed = 5
        metrics.steps_failed = 1
        metrics.package_size_bytes = 1000000000
        metrics.image_count = 50
        metrics.complete(success=True)

        prom_str = metrics.to_prometheus()

        assert 'opencenter_build_steps_completed{build_id="build-20260127"} 5' in prom_str
        assert 'opencenter_build_steps_failed{build_id="build-20260127"} 1' in prom_str
        assert 'opencenter_build_success{build_id="build-20260127"} 1' in prom_str
        assert (
            'opencenter_build_package_size_bytes{build_id="build-20260127"} 1000000000' in prom_str
        )
        assert 'opencenter_build_image_count{build_id="build-20260127"} 50' in prom_str
        assert (
            f'opencenter_build_duration_seconds{{build_id="build-20260127"}} {metrics.duration_seconds}'
            in prom_str
        )

    def test_to_prometheus_failure(self):
        """Test Prometheus export for failed build."""
        start_time = datetime.now()
        metrics = BuildMetrics(build_id="build-failed", start_time=start_time)
        metrics.complete(success=False)

        prom_str = metrics.to_prometheus()

        assert 'opencenter_build_success{build_id="build-failed"} 0' in prom_str

    def test_save_creates_files(self, tmp_path):
        """Test save creates both JSON and Prometheus files."""
        start_time = datetime.now()
        metrics = BuildMetrics(build_id="build-test", start_time=start_time)
        metrics.steps_completed = 3
        metrics.complete(success=True)

        output_dir = tmp_path / "metrics"
        metrics.save(output_dir)

        json_file = output_dir / "metrics.json"
        prom_file = output_dir / "metrics.prom"

        assert json_file.exists()
        assert prom_file.exists()

    def test_save_json_content(self, tmp_path):
        """Test saved JSON file contains correct data."""
        start_time = datetime(2026, 1, 27, 14, 30, 0)
        metrics = BuildMetrics(build_id="build-20260127", start_time=start_time)
        metrics.steps_completed = 5
        metrics.package_size_bytes = 1000000
        metrics.complete(success=True)

        output_dir = tmp_path / "metrics"
        metrics.save(output_dir)

        json_file = output_dir / "metrics.json"
        data = json.loads(json_file.read_text())

        assert data["build_id"] == "build-20260127"
        assert data["steps_completed"] == 5
        assert data["package_size_bytes"] == 1000000
        assert data["success"] is True

    def test_save_prometheus_content(self, tmp_path):
        """Test saved Prometheus file contains correct format."""
        start_time = datetime.now()
        metrics = BuildMetrics(build_id="build-test", start_time=start_time)
        metrics.steps_completed = 3
        metrics.complete(success=True)

        output_dir = tmp_path / "metrics"
        metrics.save(output_dir)

        prom_file = output_dir / "metrics.prom"
        content = prom_file.read_text()

        assert "# HELP opencenter_build_duration_seconds" in content
        assert 'opencenter_build_steps_completed{build_id="build-test"} 3' in content
        assert 'opencenter_build_success{build_id="build-test"} 1' in content

    def test_save_creates_directory(self, tmp_path):
        """Test save creates output directory if it doesn't exist."""
        start_time = datetime.now()
        metrics = BuildMetrics(build_id="build-test", start_time=start_time)

        output_dir = tmp_path / "nested" / "metrics" / "dir"
        assert not output_dir.exists()

        metrics.save(output_dir)

        assert output_dir.exists()
        assert (output_dir / "metrics.json").exists()
        assert (output_dir / "metrics.prom").exists()

    def test_multiple_saves_overwrite(self, tmp_path):
        """Test multiple saves overwrite previous files."""
        start_time = datetime.now()
        metrics = BuildMetrics(build_id="build-test", start_time=start_time)

        output_dir = tmp_path / "metrics"

        # First save
        metrics.steps_completed = 1
        metrics.save(output_dir)

        # Second save with updated metrics
        metrics.steps_completed = 5
        metrics.save(output_dir)

        # Verify latest values
        json_file = output_dir / "metrics.json"
        data = json.loads(json_file.read_text())
        assert data["steps_completed"] == 5
