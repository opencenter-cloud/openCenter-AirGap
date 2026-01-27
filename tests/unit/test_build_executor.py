"""Unit tests for build executor.

Tests sequential execution, parallel execution, error handling, and state preservation.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from datetime import datetime
import time

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "build"))

from build_executor import BuildExecutor, CircularDependencyError, DependencyResolutionError
from build_steps import StepDefinition, WorkerType
from build_state import BuildState, StepStatus


# Test worker functions
def success_worker(project_root: Path) -> bool:
    """Worker that always succeeds."""
    return True


def failure_worker(project_root: Path) -> bool:
    """Worker that always fails."""
    return False


def exception_worker(project_root: Path) -> bool:
    """Worker that raises an exception."""
    raise RuntimeError("Test exception")


def slow_worker(project_root: Path) -> bool:
    """Worker that takes time to execute."""
    time.sleep(0.1)
    return True


class TestBuildExecutor:
    """Test suite for BuildExecutor class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.tmp_path = Path(tempfile.mkdtemp())
        
    def teardown_method(self):
        """Cleanup test fixtures."""
        shutil.rmtree(self.tmp_path, ignore_errors=True)
    
    def test_sequential_execution(self):
        """Test sequential execution of steps."""
        # Create simple steps
        steps = [
            StepDefinition(
                name="step1",
                description="First step",
                dependencies=[],
                worker_type=WorkerType.PYTHON,
                worker_func=success_worker
            ),
            StepDefinition(
                name="step2",
                description="Second step",
                dependencies=["step1"],
                worker_type=WorkerType.PYTHON,
                worker_func=success_worker
            ),
            StepDefinition(
                name="step3",
                description="Third step",
                dependencies=["step2"],
                worker_type=WorkerType.PYTHON,
                worker_func=success_worker
            ),
        ]
        
        # Create state
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Create executor with sequential mode
        executor = BuildExecutor(
            steps=steps,
            state=state,
            project_root=self.tmp_path,
            max_parallel=1
        )
        
        # Execute build
        result = executor.execute_build()
        
        # Verify success
        assert result is True
        
        # Verify all steps completed
        assert state.is_step_complete("step1")
        assert state.is_step_complete("step2")
        assert state.is_step_complete("step3")
        
        # Verify execution order (step2 should start after step1 completes)
        assert state.steps["step1"].end_time <= state.steps["step2"].start_time
        assert state.steps["step2"].end_time <= state.steps["step3"].start_time
    
    def test_parallel_execution_with_max_parallel_limit(self):
        """Test parallel execution respects max_parallel limit."""
        # Create independent steps
        steps = [
            StepDefinition(
                name=f"step{i}",
                description=f"Step {i}",
                dependencies=[],
                worker_type=WorkerType.PYTHON,
                worker_func=slow_worker
            )
            for i in range(5)
        ]
        
        # Create state
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Create executor with max_parallel=2
        executor = BuildExecutor(
            steps=steps,
            state=state,
            project_root=self.tmp_path,
            max_parallel=2
        )
        
        # Execute build
        start_time = time.time()
        result = executor.execute_build()
        duration = time.time() - start_time
        
        # Verify success
        assert result is True
        
        # Verify all steps completed
        for i in range(5):
            assert state.is_step_complete(f"step{i}")
        
        # With max_parallel=2 and 5 steps of 0.1s each:
        # Sequential would take ~0.5s
        # Parallel with max=2 should take ~0.3s (3 batches: 2+2+1)
        # Allow overhead but verify it's faster than sequential
        assert duration < 0.45  # Less than 90% of sequential time
    
    def test_error_handling_and_state_preservation(self):
        """Test that errors are handled and state is preserved."""
        # Create steps with one that fails
        steps = [
            StepDefinition(
                name="step1",
                description="First step",
                dependencies=[],
                worker_type=WorkerType.PYTHON,
                worker_func=success_worker
            ),
            StepDefinition(
                name="step2",
                description="Failing step",
                dependencies=["step1"],
                worker_type=WorkerType.PYTHON,
                worker_func=failure_worker
            ),
            StepDefinition(
                name="step3",
                description="Third step",
                dependencies=["step2"],
                worker_type=WorkerType.PYTHON,
                worker_func=success_worker
            ),
        ]
        
        # Create state
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Create executor
        executor = BuildExecutor(
            steps=steps,
            state=state,
            project_root=self.tmp_path,
            max_parallel=1
        )
        
        # Execute build (should fail)
        result = executor.execute_build()
        
        # Verify failure
        assert result is False
        
        # Verify step1 completed
        assert state.is_step_complete("step1")
        
        # Verify step2 failed
        assert state.steps["step2"].status == StepStatus.FAILED
        
        # Verify step3 was not executed
        assert "step3" not in state.steps
    
    def test_exception_handling(self):
        """Test that exceptions in workers are handled properly."""
        # Create step that raises exception
        steps = [
            StepDefinition(
                name="exception_step",
                description="Step that raises exception",
                dependencies=[],
                worker_type=WorkerType.PYTHON,
                worker_func=exception_worker
            ),
        ]
        
        # Create state
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Create executor
        executor = BuildExecutor(
            steps=steps,
            state=state,
            project_root=self.tmp_path,
            max_parallel=1
        )
        
        # Execute build (should fail)
        result = executor.execute_build()
        
        # Verify failure
        assert result is False
        
        # Verify step failed with error message
        assert state.steps["exception_step"].status == StepStatus.FAILED
        assert "RuntimeError" in state.steps["exception_step"].error_message
        assert "Test exception" in state.steps["exception_step"].error_message
    
    def test_skip_completed_steps(self):
        """Test that completed steps are skipped on resume."""
        # Create steps
        steps = [
            StepDefinition(
                name="step1",
                description="First step",
                dependencies=[],
                worker_type=WorkerType.PYTHON,
                worker_func=success_worker
            ),
            StepDefinition(
                name="step2",
                description="Second step",
                dependencies=["step1"],
                worker_type=WorkerType.PYTHON,
                worker_func=success_worker
            ),
        ]
        
        # Create state with step1 already completed
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        state.mark_step_completed("step1", 1.0)
        
        # Create executor
        executor = BuildExecutor(
            steps=steps,
            state=state,
            project_root=self.tmp_path,
            max_parallel=1
        )
        
        # Execute build
        result = executor.execute_build()
        
        # Verify success
        assert result is True
        
        # Verify step1 still completed (not re-executed)
        assert state.is_step_complete("step1")
        assert state.steps["step1"].duration_seconds == 1.0  # Original duration preserved
        
        # Verify step2 completed
        assert state.is_step_complete("step2")
    
    def test_skip_steps_flag(self):
        """Test that skip_steps flag marks steps as skipped."""
        # Create steps
        steps = [
            StepDefinition(
                name="step1",
                description="First step",
                dependencies=[],
                worker_type=WorkerType.PYTHON,
                worker_func=success_worker
            ),
            StepDefinition(
                name="step2",
                description="Second step",
                dependencies=[],
                worker_type=WorkerType.PYTHON,
                worker_func=success_worker
            ),
        ]
        
        # Create state
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Create executor
        executor = BuildExecutor(
            steps=steps,
            state=state,
            project_root=self.tmp_path,
            max_parallel=1
        )
        
        # Execute build with step1 skipped
        result = executor.execute_build(skip_steps={"step1"})
        
        # Verify success
        assert result is True
        
        # Verify step1 skipped
        assert state.steps["step1"].status == StepStatus.SKIPPED
        
        # Verify step2 completed
        assert state.is_step_complete("step2")
    
    def test_completion_markers_created(self):
        """Test that completion markers are created for completed steps."""
        # Create step
        steps = [
            StepDefinition(
                name="test_step",
                description="Test step",
                dependencies=[],
                worker_type=WorkerType.PYTHON,
                worker_func=success_worker
            ),
        ]
        
        # Create state
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Create executor
        executor = BuildExecutor(
            steps=steps,
            state=state,
            project_root=self.tmp_path,
            max_parallel=1
        )
        
        # Execute build
        result = executor.execute_build()
        
        # Verify success
        assert result is True
        
        # Verify completion marker exists
        marker_file = self.tmp_path / "build" / ".completed" / "test_step"
        assert marker_file.exists()
        
        # Verify marker contains timestamp
        content = marker_file.read_text()
        assert len(content) > 0
    
    def test_validation_function_execution(self):
        """Test that validation functions are executed after step completion."""
        validation_called = []
        
        def test_validation(project_root: Path) -> bool:
            validation_called.append(True)
            return True
        
        # Create step with validation
        steps = [
            StepDefinition(
                name="test_step",
                description="Test step",
                dependencies=[],
                worker_type=WorkerType.PYTHON,
                worker_func=success_worker,
                validation_func=test_validation
            ),
        ]
        
        # Create state
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Create executor
        executor = BuildExecutor(
            steps=steps,
            state=state,
            project_root=self.tmp_path,
            max_parallel=1
        )
        
        # Execute build
        result = executor.execute_build()
        
        # Verify success
        assert result is True
        
        # Verify validation was called
        assert len(validation_called) == 1
    
    def test_validation_failure_marks_step_failed(self):
        """Test that validation failures mark the step as failed."""
        def failing_validation(project_root: Path) -> bool:
            return False
        
        # Create step with failing validation
        steps = [
            StepDefinition(
                name="test_step",
                description="Test step",
                dependencies=[],
                worker_type=WorkerType.PYTHON,
                worker_func=success_worker,
                validation_func=failing_validation
            ),
        ]
        
        # Create state
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Create executor
        executor = BuildExecutor(
            steps=steps,
            state=state,
            project_root=self.tmp_path,
            max_parallel=1
        )
        
        # Execute build (should fail)
        result = executor.execute_build()
        
        # Verify failure
        assert result is False
        
        # Verify step failed
        assert state.steps["test_step"].status == StepStatus.FAILED
        assert "Validation failed" in state.steps["test_step"].error_message


