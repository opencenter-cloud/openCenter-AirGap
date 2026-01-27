#!/usr/bin/env python3
"""
Property-Based Tests: Build State Management

Property 1: State Persistence Round Trip
Property 2: Completed Steps Are Skipped
Property 3: Corrupted State Recovery

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import json
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck, assume

# Add scripts/build to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "build"))

from build_state import BuildState, StepResult, StepStatus

# Test configuration
MIN_EXAMPLES = 100
MAX_EXAMPLES = 200


# Hypothesis strategies
step_name_strategy = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122),  # a-z
    min_size=1,
    max_size=50
).map(lambda s: s.replace(" ", "_"))

step_status_strategy = st.sampled_from(list(StepStatus))

datetime_strategy = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31)
)

duration_strategy = st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False)

error_message_strategy = st.one_of(
    st.none(),
    st.text(min_size=0, max_size=500)
)


def build_step_result_strategy():
    """Strategy for generating StepResult instances."""
    return st.builds(
        StepResult,
        name=step_name_strategy,
        status=step_status_strategy,
        start_time=st.one_of(st.none(), datetime_strategy),
        end_time=st.one_of(st.none(), datetime_strategy),
        duration_seconds=st.one_of(st.none(), duration_strategy),
        error_message=error_message_strategy
    )


def build_state_strategy():
    """Strategy for generating BuildState instances."""
    return st.builds(
        BuildState,
        build_id=st.text(min_size=1, max_size=100),
        start_time=datetime_strategy,
        last_update=datetime_strategy,
        steps=st.dictionaries(
            keys=step_name_strategy,
            values=build_step_result_strategy(),
            min_size=0,
            max_size=20
        )
    )


# Feature: resumable-build-system, Property 1: State Persistence Round Trip
@given(state=build_state_strategy())
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
def test_property_1_state_persistence_round_trip(state):
    """
    Property 1: State Persistence Round Trip
    
    For any build execution with completed steps, saving the state
    and then loading it should produce an equivalent state object
    with all step statuses, timestamps, and durations preserved.
    
    **Validates: Requirements 1.1, 1.2, 1.3, 1.5**
    """
    # Save to JSON
    json_str = state.to_json()
    
    # Verify JSON is valid
    assert json_str is not None
    assert len(json_str) > 0
    
    # Load from JSON
    loaded_state = BuildState.from_json(json_str)
    
    # Verify equivalence - build metadata
    assert loaded_state.build_id == state.build_id
    assert loaded_state.start_time == state.start_time
    assert loaded_state.last_update == state.last_update
    
    # Verify equivalence - step count
    assert len(loaded_state.steps) == len(state.steps)
    
    # Verify equivalence - each step
    for step_name in state.steps:
        assert step_name in loaded_state.steps, f"Step {step_name} missing after round trip"
        
        original = state.steps[step_name]
        loaded = loaded_state.steps[step_name]
        
        assert loaded.name == original.name
        assert loaded.status == original.status
        assert loaded.start_time == original.start_time
        assert loaded.end_time == original.end_time
        assert loaded.error_message == original.error_message
        
        # Handle floating point comparison for duration
        if original.duration_seconds is None:
            assert loaded.duration_seconds is None
        else:
            assert loaded.duration_seconds == pytest.approx(original.duration_seconds, rel=1e-9)


# Feature: resumable-build-system, Property 1: State Persistence Round Trip (File-based)
@given(state=build_state_strategy())
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
def test_property_1_state_file_persistence_round_trip(state, tmp_path):
    """
    Property 1: State Persistence Round Trip (File-based)
    
    For any build state, saving to file and loading from file
    should produce an equivalent state object.
    
    **Validates: Requirements 1.1, 1.2, 1.3, 1.5**
    """
    state_file = tmp_path / ".build-state.json"
    
    # Save to file
    state.save_to_file(state_file)
    
    # Verify file exists
    assert state_file.exists()
    
    # Verify file permissions are restrictive (owner read/write only)
    assert state_file.stat().st_mode & 0o777 == 0o600
    
    # Load from file
    loaded_state = BuildState.load_from_file(state_file)
    
    # Verify state was loaded
    assert loaded_state is not None
    
    # Verify equivalence
    assert loaded_state.build_id == state.build_id
    assert loaded_state.start_time == state.start_time
    assert loaded_state.last_update == state.last_update
    assert len(loaded_state.steps) == len(state.steps)
    
    for step_name in state.steps:
        assert step_name in loaded_state.steps
        original = state.steps[step_name]
        loaded = loaded_state.steps[step_name]
        assert loaded.name == original.name
        assert loaded.status == original.status


# Feature: resumable-build-system, Property 2: Completed Steps Are Skipped
@given(
    all_steps=st.lists(step_name_strategy, min_size=1, max_size=20, unique=True),
    completed_indices=st.data()
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
def test_property_2_completed_steps_are_skipped(all_steps, completed_indices):
    """
    Property 2: Completed Steps Are Skipped
    
    For any step marked as completed in the build state, when the build
    resumes, that step should not be re-executed unless explicitly forced.
    
    **Validates: Requirements 1.4**
    """
    # Select a subset of all_steps to mark as completed
    num_completed = completed_indices.draw(st.integers(min_value=1, max_value=len(all_steps)))
    completed_steps = completed_indices.draw(st.lists(
        st.sampled_from(all_steps),
        min_size=num_completed,
        max_size=num_completed,
        unique=True
    ))
    
    # Create state with some completed steps
    state = BuildState(
        build_id="test-build",
        start_time=datetime.now(),
        last_update=datetime.now()
    )
    
    # Mark some steps as completed
    for step_name in completed_steps:
        state.mark_step_completed(step_name, duration=10.0)
    
    # Verify completed steps are marked as complete
    for step_name in completed_steps:
        assert state.is_step_complete(step_name), (
            f"Step {step_name} should be marked as complete"
        )
    
    # Verify incomplete steps are not marked as complete
    incomplete_steps = [s for s in all_steps if s not in completed_steps]
    for step_name in incomplete_steps:
        assert not state.is_step_complete(step_name), (
            f"Step {step_name} should not be marked as complete"
        )
    
    # Get incomplete steps
    incomplete = state.get_incomplete_steps(all_steps)
    
    # Property: Incomplete steps should be exactly those not completed
    assert set(incomplete) == set(incomplete_steps)


# Feature: resumable-build-system, Property 3: Corrupted State Recovery
@given(
    valid_state=build_state_strategy(),
    corruption_type=st.sampled_from([
        "invalid_json",
        "missing_field",
        "invalid_datetime",
        "invalid_status"
    ])
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
def test_property_3_corrupted_state_recovery(valid_state, corruption_type, tmp_path):
    """
    Property 3: Corrupted State Recovery
    
    For any invalid or corrupted JSON state file, the build orchestrator
    should start a fresh build and log a warning without crashing.
    
    **Validates: Requirements 1.6**
    """
    state_file = tmp_path / ".build-state.json"
    
    # Create corrupted state file based on corruption type
    if corruption_type == "invalid_json":
        # Write invalid JSON
        state_file.write_text("{ invalid json content }")
    
    elif corruption_type == "missing_field":
        # Write JSON with missing required field
        corrupted_data = {
            "build_id": valid_state.build_id,
            # Missing start_time
            "last_update": valid_state.last_update.isoformat(),
            "steps": {}
        }
        state_file.write_text(json.dumps(corrupted_data))
    
    elif corruption_type == "invalid_datetime":
        # Write JSON with invalid datetime format
        corrupted_data = {
            "build_id": valid_state.build_id,
            "start_time": "not-a-datetime",
            "last_update": valid_state.last_update.isoformat(),
            "steps": {}
        }
        state_file.write_text(json.dumps(corrupted_data))
    
    elif corruption_type == "invalid_status":
        # Write JSON with invalid step status
        corrupted_data = {
            "build_id": valid_state.build_id,
            "start_time": valid_state.start_time.isoformat(),
            "last_update": valid_state.last_update.isoformat(),
            "steps": {
                "test_step": {
                    "name": "test_step",
                    "status": "invalid_status_value",
                    "start_time": None,
                    "end_time": None,
                    "duration_seconds": None,
                    "error_message": None
                }
            }
        }
        state_file.write_text(json.dumps(corrupted_data))
    
    # Attempt to load corrupted state
    loaded_state = BuildState.load_from_file(state_file)
    
    # Property: Corrupted state should return None (not crash)
    assert loaded_state is None, (
        f"Corrupted state ({corruption_type}) should return None, not crash"
    )


# Feature: resumable-build-system, Property 1: Step Status Transitions
@given(
    step_name=step_name_strategy,
    duration=duration_strategy,
    error_message=st.text(min_size=1, max_size=200)
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
def test_property_1_step_status_transitions(step_name, duration, error_message):
    """
    Property 1: Step Status Transitions
    
    For any step, the state management should correctly track status
    transitions (started -> completed/failed/skipped).
    
    **Validates: Requirements 1.1, 1.2, 1.5**
    """
    state = BuildState(
        build_id="test-build",
        start_time=datetime.now(),
        last_update=datetime.now()
    )
    
    # Test: mark_step_started
    state.mark_step_started(step_name)
    assert step_name in state.steps
    assert state.steps[step_name].status == StepStatus.IN_PROGRESS
    assert state.steps[step_name].start_time is not None
    
    # Test: mark_step_completed
    state_completed = BuildState(
        build_id="test-build-2",
        start_time=datetime.now(),
        last_update=datetime.now()
    )
    state_completed.mark_step_started(step_name)
    state_completed.mark_step_completed(step_name, duration)
    assert state_completed.steps[step_name].status == StepStatus.COMPLETED
    assert state_completed.steps[step_name].duration_seconds == pytest.approx(duration, rel=1e-9)
    assert state_completed.steps[step_name].end_time is not None
    
    # Test: mark_step_failed
    state_failed = BuildState(
        build_id="test-build-3",
        start_time=datetime.now(),
        last_update=datetime.now()
    )
    state_failed.mark_step_started(step_name)
    state_failed.mark_step_failed(step_name, error_message)
    assert state_failed.steps[step_name].status == StepStatus.FAILED
    assert state_failed.steps[step_name].error_message == error_message
    assert state_failed.steps[step_name].end_time is not None
    
    # Test: mark_step_skipped
    state_skipped = BuildState(
        build_id="test-build-4",
        start_time=datetime.now(),
        last_update=datetime.now()
    )
    state_skipped.mark_step_skipped(step_name)
    assert state_skipped.steps[step_name].status == StepStatus.SKIPPED


# Feature: resumable-build-system, Property 1: Empty State Handling
@given(build_id=st.text(min_size=1, max_size=100))
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
def test_property_1_empty_state_handling(build_id):
    """
    Property 1: Empty State Handling
    
    For any build state with no steps, serialization and deserialization
    should work correctly.
    
    **Validates: Requirements 1.1, 1.2, 1.3, 1.5**
    """
    # Create empty state
    state = BuildState(
        build_id=build_id,
        start_time=datetime.now(),
        last_update=datetime.now(),
        steps={}
    )
    
    # Save to JSON
    json_str = state.to_json()
    
    # Load from JSON
    loaded_state = BuildState.from_json(json_str)
    
    # Verify equivalence
    assert loaded_state.build_id == state.build_id
    assert len(loaded_state.steps) == 0
    assert loaded_state.steps == {}


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
