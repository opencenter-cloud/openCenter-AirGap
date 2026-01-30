"""Unit tests for StateManager class.

Tests state file creation, concurrent access handling, and corrupted state recovery.
Validates: Requirements 4.1, 4.5
"""

import json
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest

from opencenter_build.exceptions import StateError
from opencenter_build.state import (
    BuildState,
    StateManager,
    StepCheckpoint,
    StepStatus,
)


class TestStateFileCreation:
    """Test state file creation and initialization."""

    def test_state_file_created_on_first_write(self) -> None:
        """State file should be created on first write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state_mgr = StateManager(state_file)

            assert not state_file.exists()

            # Write state
            state = BuildState(
                build_id="test_build",
                start_time=datetime.now().isoformat(),
                steps=[],
                config_hash="test_hash",
            )
            state_mgr.write_build_state(state)

            assert state_file.exists()

    def test_state_file_in_nested_directory(self) -> None:
        """State file should be created in nested directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "build" / "nested" / "state.json"
            state_mgr = StateManager(state_file)

            # Write state
            state = BuildState(
                build_id="test_build",
                start_time=datetime.now().isoformat(),
                steps=[],
                config_hash="test_hash",
            )
            state_mgr.write_build_state(state)

            assert state_file.exists()
            assert state_file.parent.exists()

    def test_read_nonexistent_state_returns_none(self) -> None:
        """Reading nonexistent state should return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state_mgr = StateManager(state_file)

            state = state_mgr.read_build_state()
            assert state is None

    def test_write_and_read_roundtrip(self) -> None:
        """Written state should be readable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state_mgr = StateManager(state_file)

            # Create state
            original_state = BuildState(
                build_id="test_build",
                start_time=datetime.now().isoformat(),
                steps=[
                    StepCheckpoint(
                        name="step_1",
                        status=StepStatus.COMPLETED,
                        start_time=datetime.now().isoformat(),
                        end_time=datetime.now().isoformat(),
                    ),
                    StepCheckpoint(
                        name="step_2",
                        status=StepStatus.PENDING,
                    ),
                ],
                config_hash="test_hash",
            )

            # Write and read
            state_mgr.write_build_state(original_state)
            loaded_state = state_mgr.read_build_state()

            # Verify
            assert loaded_state is not None
            assert loaded_state.build_id == original_state.build_id
            assert loaded_state.start_time == original_state.start_time
            assert loaded_state.config_hash == original_state.config_hash
            assert len(loaded_state.steps) == len(original_state.steps)


class TestConcurrentAccess:
    """Test concurrent access handling with file locking."""

    def test_concurrent_writes_are_serialized(self) -> None:
        """Concurrent writes should be serialized by lock to prevent corruption."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state_mgr = StateManager(state_file)

            # Initialize state with single step
            initial_state = BuildState(
                build_id="test_build",
                start_time=datetime.now().isoformat(),
                steps=[StepCheckpoint(name="shared_step", status=StepStatus.PENDING)],
                config_hash="test_hash",
            )
            state_mgr.write_build_state(initial_state)

            # Track updates and errors
            update_count = []
            errors = []
            lock = threading.Lock()

            def update_step_repeatedly(thread_id: int) -> None:
                """Update the same step repeatedly."""
                try:
                    for i in range(5):
                        step = StepCheckpoint(
                            name="shared_step",
                            status=StepStatus.RUNNING if i % 2 == 0 else StepStatus.COMPLETED,
                            start_time=datetime.now().isoformat(),
                            end_time=datetime.now().isoformat() if i % 2 == 1 else None,
                        )
                        state_mgr.update_step("shared_step", step)

                        with lock:
                            update_count.append((thread_id, i))

                        time.sleep(0.001)
                except Exception as exc:
                    with lock:
                        errors.append((thread_id, exc))

            # Launch concurrent updates
            threads = [threading.Thread(target=update_step_repeatedly, args=(i,)) for i in range(3)]

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            # Verify no errors occurred (no corruption)
            assert len(errors) == 0, f"Errors occurred: {errors}"

            # Verify state file is still valid JSON
            final_state = state_mgr.read_build_state()
            assert final_state is not None
            assert len(final_state.steps) == 1
            assert final_state.steps[0].name == "shared_step"

    def test_concurrent_read_and_write(self) -> None:
        """Concurrent reads and writes should not corrupt state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state_mgr = StateManager(state_file)

            # Initialize state
            initial_state = BuildState(
                build_id="test_build",
                start_time=datetime.now().isoformat(),
                steps=[StepCheckpoint(name="step_1", status=StepStatus.PENDING)],
                config_hash="test_hash",
            )
            state_mgr.write_build_state(initial_state)

            errors = []

            def reader() -> None:
                """Read state repeatedly."""
                try:
                    for _ in range(20):
                        state = state_mgr.read_build_state()
                        assert state is not None
                        time.sleep(0.001)
                except Exception as exc:
                    errors.append(exc)

            def writer() -> None:
                """Write state repeatedly."""
                try:
                    for i in range(20):
                        step = StepCheckpoint(
                            name="step_1",
                            status=StepStatus.RUNNING if i % 2 == 0 else StepStatus.COMPLETED,
                            start_time=datetime.now().isoformat(),
                        )
                        state_mgr.update_step("step_1", step)
                        time.sleep(0.001)
                except Exception as exc:
                    errors.append(exc)

            # Launch concurrent readers and writers
            threads = [
                threading.Thread(target=reader),
                threading.Thread(target=reader),
                threading.Thread(target=writer),
            ]

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            # Verify no errors occurred
            assert len(errors) == 0


