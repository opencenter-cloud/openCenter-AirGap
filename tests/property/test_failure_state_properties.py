"""Property-based tests for failure state capture.

Tests Property 4: Failure State Capture
Validates: Requirements 4.2
"""

import tempfile
from datetime import datetime
from pathlib import Path

from hypothesis import given, strategies as st

from opencenter_build.state import (
    BuildState,
    StateManager,
    StepCheckpoint,
    StepStatus,
)


@given(
    step_name=st.text(min_size=1, max_size=50),
    error_message=st.text(min_size=1, max_size=200),
    build_id=st.uuids(),
)
def test_failure_state_capture(step_name: str, error_message: str, build_id: str) -> None:
    """Property 4: Failure State Capture.

    **Validates: Requirements 4.2**

    For any build step failure with an error message, the persisted state
    should contain the failure status, error message, and timestamp.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        state_mgr = StateManager(state_file)

        # Create initial state with one step
        start_time = datetime.now().isoformat()
        step = StepCheckpoint(
            name=step_name,
            status=StepStatus.RUNNING,
            start_time=start_time,
        )

        state = BuildState(
            build_id=str(build_id),
            start_time=start_time,
            steps=[step],
            config_hash="test_hash",
        )

        state_mgr.write_build_state(state)

        # Simulate step failure
        failed_step = StepCheckpoint(
            name=step_name,
            status=StepStatus.FAILED,
            start_time=start_time,
            end_time=datetime.now().isoformat(),
            error=error_message,
        )

        state_mgr.update_step(step_name, failed_step)

        # Read back state
        loaded_state = state_mgr.read_build_state()

        # Verify failure state captured
        assert loaded_state is not None
        assert len(loaded_state.steps) == 1

        loaded_step = loaded_state.steps[0]
        assert loaded_step.name == step_name
        assert loaded_step.status == StepStatus.FAILED
        assert loaded_step.error == error_message
        assert loaded_step.start_time is not None
        assert loaded_step.end_time is not None

        # Verify timestamps are valid ISO 8601
        datetime.fromisoformat(loaded_step.start_time)
        datetime.fromisoformat(loaded_step.end_time)


@given(
    num_steps=st.integers(min_value=1, max_value=10),
    failed_step_index=st.integers(min_value=0, max_value=9),
    error_message=st.text(min_size=1, max_size=200),
)
def test_failure_state_capture_multiple_steps(
    num_steps: int, failed_step_index: int, error_message: str
) -> None:
    """Property 4: Failure State Capture (multiple steps variant).

    **Validates: Requirements 4.2**

    For any build with multiple steps where one fails, the persisted state
    should correctly capture the failure in the specific step while preserving
    other step states.
    """
    # Ensure failed_step_index is within bounds
    failed_step_index = failed_step_index % num_steps

    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        state_mgr = StateManager(state_file)

        # Create initial state with multiple steps
        start_time = datetime.now().isoformat()
        steps = [
            StepCheckpoint(
                name=f"step_{i}",
                status=StepStatus.PENDING if i > failed_step_index else StepStatus.COMPLETED,
                start_time=start_time if i <= failed_step_index else None,
                end_time=start_time if i < failed_step_index else None,
            )
            for i in range(num_steps)
        ]

        state = BuildState(
            build_id="test_build",
            start_time=start_time,
            steps=steps,
            config_hash="test_hash",
        )

        state_mgr.write_build_state(state)

        # Simulate failure at specific step
        failed_step = StepCheckpoint(
            name=f"step_{failed_step_index}",
            status=StepStatus.FAILED,
            start_time=start_time,
            end_time=datetime.now().isoformat(),
            error=error_message,
        )

        state_mgr.update_step(f"step_{failed_step_index}", failed_step)

        # Read back state
        loaded_state = state_mgr.read_build_state()

        # Verify failure captured at correct step
        assert loaded_state is not None
        assert len(loaded_state.steps) == num_steps

        for i, step in enumerate(loaded_state.steps):
            if i == failed_step_index:
                assert step.status == StepStatus.FAILED
                assert step.error == error_message
                assert step.end_time is not None
            elif i < failed_step_index:
                assert step.status == StepStatus.COMPLETED
                assert step.error is None
            else:
                assert step.status == StepStatus.PENDING
                assert step.error is None
