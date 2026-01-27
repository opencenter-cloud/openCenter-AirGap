"""Unit tests for build step definitions.

Tests step validation, dependency graph construction, and step registry.
"""

import sys
from pathlib import Path

# Add scripts/build to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "build"))

import pytest
from build_steps import (
    StepDefinition,
    WorkerType,
    STEPS,
    get_step_by_name,
    get_all_step_names,
    validate_step_definitions
)


def dummy_worker(project_root: Path) -> bool:
    """Dummy worker function for testing."""
    return True


class TestStepDefinition:
    """Tests for StepDefinition dataclass."""
    
    def test_valid_bash_step(self):
        """Test creating a valid BASH step."""
        step = StepDefinition(
            name="test_bash",
            description="Test bash step",
            dependencies=[],
            worker_type=WorkerType.BASH,
            worker_path="scripts/test.sh"
        )
        
        assert step.name == "test_bash"
        assert step.worker_type == WorkerType.BASH
        assert step.worker_path == "scripts/test.sh"
        assert step.worker_func is None
    
    def test_valid_python_step(self):
        """Test creating a valid PYTHON step."""
        step = StepDefinition(
            name="test_python",
            description="Test python step",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=dummy_worker
        )
        
        assert step.name == "test_python"
        assert step.worker_type == WorkerType.PYTHON
        assert step.worker_func == dummy_worker
        assert step.worker_path is None
    
    def test_bash_step_without_worker_path_raises_error(self):
        """Test that BASH step without worker_path raises ValueError."""
        with pytest.raises(ValueError, match="BASH worker requires worker_path"):
            StepDefinition(
                name="invalid_bash",
                description="Invalid bash step",
                dependencies=[],
                worker_type=WorkerType.BASH
            )
    
    def test_python_step_without_worker_func_raises_error(self):
        """Test that PYTHON step without worker_func raises ValueError."""
        with pytest.raises(ValueError, match="PYTHON worker requires worker_func"):
            StepDefinition(
                name="invalid_python",
                description="Invalid python step",
                dependencies=[],
                worker_type=WorkerType.PYTHON
            )
    
    def test_step_with_dependencies(self):
        """Test step with multiple dependencies."""
        step = StepDefinition(
            name="dependent_step",
            description="Step with dependencies",
            dependencies=["step1", "step2", "step3"],
            worker_type=WorkerType.PYTHON,
            worker_func=dummy_worker
        )
        
        assert len(step.dependencies) == 3
        assert "step1" in step.dependencies
        assert "step2" in step.dependencies
        assert "step3" in step.dependencies
    
    def test_optional_step(self):
        """Test optional step flag."""
        step = StepDefinition(
            name="optional_step",
            description="Optional step",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=dummy_worker,
            optional=True
        )
        
        assert step.optional is True
    
    def test_step_with_timeout(self):
        """Test step with timeout."""
        step = StepDefinition(
            name="timed_step",
            description="Step with timeout",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=dummy_worker,
            timeout_seconds=300
        )
        
        assert step.timeout_seconds == 300
    
    def test_step_with_validation_func(self):
        """Test step with validation function."""
        def validate():
            return True
        
        step = StepDefinition(
            name="validated_step",
            description="Step with validation",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=dummy_worker,
            validation_func=validate
        )
        
        assert step.validation_func == validate


