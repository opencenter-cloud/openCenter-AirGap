#!/usr/bin/env python3
"""
Generate checksum manifest for Zarf packages.

This script generates MD5 and SHA256 checksums for a Zarf package file
and writes them to a manifest file for integrity verification.

Requirements: 2.6
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

# Import from checksum_utils in the same directory
try:
    from checksum_utils import calculate_checksums, ChecksumError
except ImportError:
    # Handle case where script is run directly
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from checksum_utils import calculate_checksums, ChecksumError


def generate_manifest(
    package_path: Path,
    output_path: Path = None,
    format: str = "json"
) -> Dict[str, Any]:
    """
    Generate checksum manifest for a Zarf package.
    
    Args:
        package_path: Path to the Zarf package file
        output_path: Path where manifest should be written (default: <package>.checksums.json)
        format: Output format ("json" or "text")
        
    Returns:
        Dictionary containing manifest data
        
    Raises:
        ChecksumError: If checksum calculation fails
        FileNotFoundError: If package file doesn't exist
    """
    package_path = Path(package_path)
    
    if not package_path.exists():
        raise FileNotFoundError(f"Package file not found: {package_path}")
    
    if not package_path.is_file():
        raise ValueError(f"Not a file: {package_path}")
    
    # Calculate checksums
    print(f"Calculating checksums for {package_path.name}...", file=sys.stderr)
    md5_checksum, sha256_checksum = calculate_checksums(package_path)
    
    # Get file metadata
    file_size = package_path.stat().st_size
    
    # Build manifest
    manifest = {
        "package": {
            "name": package_path.name,
            "path": str(package_path.absolute()),
            "size_bytes": file_size,
            "size_human": format_size(file_size)
        },
        "checksums": {
            "md5": md5_checksum,
            "sha256": sha256_checksum
        },
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generator": "openCenter-AirGap checksum manifest generator v1.0"
        }
    }
    
    # Determine output path
    if output_path is None:
        if format == "json":
            output_path = package_path.with_suffix(package_path.suffix + ".checksums.json")
        else:
            output_path = package_path.with_suffix(package_path.suffix + ".checksums.txt")
    else:
        output_path = Path(output_path)
    
    # Write manifest
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if format == "json":
        with open(output_path, "w") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")  # Add trailing newline
        print(f"JSON manifest written to: {output_path}", file=sys.stderr)
    else:
        with open(output_path, "w") as f:
            f.write(f"# Checksum Manifest\n")
            f.write(f"# Package: {manifest['package']['name']}\n")
            f.write(f"# Size: {manifest['package']['size_human']}\n")
            f.write(f"# Generated: {manifest['metadata']['generated_at']}\n")
            f.write(f"\n")
            f.write(f"MD5:    {manifest['checksums']['md5']}\n")
            f.write(f"SHA256: {manifest['checksums']['sha256']}\n")
        print(f"Text manifest written to: {output_path}", file=sys.stderr)
    
    return manifest


def format_size(size_bytes: int) -> str:
    """
    Format byte size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Human-readable size string (e.g., "1.5 GB")
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description="Generate checksum manifest for Zarf packages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate JSON manifest (default)
  %(prog)s zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
  
  # Generate text manifest
  %(prog)s --format text zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
  
  # Specify output path
  %(prog)s -o checksums.json zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
        """
    )
    
    parser.add_argument(
        "package",
        type=Path,
        help="Path to Zarf package file"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output path for manifest (default: <package>.checksums.json)"
    )
    
    parser.add_argument(
        "-f", "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)"
    )
    
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print checksums to stdout in addition to writing file"
    )
    
    args = parser.parse_args()
    
    try:
        manifest = generate_manifest(
            package_path=args.package,
            output_path=args.output,
            format=args.format
        )
        
        if args.print:
            print(f"\nChecksums for {manifest['package']['name']}:")
            print(f"  MD5:    {manifest['checksums']['md5']}")
            print(f"  SHA256: {manifest['checksums']['sha256']}")
        
        return 0
        
    except (ChecksumError, FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
