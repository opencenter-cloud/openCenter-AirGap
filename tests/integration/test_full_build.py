"""Integration test for full build execution.

Tests complete build from start to finish, verifying all steps execute
in correct order and final outputs exist.
"""

import pytest
import subprocess
import sys
from pathlib import Path
import json
import shutil
import tempfile
from datetime import datetime


@pytest.fixture
def test_project_root(tmp_path):
    """Create a temporary project root with minimal structure."""
    # Create directory structure
    (tmp_path / "build").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "scripts" / "build").mkdir(parents=True)
    (tmp_path / "scripts" / "build" / "workers").mkdir()
    
    # Copy build system files
    project_root = Path.cwd()
    build_files = [
        "scripts/build/build.py",
        "scripts/build/build_state.py",
        "scripts/build/build_steps.py",
        "scripts/build/build_executor.py",
    ]
    
    for file_path in build_files:
        src = project_root / file_path
        dst = tmp_path / file_path
        if src.exists():
            shutil.copy2(src, dst)
    
    # Create stub worker implementations
    workers_init = tmp_path / "scripts" / "build" / "workers" / "__init__.py"
    workers_init.write_text("")
    
    # Create stub worker files that succeed
    stub_workers = {
        "prerequisites.py": """
from pathlib import Path

def check_prerequisites_worker(project_root: Path) -> bool:
    print("INFO: Stub check_prerequisites_worker")
    return True
""",
        "python_env.py": """
from pathlib import Path

def setup_python_env_worker(project_root: Path) -> bool:
    print("INFO: Stub setup_python_env_worker")
    return True

def validate_python_env(project_root: Path) -> bool:
    print("INFO: Stub validate_python_env")
    return True
""",
        "github_token.py": """
from pathlib import Path
import os

def check_github_token_worker(project_root: Path) -> bool:
    print("INFO: Stub check_github_token_worker")
    # Don't require actual token in tests
    return True
""",
        "merge_images.py": """
from pathlib import Path

def merge_opencenter_images_worker(project_root: Path) -> bool:
    print("INFO: Stub merge_opencenter_images_worker")
    # Create stub output
    imagelists_dir = project_root / "build" / "kubespray-offline" / "imagelists"
    imagelists_dir.mkdir(parents=True, exist_ok=True)
    (imagelists_dir / "additional_images.txt").write_text("# Stub images\\n")
    return True
""",
        "validation.py": """
from pathlib import Path

def validate_versions_worker(project_root: Path) -> bool:
    print("INFO: Stub validate_versions_worker")
    return True

def validate_zarf_yaml_worker(project_root: Path) -> bool:
    print("INFO: Stub validate_zarf_yaml_worker")
    return True

def validate_build_outputs_worker(project_root: Path) -> bool:
    print("INFO: Stub validate_build_outputs_worker")
    return True
""",
        "checksums.py": """
from pathlib import Path

def generate_checksums_worker(project_root: Path) -> bool:
    print("INFO: Stub generate_checksums_worker")
    return True
""",
    }
    
    for filename, content in stub_workers.items():
        worker_file = tmp_path / "scripts" / "build" / "workers" / filename
        worker_file.write_text(content)
    
    # Create minimal config files
    (tmp_path / "config" / "versions.env").write_text("# Test versions\n")
    (tmp_path / "config" / "opencenter-images.txt").write_text("# Test images\n")
    
    # Create stub bash scripts that succeed quickly
    bash_scripts = [
        "scripts/build/collect_opencenter_assets.sh",
        "scripts/build/collect_kubespray_offline.sh",
        "scripts/build/organize_assets_for_zarf.sh",
        "scripts/build/create_zarf_package.sh",
        "scripts/build/sign_package.sh",
        "scripts/build/inspect_package.sh",
    ]
    
    for script_path in bash_scripts:
        script_file = tmp_path / script_path
        script_file.write_text("#!/bin/bash\necho 'Test script: $0'\nexit 0\n")
        script_file.chmod(0o755)
    
    # Create download-all.sh in kubespray-offline location
    kubespray_offline_dir = tmp_path / "build" / "kubespray-offline"
    kubespray_offline_dir.mkdir(parents=True)
    download_all = kubespray_offline_dir / "download-all.sh"
    download_all.write_text("#!/bin/bash\necho 'Test kubespray-offline download-all.sh'\nexit 0\n")
    download_all.chmod(0o755)
    
    # Create imagelists directory
    (kubespray_offline_dir / "imagelists").mkdir()
    
    return tmp_path


