#!/usr/bin/env python3
"""
Unit Tests: Build State Management

Tests state creation, serialization, deserialization, step status transitions,
and corrupted JSON handling.

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
"""

import sys
from pathlib import Path
from datetime import datetime
import json
import pytest

# Add scripts/build to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "build"))

from build_state import BuildState, StepResult, StepStatus


class TestStepResult:
    """Unit tests for StepResult dataclass."""
    
    def test_step_result_creation(self):
        """Test creating a StepResult instance."""
        step = StepResult(
            name="test_step",
            status=StepStatus.COMPLETED,
            start_time=datetime(2024, 1, 15, 10, 0, 0),
            end_time=datetime(2024, 1, 15, 10, 5, 0),
            duration_seconds=300.0,
            error_message=None
        )
        
        assert step.name == "test_step"
        assert step.status == StepStatus.COMPLETED
        assert step.start_time == datetime(2024, 1, 15, 10, 0, 0)
        assert step.end_time == datetime(2024, 1, 15, 10, 5, 0)
        assert step.duration_seconds == 300.0
        assert step.error_message is None
    
    def test_step_result_to_dict(self):
        """Test StepResult serialization to dictionary."""
        step = StepResult(
            name="test_step",
            status=StepStatus.IN_PROGRESS,
            start_time=datetime(2024, 1, 15, 10, 0, 0),
            end_time=None,
            duration_seconds=None,
            error_message=None
        )
        
        data = step.to_dict()
        
        assert data["name"] == "test_step"
        assert data["status"] == "in_progress"
        assert data["start_time"] == "2024-01-15T10:00:00"
        assert data["end_time"] is None
        assert data["duration_seconds"] is None
        assert data["error_message"] is None
    
    def test_step_result_from_dict(self):
        """Test StepResult deserialization from dictionary."""
        data = {
            "name": "test_step",
            "status": "completed",
            "start_time": "2024-01-15T10:00:00",
            "end_time": "2024-01-15T10:05:00",
            "duration_seconds": 300.0,
            "error_message": None
        }
        
        step = StepResult.from_dict(data)
        
        assert step.name == "test_step"
        assert step.status == StepStatus.COMPLETED
        assert step.start_time == datetime(2024, 1, 15, 10, 0, 0)
        assert step.end_time == datetime(2024, 1, 15, 10, 5, 0)
        assert step.duration_seconds == 300.0
        assert step.error_message is None
    
    def test_step_result_with_error(self):
        """Test StepResult with error message."""
        step = StepResult(
            name="failed_step",
            status=StepStatus.FAILED,
            start_time=datetime(2024, 1, 15, 10, 0, 0),
            end_time=datetime(2024, 1, 15, 10, 1, 0),
            duration_seconds=60.0,
            error_message="Network timeout"
        )
        
        assert step.status == StepStatus.FAILED
        assert step.error_message == "Network timeout"


