"""Property-based tests for logging and observability.

Tests Property 26: Log File Creation
Tests Property 27: Comprehensive Logging
Tests Property 28: Build Summary Logging
Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5, 12.6
"""

import pytest
from pathlib import Path
import tempfile
import sys
import logging

# Add scripts/build to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "build"))

from build_executor import BuildExecutor
from build_state import BuildState, StepStatus
from build_steps import StepDefinition, WorkerType
from datetime import datetime


@pytest.mark.property
def test_property_26_log_file_creation():
    """
    Property 26: Log File Creation
    
    For any build execution, a log file should be created at
    build/build-{timestamp}.log containing all output.
    
    Validates: Requirements 12.1
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create log file
        log_file = project_root / "build" / "build-test.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup logger
        logger = logging.getLogger("test_build")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Create simple step
        def test_worker(root: Path) -> bool:
            return True
        
        step = StepDefinition(
            name="test_step",
            description="Test step",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=test_worker
        )
        
        # Create state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create executor with logger
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1,
            logger=logger
        )
        
        # Execute step
        result = executor.execute_step(step)
        
        # Flush logger
        for handler in logger.handlers:
            handler.flush()
        
        # Verify log file was created
        assert log_file.exists()
        
        # Verify log file has content
        log_content = log_file.read_text()
        assert len(log_content) > 0


@pytest.mark.property
def test_property_27_comprehensive_logging_step_execution():
    """
    Property 27: Comprehensive Logging - Step Execution
    
    For any step execution, the log should contain step name,
    start time, end time, and duration.
    
    Validates: Requirements 12.2, 12.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create log file
        log_file = project_root / "build" / "build-test.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup logger
        logger = logging.getLogger("test_build_step")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Create simple step
        def test_worker(root: Path) -> bool:
            return True
        
        step = StepDefinition(
            name="test_step",
            description="Test step description",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=test_worker
        )
        
        # Create state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create executor with logger
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1,
            logger=logger
        )
        
        # Execute step
        result = executor.execute_step(step)
        
        # Flush logger
        for handler in logger.handlers:
            handler.flush()
        
        # Verify log contains required information
        log_content = log_file.read_text()
        
        # Check for step name
        assert "test_step" in log_content
        
        # Check for description
        assert "Test step description" in log_content
        
        # Check for start time
        assert "Start time:" in log_content
        
        # Check for end time
        assert "End time:" in log_content
        
        # Check for duration
        assert "Duration:" in log_content


@pytest.mark.property
def test_property_27_comprehensive_logging_subprocess_commands():
    """
    Property 27: Comprehensive Logging - Subprocess Commands
    
    For any bash worker execution, the log should contain the
    subprocess command before execution.
    
    Validates: Requirements 12.4
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create log file
        log_file = project_root / "build" / "build-test.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup logger
        logger = logging.getLogger("test_build_bash")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Create bash script
        script_path = project_root / "test_script.sh"
        script_path.write_text("""#!/bin/bash
echo "Test output"
exit 0
""")
        script_path.chmod(0o755)
        
        # Create bash step
        step = StepDefinition(
            name="test_bash_step",
            description="Test bash step",
            dependencies=[],
            worker_type=WorkerType.BASH,
            worker_path="test_script.sh"
        )
        
        # Create state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create executor with logger
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1,
            logger=logger
        )
        
        # Execute step
        result = executor.execute_step(step)
        
        # Flush logger
        for handler in logger.handlers:
            handler.flush()
        
        # Verify log contains command
        log_content = log_file.read_text()
        
        # Check for command logging
        assert "Executing command:" in log_content
        assert "/bin/bash" in log_content
        assert "test_script.sh" in log_content


@pytest.mark.property
def test_property_27_comprehensive_logging_log_levels():
    """
    Property 27: Comprehensive Logging - Log Level Indicators
    
    For any log message, the log should include log level indicators
    (INFO, WARN, ERROR).
    
    Validates: Requirements 12.5
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create log file
        log_file = project_root / "build" / "build-test.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup logger
        logger = logging.getLogger("test_build_levels")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Log messages at different levels
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        
        # Flush logger
        for handler in logger.handlers:
            handler.flush()
        
        # Verify log contains level indicators
        log_content = log_file.read_text()
        
        assert "[INFO]" in log_content
        assert "[WARNING]" in log_content
        assert "[ERROR]" in log_content


@pytest.mark.property
def test_property_27_comprehensive_logging_error_details():
    """
    Property 27: Comprehensive Logging - Error Details
    
    For any step failure, the log should contain error details
    and context.
    
    Validates: Requirements 12.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create log file
        log_file = project_root / "build" / "build-test.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup logger
        logger = logging.getLogger("test_build_error")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Create failing step
        def failing_worker(root: Path) -> bool:
            raise RuntimeError("Test error message")
        
        step = StepDefinition(
            name="failing_step",
            description="Failing step",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=failing_worker
        )
        
        # Create state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create executor with logger
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1,
            logger=logger
        )
        
        # Execute step (should fail)
        result = executor.execute_step(step)
        
        # Flush logger
        for handler in logger.handlers:
            handler.flush()
        
        # Verify log contains error details
        log_content = log_file.read_text()
        
        assert "Test error message" in log_content
        assert "[ERROR]" in log_content
        assert "Traceback" in log_content or "RuntimeError" in log_content


@pytest.mark.property
def test_property_28_build_summary_logging():
    """
    Property 28: Build Summary Logging
    
    For any completed build (success or failure), a summary should
    be written to the log file with total duration and step count.
    
    Validates: Requirements 12.6
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create log file
        log_file = project_root / "build" / "build-test.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup logger
        logger = logging.getLogger("test_build_summary")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Create simple step
        def test_worker(root: Path) -> bool:
            return True
        
        step = StepDefinition(
            name="test_step",
            description="Test step",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=test_worker
        )
        
        # Create state
        state = BuildState(
            build_id="test",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        # Create executor with logger
        executor = BuildExecutor(
            steps=[step],
            state=state,
            project_root=project_root,
            max_parallel=1,
            logger=logger
        )
        
        # Execute build
        result = executor.execute_build()
        
        # Flush logger
        for handler in logger.handlers:
            handler.flush()
        
        # Verify log contains summary
        log_content = log_file.read_text()
        
        # Check for summary section
        assert "BUILD SUMMARY" in log_content
        
        # Check for status
        assert "Status:" in log_content
        
        # Check for duration
        assert "Total duration:" in log_content
        
        # Check for step count
        assert "Steps executed:" in log_content
        
        # Check for completed steps count
        assert "Completed steps:" in log_content
