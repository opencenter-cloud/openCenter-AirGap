"""Atomic state management with file locking and recovery.

This module provides thread-safe and process-safe state file operations
with automatic backup and recovery capabilities.
"""

import fcntl
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from opencenter_build.exceptions import StateError
from opencenter_build.transaction import transactional_operation


class StateManager:
    """Manage build state with atomic operations and recovery.

    Provides atomic read/write operations on JSON state files with:
    - Exclusive file locking to prevent concurrent access issues
    - Automatic backup before writes
    - Recovery from corrupted state files
    - Atomic writes using temp file + rename

    Attributes:
        state_file: Path to the state JSON file
        lock_file: Path to the lock file for synchronization
    """

    def __init__(self, state_file: Path) -> None:
        """Initialize state manager.

        Args:
            state_file: Path to state JSON file
        """
        self.state_file = state_file
        self.lock_file = state_file.with_suffix(".lock")

    @contextmanager
    def lock(self) -> Iterator[None]:
        """Acquire exclusive lock on state file.

        Uses fcntl.flock for process-level locking. Blocks until lock
        is acquired.

        Yields:
            None

        Example:
            >>> state_mgr = StateManager(Path("build/.build-state.json"))
            >>> with state_mgr.lock():
            ...     # Perform locked operations
            ...     pass
        """
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.lock_file, "w", encoding="utf-8") as lock_fd:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)

    def read(self) -> dict[str, Any]:
        """Read state atomically.

        Returns empty dict if state file does not exist.

        Returns:
            State dictionary

        Raises:
            StateError: If state file is corrupted or cannot be read
        """
        with self.lock():
            if not self.state_file.exists():
                return {}

            try:
                data = json.loads(self.state_file.read_text())
                if not isinstance(data, dict):
                    raise StateError(f"State file must contain a JSON object, got {type(data)}")
                return data
            except json.JSONDecodeError as exc:
                raise StateError(
                    f"State file corrupted: {self.state_file}\n"
                    f"Try recovery with StateManager.recover()"
                ) from exc

    def write(self, state: dict[str, Any]) -> None:
        """Write state atomically with backup and rollback support.

        Creates backup of existing state before writing. Uses atomic
        rename to ensure state is never partially written. Automatically
        rolls back to previous state if validation fails.

        Args:
            state: State dictionary to write

        Raises:
            StateError: If write operation fails
        """
        with self.lock():
            with transactional_operation() as tx:
                self.state_file.parent.mkdir(parents=True, exist_ok=True)

                # Create backup of existing state
                if self.state_file.exists():
                    backup = self.state_file.with_suffix(".backup")
                    backup.write_bytes(self.state_file.read_bytes())
                    # Register rollback to restore from backup
                    tx.add_rollback(lambda: backup.replace(self.state_file))

                # Atomic write: temp file + rename
                temp_file = self.state_file.with_suffix(".tmp")
                try:
                    temp_file.write_text(json.dumps(state, indent=2))
                    temp_file.replace(self.state_file)

                    # Validate written state
                    written_state = json.loads(self.state_file.read_text())
                    if not isinstance(written_state, dict):
                        raise StateError("Written state is not a valid dictionary")

                except Exception as exc:
                    if temp_file.exists():
                        temp_file.unlink()
                    raise StateError(f"Failed to write state: {exc}") from exc

    def recover(self) -> bool:
        """Recover state from backup if corrupted.

        Attempts to restore state from backup file. Validates backup
        before restoration.

        Returns:
            True if recovery successful, False if no backup or backup invalid

        Example:
            >>> state_mgr = StateManager(Path("build/.build-state.json"))
            >>> if state_mgr.recover():
            ...     print("State recovered from backup")
        """
        backup = self.state_file.with_suffix(".backup")
        if not backup.exists():
            return False

        try:
            # Validate backup is valid JSON
            json.loads(backup.read_text())
            # Restore from backup
            backup.replace(self.state_file)
            return True
        except json.JSONDecodeError:
            return False