class TestBuildState:
    """Unit tests for BuildState dataclass."""
    
    def test_build_state_creation(self):
        """Test creating a BuildState instance."""
        now = datetime.now()
        state = BuildState(
            build_id="build-123",
            start_time=now,
            last_update=now,
            steps={}
        )
        
        assert state.build_id == "build-123"
        assert state.start_time == now
        assert state.last_update == now
        assert len(state.steps) == 0
    
    def test_build_state_serialization(self):
        """Test BuildState serialization to JSON."""
        state = BuildState(
            build_id="build-123",
            start_time=datetime(2024, 1, 15, 10, 0, 0),
            last_update=datetime(2024, 1, 15, 10, 5, 0),
            steps={
                "step1": StepResult(
                    name="step1",
                    status=StepStatus.COMPLETED,
                    start_time=datetime(2024, 1, 15, 10, 0, 0),
                    end_time=datetime(2024, 1, 15, 10, 2, 0),
                    duration_seconds=120.0,
                    error_message=None
                )
            }
        )
        
        json_str = state.to_json()
        
        assert json_str is not None
        assert "build-123" in json_str
        assert "step1" in json_str
        assert "completed" in json_str
        
        # Verify it's valid JSON
        data = json.loads(json_str)
        assert data["build_id"] == "build-123"
        assert "steps" in data
        assert "step1" in data["steps"]
    
    def test_build_state_deserialization(self):
        """Test BuildState deserialization from JSON."""
        json_str = """
        {
            "build_id": "build-123",
            "start_time": "2024-01-15T10:00:00",
            "last_update": "2024-01-15T10:05:00",
            "steps": {
                "step1": {
                    "name": "step1",
                    "status": "completed",
                    "start_time": "2024-01-15T10:00:00",
                    "end_time": "2024-01-15T10:02:00",
                    "duration_seconds": 120.0,
                    "error_message": null
                }
            }
        }
        """
        
        state = BuildState.from_json(json_str)
        
        assert state.build_id == "build-123"
        assert state.start_time == datetime(2024, 1, 15, 10, 0, 0)
        assert state.last_update == datetime(2024, 1, 15, 10, 5, 0)
        assert len(state.steps) == 1
        assert "step1" in state.steps
        assert state.steps["step1"].status == StepStatus.COMPLETED
    
    def test_mark_step_started(self):
        """Test marking a step as started."""
        state = BuildState(
            build_id="build-123",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        state.mark_step_started("test_step")
        
        assert "test_step" in state.steps
        assert state.steps["test_step"].status == StepStatus.IN_PROGRESS
        assert state.steps["test_step"].start_time is not None
        assert state.steps["test_step"].end_time is None
    
    def test_mark_step_completed(self):
        """Test marking a step as completed."""
        state = BuildState(
            build_id="build-123",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        state.mark_step_started("test_step")
        state.mark_step_completed("test_step", duration=150.5)
        
        assert state.steps["test_step"].status == StepStatus.COMPLETED
        assert state.steps["test_step"].duration_seconds == 150.5
        assert state.steps["test_step"].end_time is not None
    
    def test_mark_step_completed_without_start(self):
        """Test marking a step as completed without marking it started first."""
        state = BuildState(
            build_id="build-123",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        state.mark_step_completed("test_step", duration=100.0)
        
        assert "test_step" in state.steps
        assert state.steps["test_step"].status == StepStatus.COMPLETED
        assert state.steps["test_step"].duration_seconds == 100.0
    
    def test_mark_step_failed(self):
        """Test marking a step as failed."""
        state = BuildState(
            build_id="build-123",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        state.mark_step_started("test_step")
        state.mark_step_failed("test_step", error="Network timeout")
        
        assert state.steps["test_step"].status == StepStatus.FAILED
        assert state.steps["test_step"].error_message == "Network timeout"
        assert state.steps["test_step"].end_time is not None
        assert state.steps["test_step"].duration_seconds is not None
    
    def test_mark_step_failed_without_start(self):
        """Test marking a step as failed without marking it started first."""
        state = BuildState(
            build_id="build-123",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        state.mark_step_failed("test_step", error="Configuration error")
        
        assert "test_step" in state.steps
        assert state.steps["test_step"].status == StepStatus.FAILED
        assert state.steps["test_step"].error_message == "Configuration error"
    
    def test_mark_step_skipped(self):
        """Test marking a step as skipped."""
        state = BuildState(
            build_id="build-123",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        state.mark_step_skipped("test_step")
        
        assert "test_step" in state.steps
        assert state.steps["test_step"].status == StepStatus.SKIPPED
    
    def test_is_step_complete(self):
        """Test checking if a step is complete."""
        state = BuildState(
            build_id="build-123",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Step not in state
        assert not state.is_step_complete("nonexistent_step")
        
        # Step in progress
        state.mark_step_started("in_progress_step")
        assert not state.is_step_complete("in_progress_step")
        
        # Step completed
        state.mark_step_completed("completed_step", duration=100.0)
        assert state.is_step_complete("completed_step")
        
        # Step failed
        state.mark_step_failed("failed_step", error="Error")
        assert not state.is_step_complete("failed_step")
        
        # Step skipped
        state.mark_step_skipped("skipped_step")
        assert not state.is_step_complete("skipped_step")
    
    def test_get_incomplete_steps(self):
        """Test getting list of incomplete steps."""
        state = BuildState(
            build_id="build-123",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        all_steps = ["step1", "step2", "step3", "step4", "step5"]
        
        # Mark some steps as completed
        state.mark_step_completed("step1", duration=100.0)
        state.mark_step_completed("step3", duration=150.0)
        
        incomplete = state.get_incomplete_steps(all_steps)
        
        assert len(incomplete) == 3
        assert "step2" in incomplete
        assert "step4" in incomplete
        assert "step5" in incomplete
        assert "step1" not in incomplete
        assert "step3" not in incomplete
    
    def test_save_to_file(self, tmp_path):
        """Test saving state to file."""
        state = BuildState(
            build_id="build-123",
            start_time=datetime(2024, 1, 15, 10, 0, 0),
            last_update=datetime(2024, 1, 15, 10, 5, 0),
            steps={}
        )
        
        state_file = tmp_path / ".build-state.json"
        state.save_to_file(state_file)
        
        assert state_file.exists()
        
        # Verify file permissions (owner read/write only)
        assert state_file.stat().st_mode & 0o777 == 0o600
        
        # Verify content
        content = state_file.read_text()
        assert "build-123" in content
    
    def test_load_from_file(self, tmp_path):
        """Test loading state from file."""
        # Create a state file
        state_file = tmp_path / ".build-state.json"
        state_data = {
            "build_id": "build-123",
            "start_time": "2024-01-15T10:00:00",
            "last_update": "2024-01-15T10:05:00",
            "steps": {}
        }
        state_file.write_text(json.dumps(state_data))
        
        # Load state
        state = BuildState.load_from_file(state_file)
        
        assert state is not None
        assert state.build_id == "build-123"
        assert state.start_time == datetime(2024, 1, 15, 10, 0, 0)
    
    def test_load_from_nonexistent_file(self, tmp_path):
        """Test loading state from nonexistent file."""
        state_file = tmp_path / "nonexistent.json"
        
        state = BuildState.load_from_file(state_file)
        
        assert state is None
    
    def test_load_corrupted_json(self, tmp_path):
        """Test loading state from corrupted JSON file."""
        state_file = tmp_path / ".build-state.json"
        state_file.write_text("{ invalid json }")
        
        state = BuildState.load_from_file(state_file)
        
        # Should return None and not crash
        assert state is None
    
    def test_load_missing_required_field(self, tmp_path):
        """Test loading state with missing required field."""
        state_file = tmp_path / ".build-state.json"
        state_data = {
            "build_id": "build-123",
            # Missing start_time
            "last_update": "2024-01-15T10:05:00",
            "steps": {}
        }
        state_file.write_text(json.dumps(state_data))
        
        state = BuildState.load_from_file(state_file)
        
        # Should return None and not crash
        assert state is None
    
    def test_load_invalid_datetime(self, tmp_path):
        """Test loading state with invalid datetime format."""
        state_file = tmp_path / ".build-state.json"
        state_data = {
            "build_id": "build-123",
            "start_time": "not-a-datetime",
            "last_update": "2024-01-15T10:05:00",
            "steps": {}
        }
        state_file.write_text(json.dumps(state_data))
        
        state = BuildState.load_from_file(state_file)
        
        # Should return None and not crash
        assert state is None
    
    def test_load_invalid_step_status(self, tmp_path):
        """Test loading state with invalid step status."""
        state_file = tmp_path / ".build-state.json"
        state_data = {
            "build_id": "build-123",
            "start_time": "2024-01-15T10:00:00",
            "last_update": "2024-01-15T10:05:00",
            "steps": {
                "step1": {
                    "name": "step1",
                    "status": "invalid_status",
                    "start_time": None,
                    "end_time": None,
                    "duration_seconds": None,
                    "error_message": None
                }
            }
        }
        state_file.write_text(json.dumps(state_data))
        
        state = BuildState.load_from_file(state_file)
        
        # Should return None and not crash
        assert state is None


class TestStepStatusTransitions:
    """Unit tests for step status transitions."""
    
    def test_status_enum_values(self):
        """Test StepStatus enum values."""
        assert StepStatus.NOT_STARTED.value == "not_started"
        assert StepStatus.IN_PROGRESS.value == "in_progress"
        assert StepStatus.COMPLETED.value == "completed"
        assert StepStatus.FAILED.value == "failed"
        assert StepStatus.SKIPPED.value == "skipped"
    
    def test_multiple_step_transitions(self):
        """Test multiple steps with different status transitions."""
        state = BuildState(
            build_id="build-123",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Step 1: Complete successfully
        state.mark_step_started("step1")
        state.mark_step_completed("step1", duration=100.0)
        
        # Step 2: Fail
        state.mark_step_started("step2")
        state.mark_step_failed("step2", error="Error occurred")
        
        # Step 3: Skip
        state.mark_step_skipped("step3")
        
        # Verify all steps have correct status
        assert state.steps["step1"].status == StepStatus.COMPLETED
        assert state.steps["step2"].status == StepStatus.FAILED
        assert state.steps["step3"].status == StepStatus.SKIPPED
        
        # Verify only step1 is complete
        assert state.is_step_complete("step1")
        assert not state.is_step_complete("step2")
        assert not state.is_step_complete("step3")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