class TestStepRegistry:
    """Tests for the STEPS registry and helper functions."""
    
    def test_steps_registry_not_empty(self):
        """Test that STEPS registry contains steps."""
        assert len(STEPS) > 0
    
    def test_steps_registry_has_15_steps(self):
        """Test that STEPS registry has exactly 15 steps as per design."""
        assert len(STEPS) == 15
    
    def test_all_steps_have_unique_names(self):
        """Test that all step names are unique."""
        step_names = [step.name for step in STEPS]
        assert len(step_names) == len(set(step_names))
    
    def test_get_step_by_name_existing(self):
        """Test getting an existing step by name."""
        # First step should be check_prerequisites
        step = get_step_by_name("check_prerequisites")
        assert step is not None
        assert step.name == "check_prerequisites"
    
    def test_get_step_by_name_nonexistent(self):
        """Test getting a non-existent step returns None."""
        step = get_step_by_name("nonexistent_step")
        assert step is None
    
    def test_get_all_step_names(self):
        """Test getting all step names."""
        names = get_all_step_names()
        assert len(names) == 15
        assert "check_prerequisites" in names
        assert "validate_build_outputs" in names
    
    def test_first_step_has_no_dependencies(self):
        """Test that the first step (check_prerequisites) has no dependencies."""
        step = get_step_by_name("check_prerequisites")
        assert step is not None
        assert len(step.dependencies) == 0
    
    def test_last_step_has_dependencies(self):
        """Test that the last step has dependencies."""
        step = get_step_by_name("validate_build_outputs")
        assert step is not None
        assert len(step.dependencies) > 0


class TestStepValidation:
    """Tests for step definition validation."""
    
    def test_validate_step_definitions_succeeds(self):
        """Test that default STEPS pass validation."""
        # Should not raise any exception
        validate_step_definitions()
    
    def test_validate_detects_nonexistent_dependency(self):
        """Test that validation detects non-existent dependencies."""
        # Create a step with invalid dependency
        invalid_steps = [
            StepDefinition(
                name="step1",
                description="Step 1",
                dependencies=["nonexistent_step"],
                worker_type=WorkerType.PYTHON,
                worker_func=dummy_worker
            )
        ]
        
        # Temporarily replace STEPS
        import build_steps
        original_steps = build_steps.STEPS
        build_steps.STEPS = invalid_steps
        
        try:
            with pytest.raises(ValueError, match="non-existent dependency"):
                validate_step_definitions()
        finally:
            build_steps.STEPS = original_steps
    
    def test_validate_detects_duplicate_names(self):
        """Test that validation detects duplicate step names."""
        # Create steps with duplicate names
        duplicate_steps = [
            StepDefinition(
                name="duplicate",
                description="Step 1",
                dependencies=[],
                worker_type=WorkerType.PYTHON,
                worker_func=dummy_worker
            ),
            StepDefinition(
                name="duplicate",
                description="Step 2",
                dependencies=[],
                worker_type=WorkerType.PYTHON,
                worker_func=dummy_worker
            )
        ]
        
        # Temporarily replace STEPS
        import build_steps
        original_steps = build_steps.STEPS
        build_steps.STEPS = duplicate_steps
        
        try:
            with pytest.raises(ValueError, match="Duplicate step names"):
                validate_step_definitions()
        finally:
            build_steps.STEPS = original_steps
    
    def test_validate_detects_bash_without_path(self):
        """Test that validation detects BASH steps without worker_path."""
        # __post_init__ catches this at construction time
        with pytest.raises(ValueError, match="BASH worker requires worker_path"):
            StepDefinition(
                name="invalid_bash",
                description="Invalid bash step",
                dependencies=[],
                worker_type=WorkerType.BASH,
                worker_path=None  # Invalid
            )
    
    def test_validate_detects_python_without_func(self):
        """Test that validation detects PYTHON steps without worker_func."""
        # __post_init__ catches this at construction time
        with pytest.raises(ValueError, match="PYTHON worker requires worker_func"):
            StepDefinition(
                name="invalid_python",
                description="Invalid python step",
                dependencies=[],
                worker_type=WorkerType.PYTHON,
                worker_func=None  # Invalid
            )


