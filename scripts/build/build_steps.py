"""Build step definitions and configuration.

This module defines all build steps with their dependencies, worker types,
and validation logic for the resumable build system.
"""

from dataclasses import dataclass
from typing import List, Optional, Callable
from enum import Enum
from pathlib import Path


class WorkerType(Enum):
    """Type of worker that executes a build step."""
    BASH = "bash"
    PYTHON = "python"


@dataclass
class StepDefinition:
    """Definition of a build step.
    
    Attributes:
        name: Unique identifier for the step
        description: Human-readable description
        dependencies: List of step names that must complete before this step
        worker_type: Type of worker (BASH or PYTHON)
        worker_path: Path to Bash script (for BASH workers)
        worker_func: Python function reference (for PYTHON workers)
        validation_func: Optional validation function to run after step completion
        optional: Whether the step can be skipped
        timeout_seconds: Maximum execution time in seconds
        input_files: List of input file paths to check for changes (relative to project root)
        output_files: List of output file/directory paths to check for existence (relative to project root)
    """
    name: str
    description: str
    dependencies: List[str]
    worker_type: WorkerType
    worker_path: Optional[str] = None
    worker_func: Optional[Callable] = None
    validation_func: Optional[Callable] = None
    optional: bool = False
    timeout_seconds: Optional[int] = None
    input_files: Optional[List[str]] = None
    output_files: Optional[List[str]] = None

    def __post_init__(self):
        """Validate step definition after initialization."""
        # Ensure worker reference is provided based on type
        if self.worker_type == WorkerType.BASH and not self.worker_path:
            raise ValueError(f"Step '{self.name}': BASH worker requires worker_path")
        if self.worker_type == WorkerType.PYTHON and not self.worker_func:
            raise ValueError(f"Step '{self.name}': PYTHON worker requires worker_func")


# Import worker functions from workers module
try:
    from workers.prerequisites import check_prerequisites_worker
    from workers.python_env import setup_python_env_worker, validate_python_env
    from workers.github_token import check_github_token_worker
    from workers.merge_images import merge_opencenter_images_worker
    from workers.validation import (
        validate_versions_worker,
        validate_zarf_yaml_worker,
        validate_build_outputs_worker
    )
    from workers.checksums import generate_checksums_worker
except ImportError:
    # Fallback to placeholder functions if workers not yet implemented
    def check_prerequisites_worker(project_root: Path) -> bool:
        """Check build prerequisites."""
        raise NotImplementedError("Worker not yet implemented")

    def setup_python_env_worker(project_root: Path) -> bool:
        """Setup Python virtual environment."""
        raise NotImplementedError("Worker not yet implemented")

    def validate_python_env(project_root: Path) -> bool:
        """Validate Python environment."""
        raise NotImplementedError("Worker not yet implemented")

    def check_github_token_worker(project_root: Path) -> bool:
        """Check GitHub token."""
        raise NotImplementedError("Worker not yet implemented")

    def merge_opencenter_images_worker(project_root: Path) -> bool:
        """Merge openCenter images with kubespray-offline."""
        raise NotImplementedError("Worker not yet implemented")

    def validate_versions_worker(project_root: Path) -> bool:
        """Validate version pinning."""
        raise NotImplementedError("Worker not yet implemented")

    def validate_zarf_yaml_worker(project_root: Path) -> bool:
        """Validate zarf.yaml syntax."""
        raise NotImplementedError("Worker not yet implemented")

    def generate_checksums_worker(project_root: Path) -> bool:
        """Generate checksums for Zarf package."""
        raise NotImplementedError("Worker not yet implemented")

    def validate_build_outputs_worker(project_root: Path) -> bool:
        """Validate final build outputs."""
        raise NotImplementedError("Worker not yet implemented")


