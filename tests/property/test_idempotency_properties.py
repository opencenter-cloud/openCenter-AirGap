"""Property-based tests for idempotency and optimization.

Tests Property 9: Step Idempotency
Tests Property 10: Output-Based Skip Optimization
Tests Property 30: Input Change Detection
Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 14.1, 14.2, 14.3, 14.4
"""

import pytest
from hypothesis import given, strategies as st, assume
from pathlib import Path
import tempfile
import sys
import time

# Add scripts/build to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "build"))

from build_executor import BuildExecutor
from build_state import BuildState, StepStatus
from build_steps import StepDefinition, WorkerType
from datetime import datetime


@pytest.mark.property
def test_property_9_step_idempotency_bash():
    """
    Property 9: Step Idempotency - Bash Workers
    
    For any step executed multiple times with the same inputs,
    the step should produce the same result and complete successfully
    each time without errors.
    
    Validates: Requirements 4.1, 4.3, 4.5
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create a bash script that is idempotent
        script_path = project_root / "test_script.sh"
        script_path.write_text("""#!/bin/bash
# Idempotent script - creates a file if it doesn't exist
OUTPUT_FILE="output.txt"
if [ ! -f "${OUTPUT_FILE}" ]; then
    echo "Creating output file"
    echo "test content" > "${OUTPUT_FILE}"
else
    echo "Output file already exists"
fi
exit 0
""")
        script_path.chmod(0o755)
        
        # Create step
        step = StepDefinition(
            name="test_step",
            description="Test idempotent step",
            dependencies=[],
            worker_type=WorkerType.BASH,
            worker_path="test_script.sh"
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
            assert state.steps["test_step"].status == StepStatus.COMPLETED
        
        # Verify output file exists and has correct content
        output_file = project_root / "output.txt"
        assert output_file.exists()
        assert output_file.read_text() == "test content\n"


@pytest.mark.property
def test_property_9_step_idempotency_python():
    """
    Property 9: Step Idempotency - Python Workers
    
    For any Python worker executed multiple times with the same inputs,
    the step should produce the same result each time.
    
    Validates: Requirements 4.1, 4.3, 4.5
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        execution_count = 0
        
        def idempotent_worker(root: Path) -> bool:
            """Idempotent worker that creates a file if it doesn't exist."""
            nonlocal execution_count
            execution_count += 1
            
            output_file = root / "output.txt"
            if not output_file.exists():
                output_file.write_text("test content")
            
            return True
        
        # Create step
        step = StepDefinition(
            name="test_step",
            description="Test idempotent step",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=idempotent_worker
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
        
        # Verify output file exists and has correct content
        output_file = project_root / "output.txt"
        assert output_file.exists()
        assert output_file.read_text() == "test content"


@pytest.mark.property
def test_property_10_output_based_skip_optimization():
    """
    Property 10: Output-Based Skip Optimization
    
    For any step with existing valid outputs and unchanged inputs,
    the step should skip redundant work and complete successfully.
    
    Validates: Requirements 4.2, 4.4
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create input file
        input_file = project_root / "input.txt"
        input_file.write_text("input content")
        
        # Create output file (already exists)
        output_file = project_root / "output.txt"
        output_file.write_text("output content")
        
        # Wait a moment to ensure output is older than input
        time.sleep(0.1)
        
        # Touch output to make it newer than input
        output_file.touch()
        
        execution_count = 0
        
        def test_worker(root: Path) -> bool:
            """Worker that should be skipped."""
            nonlocal execution_count
            execution_count += 1
            return True
        
        # Create step with input/output files
        step = StepDefinition(
            name="test_step",
            description="Test step with I/O",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=test_worker,
            input_files=["input.txt"],
            output_files=["output.txt"]
        )
        
        # Create state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create executor (without force flag)
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1,
            force=False
        )
        
        # Execute step
        result = executor.execute_step(step)
        
        # Should succeed but skip execution
        assert result is True
        assert state.is_step_complete("test_step")
        
        # Worker should not have been called (skipped)
        assert execution_count == 0


@pytest.mark.property
def test_property_30_input_change_detection_changed():
    """
    Property 30: Input Change Detection - Changed Inputs
    
    For any step with changed inputs (based on file modification timestamps),
    the step should execute even if outputs exist.
    
    Validates: Requirements 14.1, 14.2, 14.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create output file first
        output_file = project_root / "output.txt"
        output_file.write_text("old output")
        
        # Wait to ensure timestamp difference
        time.sleep(0.1)
        
        # Create input file (newer than output)
        input_file = project_root / "input.txt"
        input_file.write_text("new input")
        
        execution_count = 0
        
        def test_worker(root: Path) -> bool:
            """Worker that should execute."""
            nonlocal execution_count
            execution_count += 1
            return True
        
        # Create step with input/output files
        step = StepDefinition(
            name="test_step",
            description="Test step with I/O",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=test_worker,
            input_files=["input.txt"],
            output_files=["output.txt"]
        )
        
        # Create state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create executor (without force flag)
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1,
            force=False
        )
        
        # Execute step
        result = executor.execute_step(step)
        
        # Should succeed and execute
        assert result is True
        assert state.is_step_complete("test_step")
        
        # Worker should have been called
        assert execution_count == 1