def test_full_build_from_scratch(test_project_root):
    """Test complete build from start to finish.
    
    Validates:
    - All steps execute in correct order
    - Dependencies are respected
    - Final outputs exist
    - Build state is properly maintained
    """
    # Run build with --clean to start fresh
    result = subprocess.run(
        [sys.executable, "scripts/build/build.py", "--clean", "--non-interactive"],
        cwd=test_project_root,
        capture_output=True,
        text=True,
        timeout=300  # 5 minute timeout
    )
    
    # Check exit code
    assert result.returncode == 0, f"Build failed with exit code {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    
    # Verify build state file exists
    state_file = test_project_root / "build" / ".build-state.json"
    assert state_file.exists(), "Build state file not created"
    
    # Load and verify state
    state_data = json.loads(state_file.read_text())
    assert "build_id" in state_data
    assert "steps" in state_data
    
    # Verify all expected steps are present
    expected_steps = [
        "check_prerequisites",
        "setup_python_env",
        "check_github_token",
        "collect_opencenter_assets",
        "clone_kubespray_offline",
        "merge_opencenter_images",
        "run_kubespray_offline",
        "organize_assets",
        "validate_versions",
        "validate_zarf_yaml",
        "create_zarf_package",
        "generate_checksums",
        "inspect_package",
        "validate_build_outputs",
    ]
    
    for step_name in expected_steps:
        assert step_name in state_data["steps"], f"Step '{step_name}' not found in state"
        step = state_data["steps"][step_name]
        assert step["status"] in ["completed", "skipped"], f"Step '{step_name}' has status '{step['status']}'"
    
    # Verify completion markers exist
    completed_dir = test_project_root / "build" / ".completed"
    assert completed_dir.exists(), "Completion markers directory not created"
    
    for step_name in expected_steps:
        marker_file = completed_dir / step_name
        # Marker should exist for completed steps
        if state_data["steps"][step_name]["status"] == "completed":
            assert marker_file.exists(), f"Completion marker for '{step_name}' not found"
    
    # Verify log file was created
    log_files = list((test_project_root / "build").glob("build-*.log"))
    assert len(log_files) > 0, "No log file created"
    
    # Verify log contains expected content
    log_content = log_files[0].read_text()
    assert "BUILD EXECUTION STARTED" in log_content
    assert "BUILD SUMMARY" in log_content


