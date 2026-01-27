"""Checksum generation worker.

Generates SHA256 and MD5 checksums for the Zarf package to enable
integrity verification during deployment.
"""

import hashlib
from pathlib import Path
from typing import Tuple


def generate_checksums_worker(project_root: Path) -> bool:
    """Generate SHA256 and MD5 checksums for Zarf package.
    
    Creates checksum files in dist/ directory:
    - <package>.sha256 - SHA256 checksum
    - <package>.md5 - MD5 checksum
    
    Args:
        project_root: Root directory of the project
        
    Returns:
        True if checksums generated successfully, False otherwise
    """
    print("\n=== Generating Checksums ===\n")
    
    dist_dir = project_root / "dist"
    
    # Find Zarf package
    if not dist_dir.exists():
        print("ERROR: dist/ directory not found")
        return False
    
    zarf_packages = list(dist_dir.glob("zarf-package-*.tar.zst"))
    
    if len(zarf_packages) == 0:
        print("ERROR: No Zarf package found in dist/")
        return False
    
    if len(zarf_packages) > 1:
        print(f"WARNING: Multiple Zarf packages found, using: {zarf_packages[0].name}")
    
    package = zarf_packages[0]
    print(f"Package: {package.name}")
    print(f"Size: {package.stat().st_size / (1024 * 1024):.2f} MB\n")
    
    # Generate checksums
    print("Calculating checksums...")
    sha256_hash, md5_hash = _calculate_checksums(package)
    
    # Write SHA256
    sha256_file = dist_dir / f"{package.name}.sha256"
    with open(sha256_file, 'w') as f:
        f.write(f"{sha256_hash}  {package.name}\n")
    print(f"✓ SHA256: {sha256_hash}")
    print(f"  Written to: {sha256_file.name}")
    
    # Write MD5
    md5_file = dist_dir / f"{package.name}.md5"
    with open(md5_file, 'w') as f:
        f.write(f"{md5_hash}  {package.name}\n")
    print(f"✓ MD5: {md5_hash}")
    print(f"  Written to: {md5_file.name}")
    
    print("\n✓ Checksums generated successfully\n")
    return True


def _calculate_checksums(file_path: Path, chunk_size: int = 8192) -> Tuple[str, str]:
    """Calculate SHA256 and MD5 checksums for a file.
    
    Args:
        file_path: Path to file
        chunk_size: Size of chunks to read (default: 8KB)
        
    Returns:
        Tuple of (sha256_hex, md5_hex)
    """
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)
            md5.update(chunk)
    
    return sha256.hexdigest(), md5.hexdigest()
