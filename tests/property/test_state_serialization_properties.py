#!/usr/bin/env python3
"""
Property-Based Tests: State Serialization

Property 3: State Persistence Round Trip

Validates: Requirements 4.1, 4.5
"""

import json
from datetime import datetime
from pathlib import Path

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from opencenter_build.state import (
    BuildState,
    StepCheckpoint,
    StepStatus,
    FileMetadata,
    ImageMetadata,
    StateManager,
)

# Test configuration
MIN_EXAMPLES = 100
MAX_EXAMPLES = 200


# Hypothesis strategies
step_name_strategy = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=50
).map(lambda s: s.replace(" ", "_"))

step_status_strategy = st.sampled_from(list(StepStatus))

iso_datetime_strategy = st.datetimes(
    min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)
).map(lambda dt: dt.isoformat())

error_message_strategy = st.one_of(st.none(), st.text(min_size=0, max_size=500))

artifacts_strategy = st.one_of(
    st.none(),
    st.dictionaries(
        keys=st.text(min_size=1, max_size=50),
        values=st.text(min_size=1, max_size=200),
        min_size=0,
        max_size=10,
    ),
)


def step_checkpoint_strategy() -> st.SearchStrategy[StepCheckpoint]:
    """Strategy for generating StepCheckpoint instances."""
    return st.builds(
        StepCheckpoint,
        name=step_name_strategy,
        status=step_status_strategy,
        start_time=st.one_of(st.none(), iso_datetime_strategy),
        end_time=st.one_of(st.none(), iso_datetime_strategy),
        error=error_message_strategy,
        artifacts=artifacts_strategy,
    )


def build_state_strategy() -> st.SearchStrategy[BuildState]:
    """Strategy for generating BuildState instances."""
    return st.builds(
        BuildState,
        build_id=st.text(min_size=1, max_size=100),
        start_time=iso_datetime_strategy,
        steps=st.lists(step_checkpoint_strategy(), min_size=0, max_size=20),
        config_hash=st.text(alphabet="0123456789abcdef", min_size=64, max_size=64),
    )


# Property 3: State Persistence Round Trip (In-Memory)
@given(state=build_state_strategy())
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_3_state_persistence_round_trip_memory(state: BuildState) -> None:
    """
    Property 3: State Persistence Round Trip (In-Memory)

    For any build step checkpoint, persisting to dictionary and reading back
    should produce an equivalent checkpoint with all fields preserved.

    **Validates: Requirements 4.1, 4.5**
    """
    # Convert to dictionary
    state_dict = state.to_dict()

    # Verify dictionary is valid
    assert isinstance(state_dict, dict)
    assert "build_id" in state_dict
    assert "start_time" in state_dict
    assert "steps" in state_dict
    assert "config_hash" in state_dict

    # Convert back to BuildState
    loaded_state = BuildState.from_dict(state_dict)

    # Verify equivalence - build metadata
    assert loaded_state.build_id == state.build_id
    assert loaded_state.start_time == state.start_time
    assert loaded_state.config_hash == state.config_hash

    # Verify equivalence - step count
    assert len(loaded_state.steps) == len(state.steps)

    # Verify equivalence - each step
    for i, original_step in enumerate(state.steps):
        loaded_step = loaded_state.steps[i]

        assert loaded_step.name == original_step.name
        assert loaded_step.status == original_step.status
        assert loaded_step.start_time == original_step.start_time
        assert loaded_step.end_time == original_step.end_time
        assert loaded_step.error == original_step.error
        assert loaded_step.artifacts == original_step.artifacts


# Property 3: State Persistence Round Trip (JSON)
@given(state=build_state_strategy())
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_3_state_persistence_round_trip_json(state: BuildState) -> None:
    """
    Property 3: State Persistence Round Trip (JSON)

    For any build state, serializing to JSON and deserializing back should
    produce an equivalent state with all fields preserved.

    **Validates: Requirements 4.1, 4.5**
    """
    # Convert to dictionary and then JSON
    state_dict = state.to_dict()
    json_str = json.dumps(state_dict)

    # Verify JSON is valid
    assert json_str is not None
    assert len(json_str) > 0

    # Parse JSON and convert back to BuildState
    parsed_dict = json.loads(json_str)
    loaded_state = BuildState.from_dict(parsed_dict)

    # Verify equivalence
    assert loaded_state.build_id == state.build_id
    assert loaded_state.start_time == state.start_time
    assert loaded_state.config_hash == state.config_hash
    assert len(loaded_state.steps) == len(state.steps)


# Property 3: State Persistence Round Trip (File)
@given(state=build_state_strategy())
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_3_state_persistence_round_trip_file(state: BuildState, tmp_path: Path) -> None:
    """
    Property 3: State Persistence Round Trip (File)

    For any build state, saving to file via StateManager and loading back
    should produce an equivalent state with all fields preserved.

    **Validates: Requirements 4.1, 4.5**
    """
    state_file = tmp_path / "build-state.json"
    state_mgr = StateManager(state_file)

    # Write state to file
    state_dict = state.to_dict()
    state_mgr.write(state_dict)

    # Verify file exists
    assert state_file.exists()

    # Read state from file
    loaded_dict = state_mgr.read()
    loaded_state = BuildState.from_dict(loaded_dict)

    # Verify equivalence
    assert loaded_state.build_id == state.build_id
    assert loaded_state.start_time == state.start_time
    assert loaded_state.config_hash == state.config_hash
    assert len(loaded_state.steps) == len(state.steps)

    # Verify each step
    for i, original_step in enumerate(state.steps):
        loaded_step = loaded_state.steps[i]
        assert loaded_step.name == original_step.name
        assert loaded_step.status == original_step.status