# Step registry - defines all 15 build steps with dependencies
STEPS: List[StepDefinition] = [
    StepDefinition(
        name="check_prerequisites",
        description="Check build prerequisites (Python, container runtime, git, jq, zarf, disk space)",
        dependencies=[],
        worker_type=WorkerType.PYTHON,
        worker_func=check_prerequisites_worker,
        timeout_seconds=30
    ),
    
    StepDefinition(
        name="setup_python_env",
        description="Setup Python virtual environment and install dependencies",
        dependencies=["check_prerequisites"],
        worker_type=WorkerType.PYTHON,
        worker_func=setup_python_env_worker,
        validation_func=validate_python_env,
        timeout_seconds=120
    ),
    
    StepDefinition(
        name="check_github_token",
        description="Verify GITHUB_TOKEN environment variable",
        dependencies=["setup_python_env"],
        worker_type=WorkerType.PYTHON,
        worker_func=check_github_token_worker,
        timeout_seconds=10
    ),
    
    StepDefinition(
        name="collect_opencenter_assets",
        description="Collect openCenter platform assets (images, configs)",
        dependencies=["check_github_token"],
        worker_type=WorkerType.BASH,
        worker_path="scripts/build/collect_opencenter_assets.sh",
        timeout_seconds=3600  # 1 hour for image downloads
    ),
    
    StepDefinition(
        name="clone_kubespray_offline",
        description="Clone or update kubespray-offline repository",
        dependencies=["setup_python_env"],
        worker_type=WorkerType.BASH,
        worker_path="scripts/build/collect_kubespray_offline.sh",
        timeout_seconds=300
    ),
    
    StepDefinition(
        name="merge_opencenter_images",
        description="Merge openCenter images with kubespray-offline image list",
        dependencies=["clone_kubespray_offline"],
        worker_type=WorkerType.PYTHON,
        worker_func=merge_opencenter_images_worker,
        timeout_seconds=30
    ),
    
    StepDefinition(
        name="run_kubespray_offline",
        description="Execute kubespray-offline download-all.sh to collect K8s assets",
        dependencies=["collect_opencenter_assets", "merge_opencenter_images"],
        worker_type=WorkerType.BASH,
        worker_path="scripts/build/run_kubespray_offline.sh",
        timeout_seconds=7200  # 2 hours for all downloads
    ),
    
    StepDefinition(
        name="organize_assets",
        description="Organize assets for Zarf packaging",
        dependencies=["run_kubespray_offline"],
        worker_type=WorkerType.BASH,
        worker_path="scripts/build/organize_assets_for_zarf.sh",
        timeout_seconds=600
    ),
    
    StepDefinition(
        name="validate_versions",
        description="Validate version pinning in config/versions.env",
        dependencies=["organize_assets"],
        worker_type=WorkerType.PYTHON,
        worker_func=validate_versions_worker,
        timeout_seconds=30
    ),
    
    StepDefinition(
        name="validate_zarf_yaml",
        description="Validate zarf.yaml syntax and structure",
        dependencies=["validate_versions"],
        worker_type=WorkerType.PYTHON,
        worker_func=validate_zarf_yaml_worker,
        timeout_seconds=30
    ),
    
    StepDefinition(
        name="create_zarf_package",
        description="Create Zarf package with all assets",
        dependencies=["validate_zarf_yaml"],
        worker_type=WorkerType.BASH,
        worker_path="scripts/build/create_zarf_package.sh",
        timeout_seconds=3600  # 1 hour for package creation
    ),
    
    StepDefinition(
        name="generate_checksums",
        description="Generate SHA256 and MD5 checksums for Zarf package",
        dependencies=["create_zarf_package"],
        worker_type=WorkerType.PYTHON,
        worker_func=generate_checksums_worker,
        timeout_seconds=300
    ),
    
    StepDefinition(
        name="sign_package",
        description="Sign Zarf package with Cosign (optional)",
        dependencies=["create_zarf_package"],
        worker_type=WorkerType.BASH,
        worker_path="scripts/build/sign_package.sh",
        optional=True,
        timeout_seconds=60
    ),
    
    StepDefinition(
        name="inspect_package",
        description="Generate SBOM and inspect Zarf package",
        dependencies=["create_zarf_package"],
        worker_type=WorkerType.BASH,
        worker_path="scripts/build/inspect_package.sh",
        timeout_seconds=300
    ),
    
    StepDefinition(
        name="validate_build_outputs",
        description="Validate final build outputs and package integrity",
        dependencies=["generate_checksums", "sign_package", "inspect_package"],
        worker_type=WorkerType.PYTHON,
        worker_func=validate_build_outputs_worker,
        timeout_seconds=60
    ),
]


def get_step_by_name(step_name: str) -> Optional[StepDefinition]:
    """Get step definition by name.
    
    Args:
        step_name: Name of the step to retrieve
        
    Returns:
        StepDefinition if found, None otherwise
    """
    for step in STEPS:
        if step.name == step_name:
            return step
    return None


def get_all_step_names() -> List[str]:
    """Get list of all step names.
    
    Returns:
        List of step names in definition order
    """
    return [step.name for step in STEPS]


def validate_step_definitions() -> None:
    """Validate all step definitions.
    
    Raises:
        ValueError: If any step definition is invalid
    """
    step_names = set(get_all_step_names())
    
    # Check for duplicate step names
    if len(step_names) != len(STEPS):
        raise ValueError("Duplicate step names detected")
    
    # Validate dependencies exist
    for step in STEPS:
        for dep in step.dependencies:
            if dep not in step_names:
                raise ValueError(
                    f"Step '{step.name}' has non-existent dependency: '{dep}'"
                )
    
    # Validate worker references
    for step in STEPS:
        if step.worker_type == WorkerType.BASH:
            if not step.worker_path:
                raise ValueError(
                    f"Step '{step.name}' is BASH type but has no worker_path"
                )
        elif step.worker_type == WorkerType.PYTHON:
            if not step.worker_func:
                raise ValueError(
                    f"Step '{step.name}' is PYTHON type but has no worker_func"
                )
