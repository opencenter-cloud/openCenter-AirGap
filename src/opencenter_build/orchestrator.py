"""Build orchestration with checkpoint/resume capability.

This module provides the BuildOrchestrator class that coordinates the
build pipeline execution with state management, error handling, and
automatic checkpoint/resume functionality.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from opencenter_build.config import BuildConfig
from opencenter_build.exceptions import BuildError
from opencenter_build.state import BuildState, StateManager, StepCheckpoint, StepStatus

logger = logging.getLogger(__name__)


@dataclass
class BuildResult:
    """Result of build execution.

    Attributes:
        success: Whether build completed successfully
        build_id: Unique build identifier
        duration_seconds: Total build duration in seconds
        package_path: Path to created Zarf package (if successful)
        manifest_path: Path to artifact manifest (if successful)
        error: Error message if build failed
        completed_steps: Number of steps completed
        total_steps: Total number of steps
    """

    success: bool
    build_id: str
    duration_seconds: float
    package_path: Path | None = None
    manifest_path: Path | None = None
    error: str | None = None
    completed_steps: int = 0
    total_steps: int = 0

    def summary(self) -> str:
        """Generate human-readable summary.

        Returns:
            Multi-line summary string
        """
        lines = [
            f"Build ID: {self.build_id}",
            f"Status: {'SUCCESS' if self.success else 'FAILED'}",
            f"Duration: {self.duration_seconds:.1f}s",
            f"Steps: {self.completed_steps}/{self.total_steps}",
        ]

        if self.package_path:
            lines.append(f"Package: {self.package_path}")
        if self.manifest_path:
            lines.append(f"Manifest: {self.manifest_path}")
        if self.error:
            lines.append(f"Error: {self.error}")

        return "\n".join(lines)


class BuildOrchestrator:
    """Orchestrate build pipeline with state management.

    Coordinates execution of build steps with automatic checkpointing,
    resume capability, and rollback on failure.

    Attributes:
        config: Build configuration
        state_mgr: State manager for persistence
        clean: Whether to start clean build (ignore checkpoints)
        steps: List of step names in execution order
        step_handlers: Dictionary mapping step names to handler functions
    """

    def __init__(
        self,
        config: BuildConfig,
        state_mgr: StateManager,
        clean: bool = False,
    ):
        """Initialize build orchestrator.

        Args:
            config: Build configuration
            state_mgr: State manager for checkpoint persistence
            clean: If True, ignore existing checkpoints and start fresh
        """
        self.config = config
        self.state_mgr = state_mgr
        self.clean = clean

        # Define build steps in execution order
        self.steps = [
            "scan_repositories",
            "collect_helm_charts",
            "generate_kubespray_lists",
            "mirror_terraform_providers",
            "organize_assets",
            "generate_zarf_yaml",
            "create_zarf_package",
            "generate_manifest",
        ]

        # Step handler registry
        self.step_handlers: dict[str, Callable[[], dict[str, str]]] = {}

    def register_step_handler(self, step_name: str, handler: Callable[[], dict[str, str]]) -> None:
        """Register handler function for a build step.

        Args:
            step_name: Name of step
            handler: Function that executes step and returns artifact paths

        Example:
            >>> orchestrator = BuildOrchestrator(config, state_mgr)
            >>> def scan_handler():
            ...     # Scan repositories
            ...     return {"images": "config/all-images.txt"}
            >>> orchestrator.register_step_handler("scan_repositories", scan_handler)
        """
        self.step_handlers[step_name] = handler

    def execute(self, resume: bool = True) -> BuildResult:
        """Execute build pipeline with checkpoint/resume.

        Args:
            resume: If True, resume from last checkpoint (unless clean=True)

        Returns:
            BuildResult with execution details

        Raises:
            BuildError: If build fails and cannot be recovered
        """
        start_time = datetime.now()

        # Initialize or load build state
        if self.clean or not resume:
            build_state = self._initialize_state()
        else:
            build_state = self._load_or_initialize_state()

        # Configure build-specific log file
        self._setup_build_logging(build_state.build_id)

        # Find resume point
        start_index = 0
        if resume and not self.clean:
            start_index = self.state_mgr.find_resume_point(build_state)

        # Execute steps
        completed_steps = 0
        last_error: str | None = None

        try:
            for i in range(start_index, len(self.steps)):
                step_name = self.steps[i]
                step = build_state.steps[i]

                # Skip completed steps
                if step.status == StepStatus.COMPLETED:
                    completed_steps += 1
                    continue

                # Execute step
                try:
                    artifacts = self._execute_step(step_name, step)
                    completed_steps += 1

                    # Update step as completed
                    step.status = StepStatus.COMPLETED
                    step.end_time = datetime.now().isoformat()
                    step.artifacts = artifacts
                    self.state_mgr.update_step(step_name, step)

                except Exception as exc:
                    # Mark step as failed
                    step.status = StepStatus.FAILED
                    step.end_time = datetime.now().isoformat()
                    step.error = str(exc)
                    self.state_mgr.update_step(step_name, step)

                    # Attempt rollback
                    self._rollback_step(step_name)

                    last_error = f"Step '{step_name}' failed: {exc}"
                    raise BuildError(last_error) from exc

        except BuildError:
            # Build failed
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return BuildResult(
                success=False,
                build_id=build_state.build_id,
                duration_seconds=duration,
                error=last_error,
                completed_steps=completed_steps,
                total_steps=len(self.steps),
            )

        # Build succeeded
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Extract artifact paths from final steps
        package_path = None
        manifest_path = None

        for step in build_state.steps:
            if step.name == "create_zarf_package" and step.artifacts:
                package_path = Path(step.artifacts.get("package", ""))
            if step.name == "generate_manifest" and step.artifacts:
                manifest_path = Path(step.artifacts.get("manifest", ""))

        return BuildResult(
            success=True,
            build_id=build_state.build_id,
            duration_seconds=duration,
            package_path=package_path if package_path and package_path.exists() else None,
            manifest_path=manifest_path if manifest_path and manifest_path.exists() else None,
            completed_steps=completed_steps,
            total_steps=len(self.steps),
        )

    def _initialize_state(self) -> BuildState:
        """Initialize new build state.

        Returns:
            New BuildState with all steps pending
        """
        build_id = str(uuid.uuid4())
        start_time = datetime.now().isoformat()

        steps = [
            StepCheckpoint(name=step_name, status=StepStatus.PENDING) for step_name in self.steps
        ]

        state = BuildState(
            build_id=build_id,
            start_time=start_time,
            steps=steps,
            config_hash=self.config.hash(),
        )

        self.state_mgr.write_build_state(state)
        return state

    def _load_or_initialize_state(self) -> BuildState:
        """Load existing state or initialize new one.

        Returns:
            BuildState instance
        """
        existing_state = self.state_mgr.read_build_state()

        if existing_state is None:
            return self._initialize_state()

        # Check if config changed
        current_hash = self.config.hash()
        if existing_state.config_hash != current_hash:
            # Config changed, start fresh
            return self._initialize_state()

        return existing_state

    def _execute_step(self, step_name: str, step: StepCheckpoint) -> dict[str, str]:
        """Execute single build step with checkpoint.

        Args:
            step_name: Name of step to execute
            step: Step checkpoint to update

        Returns:
            Dictionary of artifact paths produced by step

        Raises:
            BuildError: If step handler not registered or execution fails
        """
        if step_name not in self.step_handlers:
            raise BuildError(f"No handler registered for step: {step_name}")

        # Mark step as running
        step.status = StepStatus.RUNNING
        step.start_time = datetime.now().isoformat()
        self.state_mgr.update_step(step_name, step)

        try:
            # Execute step handler
            handler = self.step_handlers[step_name]
            artifacts = handler()

            if not isinstance(artifacts, dict):
                raise BuildError(f"Step handler must return dict, got {type(artifacts).__name__}")

            return artifacts

        except Exception as exc:
            raise BuildError(f"Step execution failed: {exc}") from exc

    def _rollback_step(self, step_name: str) -> None:
        """Rollback failed step artifacts.

        Attempts to clean up any partial artifacts created by failed step.
        This is a best-effort operation and does not raise exceptions.

        Args:
            step_name: Name of step to rollback
        """
        import logging
        import shutil

        logger = logging.getLogger(__name__)

        # Define rollback actions per step
        rollback_actions: dict[str, Any] = {
            "scan_repositories": lambda: self._cleanup_file(Path("config/all-images.txt")),
            "collect_kubespray_offline": lambda: self._cleanup_directory(
                Path("build/kubespray-offline/outputs")
            ),
            "mirror_terraform_providers": lambda: self._cleanup_directory(
                Path("assets/terraform-mirror")
            ),
            "organize_assets": lambda: self._cleanup_directory(Path("assets")),
            "create_zarf_package": lambda: self._cleanup_file(
                Path("dist/zarf-package-opencenter-airgap.tar.zst")
            ),
            "generate_manifest": lambda: self._cleanup_file(Path("dist/artifact-manifest.json")),
        }

        # Execute rollback if defined
        if step_name in rollback_actions:
            try:
                rollback_actions[step_name]()
                logger.info(f"Rolled back artifacts for step: {step_name}")
            except Exception as exc:
                logger.warning(f"Rollback failed for step {step_name}: {exc}")

    def _setup_build_logging(self, build_id: str) -> None:
        """Configure file handler for build session logs.

        Args:
            build_id: Build session identifier
        """
        import logging as logging_module

        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        log_file = log_dir / f"{build_id}.log"

        # Create file handler
        file_handler = logging_module.FileHandler(log_file, mode="a", encoding="utf-8")
        file_handler.setLevel(logging_module.DEBUG)

        # Format: timestamp - level - module - message
        formatter = logging_module.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)

        # Add handler to root logger (captures all module logs)
        root_logger = logging_module.getLogger()
        root_logger.addHandler(file_handler)

        logger.info(f"Build session started: {build_id}")
        logger.info(f"Logging to: {log_file}")

    def _cleanup_file(self, file_path: Path) -> None:
        """Remove file if it exists.

        Args:
            file_path: Path to file to remove
        """
        if file_path.exists() and file_path.is_file():
            file_path.unlink()

    def _cleanup_directory(self, dir_path: Path) -> None:
        """Remove directory and contents if it exists.

        Args:
            dir_path: Path to directory to remove
        """
        import shutil

        if dir_path.exists() and dir_path.is_dir():
            shutil.rmtree(dir_path)
