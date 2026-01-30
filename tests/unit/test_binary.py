"""Unit tests for PyInstaller binary.

Tests verify that the standalone binary:
- Executes successfully
- Has all commands available
- Displays version information correctly
- Has size under 25MB

Requirements: 11.2, 11.3, 11.4
"""

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def binary_path() -> Path:
    """Get path to binary.

    Returns:
        Path to opencenter-airgap binary
    """
    binary = Path("dist/opencenter-airgap")
    if not binary.exists():
        pytest.skip("Binary not built - run 'pyinstaller opencenter-airgap.spec' first")
    return binary


def test_binary_exists(binary_path: Path) -> None:
    """Test that binary exists and is executable.

    Validates: Requirement 11.2 (binary is executable)
    """
    assert binary_path.exists(), "Binary does not exist"
    assert binary_path.is_file(), "Binary is not a file"

    # Check executable permission
    import os

    assert os.access(binary_path, os.X_OK), "Binary is not executable"


def test_binary_size(binary_path: Path) -> None:
    """Test that binary size is under 25MB.

    Validates: Requirement 11.4 (binary size <25MB)
    """
    size_bytes = binary_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)

    assert size_mb < 25, f"Binary size {size_mb:.1f}MB exceeds 25MB limit"


def test_binary_execution(binary_path: Path) -> None:
    """Test that binary executes successfully.

    Validates: Requirement 11.2 (binary is executable)
    """
    result = subprocess.run(
        [str(binary_path), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, f"Binary failed with exit code {result.returncode}"
    assert "opencenter-airgap" in result.stdout.lower(), "Binary help output missing"


def test_binary_version_command(binary_path: Path) -> None:
    """Test that version command works.

    Validates: Requirement 11.3 (version output)
    """
    result = subprocess.run(
        [str(binary_path), "version"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, f"Version command failed with exit code {result.returncode}"
    assert "opencenter-airgap" in result.stdout.lower(), "Version output missing tool name"
    assert "version" in result.stdout.lower(), "Version output missing version info"
    assert "python" in result.stdout.lower(), "Version output missing Python version"


def test_binary_commands_available(binary_path: Path) -> None:
    """Test that all expected commands are available.

    Validates: Requirement 11.3 (command availability)
    """
    result = subprocess.run(
        [str(binary_path), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, "Help command failed"

    # Check for expected commands
    expected_commands = [
        "init",
        "add",
        "scan",
        "generate-manifest",
        "build",
        "validate",
        "verify",
        "status",
        "clean",
        "serve",
        "version",
    ]

    for command in expected_commands:
        assert command in result.stdout, f"Command '{command}' not found in help output"


def test_binary_init_command_help(binary_path: Path) -> None:
    """Test that init command help works.

    Validates: Requirement 11.3 (command availability)
    """
    result = subprocess.run(
        [str(binary_path), "init", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, "Init help command failed"
    assert "init" in result.stdout.lower(), "Init help output missing"
    assert "--create-manifest" in result.stdout, "Init help missing --create-manifest option"


def test_binary_scan_command_help(binary_path: Path) -> None:
    """Test that scan command help works.

    Validates: Requirement 11.3 (command availability)
    """
    result = subprocess.run(
        [str(binary_path), "scan", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, "Scan help command failed"
    assert "scan" in result.stdout.lower(), "Scan help output missing"
    assert "--repo" in result.stdout, "Scan help missing --repo option"


def test_binary_build_command_help(binary_path: Path) -> None:
    """Test that build command help works.

    Validates: Requirement 11.3 (command availability)
    """
    result = subprocess.run(
        [str(binary_path), "build", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, "Build help command failed"
    assert "build" in result.stdout.lower(), "Build help output missing"
    assert "--clean" in result.stdout, "Build help missing --clean option"
    assert "--resume" in result.stdout, "Build help missing --resume option"


def test_binary_validate_command_help(binary_path: Path) -> None:
    """Test that validate command help works.

    Validates: Requirement 11.3 (command availability)
    """
    result = subprocess.run(
        [str(binary_path), "validate", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, "Validate help command failed"
    assert "validate" in result.stdout.lower(), "Validate help output missing"
    assert "--strict" in result.stdout, "Validate help missing --strict option"


def test_binary_no_python_required(binary_path: Path) -> None:
    """Test that binary runs without Python in PATH.

    This test verifies that the binary is truly standalone and doesn't
    require Python to be installed on the system.

    Validates: Requirement 11.4 (includes all dependencies)
    """
    import os

    # Create environment without Python in PATH
    env = os.environ.copy()

    # Remove Python-related paths
    if "PYTHONPATH" in env:
        del env["PYTHONPATH"]
    if "PYTHONHOME" in env:
        del env["PYTHONHOME"]

    # Minimal PATH (exclude Python directories)
    env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"

    result = subprocess.run(
        [str(binary_path), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )

    assert result.returncode == 0, "Binary requires Python in PATH"
    assert "opencenter-airgap" in result.stdout.lower(), "Binary failed without Python"


def test_binary_dependencies_included(binary_path: Path) -> None:
    """Test that binary includes all required dependencies.

    Validates: Requirement 11.4 (includes all dependencies)
    """
    result = subprocess.run(
        [str(binary_path), "version"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, "Version command failed"

    # Check for key dependencies in version output
    expected_deps = ["typer", "pyyaml", "jsonschema"]

    for dep in expected_deps:
        assert dep in result.stdout.lower(), f"Dependency '{dep}' not found in version output"
