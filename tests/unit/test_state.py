#!/usr/bin/env python3
"""
Unit Tests: StateManager - Atomic State Management

Tests for atomic state file operations with file locking, backup,
and recovery capabilities.

Validates: Requirements 1.3 (Atomic State Management)
"""

import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from opencenter_build.exceptions import StateError
from opencenter_build.state import StateManager


class TestStateManagerBasics:
    """Test basic StateManager operations."""

    def test_init_creates_state_manager(self, tmp_path: Path) -> None:
        """Test StateManager initialization."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        assert state_mgr.state_file == state_file
        assert state_mgr.lock_file == state_file.with_suffix(".lock")

    def test_read_nonexistent_file_returns_empty_dict(self, tmp_path: Path) -> None:
        """Test reading state when file doesn't exist returns empty dict."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        state = state_mgr.read()

        assert state == {}
        assert isinstance(state, dict)

    def test_write_creates_state_file(self, tmp_path: Path) -> None:
        """Test writing state creates the file."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        test_state = {"build_id": "test-123", "step": "collect"}
        state_mgr.write(test_state)

        assert state_file.exists()
        assert state_file.is_file()

    def test_write_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test writing state creates parent directories if needed."""
        state_file = tmp_path / "nested" / "dir" / ".build-state.json"
        state_mgr = StateManager(state_file)

        test_state = {"build_id": "test-123"}
        state_mgr.write(test_state)

        assert state_file.exists()
        assert state_file.parent.exists()

    def test_read_write_round_trip(self, tmp_path: Path) -> None:
        """Test writing and reading state preserves data."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        original_state = {
            "build_id": "build-20260127-1430",
            "started_at": "2026-01-27T14:30:00Z",
            "kubespray_collected": True,
            "assets_organized": False,
            "last_step": "collect_kubespray",
            "checkpoints": [
                {
                    "step": "collect_kubespray",
                    "timestamp": "2026-01-27T14:35:00Z",
                    "success": True,
                }
            ],
        }

        state_mgr.write(original_state)
        loaded_state = state_mgr.read()

        assert loaded_state == original_state
        assert loaded_state["build_id"] == "build-20260127-1430"
        assert loaded_state["kubespray_collected"] is True
        assert len(loaded_state["checkpoints"]) == 1


class TestStateManagerAtomicity:
    """Test atomic write operations."""

    def test_write_uses_temp_file_and_rename(self, tmp_path: Path) -> None:
        """Test atomic write uses temp file + rename pattern."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        test_state = {"build_id": "test-123"}
        state_mgr.write(test_state)

        # Temp file should not exist after write
        temp_file = state_file.with_suffix(".tmp")
        assert not temp_file.exists()

        # State file should exist
        assert state_file.exists()

    def test_write_creates_backup_before_overwrite(self, tmp_path: Path) -> None:
        """Test writing state creates backup of existing state."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        # Write initial state
        initial_state = {"build_id": "initial", "step": 1}
        state_mgr.write(initial_state)

        # Write updated state
        updated_state = {"build_id": "updated", "step": 2}
        state_mgr.write(updated_state)

        # Backup should exist with initial state
        backup_file = state_file.with_suffix(".backup")
        assert backup_file.exists()

        backup_data = json.loads(backup_file.read_text())
        assert backup_data["build_id"] == "initial"
        assert backup_data["step"] == 1

    def test_write_no_backup_for_first_write(self, tmp_path: Path) -> None:
        """Test first write doesn't create backup (no existing state)."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        test_state = {"build_id": "test-123"}
        state_mgr.write(test_state)

        backup_file = state_file.with_suffix(".backup")
        assert not backup_file.exists()

    def test_write_preserves_json_formatting(self, tmp_path: Path) -> None:
        """Test written state is properly formatted JSON."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        test_state = {"build_id": "test-123", "nested": {"key": "value"}}
        state_mgr.write(test_state)

        # Read raw file content
        content = state_file.read_text()

        # Should be valid JSON
        parsed = json.loads(content)
        assert parsed == test_state

        # Should be indented (pretty-printed)
        assert "\n" in content
        assert "  " in content  # 2-space indent


class TestStateManagerLocking:
    """Test file locking for concurrent access."""

    def test_lock_creates_lock_file(self, tmp_path: Path) -> None:
        """Test lock context manager creates lock file."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        with state_mgr.lock():
            assert state_mgr.lock_file.exists()

    def test_lock_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test lock creates parent directories if needed."""
        state_file = tmp_path / "nested" / ".build-state.json"
        state_mgr = StateManager(state_file)

        with state_mgr.lock():
            assert state_mgr.lock_file.parent.exists()

    def test_concurrent_writes_no_corruption(self, tmp_path: Path) -> None:
        """Test concurrent writes don't corrupt state file (valid JSON maintained)."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        # Initialize state
        state_mgr.write({"counter": 0})

        results: list[Exception | None] = []
        num_threads = 5
        writes_per_thread = 10

        def write_state(thread_id: int) -> None:
            """Write state multiple times."""
            try:
                for i in range(writes_per_thread):
                    # Each thread writes its own unique state
                    state = {
                        "thread_id": thread_id,
                        "write_number": i,
                        "timestamp": time.time(),
                    }
                    state_mgr.write(state)
                    time.sleep(0.001)  # Small delay to increase contention
                results.append(None)
            except Exception as e:
                results.append(e)

        # Run concurrent writes
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=write_state, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Check for exceptions
        exceptions = [r for r in results if r is not None]
        assert len(exceptions) == 0, f"Threads raised exceptions: {exceptions}"

        # Property: State file is valid JSON (no corruption)
        final_state = state_mgr.read()
        assert isinstance(final_state, dict)

        # Property: State contains one of the written states
        assert "thread_id" in final_state
        assert 0 <= final_state["thread_id"] < num_threads

        # Property: File is valid JSON
        file_content = state_file.read_text()
        parsed = json.loads(file_content)
        assert isinstance(parsed, dict)


