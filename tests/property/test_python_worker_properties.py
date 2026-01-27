"""Property-based tests for Python worker execution.

Tests Property 20: Python Worker Execution
Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5
"""

import pytest
from hypothesis import given, strategies as st, assume
from pathlib import Path
import tempfile
import shutil
import sys

# Add scripts/build to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "build"))

from build_executor import BuildExecutor
from build_state import BuildState, StepStatus
from build_steps import StepDefinition, WorkerType
from datetime import datetime


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


def none_worker(project_root: Path) -> None:
    """Worker that returns None (should be treated as success)."""
    pass


@pytest.mark.property
def test_property_20_python_worker_success():
    """
    Property 20: Python Worker Execution - Success Case
    
    For any step defined as a Python worker that returns True,
    the build orchestrator should mark it as completed.
    
    Validates: Requirements 9.1, 9.5
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create build state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create step with success worker
        step = StepDefinition(
            name="test_step",
            description="Test step",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=success_worker
        )
        
        # Create executor
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1
        )
        
        # Execute step
        result = executor.execute_step(step)
        
        # Verify success
        assert result is True
        assert state.is_step_complete("test_step")
        assert state.steps["test_step"].status == StepStatus.COMPLETED
        assert state.steps["test_step"].error_message is None


@pytest.mark.property
def test_property_20_python_worker_failure():
    """
    Property 20: Python Worker Execution - Failure Case
    
    For any step defined as a Python worker that returns False,
    the build orchestrator should mark it as failed.
    
    Validates: Requirements 9.1, 9.4
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create build state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create step with failure worker
        step = StepDefinition(
            name="test_step",
            description="Test step",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=failure_worker
        )
        
        # Create executor
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1
        )
        
        # Execute step
        result = executor.execute_step(step)
        
        # Verify failure
        assert result is False
        assert not state.is_step_complete("test_step")
        assert state.steps["test_step"].status == StepStatus.FAILED


@pytest.mark.property
def test_property_20_python_worker_exception():
    """
    Property 20: Python Worker Execution - Exception Case
    
    For any step defined as a Python worker that raises an exception,
    the build orchestrator should capture it and mark the step as failed.
    
    Validates: Requirements 9.1, 9.2
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create build state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create step with exception worker
        step = StepDefinition(
            name="test_step",
            description="Test step",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=exception_worker
        )
        
        # Create executor
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1
        )
        
        # Execute step
        result = executor.execute_step(step)
        
        # Verify failure with error message
        assert result is False
        assert not state.is_step_complete("test_step")
        assert state.steps["test_step"].status == StepStatus.FAILED
        assert "Test exception" in state.steps["test_step"].error_message


@pytest.mark.property
def test_property_20_python_worker_parameters():
    """
    Property 20: Python Worker Execution - Parameter Passing
    
    For any step defined as a Python worker, the build orchestrator
    should pass the project_root parameter correctly.
    
    Validates: Requirements 9.1, 9.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create a marker file to verify parameter passing
        marker_file = project_root / "marker.txt"
        
        def parameter_test_worker(root: Path) -> bool:
            """Worker that verifies it received the correct parameter."""
            # Write to marker file to prove we got the right path
            (root / "marker.txt").write_text("success")
            return True
        
        # Create build state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create step
        step = StepDefinition(
            name="test_step",
            description="Test step",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=parameter_test_worker
        )
        
        # Create executor
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1
        )
        
        # Execute step
        result = executor.execute_step(step)
        
        # Verify success and parameter was passed correctly
        assert result is True
        assert marker_file.exists()
        assert marker_file.read_text() == "success"


@pytest.mark.property
@given(
    worker_returns=st.sampled_from([True, False, None]),
    step_name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_-'))
)
def test_property_20_python_worker_return_values(worker_returns, step_name):
    """
    Property 20: Python Worker Execution - Return Value Handling
    
    For any Python worker return value:
    - True should mark step as completed
    - False should mark step as failed
    - None should mark step as completed (implicit success)
    
    Validates: Requirements 9.1, 9.4, 9.5
    """
    assume(len(step_name) > 0)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create worker with specific return value
        def test_worker(root: Path):
            return worker_returns
        
        # Create build state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create step
        step = StepDefinition(
            name=step_name,
            description="Test step",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=test_worker
        )
        
        # Create executor
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1
        )
        
        # Execute step
        result = executor.execute_step(step)
        
        # Verify behavior based on return value
        if worker_returns is False:
            assert result is False
            assert state.steps[step_name].status == StepStatus.FAILED
        else:
            # True or None should both succeed
            assert result is True
            assert state.steps[step_name].status == StepStatus.COMPLETED


@pytest.mark.property
def test_property_20_python_worker_multiple_executions():
    """
    Property 20: Python Worker Execution - Multiple Executions
    
    For any Python worker, executing it multiple times should
    produce consistent results (idempotency).
    
    Validates: Requirements 9.1
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        execution_count = 0
        
        def counting_worker(root: Path) -> bool:
            """Worker that counts executions."""
            nonlocal execution_count
            execution_count += 1
            return True
        
        # Create step
        step = StepDefinition(
            name="test_step",
            description="Test step",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=counting_worker
        )
        
        # Execute multiple times
        for i in range(3):
            state = BuildState(
                build_id=f"test-{i}",
                start_time=datetime.now(),
                last_update=datetime.now(),
                steps={}
            )
            
            executor = BuildExecutor(
                steps=[step],
                state=state,
                project_root=project_root,
                max_parallel=1
            )
            
            result = executor.execute_step(step)
            
            # Each execution should succeed
            assert result is True
            assert state.is_step_complete("test_step")
        
        # Verify all executions happened
        assert execution_count == 3
