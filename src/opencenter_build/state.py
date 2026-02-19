"""Atomic state management with file locking and recovery.

This module provides thread-safe and process-safe state file operations
with automatic backup and recovery capabilities.
"""

import fcntl
import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterator

from opencenter_build.exceptions import StateError
from opencenter_build.transaction import transactional_operation


class StepStatus(Enum):
    """Build step execution status.

    Attributes:
        PENDING: Step has not started
        RUNNING: Step is currently executing
        COMPLETED: Step completed successfully
        FAILED: Step failed with error
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class StepCheckpoint:
    """Checkpoint for a single build step.

    Attributes:
        name: Step name (e.g., "scan_repositories")
        status: Current step status
        start_time: When step started (ISO 8601 format)
        end_time: When step completed or failed (ISO 8601 format)
        error: Error message if step failed
        artifacts: Dictionary of artifact paths produced by step
    """

    name: str
    status: StepStatus
    start_time: str | None = None
    end_time: str | None = None
    error: str | None = None
    artifacts: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert checkpoint to dictionary for JSON serialization.

        Returns:
            Dictionary representation of checkpoint
        """
        return {
            "name": self.name,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "error": self.error,
            "artifacts": self.artifacts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StepCheckpoint":
        """Create checkpoint from dictionary.

        Args:
            data: Dictionary with checkpoint data

        Returns:
            StepCheckpoint instance
        """
        return cls(
            name=data["name"],
            status=StepStatus(data["status"]),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            error=data.get("error"),
            artifacts=data.get("artifacts"),
        )


@dataclass
class BuildState:
    """Complete build state with step checkpoints.

    Attributes:
        build_id: Unique build identifier
        start_time: When build started (ISO 8601 format)
        steps: List of step checkpoints
        config_hash: SHA256 hash of configuration
    """

    build_id: str
    start_time: str
    steps: list[StepCheckpoint]
    config_hash: str

    def to_dict(self) -> dict[str, Any]:
        """Convert build state to dictionary for JSON serialization.

        Returns:
            Dictionary representation of build state
        """
        return {
            "build_id": self.build_id,
            "start_time": self.start_time,
            "steps": [step.to_dict() for step in self.steps],
            "config_hash": self.config_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BuildState":
        """Create build state from dictionary.

        Args:
            data: Dictionary with build state data

        Returns:
            BuildState instance
        """
        return cls(
            build_id=data["build_id"],
            start_time=data["start_time"],
            steps=[StepCheckpoint.from_dict(step) for step in data["steps"]],
            config_hash=data["config_hash"],
        )


@dataclass
class FileMetadata:
    """Metadata for a single file artifact.

    Attributes:
        path: File path relative to build directory
        size: File size in bytes
        sha256: SHA256 checksum
        mtime: Last modification time (ISO 8601 format)
    """

    path: str
    size: int
    sha256: str
    mtime: str

    @classmethod
    def from_path(cls, path: Path) -> "FileMetadata":
        """Calculate metadata from file.

        Args:
            path: Path to file

        Returns:
            FileMetadata instance

        Raises:
            FileNotFoundError: If file does not exist
        """
        import hashlib

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        stat = path.stat()
        sha256_hash = hashlib.sha256()

        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return cls(
            path=str(path),
            size=stat.st_size,
            sha256=sha256_hash.hexdigest(),
            mtime=datetime.fromtimestamp(stat.st_mtime).isoformat(),
        )


@dataclass
class ImageMetadata:
    """Metadata for container image.

    Attributes:
        registry: Registry hostname (e.g., "docker.io")
        repository: Repository path (e.g., "library/nginx")
        tag: Image tag (e.g., "1.29.2")
        digest: Image digest (SHA256, optional)
        size: Image size in bytes (optional)
    """

    registry: str
    repository: str
    tag: str
    digest: str | None = None
    size: int | None = None

    @property
    def full_name(self) -> str:
        """Return full image name.

        Returns:
            Full image name in format registry/repository:tag

        Example:
            >>> img = ImageMetadata("docker.io", "library/nginx", "1.29.2")
            >>> print(img.full_name)
            docker.io/library/nginx:1.29.2
        """
        return f"{self.registry}/{self.repository}:{self.tag}"


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
                    def restore_backup() -> None:
                        backup.replace(self.state_file)

                    tx.add_rollback(restore_backup)

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

    def read_build_state(self) -> BuildState | None:
        """Read build state from disk.

        Returns:
            BuildState instance or None if no state exists

        Raises:
            StateError: If state file is corrupted or invalid
        """
        state_dict = self.read()
        if not state_dict:
            return None

        try:
            return BuildState.from_dict(state_dict)
        except (KeyError, ValueError) as exc:
            raise StateError(f"Invalid build state format: {exc}") from exc

    def write_build_state(self, state: BuildState) -> None:
        """Write build state to disk atomically.

        Args:
            state: BuildState instance to persist

        Raises:
            StateError: If write operation fails
        """
        self.write(state.to_dict())

    def update_step(self, step_name: str, checkpoint: StepCheckpoint) -> None:
        """Update single step checkpoint in existing state.

        Reads current state, updates the specified step, and writes back
        atomically. Creates new state if none exists.

        Args:
            step_name: Name of step to update
            checkpoint: New checkpoint data for step

        Raises:
            StateError: If state cannot be read or written
        """
        state = self.read_build_state()
        if state is None:
            raise StateError("Cannot update step: no build state exists")

        # Find and update step
        step_found = False
        for i, step in enumerate(state.steps):
            if step.name == step_name:
                state.steps[i] = checkpoint
                step_found = True
                break

        if not step_found:
            raise StateError(f"Step not found in state: {step_name}")

        self.write_build_state(state)

    def find_resume_point(self, state: BuildState) -> int:
        """Find first incomplete step index for resume.

        Scans step list to find first step that is not COMPLETED.
        Returns index of first PENDING, RUNNING, or FAILED step.

        Args:
            state: BuildState to analyze

        Returns:
            Index of first incomplete step, or len(steps) if all complete

        Example:
            >>> state = BuildState(...)
            >>> state_mgr = StateManager(Path("build/state.json"))
            >>> resume_idx = state_mgr.find_resume_point(state)
            >>> if resume_idx < len(state.steps):
            ...     print(f"Resume from: {state.steps[resume_idx].name}")
        """
        for i, step in enumerate(state.steps):
            if step.status != StepStatus.COMPLETED:
                return i
        return len(state.steps)

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