@pytest.mark.property
def test_property_30_input_change_detection_missing_output():
    """
    Property 30: Input Change Detection - Missing Output
    
    For any step with missing outputs, the step should execute
    regardless of input timestamps.
    
    Validates: Requirements 14.1, 14.2
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create input file
        input_file = project_root / "input.txt"
        input_file.write_text("input content")
        
        # Output file does NOT exist
        
        execution_count = 0
        
        def test_worker(root: Path) -> bool:
            """Worker that should execute."""
            nonlocal execution_count
            execution_count += 1
            # Create output
            (root / "output.txt").write_text("output")
            return True
        
        # Create step with input/output files
        step = StepDefinition(
            name="test_step",
            description="Test step with I/O",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=test_worker,
            input_files=["input.txt"],
            output_files=["output.txt"]
        )
        
        # Create state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create executor (without force flag)
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1,
            force=False
        )
        
        # Execute step
        result = executor.execute_step(step)
        
        # Should succeed and execute
        assert result is True
        assert state.is_step_complete("test_step")
        
        # Worker should have been called
        assert execution_count == 1


@pytest.mark.property
def test_property_30_force_flag_bypasses_detection():
    """
    Property 30: Input Change Detection - Force Flag
    
    For any step with --force flag, input change detection should be
    bypassed and the step should always execute.
    
    Validates: Requirements 14.4
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create input file
        input_file = project_root / "input.txt"
        input_file.write_text("input content")
        
        # Create output file (newer than input)
        output_file = project_root / "output.txt"
        output_file.write_text("output content")
        
        # Wait to ensure output is newer
        time.sleep(0.1)
        output_file.touch()
        
        execution_count = 0
        
        def test_worker(root: Path) -> bool:
            """Worker that should execute due to force flag."""
            nonlocal execution_count
            execution_count += 1
            return True
        
        # Create step with input/output files
        step = StepDefinition(
            name="test_step",
            description="Test step with I/O",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=test_worker,
            input_files=["input.txt"],
            output_files=["output.txt"]
        )
        
        # Create state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create executor WITH force flag
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1,
            force=True  # Force execution
        )
        
        # Execute step
        result = executor.execute_step(step)
        
        # Should succeed and execute (not skip)
        assert result is True
        assert state.is_step_complete("test_step")
        
        # Worker should have been called despite unchanged inputs
        assert execution_count == 1


@pytest.mark.property
def test_property_30_directory_input_detection():
    """
    Property 30: Input Change Detection - Directory Inputs
    
    For any step with directory inputs, changes to files within
    the directory should be detected.
    
    Validates: Requirements 14.1, 14.2
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create input directory with files
        input_dir = project_root / "inputs"
        input_dir.mkdir()
        (input_dir / "file1.txt").write_text("content1")
        (input_dir / "file2.txt").write_text("content2")
        
        # Create output file (older than inputs)
        output_file = project_root / "output.txt"
        output_file.write_text("old output")
        
        # Wait to ensure timestamp difference
        time.sleep(0.1)
        
        # Modify a file in input directory
        (input_dir / "file1.txt").write_text("modified content")
        
        execution_count = 0
        
        def test_worker(root: Path) -> bool:
            """Worker that should execute."""
            nonlocal execution_count
            execution_count += 1
            return True
        
        # Create step with directory input
        step = StepDefinition(
            name="test_step",
            description="Test step with directory input",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=test_worker,
            input_files=["inputs"],  # Directory
            output_files=["output.txt"]
        )
        
        # Create state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create executor (without force flag)
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1,
            force=False
        )
        
        # Execute step
        result = executor.execute_step(step)
        
        # Should succeed and execute (input directory changed)
        assert result is True
        assert state.is_step_complete("test_step")
        
        # Worker should have been called
        assert execution_count == 1


@pytest.mark.property
def test_property_9_step_creates_directories_idempotently():
    """
    Property 9: Step Idempotency - Directory Creation
    
    For any step that creates directories, executing multiple times
    should succeed even if directories already exist.
    
    Validates: Requirements 4.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        def directory_worker(root: Path) -> bool:
            """Worker that creates directories idempotently."""
            output_dir = root / "output" / "subdir"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "file.txt").write_text("content")
            return True
        
        # Create step
        step = StepDefinition(
            name="test_step",
            description="Test directory creation",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=directory_worker
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
        
        # Verify directory and file exist
        output_file = project_root / "output" / "subdir" / "file.txt"
        assert output_file.exists()
        assert output_file.read_text() == "content"