class TestDependencyGraph:
    """Tests for dependency graph structure."""
    
    def test_setup_python_env_depends_on_check_prerequisites(self):
        """Test that setup_python_env depends on check_prerequisites."""
        step = get_step_by_name("setup_python_env")
        assert step is not None
        assert "check_prerequisites" in step.dependencies
    
    def test_collect_opencenter_assets_depends_on_check_github_token(self):
        """Test dependency: collect_opencenter_assets -> check_github_token."""
        step = get_step_by_name("collect_opencenter_assets")
        assert step is not None
        assert "check_github_token" in step.dependencies
    
    def test_clone_kubespray_offline_depends_on_setup_python_env(self):
        """Test dependency: clone_kubespray_offline -> setup_python_env."""
        step = get_step_by_name("clone_kubespray_offline")
        assert step is not None
        assert "setup_python_env" in step.dependencies
    
    def test_run_kubespray_offline_has_two_dependencies(self):
        """Test that run_kubespray_offline has two dependencies."""
        step = get_step_by_name("run_kubespray_offline")
        assert step is not None
        assert len(step.dependencies) == 2
        assert "collect_opencenter_assets" in step.dependencies
        assert "merge_opencenter_images" in step.dependencies
    
    def test_validate_build_outputs_has_three_dependencies(self):
        """Test that validate_build_outputs has three dependencies."""
        step = get_step_by_name("validate_build_outputs")
        assert step is not None
        assert len(step.dependencies) == 3
        assert "generate_checksums" in step.dependencies
        assert "sign_package" in step.dependencies
        assert "inspect_package" in step.dependencies
    
    def test_sign_package_is_optional(self):
        """Test that sign_package is marked as optional."""
        step = get_step_by_name("sign_package")
        assert step is not None
        assert step.optional is True
    
    def test_all_dependencies_exist(self):
        """Test that all dependencies reference existing steps."""
        step_names = set(get_all_step_names())
        
        for step in STEPS:
            for dep in step.dependencies:
                assert dep in step_names, (
                    f"Step '{step.name}' has non-existent dependency: '{dep}'"
                )
    
    def test_no_self_dependencies(self):
        """Test that no step depends on itself."""
        for step in STEPS:
            assert step.name not in step.dependencies, (
                f"Step '{step.name}' depends on itself"
            )


class TestWorkerTypes:
    """Tests for worker type distribution."""
    
    def test_has_both_bash_and_python_workers(self):
        """Test that registry has both BASH and PYTHON workers."""
        bash_count = sum(1 for step in STEPS if step.worker_type == WorkerType.BASH)
        python_count = sum(1 for step in STEPS if step.worker_type == WorkerType.PYTHON)
        
        assert bash_count > 0, "Should have at least one BASH worker"
        assert python_count > 0, "Should have at least one PYTHON worker"
    
    def test_bash_workers_have_paths(self):
        """Test that all BASH workers have worker_path set."""
        for step in STEPS:
            if step.worker_type == WorkerType.BASH:
                assert step.worker_path is not None, (
                    f"BASH step '{step.name}' missing worker_path"
                )
    
    def test_python_workers_have_funcs(self):
        """Test that all PYTHON workers have worker_func set."""
        for step in STEPS:
            if step.worker_type == WorkerType.PYTHON:
                assert step.worker_func is not None, (
                    f"PYTHON step '{step.name}' missing worker_func"
                )


class TestTimeouts:
    """Tests for timeout configuration."""
    
    def test_long_running_steps_have_timeouts(self):
        """Test that long-running steps have appropriate timeouts."""
        # Steps that download or process large amounts of data should have timeouts
        long_running = [
            "collect_opencenter_assets",
            "run_kubespray_offline",
            "create_zarf_package"
        ]
        
        for step_name in long_running:
            step = get_step_by_name(step_name)
            assert step is not None
            assert step.timeout_seconds is not None, (
                f"Long-running step '{step_name}' should have timeout"
            )
            assert step.timeout_seconds >= 300, (
                f"Step '{step_name}' timeout seems too short: {step.timeout_seconds}s"
            )
    
    def test_quick_steps_have_short_timeouts(self):
        """Test that quick validation steps have short timeouts."""
        quick_steps = [
            "check_prerequisites",
            "check_github_token",
            "validate_versions",
            "validate_zarf_yaml"
        ]
        
        for step_name in quick_steps:
            step = get_step_by_name(step_name)
            assert step is not None
            if step.timeout_seconds is not None:
                assert step.timeout_seconds <= 60, (
                    f"Quick step '{step_name}' has unexpectedly long timeout: "
                    f"{step.timeout_seconds}s"
                )
