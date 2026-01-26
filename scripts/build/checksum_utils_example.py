#!/usr/bin/env python3
"""
Example usage of checksum_utils.py for openCenter AirGap.

This demonstrates how to use the checksum utilities in build scripts.
"""

from pathlib import Path
from checksum_utils import (
    calculate_md5,
    calculate_sha256,
    calculate_checksums,
    verify_checksum,
    download_file,
    ChecksumError,
    DownloadError
)


def example_calculate_checksums():
    """Example: Calculate checksums for a file."""
    filepath = Path("config/versions.env")
    
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return
    
    # Calculate individual checksums
    md5 = calculate_md5(filepath)
    sha256 = calculate_sha256(filepath)
    
    print(f"File: {filepath}")
    print(f"MD5:    {md5}")
    print(f"SHA256: {sha256}")
    
    # Or calculate both at once
    md5, sha256 = calculate_checksums(filepath)


def example_verify_checksum():
    """Example: Verify file checksum."""
    filepath = Path("config/versions.env")
    expected_sha256 = "abc123..."  # Replace with actual checksum
    
    try:
        if verify_checksum(filepath, expected_sha256, algorithm="sha256"):
            print("✓ Checksum verified")
        else:
            print("✗ Checksum mismatch")
    except ChecksumError as e:
        print(f"Error: {e}")


def example_download_with_verification():
    """Example: Download file with checksum verification."""
    url = "https://github.com/kubernetes/kubernetes/releases/download/v1.28.6/kubernetes.tar.gz"
    destination = Path("build/downloads/kubernetes.tar.gz")
    expected_sha256 = "abc123..."  # Replace with actual checksum from release notes
    
    try:
        result = download_file(
            url=url,
            destination=destination,
            max_retries=3,
            retry_delay=5,
            timeout=60,
            expected_checksum=expected_sha256,
            checksum_algorithm="sha256"
        )
        print(f"✓ Downloaded and verified: {result}")
    except DownloadError as e:
        print(f"✗ Download failed: {e}")
    except ChecksumError as e:
        print(f"✗ Checksum verification failed: {e}")


def example_download_without_verification():
    """Example: Download file without checksum verification."""
    url = "https://example.com/file.tar.gz"
    destination = Path("build/downloads/file.tar.gz")
    
    try:
        result = download_file(
            url=url,
            destination=destination,
            max_retries=3,
            retry_delay=5,
            timeout=30
        )
        print(f"✓ Downloaded: {result}")
        
        # Calculate checksum after download
        sha256 = calculate_sha256(result)
        print(f"SHA256: {sha256}")
    except DownloadError as e:
        print(f"✗ Download failed: {e}")


if __name__ == "__main__":
    print("Checksum Utilities Examples")
    print("=" * 50)
    
    print("\n1. Calculate checksums:")
    example_calculate_checksums()
    
    print("\n2. Verify checksum:")
    example_verify_checksum()
    
    print("\n3. Download with verification:")
    print("   (See function for usage)")
    
    print("\n4. Download without verification:")
    print("   (See function for usage)")
