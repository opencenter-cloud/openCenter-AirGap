"""Property-based tests for parallel execution.

Tests Properties 6, 7, and 8 from the design document.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from pathlib import Path
import time
from datetime import datetime
from typing import List, Set
import tempfile
import shutil

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "build"))

from build_executor import BuildExecutor, CircularDependencyError
from build_steps import StepDefinition, WorkerType
from build_state import BuildState, StepStatus


# Test worker functions that track execution
execution_log = []
execution_times = {}


def create_test_worker(step_name: str, duration: float = 0.1):
    """Create a test worker function that logs execution."""
    def worker(project_root: Path) -> bool:
        start = time.time()
        execution_log.append((step_name, start))
        time.sleep(duration)
        execution_times[step_name] = time.time() - start
        return True
    return worker


def create_failing_worker(step_name: str):
    """Create a test worker that fails."""
    def worker(project_root: Path) -> bool:
        execution_log.append((step_name, time.time()))
        return False
    return worker


@st.composite
def independent_steps_strategy(draw):
    """Generate a list of independent steps (no dependencies)."""
    num_steps = draw(st.integers(min_value=2, max_value=5))
    steps = []
    
    for i in range(num_steps):
        step_name = f"step_{i}"
        steps.append(StepDefinition(
            name=step_name,
            description=f"Test step {i}",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=create_test_worker(step_name, duration=0.05)
        ))
    
    return steps


@st.composite
def steps_with_dependencies_strategy(draw):
    """Generate steps with dependency relationships."""
    num_steps = draw(st.integers(min_value=3, max_value=6))
    steps = []
    
    # Create first step with no dependencies
    steps.append(StepDefinition(
        name="step_0",
        description="Root step",
        dependencies=[],
        worker_type=WorkerType.PYTHON,
        worker_func=create_test_worker("step_0", duration=0.05)
    ))
    
    # Create remaining steps with dependencies on previous steps
    for i in range(1, num_steps):
        # Randomly choose dependencies from previous steps
        max_deps = min(i, 2)
        num_deps = draw(st.integers(min_value=1, max_value=max_deps))
        deps = draw(st.lists(
            st.integers(min_value=0, max_value=i-1),
            min_size=num_deps,
            max_size=num_deps,
            unique=True
        ))
        
        step_name = f"step_{i}"
        steps.append(StepDefinition(
            name=step_name,
            description=f"Test step {i}",
            dependencies=[f"step_{d}" for d in deps],
            worker_type=WorkerType.PYTHON,
            worker_func=create_test_worker(step_name, duration=0.05)
        ))
    
    return steps


# Feature: resumable-build-system, Property 6: Parallel Execution of Independent Steps
@given(steps=independent_steps_strategy())
@settings(max_examples=50, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_parallel_execution_of_independent_steps(steps):
    """
    For any two or more steps with no dependency relationship, when parallel
    execution is enabled, those steps should execute concurrently up to the
    configured maximum.
    
    Validates: Requirements 2.5, 3.1, 3.2
    """
    global execution_log, execution_times
    execution_log = []
    execution_times = {}
    
    # Create temporary directory
    tmp_path = Path(tempfile.mkdtemp())
    
    try:
        # Create state
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Create executor with parallel execution enabled
        max_parallel = min(len(steps), 3)
        executor = BuildExecutor(
            steps=steps,
            state=state,
            project_root=tmp_path,
            max_parallel=max_parallel
        )
        
        # Execute build
        start_time = time.time()
        result = executor.execute_build()
        total_duration = time.time() - start_time
        
        # Verify all steps executed
        assert result is True
        assert len(execution_log) == len(steps)
        
        # Verify all steps completed
        for step in steps:
            assert state.is_step_complete(step.name)
        
        # Verify parallel execution occurred (total time should be less than sequential)
        sequential_time = sum(execution_times.values())
        
        # With parallel execution, total time should be significantly less than sequential
        # Allow some overhead for thread management
        if len(steps) >= max_parallel:
            # Should see time savings from parallelization
            assert total_duration < sequential_time * 0.9
    finally:
        # Cleanup
        shutil.rmtree(tmp_path, ignore_errors=True)


# Feature: resumable-build-system, Property 7: Parallel Failure Isolation
@given(
    num_steps=st.integers(min_value=3, max_value=5),
    fail_index=st.integers(min_value=0, max_value=4)
)
@settings(max_examples=30, deadline=3000, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_parallel_failure_isolation(num_steps, fail_index):
    """
    For any set of parallel steps where one fails, the other parallel steps
    should be allowed to complete before the build halts.
    
    Validates: Requirements 3.3
    """
    global execution_log
    execution_log = []
    
    # Ensure fail_index is within bounds
    assume(fail_index < num_steps)
    
    # Create temporary directory
    tmp_path = Path(tempfile.mkdtemp())
    
    try:
        # Create independent steps with one that fails
        steps = []
        for i in range(num_steps):
            step_name = f"step_{i}"
            if i == fail_index:
                worker = create_failing_worker(step_name)
            else:
                worker = create_test_worker(step_name, duration=0.1)
            
            steps.append(StepDefinition(
                name=step_name,
                description=f"Test step {i}",
                dependencies=[],
                worker_type=WorkerType.PYTHON,
                worker_func=worker
            ))
        
        # Create state
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Create executor with parallel execution
        executor = BuildExecutor(
            steps=steps,
            state=state,
            project_root=tmp_path,
            max_parallel=num_steps
        )
        
        # Execute build (should fail)
        result = executor.execute_build()
        
        # Verify build failed
        assert result is False
        
        # Verify the failing step is marked as failed
        assert state.steps[f"step_{fail_index}"].status == StepStatus.FAILED
        
        # Verify other steps were allowed to complete
        # All steps should have been started (logged in execution_log)
        assert len(execution_log) == num_steps
        
        # Other steps should have completed successfully
        for i in range(num_steps):
            if i != fail_index:
                step_name = f"step_{i}"
                # Step should be completed
                assert state.steps[step_name].status == StepStatus.COMPLETED
    finally:
        # Cleanup
        shutil.rmtree(tmp_path, ignore_errors=True)


# Feature: resumable-build-system, Property 8: Sequential Mode Enforcement
@given(steps=independent_steps_strategy())
@settings(max_examples=30, deadline=3000, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_sequential_mode_enforcement(steps):
    """
    For any build execution with parallel execution disabled, all steps should
    execute sequentially regardless of dependency relationships.
    
    Validates: Requirements 3.4
    """
    global execution_log, execution_times
    execution_log = []
    execution_times = {}
    
    # Create temporary directory
    tmp_path = Path(tempfile.mkdtemp())
    
    try:
        # Create state
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Create executor with parallel execution disabled (max_parallel=1)
        executor = BuildExecutor(
            steps=steps,
            state=state,
            project_root=tmp_path,
            max_parallel=1
        )
        
        # Execute build
        result = executor.execute_build()
        
        # Verify all steps executed
        assert result is True
        assert len(execution_log) == len(steps)
        
        # Verify sequential execution - each step should start after previous completes
        for i in range(1, len(execution_log)):
            prev_step_name = execution_log[i-1][0]
            curr_step_start = execution_log[i][1]
            
            # Previous step should have completed before current step started
            prev_step_result = state.steps[prev_step_name]
            assert prev_step_result.end_time is not None
            
            # Current step start time should be after previous step end time
            # (allowing small timing tolerance)
            prev_end_timestamp = prev_step_result.end_time.timestamp()
            assert curr_step_start >= prev_end_timestamp - 0.01
    finally:
        # Cleanup
        shutil.rmtree(tmp_path, ignore_errors=True)


# Additional test: Verify parallel execution with dependencies
@given(steps=steps_with_dependencies_strategy())
@settings(max_examples=30, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_parallel_execution_respects_dependencies(steps):
    """
    Verify that parallel execution respects dependency constraints.
    Steps should only execute after their dependencies complete.
    """
    global execution_log
    execution_log = []
    
    # Create temporary directory
    tmp_path = Path(tempfile.mkdtemp())
    
    try:
        # Create state
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Create executor with parallel execution
        executor = BuildExecutor(
            steps=steps,
            state=state,
            project_root=tmp_path,
            max_parallel=3
        )
        
        # Execute build
        result = executor.execute_build()
        
        # Verify all steps executed
        assert result is True
        assert len(execution_log) == len(steps)
        
        # Verify dependencies were respected
        for step in steps:
            if not step.dependencies:
                continue
            
            step_result = state.steps[step.name]
            assert step_result.start_time is not None
            
            # All dependencies should have completed before this step started
            for dep_name in step.dependencies:
                dep_result = state.steps[dep_name]
                assert dep_result.end_time is not None
                assert dep_result.end_time <= step_result.start_time
    finally:
        # Cleanup
        shutil.rmtree(tmp_path, ignore_errors=True)