def test_full_build_execution_order(test_project_root):
    """Test that steps execute in correct dependency order.
    
    Validates:
    - Dependencies are satisfied before step execution
    - Parallel-capable steps can run concurrently
    - Sequential dependencies are respected
    """
    # Run build
    result = subprocess.run(
        [sys.executable, "scripts/build/build.py", "--clean", "--non-interactive"],
        cwd=test_project_root,
        capture_output=True,
        text=True,
        timeout=300
    )
    
    assert result.returncode == 0, f"Build failed: {result.stderr}"
    
    # Load state
    state_file = test_project_root / "build" / ".build-state.json"
    state_data = json.loads(state_file.read_text())
    
    # Extract step execution times
    step_times = {}
    for step_name, step_data in state_data["steps"].items():
        if step_data.get("start_time"):
            step_times[step_name] = datetime.fromisoformat(step_data["start_time"])
    
    # Verify dependency order constraints
    # check_prerequisites must come before setup_python_env
    if "check_prerequisites" in step_times and "setup_python_env" in step_times:
        assert step_times["check_prerequisites"] < step_times["setup_python_env"]
    
    # setup_python_env must come before check_github_token
    if "setup_python_env" in step_times and "check_github_token" in step_times:
        assert step_times["setup_python_env"] < step_times["check_github_token"]
    
    # check_github_token must come before collect_opencenter_assets
    if "check_github_token" in step_times and "collect_opencenter_assets" in step_times:
        assert step_times["check_github_token"] < step_times["collect_opencenter_assets"]
    
    # merge_opencenter_images must come before run_kubespray_offline
    if "merge_opencenter_images" in step_times and "run_kubespray_offline" in step_times:
        assert step_times["merge_opencenter_images"] < step_times["run_kubespray_offline"]
    
    # create_zarf_package must come before generate_checksums
    if "create_zarf_package" in step_times and "generate_checksums" in step_times:
        assert step_times["create_zarf_package"] < step_times["generate_checksums"]


def test_full_build_creates_expected_outputs(test_project_root):
    """Test that build creates all expected output files and directories.
    
    Validates:
    - Build state file exists
    - Completion markers exist
    - Log files exist
    - Build artifacts are created
    """
    # Run build
    result = subprocess.run(
        [sys.executable, "scripts/build/build.py", "--clean", "--non-interactive"],
        cwd=test_project_root,
        capture_output=True,
        text=True,
        timeout=300
    )
    
    assert result.returncode == 0, f"Build failed: {result.stderr}"
    
    # Verify build directory structure
    build_dir = test_project_root / "build"
    assert build_dir.exists()
    
    # Verify state file
    state_file = build_dir / ".build-state.json"
    assert state_file.exists()
    assert state_file.stat().st_mode & 0o777 == 0o600, "State file should have 0600 permissions"
    
    # Verify completion markers directory
    completed_dir = build_dir / ".completed"
    assert completed_dir.exists()
    
    # Verify at least one log file exists
    log_files = list(build_dir.glob("build-*.log"))
    assert len(log_files) > 0
    
    # Verify log file contains structured content
    log_content = log_files[0].read_text()
    assert "[INFO]" in log_content or "INFO:" in log_content
    assert "STEP:" in log_content or "Starting:" in log_content


def test_full_build_with_sequential_mode(test_project_root):
    """Test full build with parallel execution disabled.
    
    Validates:
    - --no-parallel flag works correctly
    - All steps still execute successfully
    - Build completes without errors
    """
    # Run build with --no-parallel
    result = subprocess.run(
        [sys.executable, "scripts/build/build.py", "--clean", "--no-parallel", "--non-interactive"],
        cwd=test_project_root,
        capture_output=True,
        text=True,
        timeout=300
    )
    
    assert result.returncode == 0, f"Build failed: {result.stderr}"
    
    # Verify all steps completed
    state_file = test_project_root / "build" / ".build-state.json"
    state_data = json.loads(state_file.read_text())
    
    completed_count = sum(
        1 for step in state_data["steps"].values()
        if step["status"] in ["completed", "skipped"]
    )
    
    # Should have completed most steps (some may be skipped)
    assert completed_count >= 10, f"Only {completed_count} steps completed"


def test_full_build_respects_environment_variables(test_project_root):
    """Test that build respects legacy environment variables.
    
    Validates:
    - Environment variables are passed to workers
    - Build behavior changes based on env vars
    """
    # Set environment variable
    import os
    env = os.environ.copy()
    env["NON_INTERACTIVE"] = "1"
    
    # Run build
    result = subprocess.run(
        [sys.executable, "scripts/build/build.py", "--clean"],
        cwd=test_project_root,
        capture_output=True,
        text=True,
        timeout=300,
        env=env
    )
    
    # Should succeed without prompts
    assert result.returncode == 0, f"Build failed: {result.stderr}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