class TestBashWorkerExecution:
    """Test suite for Bash worker execution."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.tmp_path = Path(tempfile.mkdtemp())
    
    def teardown_method(self):
        """Cleanup test fixtures."""
        shutil.rmtree(self.tmp_path, ignore_errors=True)
    
    def test_bash_worker_success(self):
        """Test successful Bash worker execution."""
        # Create test script
        script_path = self.tmp_path / "test_script.sh"
        script_path.write_text("#!/bin/bash\necho 'Success'\nexit 0\n")
        script_path.chmod(0o755)
        
        # Create step
        steps = [
            StepDefinition(
                name="bash_step",
                description="Bash test step",
                dependencies=[],
                worker_type=WorkerType.BASH,
                worker_path=str(script_path.relative_to(self.tmp_path))
            ),
        ]
        
        # Create state
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Create executor
        executor = BuildExecutor(
            steps=steps,
            state=state,
            project_root=self.tmp_path,
            max_parallel=1
        )
        
        # Execute build
        result = executor.execute_build()
        
        # Verify success
        assert result is True
        assert state.is_step_complete("bash_step")
    
    def test_bash_worker_failure(self):
        """Test Bash worker failure handling."""
        # Create failing script
        script_path = self.tmp_path / "failing_script.sh"
        script_path.write_text("#!/bin/bash\necho 'Failure' >&2\nexit 1\n")
        script_path.chmod(0o755)
        
        # Create step
        steps = [
            StepDefinition(
                name="bash_step",
                description="Failing bash step",
                dependencies=[],
                worker_type=WorkerType.BASH,
                worker_path=str(script_path.relative_to(self.tmp_path))
            ),
        ]
        
        # Create state
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Create executor
        executor = BuildExecutor(
            steps=steps,
            state=state,
            project_root=self.tmp_path,
            max_parallel=1
        )
        
        # Execute build (should fail)
        result = executor.execute_build()
        
        # Verify failure
        assert result is False
        assert state.steps["bash_step"].status == StepStatus.FAILED
    
    def test_bash_worker_missing_script(self):
        """Test Bash worker with missing script."""
        # Create step with non-existent script
        steps = [
            StepDefinition(
                name="bash_step",
                description="Missing script step",
                dependencies=[],
                worker_type=WorkerType.BASH,
                worker_path="nonexistent_script.sh"
            ),
        ]
        
        # Create state
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Create executor
        executor = BuildExecutor(
            steps=steps,
            state=state,
            project_root=self.tmp_path,
            max_parallel=1
        )
        
        # Execute build (should fail)
        result = executor.execute_build()
        
        # Verify failure
        assert result is False
        assert state.steps["bash_step"].status == StepStatus.FAILED