class TestStateManagerValidation:
    """Test state validation."""

    def test_read_validates_json_structure(self, tmp_path: Path) -> None:
        """Test reading validates state is a JSON object."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        # Write invalid JSON structure (array instead of object)
        state_file.write_text('["not", "an", "object"]')

        with pytest.raises(StateError) as exc_info:
            state_mgr.read()

        assert "must contain a JSON object" in str(exc_info.value)

    def test_read_corrupted_json_raises_state_error(self, tmp_path: Path) -> None:
        """Test reading corrupted JSON raises StateError."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        # Write invalid JSON
        state_file.write_text("{ invalid json content }")

        with pytest.raises(StateError) as exc_info:
            state_mgr.read()

        assert "State file corrupted" in str(exc_info.value)
        assert "Try recovery" in str(exc_info.value)

    def test_read_error_includes_file_path(self, tmp_path: Path) -> None:
        """Test error message includes file path for debugging."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        state_file.write_text("{ invalid }")

        with pytest.raises(StateError) as exc_info:
            state_mgr.read()

        assert str(state_file) in str(exc_info.value)

    def test_write_validates_dict_type(self, tmp_path: Path) -> None:
        """Test writing validates state is a dictionary."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        # Write list (valid JSON but wrong type for state)
        # With transaction support, validation happens during write
        with pytest.raises(StateError) as exc_info:
            state_mgr.write(["not", "a", "dict"])  # type: ignore

        assert "not a valid dictionary" in str(exc_info.value).lower()


