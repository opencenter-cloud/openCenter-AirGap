"""Build metrics collection and export.

This module provides the BuildMetrics class for collecting, tracking, and
exporting build operation metrics in JSON and Prometheus formats.
"""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class BuildMetrics:
    """Build operation metrics.

    Tracks build execution metrics including timing, success/failure counts,
    and resource usage. Supports export to JSON and Prometheus formats.

    Attributes:
        build_id: Unique identifier for the build
        start_time: Build start timestamp
        end_time: Build completion timestamp (None if not complete)
        duration_seconds: Total build duration in seconds
        steps_completed: Number of successfully completed steps
        steps_failed: Number of failed steps
        package_size_bytes: Final package size in bytes
        image_count: Number of container images processed
        success: Whether the build completed successfully
    """

    build_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    steps_completed: int = 0
    steps_failed: int = 0
    package_size_bytes: Optional[int] = None
    image_count: int = 0
    success: bool = False

    def complete(self, success: bool = True) -> None:
        """Mark build as complete and calculate duration.

        Args:
            success: Whether the build completed successfully
        """
        self.end_time = datetime.now()
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        self.success = success

    def to_json(self) -> str:
        """Export metrics as JSON string.

        Returns:
            JSON-formatted string containing all metrics
        """
        data = asdict(self)
        data["start_time"] = self.start_time.isoformat()
        if self.end_time:
            data["end_time"] = self.end_time.isoformat()
        return json.dumps(data, indent=2)

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus text format.

        Returns:
            Prometheus-formatted metrics string
        """
        lines = [
            "# HELP opencenter_build_duration_seconds Build duration",
            "# TYPE opencenter_build_duration_seconds gauge",
            f'opencenter_build_duration_seconds{{build_id="{self.build_id}"}} {self.duration_seconds or 0}',
            "",
            "# HELP opencenter_build_success Build success (1=success, 0=failure)",
            "# TYPE opencenter_build_success gauge",
            f'opencenter_build_success{{build_id="{self.build_id}"}} {1 if self.success else 0}',
            "",
            "# HELP opencenter_build_steps_completed Steps completed",
            "# TYPE opencenter_build_steps_completed counter",
            f'opencenter_build_steps_completed{{build_id="{self.build_id}"}} {self.steps_completed}',
            "",
            "# HELP opencenter_build_steps_failed Steps failed",
            "# TYPE opencenter_build_steps_failed counter",
            f'opencenter_build_steps_failed{{build_id="{self.build_id}"}} {self.steps_failed}',
            "",
            "# HELP opencenter_build_package_size_bytes Package size in bytes",
            "# TYPE opencenter_build_package_size_bytes gauge",
            f'opencenter_build_package_size_bytes{{build_id="{self.build_id}"}} {self.package_size_bytes or 0}',
            "",
            "# HELP opencenter_build_image_count Number of container images",
            "# TYPE opencenter_build_image_count gauge",
            f'opencenter_build_image_count{{build_id="{self.build_id}"}} {self.image_count}',
        ]
        return "\n".join(lines)

    def save(self, output_dir: Path) -> None:
        """Save metrics to files in JSON and Prometheus formats.

        Args:
            output_dir: Directory to write metrics files
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # JSON format
        json_file = output_dir / "metrics.json"
        json_file.write_text(self.to_json())

        # Prometheus format
        prom_file = output_dir / "metrics.prom"
        prom_file.write_text(self.to_prometheus())