class TestCorruptedStateRecovery:
    """Test recovery from corrupted state files."""

    def test_corrupted_state_raises_error(self) -> None:
        """Reading corrupted state should raise StateError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state_mgr = StateManager(state_file)

            # Write corrupted JSON
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text("{ invalid json }")

            with pytest.raises(StateError, match="State file corrupted"):
                state_mgr.read_build_state()

    def test_recover_from_backup(self) -> None:
        """Should recover state from backup file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state_mgr = StateManager(state_file)

            # Write valid state (first write, no backup yet)
            original_state = BuildState(
                build_id="test_build",
                start_time=datetime.now().isoformat(),
                steps=[],
                config_hash="test_hash",
            )
            state_mgr.write_build_state(original_state)

            # Write again to create backup
            state_mgr.write_build_state(original_state)

            # Backup should now exist
            backup_file = state_file.with_suffix(".backup")
            assert backup_file.exists()

            # Corrupt main state file
            state_file.write_text("{ corrupted }")

            # Recover from backup
            recovered = state_mgr.recover()
            assert recovered is True

            # Verify state is restored
            loaded_state = state_mgr.read_build_state()
            assert loaded_state is not None
            assert loaded_state.build_id == original_state.build_id

    def test_recover_without_backup_fails(self) -> None:
        """Recovery should fail if no backup exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state_mgr = StateManager(state_file)

            recovered = state_mgr.recover()
            assert recovered is False

    def test_recover_with_corrupted_backup_fails(self) -> None:
        """Recovery should fail if backup is also corrupted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            backup_file = state_file.with_suffix(".backup")
            state_mgr = StateManager(state_file)

            # Create corrupted backup
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            backup_file.write_text("{ corrupted }")

            recovered = state_mgr.recover()
            assert recovered is False

    def test_atomic_write_prevents_corruption(self) -> None:
        """Atomic write should prevent partial state corruption."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state_mgr = StateManager(state_file)

            # Write initial state
            state1 = BuildState(
                build_id="build_1",
                start_time=datetime.now().isoformat(),
                steps=[],
                config_hash="hash_1",
            )
            state_mgr.write_build_state(state1)

            # Verify temp file is cleaned up
            temp_file = state_file.with_suffix(".tmp")
            assert not temp_file.exists()

            # Write second state
            state2 = BuildState(
                build_id="build_2",
                start_time=datetime.now().isoformat(),
                steps=[],
                config_hash="hash_2",
            )
            state_mgr.write_build_state(state2)

            # Verify state is updated
            loaded_state = state_mgr.read_build_state()
            assert loaded_state is not None
            assert loaded_state.build_id == "build_2"

            # Verify no temp files left behind
            assert not temp_file.exists()


class TestStepOperations:
    """Test step-level operations."""

    def test_update_step_modifies_existing_step(self) -> None:
        """Updating a step should modify it in place."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state_mgr = StateManager(state_file)

            # Create state with steps
            state = BuildState(
                build_id="test_build",
                start_time=datetime.now().isoformat(),
                steps=[
                    StepCheckpoint(name="step_1", status=StepStatus.PENDING),
                    StepCheckpoint(name="step_2", status=StepStatus.PENDING),
                ],
                config_hash="test_hash",
            )
            state_mgr.write_build_state(state)

            # Update step_1
            updated_step = StepCheckpoint(
                name="step_1",
                status=StepStatus.COMPLETED,
                start_time=datetime.now().isoformat(),
                end_time=datetime.now().isoformat(),
            )
            state_mgr.update_step("step_1", updated_step)

            # Verify update
            loaded_state = state_mgr.read_build_state()
            assert loaded_state is not None
            assert loaded_state.steps[0].status == StepStatus.COMPLETED
            assert loaded_state.steps[1].status == StepStatus.PENDING

    def test_update_nonexistent_step_raises_error(self) -> None:
        """Updating nonexistent step should raise error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state_mgr = StateManager(state_file)

            # Create state
            state = BuildState(
                build_id="test_build",
                start_time=datetime.now().isoformat(),
                steps=[
                    StepCheckpoint(name="step_1", status=StepStatus.PENDING),
                ],
                config_hash="test_hash",
            )
            state_mgr.write_build_state(state)

            # Try to update nonexistent step
            updated_step = StepCheckpoint(
                name="nonexistent",
                status=StepStatus.COMPLETED,
            )

            with pytest.raises(StateError, match="Step not found"):
                state_mgr.update_step("nonexistent", updated_step)

    def test_find_resume_point_with_all_pending(self) -> None:
        """Resume point should be 0 when all steps are pending."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state_mgr = StateManager(state_file)

            state = BuildState(
                build_id="test_build",
                start_time=datetime.now().isoformat(),
                steps=[
                    StepCheckpoint(name="step_1", status=StepStatus.PENDING),
                    StepCheckpoint(name="step_2", status=StepStatus.PENDING),
                ],
                config_hash="test_hash",
            )

            resume_point = state_mgr.find_resume_point(state)
            assert resume_point == 0

    def test_find_resume_point_with_all_completed(self) -> None:
        """Resume point should be at end when all steps are completed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state_mgr = StateManager(state_file)

            state = BuildState(
                build_id="test_build",
                start_time=datetime.now().isoformat(),
                steps=[
                    StepCheckpoint(
                        name="step_1",
                        status=StepStatus.COMPLETED,
                        start_time=datetime.now().isoformat(),
                        end_time=datetime.now().isoformat(),
                    ),
                    StepCheckpoint(
                        name="step_2",
                        status=StepStatus.COMPLETED,
                        start_time=datetime.now().isoformat(),
                        end_time=datetime.now().isoformat(),
                    ),
                ],
                config_hash="test_hash",
            )

            resume_point = state_mgr.find_resume_point(state)
            assert resume_point == 2

    def test_find_resume_point_with_mixed_statuses(self) -> None:
        """Resume point should be at first non-completed step."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state_mgr = StateManager(state_file)

            state = BuildState(
                build_id="test_build",
                start_time=datetime.now().isoformat(),
                steps=[
                    StepCheckpoint(
                        name="step_1",
                        status=StepStatus.COMPLETED,
                        start_time=datetime.now().isoformat(),
                        end_time=datetime.now().isoformat(),
                    ),
                    StepCheckpoint(
                        name="step_2",
                        status=StepStatus.FAILED,
                        start_time=datetime.now().isoformat(),
                        end_time=datetime.now().isoformat(),
                        error="test error",
                    ),
                    StepCheckpoint(name="step_3", status=StepStatus.PENDING),
                ],
                config_hash="test_hash",
            )

            resume_point = state_mgr.find_resume_point(state)
            assert resume_point == 1  # First non-completed is step_2 (FAILED)
