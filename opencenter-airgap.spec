# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for opencenter-airgap binary.

This spec file configures PyInstaller to create a standalone binary
for the openCenter AirGap build system targeting Ubuntu 24.04 AMD64.

Requirements:
- Binary name: opencenter-airgap
- Target: Ubuntu 24.04 AMD64
- Size: <25MB
- Include all Python dependencies
"""

import sys
from pathlib import Path

# Determine project root
project_root = Path(SPECPATH)
src_path = project_root / "src"

# Analysis: Discover all Python files and dependencies
a = Analysis(
    # Entry point script
    [str(src_path / "opencenter_build" / "cli.py")],

    # Additional paths to search for imports
    pathex=[str(src_path)],

    # Binary dependencies (none for pure Python)
    binaries=[],

    # Data files to include
    datas=[
        # Include JSON schemas if they exist
        (str(project_root / "config" / "schemas" / "*.json"), "config/schemas"),
    ],

    # Hidden imports that PyInstaller might miss
    hiddenimports=[
        "opencenter_build",
        "opencenter_build.cli",
        "opencenter_build.config",
        "opencenter_build.state",
        "opencenter_build.scanner",
        "opencenter_build.orchestrator",
        "opencenter_build.zarf_generator",
        "opencenter_build.manifest",
        "opencenter_build.validation",
        "opencenter_build.verifier",
        "opencenter_build.component_manifest",
        "opencenter_build.exceptions",
        "opencenter_build.logging_config",
        "opencenter_build.metrics",
        "opencenter_build.workers",
        "opencenter_build.image_manager",
        "opencenter_build.transaction",
        # Third-party dependencies
        "typer",
        "rich",
        "rich.console",
        "rich.progress",
        "rich.table",
        "rich.panel",
        "yaml",
        "jsonschema",
        "dotenv",
    ],

    # Hooks directory (if custom hooks needed)
    hookspath=[],

    # Runtime hooks
    hooksconfig={},

    # Modules to exclude (reduce size)
    excludes=[
        # Test frameworks
        "pytest",
        "hypothesis",
        "unittest",
        "test",
        "tests",
        # Development tools
        "black",
        "mypy",
        "pylint",
        "setuptools",
        "pip",
        "wheel",
        # Unused standard library modules
        "tkinter",
        "turtle",
        "pydoc",
        "doctest",
        "pdb",
        "profile",
        "cProfile",
        "pstats",
        # Unused encodings (keep only UTF-8 and ASCII)
        "encodings.cp*",
        "encodings.iso*",
        "encodings.mac*",
        "encodings.shift*",
        "encodings.big5*",
        "encodings.gb*",
        "encodings.euc*",
        "encodings.hz*",
        "encodings.johab*",
        "encodings.koi*",
        "encodings.ptcp*",
    ],

    # Don't collect submodules for these packages
    noarchive=False,

    # Optimize Python bytecode
    optimize=2,
)

# PYZ: Create Python archive
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None,
)

# EXE: Create executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],

    # Binary name
    name="opencenter-airgap",

    # Debug options
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # Strip symbols to reduce size
    upx=True,    # Use UPX compression
    upx_exclude=[],

    # Runtime options
    runtime_tmpdir=None,
    console=True,  # Console application
    disable_windowed_traceback=False,

    # Target architecture
    target_arch=None,  # Use host architecture (AMD64)
    codesign_identity=None,
    entitlements_file=None,

    # Single file bundle
    onefile=True,
)
