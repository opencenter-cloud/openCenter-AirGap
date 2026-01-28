#!/usr/bin/env python3
"""
Property-Based Tests: StateManager - Atomic State Operations

Property 1: Atomic Write Idempotence
Property 2: Concurrent Access Safety
Property 3: Backup Preservation
Property 4: Recovery Correctness

Validates: Requirements 1.3 (Atomic State Management)
"""

import json
import threading
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from opencenter_build.exceptions import StateError
from opencenter_build.state import StateManager

# Test configuration
MIN_EXAMPLES = 50
MAX_EXAMPLES = 100


# Hypothesis strategies
state_dict_strategy = st.dictionaries(
    keys=st.text(
        min_size=1, max_size=50, alphabet=st.characters(min_codepoint=97, max_codepoint=122)
    ),
    values=st.one_of(
        st.text(min_size=0, max_size=100),
        st.integers(min_value=-1000000, max_value=1000000),
        st.floats(allow_nan=False, allow_infinity=False),
        st.booleans(),
        st.none(),
        st.lists(st.integers(min_value=0, max_value=100), max_size=10),
    ),
    min_size=1,
    max_size=20,
)


# Property 1: Atomic Write Idempotence
@given(state=state_dict_strategy)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_1_atomic_write_idempotence(state: dict[str, Any], tmp_path: Path) -> None:
    """
    Property 1: Atomic Write Idempotence

    For any state dictionary, writing it multiple times should produce
    the same result as writing it once. The state file should always
    contain exactly the last written state.

    **Validates: Requirements 1.3**
    """
    state_file = tmp_path / ".build-state.json"
    state_mgr = StateManager(state_file)

    # Write state multiple times
    state_mgr.write(state)
    state_mgr.write(state)
    state_mgr.write(state)

    # Read back
    loaded_state = state_mgr.read()

    # Property: State should match exactly
    assert loaded_state == state

    # Property: File should be valid JSON
    file_content = state_file.read_text()
    parsed = json.loads(file_content)
    assert parsed == state


# Property 2: Read-Write Round Trip Preservation
@given(state=state_dict_strategy)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_2_read_write_round_trip(state: dict[str, Any], tmp_path: Path) -> None:
    """
    Property 2: Read-Write Round Trip Preservation

    For any state dictionary, writing it and reading it back should
    produce an equivalent dictionary with all keys and values preserved.

    **Validates: Requirements 1.3**
    """
    state_file = tmp_path / ".build-state.json"
    state_mgr = StateManager(state_file)

    # Write state
    state_mgr.write(state)

    # Read state
    loaded_state = state_mgr.read()

    # Property: Loaded state equals original
    assert loaded_state == state
    assert len(loaded_state) == len(state)
    assert set(loaded_state.keys()) == set(state.keys())

    for key in state:
        assert loaded_state[key] == state[key]


# Property 3: Backup Preservation
@given(initial_state=state_dict_strategy, updated_state=state_dict_strategy)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_3_backup_preservation(
    initial_state: dict[str, Any], updated_state: dict[str, Any], tmp_path: Path
) -> None:
    """
    Property 3: Backup Preservation

    For any two different states, writing the second state should
    preserve the first state in a backup file.

    **Validates: Requirements 1.3**
    """
    state_file = tmp_path / ".build-state.json"
    backup_file = state_file.with_suffix(".backup")
    state_mgr = StateManager(state_file)

    # Write initial state
    state_mgr.write(initial_state)

    # Write updated state (should create backup)
    state_mgr.write(updated_state)

    # Property: Backup file exists
    assert backup_file.exists()

    # Property: Backup contains initial state
    backup_data = json.loads(backup_file.read_text())
    assert backup_data == initial_state

    # Property: Current state contains updated state
    current_data = state_mgr.read()
    assert current_data == updated_state


# Property 4: Recovery Correctness
@given(valid_state=state_dict_strategy)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_4_recovery_correctness(valid_state: dict[str, Any], tmp_path: Path) -> None:
    """
    Property 4: Recovery Correctness

    For any valid state, if the current state file is corrupted but
    a valid backup exists, recovery should restore the backup state.

    **Validates: Requirements 1.3**
    """
    state_file = tmp_path / ".build-state.json"
    backup_file = state_file.with_suffix(".backup")
    state_mgr = StateManager(state_file)

    # Create valid backup
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    backup_file.write_text(json.dumps(valid_state))

    # Corrupt current state
    state_file.write_text("{ corrupted json }")

    # Recover
    success = state_mgr.recover()

    # Property: Recovery succeeds
    assert success is True

    # Property: Recovered state matches backup
    recovered_state = state_mgr.read()
    assert recovered_state == valid_state


# Property 5: Empty State Handling
def test_property_5_empty_state_handling(tmp_path: Path) -> None:
    """
    Property 5: Empty State Handling

    Reading from a non-existent state file should always return an
    empty dictionary, never None or raise an exception.

    **Validates: Requirements 1.3**
    """
    state_file = tmp_path / ".build-state.json"
    state_mgr = StateManager(state_file)

    # Property: Reading non-existent file returns empty dict
    state = state_mgr.read()
    assert state == {}
    assert isinstance(state, dict)


