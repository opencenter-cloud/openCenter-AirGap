"""Validation workers for build outputs and configurations.

Provides validation functions for version pinning, zarf.yaml syntax,
and final build outputs.
"""

import subprocess
import yaml
from pathlib import Path
from typing import List, Optional
import sys

# Add parent directory to path to import version_validator
sys.path.insert(0, str(Path(__file__).parent.parent))
from version_validator import VersionValidator


def validate_versions_worker(project_root: Path) -> bool:
    """Validate version pinning in config/versions.env.
    
    Ensures all versions are pinned to specific versions (no "latest", wildcards, etc.)
    Reports violations as warnings but does not fail the build.
    
    Args:
        project_root: Root directory of the project
        
    Returns:
        True (always succeeds, violations are warnings only)
    """
    print("\n=== Validating Version Pinning ===\n")
    
    config_dir = project_root / "config"
    if not config_dir.exists():
        print("WARNING: config/ directory not found")
        return True  # Non-blocking
    
    # Run version validator on config directory
    validator = VersionValidator(config_dir)
    is_valid = validator.validate()
    
    violations_report = validator.report_violations()
    
    if not is_valid:
        print(violations_report)
        print("\n⚠ Version pinning validation found issues")
        print("WARNING: Some versions are not pinned to specific versions.")
        print("This may affect build reproducibility.")
        print("Consider pinning: 'latest', 'stable', 'master', 'main' tags\n")
        # Return True to make this non-blocking
        return True
    
    print("\n✓ Version pinning validation passed\n")
    return True


def validate_zarf_yaml_worker(project_root: Path) -> bool:
    """Validate zarf.yaml syntax and structure.
    
    Checks:
    - File exists
    - Valid YAML syntax
    - Required fields present (kind, metadata, components)
    - Component structure is valid
    
    Args:
        project_root: Root directory of the project
        
    Returns:
        True if zarf.yaml is valid, False otherwise
    """
    print("\n=== Validating zarf.yaml ===\n")
    
    zarf_yaml = project_root / "zarf.yaml"
    
    # Check file exists
    if not zarf_yaml.exists():
        print(f"ERROR: zarf.yaml not found at: {zarf_yaml}")
        return False
    print("✓ zarf.yaml exists")
    
    # Parse YAML
    try:
        with open(zarf_yaml, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"ERROR: Invalid YAML syntax: {e}")
        return False
    print("✓ Valid YAML syntax")
    
    # Validate required top-level fields
    required_fields = ['kind', 'metadata', 'components']
    missing_fields = [field for field in required_fields if field not in config]
    
    if missing_fields:
        print(f"ERROR: Missing required fields: {', '.join(missing_fields)}")
        return False
    print(f"✓ Required fields present: {', '.join(required_fields)}")
    
    # Validate kind
    if config.get('kind') != 'ZarfPackageConfig':
        print(f"ERROR: Invalid kind: {config.get('kind')} (expected: ZarfPackageConfig)")
        return False
    print("✓ Valid kind: ZarfPackageConfig")
    
    # Validate metadata
    metadata = config.get('metadata', {})
    if not isinstance(metadata, dict):
        print("ERROR: metadata must be a dictionary")
        return False
    
    required_metadata = ['name', 'version']
    missing_metadata = [field for field in required_metadata if field not in metadata]
    if missing_metadata:
        print(f"ERROR: Missing required metadata fields: {', '.join(missing_metadata)}")
        return False
    print(f"✓ Valid metadata: name={metadata['name']}, version={metadata['version']}")
    
    # Validate components
    components = config.get('components', [])
    if not isinstance(components, list):
        print("ERROR: components must be a list")
        return False
    
    if len(components) == 0:
        print("ERROR: At least one component is required")
        return False
    print(f"✓ {len(components)} components defined")
    
    # Validate each component
    for i, component in enumerate(components):
        if not isinstance(component, dict):
            print(f"ERROR: Component {i} is not a dictionary")
            return False
        
        if 'name' not in component:
            print(f"ERROR: Component {i} missing 'name' field")
            return False
        
        print(f"  ✓ Component: {component['name']}")
    
    # Optional: Validate with zarf CLI if available
    zarf_cli = _find_zarf_cli()
    if zarf_cli:
        print("\nValidating with zarf CLI...")
        result = subprocess.run(
            [zarf_cli, "package", "inspect", str(zarf_yaml)],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"WARNING: zarf CLI validation failed: {result.stderr}")
            # Don't fail the build, just warn
        else:
            print("✓ zarf CLI validation passed")
    
    print("\n✓ zarf.yaml validation passed\n")
    return True


def validate_build_outputs_worker(project_root: Path) -> bool:
    """Validate final build outputs and package integrity.
    
    Checks:
    - Zarf package exists in dist/
    - Package has expected naming format
    - Checksum files exist
    - SBOM file exists (if inspect_package ran)
    
    Args:
        project_root: Root directory of the project
        
    Returns:
        True if all outputs are valid, False otherwise
    """
    print("\n=== Validating Build Outputs ===\n")
    
    dist_dir = project_root / "dist"
    
    # Check dist directory exists
    if not dist_dir.exists():
        print("ERROR: dist/ directory not found")
        return False
    print("✓ dist/ directory exists")
    
    # Find Zarf package
    zarf_packages = list(dist_dir.glob("zarf-package-*.tar.zst"))
    
    if len(zarf_packages) == 0:
        print("ERROR: No Zarf package found in dist/")
        return False
    
    if len(zarf_packages) > 1:
        print(f"WARNING: Multiple Zarf packages found: {len(zarf_packages)}")
    
    package = zarf_packages[0]
    print(f"✓ Zarf package found: {package.name}")
    
    # Check package size
    package_size_mb = package.stat().st_size / (1024 * 1024)
    print(f"  Package size: {package_size_mb:.2f} MB")
    
    if package_size_mb < 100:
        print(f"  WARNING: Package seems small (< 100 MB)")
    
    # Check for checksum files
    checksums_found = []
    for ext in ['.sha256', '.md5']:
        checksum_file = dist_dir / f"{package.stem}{ext}"
        if checksum_file.exists():
            checksums_found.append(ext)
            print(f"✓ Checksum file found: {checksum_file.name}")
    
    if not checksums_found:
        print("WARNING: No checksum files found")
    
    # Check for SBOM
    sbom_files = list(dist_dir.glob("*sbom*.json")) + list(dist_dir.glob("*sbom*.txt"))
    if sbom_files:
        for sbom in sbom_files:
            print(f"✓ SBOM file found: {sbom.name}")
    else:
        print("INFO: No SBOM files found (inspect_package may not have run)")
    
    # Check for signature
    sig_files = list(dist_dir.glob("*.sig")) + list(dist_dir.glob("*.asc"))
    if sig_files:
        for sig in sig_files:
            print(f"✓ Signature file found: {sig.name}")
    else:
        print("INFO: No signature files found (sign_package may not have run)")
    
    print("\n✓ Build outputs validation passed\n")
    return True


def _find_zarf_cli() -> Optional[str]:
    """Find zarf CLI in PATH.
    
    Returns:
        Path to zarf CLI if found, None otherwise
    """
    import shutil
    return shutil.which("zarf")
