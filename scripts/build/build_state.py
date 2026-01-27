"""Build state management for resumable builds.

This module provides state persistence and tracking for the build system,
enabling resume capability after failures.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Dict, Optional, List
from enum import Enum
from pathlib import Path
import json


class StepStatus(Enum):
    """Status of a build step."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of a build step execution."""
    name: str
    status: StepStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'StepResult':
        """Create from dictionary (JSON deserialization)."""
        return cls(
            name=data["name"],
            status=StepStatus(data["status"]),
            start_time=datetime.fromisoformat(data["start_time"]) if data.get("start_time") else None,
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            duration_seconds=data.get("duration_seconds"),
            error_message=data.get("error_message")
        )


@dataclass
class BuildState:
    """State of a build execution."""
    build_id: str
    start_time: datetime
    last_update: datetime
    steps: Dict[str, StepResult] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        data = {
            "build_id": self.build_id,
            "start_time": self.start_time.isoformat(),
            "last_update": self.last_update.isoformat(),
            "steps": {name: step.to_dict() for name, step in self.steps.items()}
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'BuildState':
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(
            build_id=data["build_id"],
            start_time=datetime.fromisoformat(data["start_time"]),
            last_update=datetime.fromisoformat(data["last_update"]),
            steps={
                name: StepResult.from_dict(step_data)
                for name, step_data in data["steps"].items()
            }
        )

    def mark_step_started(self, step_name: str) -> None:
        """Mark step as in progress."""
        now = datetime.now()
        self.steps[step_name] = StepResult(
            name=step_name,
            status=StepStatus.IN_PROGRESS,
            start_time=now
        )
        self.last_update = now

    def mark_step_completed(self, step_name: str, duration: float) -> None:
        """Mark step as completed."""
        now = datetime.now()
        if step_name in self.steps:
            step = self.steps[step_name]
            step.status = StepStatus.COMPLETED
            step.end_time = now
            step.duration_seconds = duration
        else:
            # Step wasn't marked as started, create completed entry
            self.steps[step_name] = StepResult(
                name=step_name,
                status=StepStatus.COMPLETED,
                end_time=now,
                duration_seconds=duration
            )
        self.last_update = now

    def mark_step_failed(self, step_name: str, error: str) -> None:
        """Mark step as failed."""
        now = datetime.now()
        if step_name in self.steps:
            step = self.steps[step_name]
            step.status = StepStatus.FAILED
            step.end_time = now
            step.error_message = error
            if step.start_time:
                step.duration_seconds = (now - step.start_time).total_seconds()
        else:
            # Step wasn't marked as started, create failed entry
            self.steps[step_name] = StepResult(
                name=step_name,
                status=StepStatus.FAILED,
                end_time=now,
                error_message=error
            )
        self.last_update = now

    def mark_step_skipped(self, step_name: str) -> None:
        """Mark step as skipped."""
        now = datetime.now()
        self.steps[step_name] = StepResult(
            name=step_name,
            status=StepStatus.SKIPPED
        )
        self.last_update = now

    def is_step_complete(self, step_name: str) -> bool:
        """Check if step completed successfully."""
        return (
            step_name in self.steps and
            self.steps[step_name].status == StepStatus.COMPLETED
        )

    def get_incomplete_steps(self, all_step_names: List[str]) -> List[str]:
        """Get list of steps that haven't completed."""
        return [
            name for name in all_step_names
            if not self.is_step_complete(name)
        ]

    def save_to_file(self, file_path: Path) -> None:
        """Save state to file with restricted permissions."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        json_str = self.to_json()
        file_path.write_text(json_str)
        # Set restrictive permissions (owner read/write only)
        file_path.chmod(0o600)

    @classmethod
    def load_from_file(cls, file_path: Path) -> Optional['BuildState']:
        """Load state from file, return None if file doesn't exist or is corrupted."""
        if not file_path.exists():
            return None
        
        try:
            json_str = file_path.read_text()
            return cls.from_json(json_str)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Corrupted state file - log warning and return None
            print(f"WARN: Corrupted state file {file_path}: {e}")
            print("WARN: Starting fresh build")
            return None