# Property 6: Concurrent Write No Corruption
@given(
    num_threads=st.integers(min_value=2, max_value=10),
    writes_per_thread=st.integers(min_value=5, max_value=20),
)
@settings(
    max_examples=20,  # Fewer examples due to threading overhead
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_6_concurrent_write_no_corruption(
    num_threads: int, writes_per_thread: int, tmp_path: Path
) -> None:
    """
    Property 6: Concurrent Write No Corruption

    For any number of concurrent threads writing to the same state file,
    the final state should be valid JSON with no corruption. File locking
    ensures atomic individual operations but doesn't guarantee read-modify-write
    atomicity (that requires application-level locking).

    **Validates: Requirements 1.3**
    """
    state_file = tmp_path / ".build-state.json"
    state_mgr = StateManager(state_file)

    # Initialize state
    state_mgr.write({"initialized": True})

    errors: list[Exception] = []

    def write_state(thread_id: int) -> None:
        """Write state multiple times."""
        try:
            for i in range(writes_per_thread):
                # Each thread writes its own unique state
                state = {
                    "thread_id": thread_id,
                    "write_number": i,
                    "total_writes": writes_per_thread,
                }
                state_mgr.write(state)
        except Exception as e:
            errors.append(e)

    # Run concurrent writes
    threads = []
    for i in range(num_threads):
        thread = threading.Thread(target=write_state, args=(i,))
        threads.append(thread)
        thread.start()

    # Wait for completion
    for thread in threads:
        thread.join()

    # Property: No exceptions occurred
    assert len(errors) == 0, f"Concurrent writes raised errors: {errors}"

    # Property: Final state is valid JSON
    final_state = state_mgr.read()
    assert isinstance(final_state, dict)

    # Property: State contains one of the written states
    assert "thread_id" in final_state
    assert 0 <= final_state["thread_id"] < num_threads

    # Property: State file is valid JSON
    file_content = state_file.read_text()
    parsed = json.loads(file_content)
    assert isinstance(parsed, dict)


# Property 7: Nested Structure Preservation
@given(
    nested_state=st.dictionaries(
        keys=st.text(
            min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)
        ),
        values=st.recursive(
            st.one_of(
                st.text(min_size=0, max_size=50),
                st.integers(min_value=-1000, max_value=1000),
                st.booleans(),
                st.none(),
            ),
            lambda children: st.dictionaries(
                keys=st.text(
                    min_size=1,
                    max_size=20,
                    alphabet=st.characters(min_codepoint=97, max_codepoint=122),
                ),
                values=children,
                max_size=5,
            ),
            max_leaves=20,
        ),
        min_size=1,
        max_size=10,
    )
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_7_nested_structure_preservation(
    nested_state: dict[str, Any], tmp_path: Path
) -> None:
    """
    Property 7: Nested Structure Preservation

    For any nested dictionary structure, writing and reading should
    preserve the entire structure including all nested levels.

    **Validates: Requirements 1.3**
    """
    state_file = tmp_path / ".build-state.json"
    state_mgr = StateManager(state_file)

    # Write nested state
    state_mgr.write(nested_state)

    # Read back
    loaded_state = state_mgr.read()

    # Property: Nested structure preserved
    assert loaded_state == nested_state


# Property 8: Lock File Cleanup
@given(state=state_dict_strategy)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_8_lock_file_cleanup(state: dict[str, Any], tmp_path: Path) -> None:
    """
    Property 8: Lock File Cleanup

    For any state operation, the lock file should exist during the
    operation but the lock should be released after completion.

    **Validates: Requirements 1.3**
    """
    state_file = tmp_path / ".build-state.json"
    state_mgr = StateManager(state_file)

    # Write state
    state_mgr.write(state)

    # Property: Lock file exists (created during operation)
    assert state_mgr.lock_file.exists()

    # Property: Can acquire lock again (lock was released)
    with state_mgr.lock():
        pass  # Lock acquired successfully

    # Read state
    loaded = state_mgr.read()

    # Property: Can still acquire lock after read
    with state_mgr.lock():
        pass


# Property 9: Corruption Detection
@given(
    corruption_type=st.sampled_from(
        [
            "invalid_json",
            "json_array",
            "empty_file",
            "partial_json",
        ]
    )
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_9_corruption_detection(corruption_type: str, tmp_path: Path) -> None:
    """
    Property 9: Corruption Detection

    For any type of state file corruption, reading should raise
    StateError with a helpful message, never return invalid data.

    **Validates: Requirements 1.3**
    """
    state_file = tmp_path / ".build-state.json"
    state_mgr = StateManager(state_file)

    # Create corrupted state based on type
    state_file.parent.mkdir(parents=True, exist_ok=True)

    if corruption_type == "invalid_json":
        state_file.write_text("{ invalid json }")
    elif corruption_type == "json_array":
        state_file.write_text('["array", "not", "object"]')
    elif corruption_type == "empty_file":
        state_file.write_text("")
    elif corruption_type == "partial_json":
        state_file.write_text('{"key": "value"')

    # Property: Reading corrupted state raises StateError
    with pytest.raises(StateError):
        state_mgr.read()


# Property 10: Multiple Sequential Updates
@given(
    states=st.lists(
        state_dict_strategy,
        min_size=2,
        max_size=10,
    )
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_property_10_multiple_sequential_updates(
    states: list[dict[str, Any]], tmp_path: Path
) -> None:
    """
    Property 10: Multiple Sequential Updates

    For any sequence of state updates, each write should preserve
    the previous state in backup, and the final state should match
    the last write.

    **Validates: Requirements 1.3**
    """
    state_file = tmp_path / ".build-state.json"
    backup_file = state_file.with_suffix(".backup")
    state_mgr = StateManager(state_file)

    # Write states sequentially
    for state in states:
        state_mgr.write(state)

    # Property: Final state matches last write
    final_state = state_mgr.read()
    assert final_state == states[-1]

    # Property: Backup contains second-to-last state
    if len(states) >= 2:
        backup_data = json.loads(backup_file.read_text())
        assert backup_data == states[-2]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