class TestStateManagerRecovery:
    """Test state recovery from backup."""

    def test_recover_restores_from_backup(self, tmp_path: Path) -> None:
        """Test recovery restores state from backup."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        # Write initial state
        initial_state = {"build_id": "initial", "step": 1}
        state_mgr.write(initial_state)

        # Write updated state (creates backup)
        updated_state = {"build_id": "updated", "step": 2}
        state_mgr.write(updated_state)

        # Corrupt current state
        state_file.write_text("{ corrupted }")

        # Recover from backup
        success = state_mgr.recover()

        assert success is True
        assert state_file.exists()

        # Verify recovered state is the backup (initial state)
        recovered_state = state_mgr.read()
        assert recovered_state["build_id"] == "initial"
        assert recovered_state["step"] == 1

    def test_recover_returns_false_when_no_backup(self, tmp_path: Path) -> None:
        """Test recovery returns False when no backup exists."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        success = state_mgr.recover()

        assert success is False

    def test_recover_returns_false_when_backup_corrupted(self, tmp_path: Path) -> None:
        """Test recovery returns False when backup is also corrupted."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        # Create corrupted backup
        backup_file = state_file.with_suffix(".backup")
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        backup_file.write_text("{ corrupted backup }")

        success = state_mgr.recover()

        assert success is False

    def test_recover_validates_backup_before_restore(self, tmp_path: Path) -> None:
        """Test recovery validates backup is valid JSON before restoring."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        # Write valid state
        state_mgr.write({"build_id": "test"})

        # Create corrupted backup
        backup_file = state_file.with_suffix(".backup")
        backup_file.write_text("{ invalid }")

        # Corrupt current state
        state_file.write_text("{ also invalid }")

        # Recovery should fail (backup invalid)
        success = state_mgr.recover()

        assert success is False

    def test_recover_replaces_corrupted_state(self, tmp_path: Path) -> None:
        """Test recovery replaces corrupted state file."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        # Write initial state
        initial_state = {"build_id": "backup-state"}
        state_mgr.write(initial_state)

        # Create backup manually
        backup_file = state_file.with_suffix(".backup")
        backup_file.write_text(json.dumps(initial_state))

        # Corrupt current state
        state_file.write_text("{ corrupted }")

        # Recover
        success = state_mgr.recover()

        assert success is True

        # State file should now contain backup data
        recovered = json.loads(state_file.read_text())
        assert recovered["build_id"] == "backup-state"


class TestStateManagerEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_state_dict(self, tmp_path: Path) -> None:
        """Test writing and reading empty state dict."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        state_mgr.write({})
        loaded = state_mgr.read()

        assert loaded == {}

    def test_nested_state_structure(self, tmp_path: Path) -> None:
        """Test deeply nested state structure."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        nested_state = {
            "level1": {
                "level2": {
                    "level3": {"level4": {"value": "deep"}},
                    "list": [1, 2, 3],
                },
                "bool": True,
            },
            "null_value": None,
        }

        state_mgr.write(nested_state)
        loaded = state_mgr.read()

        assert loaded == nested_state
        assert loaded["level1"]["level2"]["level3"]["level4"]["value"] == "deep"
        assert loaded["level1"]["level2"]["list"] == [1, 2, 3]
        assert loaded["null_value"] is None

    def test_unicode_in_state(self, tmp_path: Path) -> None:
        """Test state with unicode characters."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        unicode_state = {
            "message": "Hello 世界 🌍",
            "emoji": "✅ ❌ ⚠️",
            "special": "café résumé naïve",
        }

        state_mgr.write(unicode_state)
        loaded = state_mgr.read()

        assert loaded == unicode_state
        assert loaded["message"] == "Hello 世界 🌍"

    def test_large_state_dict(self, tmp_path: Path) -> None:
        """Test handling large state dictionary."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        # Create large state with many keys
        large_state = {f"key_{i}": f"value_{i}" for i in range(1000)}
        large_state["nested"] = {f"nested_{i}": i for i in range(1000)}

        state_mgr.write(large_state)
        loaded = state_mgr.read()

        assert len(loaded) == 1001  # 1000 keys + 1 nested
        assert loaded["key_500"] == "value_500"
        assert loaded["nested"]["nested_500"] == 500

    def test_special_characters_in_values(self, tmp_path: Path) -> None:
        """Test state with special characters in values."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        special_state = {
            "quotes": 'He said "hello"',
            "backslash": "path\\to\\file",
            "newline": "line1\nline2",
            "tab": "col1\tcol2",
        }

        state_mgr.write(special_state)
        loaded = state_mgr.read()

        assert loaded == special_state
        assert loaded["quotes"] == 'He said "hello"'
        assert loaded["newline"] == "line1\nline2"


class TestStateManagerIntegration:
    """Integration tests for realistic usage patterns."""

    def test_build_workflow_simulation(self, tmp_path: Path) -> None:
        """Test simulating a build workflow with state updates."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        # Initialize build
        state = {"build_id": "build-001", "steps": {}}
        state_mgr.write(state)

        # Step 1: Collect kubespray
        state = state_mgr.read()
        state["steps"]["collect_kubespray"] = {"status": "completed", "duration": 120.5}
        state_mgr.write(state)

        # Step 2: Organize assets
        state = state_mgr.read()
        state["steps"]["organize_assets"] = {"status": "completed", "duration": 45.2}
        state_mgr.write(state)

        # Step 3: Generate zarf.yaml
        state = state_mgr.read()
        state["steps"]["generate_zarf"] = {"status": "completed", "duration": 5.1}
        state_mgr.write(state)

        # Verify final state
        final_state = state_mgr.read()
        assert len(final_state["steps"]) == 3
        assert final_state["steps"]["collect_kubespray"]["status"] == "completed"
        assert final_state["steps"]["organize_assets"]["status"] == "completed"
        assert final_state["steps"]["generate_zarf"]["status"] == "completed"

    def test_resume_after_failure(self, tmp_path: Path) -> None:
        """Test resuming build after failure using state."""
        state_file = tmp_path / ".build-state.json"
        state_mgr = StateManager(state_file)

        # Initial build with partial completion
        state = {
            "build_id": "build-002",
            "steps": {
                "step1": {"status": "completed"},
                "step2": {"status": "completed"},
                "step3": {"status": "failed", "error": "Network timeout"},
            },
        }
        state_mgr.write(state)

        # Resume: read state and skip completed steps
        resumed_state = state_mgr.read()
        completed_steps = [
            name for name, info in resumed_state["steps"].items() if info["status"] == "completed"
        ]

        assert "step1" in completed_steps
        assert "step2" in completed_steps
        assert "step3" not in completed_steps

        # Retry failed step
        resumed_state["steps"]["step3"] = {"status": "completed"}
        state_mgr.write(resumed_state)

        # Verify recovery
        final_state = state_mgr.read()
        assert final_state["steps"]["step3"]["status"] == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
