#!/usr/bin/env python3
"""
Checksum calculation and file download utilities for openCenter AirGap.

This module provides utilities for:
- MD5 checksum calculation (Requirement 1.10, 2.6)
- SHA256 checksum calculation (Requirement 1.10, 2.6)
- File download with retry logic (Requirement 1.10)

All functions are designed to work in the project venv (Python 3.12+).
"""

import hashlib
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


class ChecksumError(Exception):
    """Raised when checksum calculation or verification fails."""
    pass


class DownloadError(Exception):
    """Raised when file download fails after all retries."""
    pass


def calculate_md5(filepath: Path) -> str:
    """
    Calculate MD5 checksum of a file.
    
    Args:
        filepath: Path to the file to checksum
        
    Returns:
        Hexadecimal MD5 checksum string
        
    Raises:
        ChecksumError: If file cannot be read or checksum calculation fails
        
    Requirements: 1.10, 2.6
    """
    if not filepath.exists():
        raise ChecksumError(f"File not found: {filepath}")
    
    if not filepath.is_file():
        raise ChecksumError(f"Not a file: {filepath}")
    
    try:
        md5_hash = hashlib.md5()
        with open(filepath, "rb") as f:
            # Read in 64KB chunks to handle large files efficiently
            for chunk in iter(lambda: f.read(65536), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except OSError as e:
        raise ChecksumError(f"Failed to read file {filepath}: {e}") from e


def calculate_sha256(filepath: Path) -> str:
    """
    Calculate SHA256 checksum of a file.
    
    Args:
        filepath: Path to the file to checksum
        
    Returns:
        Hexadecimal SHA256 checksum string
        
    Raises:
        ChecksumError: If file cannot be read or checksum calculation fails
        
    Requirements: 1.10, 2.6
    """
    if not filepath.exists():
        raise ChecksumError(f"File not found: {filepath}")
    
    if not filepath.is_file():
        raise ChecksumError(f"Not a file: {filepath}")
    
    try:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            # Read in 64KB chunks to handle large files efficiently
            for chunk in iter(lambda: f.read(65536), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except OSError as e:
        raise ChecksumError(f"Failed to read file {filepath}: {e}") from e


def calculate_checksums(filepath: Path) -> Tuple[str, str]:
    """
    Calculate both MD5 and SHA256 checksums of a file.
    
    Args:
        filepath: Path to the file to checksum
        
    Returns:
        Tuple of (md5_checksum, sha256_checksum)
        
    Raises:
        ChecksumError: If file cannot be read or checksum calculation fails
        
    Requirements: 1.10, 2.6
    """
    return (calculate_md5(filepath), calculate_sha256(filepath))


def verify_checksum(filepath: Path, expected_checksum: str, algorithm: str = "sha256") -> bool:
    """
    Verify file checksum against expected value.
    
    Args:
        filepath: Path to the file to verify
        expected_checksum: Expected checksum value (hexadecimal string)
        algorithm: Hash algorithm to use ("md5" or "sha256")
        
    Returns:
        True if checksum matches, False otherwise
        
    Raises:
        ChecksumError: If file cannot be read or algorithm is invalid
        ValueError: If algorithm is not supported
        
    Requirements: 1.10, 2.6
    """
    algorithm = algorithm.lower()
    
    if algorithm == "md5":
        actual_checksum = calculate_md5(filepath)
    elif algorithm == "sha256":
        actual_checksum = calculate_sha256(filepath)
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}. Use 'md5' or 'sha256'.")
    
    return actual_checksum.lower() == expected_checksum.lower()


def download_file(
    url: str,
    destination: Path,
    max_retries: int = 3,
    retry_delay: int = 5,
    timeout: int = 30,
    expected_checksum: Optional[str] = None,
    checksum_algorithm: str = "sha256"
) -> Path:
    """
    Download a file from URL with retry logic and optional checksum verification.
    
    Args:
        url: URL to download from
        destination: Path where file should be saved
        max_retries: Maximum number of retry attempts (default: 3)
        retry_delay: Delay in seconds between retries (default: 5)
        timeout: Request timeout in seconds (default: 30)
        expected_checksum: Optional checksum to verify after download
        checksum_algorithm: Algorithm for checksum verification ("md5" or "sha256")
        
    Returns:
        Path to the downloaded file
        
    Raises:
        DownloadError: If download fails after all retries
        ChecksumError: If checksum verification fails
        
    Requirements: 1.10
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            # Create request with user agent to avoid blocks
            request = Request(
                url,
                headers={"User-Agent": "openCenter-AirGap/1.0"}
            )
            
            # Download file
            with urlopen(request, timeout=timeout) as response:
                content = response.read()
            
            # Write to destination
            with open(destination, "wb") as f:
                f.write(content)
            
            # Verify checksum if provided
            if expected_checksum:
                if not verify_checksum(destination, expected_checksum, checksum_algorithm):
                    actual = (calculate_md5(destination) if checksum_algorithm == "md5" 
                             else calculate_sha256(destination))
                    raise ChecksumError(
                        f"Checksum mismatch for {url}\n"
                        f"Expected: {expected_checksum}\n"
                        f"Actual: {actual}"
                    )
            
            return destination
            
        except (URLError, HTTPError, OSError) as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            else:
                break
    
    # All retries exhausted
    raise DownloadError(
        f"Failed to download {url} after {max_retries} attempts. "
        f"Last error: {last_error}"
    ) from last_error


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: checksum_utils.py <file> [algorithm]")
        print("  algorithm: md5 or sha256 (default: both)")
        sys.exit(1)
    
    filepath = Path(sys.argv[1])
    algorithm = sys.argv[2].lower() if len(sys.argv) > 2 else "both"
    
    try:
        if algorithm == "md5":
            print(f"MD5: {calculate_md5(filepath)}")
        elif algorithm == "sha256":
            print(f"SHA256: {calculate_sha256(filepath)}")
        else:
            md5, sha256 = calculate_checksums(filepath)
            print(f"MD5:    {md5}")
            print(f"SHA256: {sha256}")
    except ChecksumError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