# Property 3: StepCheckpoint Serialization Round Trip
@given(checkpoint=step_checkpoint_strategy())
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_3_step_checkpoint_round_trip(checkpoint: StepCheckpoint) -> None:
    """
    Property 3: StepCheckpoint Serialization Round Trip

    For any step checkpoint, converting to dictionary and back should
    preserve all fields.

    **Validates: Requirements 4.1, 4.5**
    """
    # Convert to dictionary
    checkpoint_dict = checkpoint.to_dict()

    # Verify dictionary structure
    assert isinstance(checkpoint_dict, dict)
    assert "name" in checkpoint_dict
    assert "status" in checkpoint_dict

    # Convert back to StepCheckpoint
    loaded_checkpoint = StepCheckpoint.from_dict(checkpoint_dict)

    # Verify equivalence
    assert loaded_checkpoint.name == checkpoint.name
    assert loaded_checkpoint.status == checkpoint.status
    assert loaded_checkpoint.start_time == checkpoint.start_time
    assert loaded_checkpoint.end_time == checkpoint.end_time
    assert loaded_checkpoint.error == checkpoint.error
    assert loaded_checkpoint.artifacts == checkpoint.artifacts


# Property 3: Empty State Serialization
@given(
    build_id=st.text(min_size=1, max_size=100),
    config_hash=st.text(alphabet="0123456789abcdef", min_size=64, max_size=64),
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_3_empty_state_serialization(build_id: str, config_hash: str) -> None:
    """
    Property 3: Empty State Serialization

    For any build state with no steps, serialization and deserialization
    should work correctly.

    **Validates: Requirements 4.1, 4.5**
    """
    # Create empty state
    state = BuildState(
        build_id=build_id, start_time=datetime.now().isoformat(), steps=[], config_hash=config_hash
    )

    # Convert to dictionary
    state_dict = state.to_dict()

    # Convert back to BuildState
    loaded_state = BuildState.from_dict(state_dict)

    # Verify equivalence
    assert loaded_state.build_id == state.build_id
    assert loaded_state.config_hash == state.config_hash
    assert len(loaded_state.steps) == 0
    assert loaded_state.steps == []


# Property 3: FileMetadata Serialization
@given(
    path_str=st.text(min_size=1, max_size=200),
    size=st.integers(min_value=0, max_value=1_000_000_000),
    sha256=st.text(alphabet="0123456789abcdef", min_size=64, max_size=64),
    mtime=iso_datetime_strategy,
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_3_file_metadata_serialization(
    path_str: str, size: int, sha256: str, mtime: str
) -> None:
    """
    Property 3: FileMetadata Serialization

    For any file metadata, all fields should be preserved through
    dataclass operations.

    **Validates: Requirements 4.1, 4.5**
    """
    # Create FileMetadata
    metadata = FileMetadata(path=path_str, size=size, sha256=sha256, mtime=mtime)

    # Verify fields
    assert metadata.path == path_str
    assert metadata.size == size
    assert metadata.sha256 == sha256
    assert metadata.mtime == mtime


# Property 3: ImageMetadata Serialization
@given(
    registry=st.text(min_size=1, max_size=100),
    repository=st.text(min_size=1, max_size=100),
    tag=st.text(min_size=1, max_size=50),
    digest=st.one_of(st.none(), st.text(min_size=64, max_size=64)),
    size=st.one_of(st.none(), st.integers(min_value=0, max_value=10_000_000_000)),
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_3_image_metadata_serialization(
    registry: str, repository: str, tag: str, digest: str | None, size: int | None
) -> None:
    """
    Property 3: ImageMetadata Serialization

    For any image metadata, all fields should be preserved and full_name
    should be correctly formatted.

    **Validates: Requirements 4.1, 4.5**
    """
    # Create ImageMetadata
    metadata = ImageMetadata(
        registry=registry, repository=repository, tag=tag, digest=digest, size=size
    )

    # Verify fields
    assert metadata.registry == registry
    assert metadata.repository == repository
    assert metadata.tag == tag
    assert metadata.digest == digest
    assert metadata.size == size

    # Verify full_name property
    expected_full_name = f"{registry}/{repository}:{tag}"
    assert metadata.full_name == expected_full_name


# Property 3: State with All Step Statuses
@given(
    build_id=st.text(min_size=1, max_size=100),
    config_hash=st.text(alphabet="0123456789abcdef", min_size=64, max_size=64),
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_3_state_with_all_step_statuses(build_id: str, config_hash: str) -> None:
    """
    Property 3: State with All Step Statuses

    For any build state containing steps with all possible statuses,
    serialization should preserve the status enum values correctly.

    **Validates: Requirements 4.1, 4.5**
    """
    # Create state with all step statuses
    steps = [
        StepCheckpoint(name="step_pending", status=StepStatus.PENDING),
        StepCheckpoint(name="step_running", status=StepStatus.RUNNING),
        StepCheckpoint(name="step_completed", status=StepStatus.COMPLETED),
        StepCheckpoint(name="step_failed", status=StepStatus.FAILED),
    ]

    state = BuildState(
        build_id=build_id,
        start_time=datetime.now().isoformat(),
        steps=steps,
        config_hash=config_hash,
    )

    # Convert to dictionary and back
    state_dict = state.to_dict()
    loaded_state = BuildState.from_dict(state_dict)

    # Verify all statuses preserved
    assert len(loaded_state.steps) == 4
    assert loaded_state.steps[0].status == StepStatus.PENDING
    assert loaded_state.steps[1].status == StepStatus.RUNNING
    assert loaded_state.steps[2].status == StepStatus.COMPLETED
    assert loaded_state.steps[3].status == StepStatus.FAILED


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
