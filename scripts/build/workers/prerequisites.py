"""Prerequisites checking worker.

Validates that all required tools and resources are available before
starting the build process.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Tuple, List


def check_prerequisites_worker(project_root: Path) -> bool:
    """Check all build prerequisites.
    
    Validates:
    - Python 3.12+
    - Container runtime (podman or docker)
    - git
    - jq
    - zarf (optional, warns if missing)
    - Disk space (100GB+ recommended)
    
    Args:
        project_root: Root directory of the project
        
    Returns:
        True if all required prerequisites are satisfied, False otherwise
    """
    print("\n=== Checking Build Prerequisites ===\n")
    
    missing: List[str] = []
    warnings: List[str] = []
    
    # Check Python version
    if not _check_python_version():
        missing.append("python3.12+")
    
    # Check container runtime
    if not _check_container_runtime():
        missing.append("podman or docker")
    
    # Check git
    if not _check_git():
        missing.append("git")
    
    # Check jq
    if not _check_jq():
        missing.append("jq")
    
    # Check zarf (optional)
    if not _check_zarf():
        warnings.append("Zarf CLI not found (will be needed for package creation)")
    
    # Check disk space
    disk_warning = _check_disk_space(project_root)
    if disk_warning:
        warnings.append(disk_warning)
    
    # Print warnings
    if warnings:
        print("\nWARNINGS:")
        for warning in warnings:
            print(f"  ⚠ {warning}")
    
    # Check for missing dependencies
    if missing:
        print("\nERROR: Missing required dependencies:")
        for dep in missing:
            print(f"  ✗ {dep}")
        print("\nPlease install missing dependencies and re-run the build.")
        return False
    
    print("\n✓ All required prerequisites satisfied\n")
    return True


def _check_python_version() -> bool:
    """Check Python version is 3.12 or higher."""
    try:
        result = subprocess.run(
            ["python3", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        version_str = result.stdout.split()[1]
        major, minor = map(int, version_str.split('.')[:2])
        
        if major < 3 or (major == 3 and minor < 12):
            print(f"✗ Python 3.12+ required, found: {version_str}")
            return False
        
        print(f"✓ Python version: {version_str}")
        return True
        
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError, IndexError):
        print("✗ Python 3 not found or version check failed")
        return False


def _check_container_runtime() -> bool:
    """Check for podman or docker."""
    # Try podman first
    if shutil.which("podman"):
        try:
            result = subprocess.run(
                ["podman", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✓ Container runtime: {result.stdout.strip()}")
            return True
        except subprocess.CalledProcessError:
            pass
    
    # Try docker
    if shutil.which("docker"):
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✓ Container runtime: {result.stdout.strip()}")
            return True
        except subprocess.CalledProcessError:
            pass
    
    print("✗ Neither podman nor docker found")
    return False


def _check_git() -> bool:
    """Check for git."""
    if not shutil.which("git"):
        print("✗ git not found")
        return False
    
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✓ {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError:
        print("✗ git found but version check failed")
        return False


def _check_jq() -> bool:
    """Check for jq."""
    if not shutil.which("jq"):
        print("✗ jq not found")
        return False
    
    try:
        result = subprocess.run(
            ["jq", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✓ {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError:
        print("✗ jq found but version check failed")
        return False


def _check_zarf() -> bool:
    """Check for zarf (optional)."""
    if not shutil.which("zarf"):
        return False
    
    try:
        result = subprocess.run(
            ["zarf", "version"],
            capture_output=True,
            text=True,
            check=True
        )
        # Extract version from output
        version_line = result.stdout.strip().split('\n')[0]
        print(f"✓ Zarf: {version_line}")
        return True
    except subprocess.CalledProcessError:
        return False


def _check_disk_space(project_root: Path) -> str:
    """Check available disk space.
    
    Returns:
        Warning message if disk space is low, empty string otherwise
    """
    try:
        stat = shutil.disk_usage(project_root)
        available_gb = stat.free // (1024 ** 3)
        
        if available_gb < 100:
            return f"Low disk space: {available_gb}GB available (100GB+ recommended)"
        
        print(f"✓ Disk space: {available_gb}GB available")
        return ""
        
    except Exception as e:
        return f"Could not check disk space: {e}"
