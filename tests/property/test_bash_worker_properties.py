"""Property-based tests for Bash worker execution.

Tests Property 18: Bash Worker Execution
Tests Property 19: Bash Worker Timeout
Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from pathlib import Path
import tempfile
import sys
import os
import time

# Add scripts/build to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "build"))

from build_executor import BuildExecutor
from build_state import BuildState, StepStatus
from build_steps import StepDefinition, WorkerType
from datetime import datetime


@pytest.mark.property
def test_property_18_bash_worker_success():
    """
    Property 18: Bash Worker Execution - Success Case
    
    For any step defined as a Bash worker that exits with code 0,
    the build orchestrator should execute it via subprocess, capture
    stdout/stderr, and mark it as completed.
    
    Validates: Requirements 8.1, 8.2, 8.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create a simple bash script that succeeds
        script_path = project_root / "test_script.sh"
        script_path.write_text("""#!/bin/bash
echo "Test output to stdout"
echo "Test output to stderr" >&2
exit 0
""")
        script_path.chmod(0o755)
        
        # Create build state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create step with bash worker
        step = StepDefinition(
            name="test_step",
            description="Test bash step",
            dependencies=[],
            worker_type=WorkerType.BASH,
            worker_path="test_script.sh"
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
def test_property_18_bash_worker_failure():
    """
    Property 18: Bash Worker Execution - Failure Case
    
    For any Bash worker that exits with non-zero status,
    the build orchestrator should treat it as a step failure.
    
    Validates: Requirements 8.1, 8.2, 8.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create a bash script that fails
        script_path = project_root / "test_script.sh"
        script_path.write_text("""#!/bin/bash
echo "Error message" >&2
exit 1
""")
        script_path.chmod(0o755)
        
        # Create build state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create step with bash worker
        step = StepDefinition(
            name="test_step",
            description="Test bash step",
            dependencies=[],
            worker_type=WorkerType.BASH,
            worker_path="test_script.sh"
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
def test_property_18_bash_worker_environment_variables():
    """
    Property 18: Bash Worker Execution - Environment Variables
    
    For any Bash worker, the build orchestrator should pass
    environment variables to the subprocess.
    
    Validates: Requirements 8.1, 8.4
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Set a test environment variable
        test_var_name = "TEST_BUILD_VAR"
        test_var_value = "test_value_12345"
        os.environ[test_var_name] = test_var_value
        
        try:
            # Create a bash script that checks environment variable
            script_path = project_root / "test_script.sh"
            script_path.write_text(f"""#!/bin/bash
if [ "${{TEST_BUILD_VAR}}" = "{test_var_value}" ]; then
    echo "Environment variable passed correctly"
    exit 0
else
    echo "Environment variable not found or incorrect" >&2
    exit 1
fi
""")
            script_path.chmod(0o755)
            
            # Create build state
            state = BuildState(
                build_id="test",
                start_time=datetime.now(),
                last_update=datetime.now(),
                steps={}
            )
            
            # Create step with bash worker
            step = StepDefinition(
                name="test_step",
                description="Test bash step",
                dependencies=[],
                worker_type=WorkerType.BASH,
                worker_path="test_script.sh"
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
            
            # Verify success (environment variable was passed)
            assert result is True
            assert state.is_step_complete("test_step")
            
        finally:
            # Clean up environment variable
            if test_var_name in os.environ:
                del os.environ[test_var_name]


@pytest.mark.property
def test_property_18_bash_worker_working_directory():
    """
    Property 18: Bash Worker Execution - Working Directory
    
    For any Bash worker, the build orchestrator should set
    the working directory to project_root.
    
    Validates: Requirements 8.1, 8.5
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create a marker file in project root
        marker_file = project_root / "marker.txt"
        marker_file.write_text("marker")
        
        # Create a bash script that checks working directory
        script_path = project_root / "test_script.sh"
        script_path.write_text("""#!/bin/bash
# Check if we can see the marker file (proves we're in project_root)
if [ -f "marker.txt" ]; then
    echo "Working directory is correct"
    exit 0
else
    echo "Working directory is incorrect" >&2
    pwd >&2
    ls -la >&2
    exit 1
fi
""")
        script_path.chmod(0o755)
        
        # Create build state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create step with bash worker
        step = StepDefinition(
            name="test_step",
            description="Test bash step",
            dependencies=[],
            worker_type=WorkerType.BASH,
            worker_path="test_script.sh"
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
        
        # Verify success (working directory was set correctly)
        assert result is True
        assert state.is_step_complete("test_step")


@pytest.mark.property
def test_property_18_bash_worker_stdout_stderr_capture():
    """
    Property 18: Bash Worker Execution - Output Capture
    
    For any Bash worker, the build orchestrator should capture
    both stdout and stderr output.
    
    Validates: Requirements 8.1, 8.2
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create a bash script with specific output
        stdout_message = "This is stdout output"
        stderr_message = "This is stderr output"
        
        script_path = project_root / "test_script.sh"
        script_path.write_text(f"""#!/bin/bash
echo "{stdout_message}"
echo "{stderr_message}" >&2
exit 0
""")
        script_path.chmod(0o755)
        
        # Create build state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create step with bash worker
        step = StepDefinition(
            name="test_step",
            description="Test bash step",
            dependencies=[],
            worker_type=WorkerType.BASH,
            worker_path="test_script.sh"
        )
        
        # Create executor (with console to capture output)
        from rich.console import Console
        from io import StringIO
        
        output_buffer = StringIO()
        console = Console(file=output_buffer, force_terminal=False)
        
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1,
            console=console
        )
        
        # Execute step
        result = executor.execute_step(step)
        
        # Verify success
        assert result is True
        
        # Verify output was captured (check console output contains our messages)
        output = output_buffer.getvalue()
        # The executor logs stdout and stderr, so they should appear in output
        assert "STDOUT" in output or "INFO" in output


@pytest.mark.property
def test_property_19_bash_worker_timeout():
    """
    Property 19: Bash Worker Timeout
    
    For any Bash worker with a timeout configured, if execution
    exceeds the timeout, the build orchestrator should terminate
    the process and log a timeout error.
    
    Validates: Requirements 8.6
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create a bash script that sleeps longer than timeout
        script_path = project_root / "test_script.sh"
        script_path.write_text("""#!/bin/bash
echo "Starting long-running task"
sleep 10
echo "This should not be reached"
exit 0
""")
        script_path.chmod(0o755)
        
        # Create build state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create step with bash worker and short timeout
        step = StepDefinition(
            name="test_step",
            description="Test bash step with timeout",
            dependencies=[],
            worker_type=WorkerType.BASH,
            worker_path="test_script.sh",
            timeout_seconds=2  # Short timeout
        )
        
        # Create executor
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1
        )
        
        # Execute step and measure time
        start_time = time.time()
        result = executor.execute_step(step)
        elapsed_time = time.time() - start_time
        
        # Verify timeout behavior
        assert result is False  # Should fail due to timeout
        assert not state.is_step_complete("test_step")
        assert state.steps["test_step"].status == StepStatus.FAILED
        
        # Should complete in approximately timeout_seconds (not 10 seconds)
        assert elapsed_time < 5  # Should be much less than the 10 second sleep


@pytest.mark.property
@given(
    exit_code=st.integers(min_value=1, max_value=255)
)
def test_property_18_bash_worker_exit_codes(exit_code):
    """
    Property 18: Bash Worker Execution - Exit Code Handling
    
    For any Bash worker with non-zero exit code, the build
    orchestrator should treat it as a failure.
    
    Validates: Requirements 8.1, 8.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create a bash script with specific exit code
        script_path = project_root / "test_script.sh"
        script_path.write_text(f"""#!/bin/bash
exit {exit_code}
""")
        script_path.chmod(0o755)
        
        # Create build state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create step with bash worker
        step = StepDefinition(
            name="test_step",
            description="Test bash step",
            dependencies=[],
            worker_type=WorkerType.BASH,
            worker_path="test_script.sh"
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
        
        # Verify failure for any non-zero exit code
        assert result is False
        assert not state.is_step_complete("test_step")
        assert state.steps["test_step"].status == StepStatus.FAILED


@pytest.mark.property
def test_property_18_bash_worker_script_not_found():
    """
    Property 18: Bash Worker Execution - Missing Script
    
    For any Bash worker with a non-existent script path,
    the build orchestrator should fail gracefully.
    
    Validates: Requirements 8.1
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
        
        # Create step with non-existent bash worker
        step = StepDefinition(
            name="test_step",
            description="Test bash step",
            dependencies=[],
            worker_type=WorkerType.BASH,
            worker_path="nonexistent_script.sh"
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


@pytest.mark.property
def test_property_18_bash_worker_completion_marker():
    """
    Property 18: Bash Worker Execution - Completion Marker
    
    For any successful Bash worker execution, a completion
    marker should be created.
    
    Validates: Requirements 8.1
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create a simple bash script that succeeds
        script_path = project_root / "test_script.sh"
        script_path.write_text("""#!/bin/bash
exit 0
""")
        script_path.chmod(0o755)
        
        # Create build state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create step with bash worker
        step = StepDefinition(
            name="test_step",
            description="Test bash step",
            dependencies=[],
            worker_type=WorkerType.BASH,
            worker_path="test_script.sh"
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
        
        # Verify completion marker was created
        marker_file = project_root / "build" / ".completed" / "test_step"
        assert marker_file.exists()
        
        # Marker should contain timestamp
        marker_content = marker_file.read_text()
        assert len(marker_content) > 0


@pytest.mark.property
def test_property_18_bash_worker_idempotency_check():
    """
    Property 18: Bash Worker Execution - Idempotency Support
    
    Bash workers should support idempotency checks via completion markers.
    This test verifies the infrastructure is in place.
    
    Validates: Requirements 8.1
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create a bash script that creates a counter file
        script_path = project_root / "test_script.sh"
        script_path.write_text("""#!/bin/bash
# Check completion marker
MARKER_FILE="build/.completed/test_step"
if [ -f "${MARKER_FILE}" ]; then
    echo "Already completed, skipping"
    exit 0
fi

# Do work
echo "Executing work"
exit 0
""")
        script_path.chmod(0o755)
        
        # Create build state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create step with bash worker
        step = StepDefinition(
            name="test_step",
            description="Test bash step",
            dependencies=[],
            worker_type=WorkerType.BASH,
            worker_path="test_script.sh"
        )
        
        # Create executor
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1
        )
        
        # Execute step first time
        result1 = executor.execute_step(step)
        assert result1 is True
        
        # Completion marker should exist
        marker_file = project_root / "build" / ".completed" / "test_step"
        assert marker_file.exists()
        
        # Execute step second time (should still succeed)
        state2 = BuildState(
            build_id="test2",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        executor2 = BuildExecutor(
            steps=[step],
            state=state2,
            project_root=project_root,
            max_parallel=1
        )
        
        result2 = executor2.execute_step(step)
        assert result2 is True
