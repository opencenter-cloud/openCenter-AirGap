"""Python environment setup worker.

Creates and configures the Python virtual environment with all required
dependencies for the build system.
"""

import subprocess
from pathlib import Path
from typing import List


def setup_python_env_worker(project_root: Path) -> bool:
    """Setup Python virtual environment and install dependencies.
    
    Creates a virtual environment at project_root/venv and installs:
    - PyYAML
    - Jinja2
    - requests
    - hypothesis
    - pytest
    - rich
    
    Args:
        project_root: Root directory of the project
        
    Returns:
        True if setup succeeds, False otherwise
    """
    print("\n=== Setting Up Python Environment ===\n")
    
    venv_dir = project_root / "venv"
    
    # Create venv if it doesn't exist
    if not venv_dir.exists():
        print("Creating Python virtual environment...")
        result = subprocess.run(
            ["python3", "-m", "venv", str(venv_dir)],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"ERROR: Failed to create venv: {result.stderr}")
            return False
        
        print("✓ Virtual environment created")
    else:
        print("✓ Virtual environment already exists")
    
    # Install dependencies
    pip_path = venv_dir / "bin" / "pip"
    print("\nInstalling Python dependencies...")
    
    packages = [
        "pyyaml",
        "jinja2",
        "requests",
        "hypothesis",
        "pytest",
        "rich"
    ]
    
    # Upgrade pip first
    result = subprocess.run(
        [str(pip_path), "install", "--upgrade", "pip"],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"WARNING: Failed to upgrade pip: {result.stderr}")
    else:
        print("✓ pip upgraded")
    
    # Install packages
    result = subprocess.run(
        [str(pip_path), "install"] + packages,
        cwd=project_root,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"ERROR: Failed to install dependencies: {result.stderr}")
        return False
    
    print(f"✓ Installed {len(packages)} packages")
    
    # List installed packages for verification
    result = subprocess.run(
        [str(pip_path), "list", "--format=columns"],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("\nInstalled packages:")
        for line in result.stdout.strip().split('\n')[2:]:  # Skip header lines
            if any(pkg in line.lower() for pkg in packages):
                print(f"  {line}")
    
    print("\n✓ Python environment ready\n")
    return True


def validate_python_env(project_root: Path) -> bool:
    """Validate Python environment is properly configured.
    
    Checks:
    - venv directory exists
    - python3 binary exists in venv
    - Required packages are installed
    
    Args:
        project_root: Root directory of the project
        
    Returns:
        True if validation passes, False otherwise
    """
    print("\n=== Validating Python Environment ===\n")
    
    venv_dir = project_root / "venv"
    
    # Check venv directory
    if not venv_dir.exists():
        print("ERROR: venv directory does not exist")
        return False
    print("✓ venv directory exists")
    
    # Check python3 binary
    python_path = venv_dir / "bin" / "python3"
    if not python_path.exists():
        print("ERROR: venv python3 binary not found")
        return False
    print("✓ python3 binary exists")
    
    # Check pip
    pip_path = venv_dir / "bin" / "pip"
    if not pip_path.exists():
        print("ERROR: venv pip not found")
        return False
    print("✓ pip exists")
    
    # Verify required packages
    result = subprocess.run(
        [str(pip_path), "list", "--format=freeze"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"ERROR: Failed to list installed packages: {result.stderr}")
        return False
    
    required = ["pyyaml", "jinja2", "requests", "hypothesis", "pytest", "rich"]
    installed = result.stdout.lower()
    
    missing = []
    for package in required:
        if package not in installed:
            missing.append(package)
        else:
            print(f"✓ {package} installed")
    
    if missing:
        print(f"\nERROR: Missing required packages: {', '.join(missing)}")
        return False
    
    print("\n✓ Python environment validation passed\n")
    return True
