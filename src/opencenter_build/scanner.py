"""Repository scanner for container image discovery.

This module provides concurrent repository scanning to discover container
images in Git repositories. Uses ProcessPoolExecutor for parallel processing
and memory-mapped I/O for large files.
"""

import mmap
import multiprocessing
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
from typing import Pattern

from opencenter_build.exceptions import ScanError


# Default regex patterns for container image detection
DEFAULT_IMAGE_PATTERNS = [
    # Full image references: registry/repo:tag or registry/namespace/repo:tag
    r"(?:image|Image|IMAGE):\s*['\"]?([a-zA-Z0-9._-]+(?:[:/][a-zA-Z0-9._/-]+)+:[a-zA-Z0-9._-]+)['\"]?",
    # Docker Hub shorthand: namespace/image:tag
    r"(?:image|Image|IMAGE):\s*['\"]?([a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+:[a-zA-Z0-9._-]+)['\"]?",
    # Simple image:tag format (e.g., nginx:latest)
    r"(?:image|Image|IMAGE):\s+([a-zA-Z0-9._-]+:[a-zA-Z0-9._-]+)",
    # Helm values repository and tag (separate fields)
    r"repository:\s*['\"]?([a-zA-Z0-9._-]+(?:[:/][a-zA-Z0-9._/-]+)+)['\"]?",
    r"tag:\s*['\"]?([a-zA-Z0-9._-]+)['\"]?",
]

# File extensions to scan
SCANNABLE_EXTENSIONS = {
    ".yaml",
    ".yml",
    ".json",
    ".tf",
    ".hcl",
    ".toml",
    ".md",
    ".txt",
}

# Memory-mapped I/O threshold (1MB)
MMAP_THRESHOLD = 1024 * 1024


@lru_cache(maxsize=1)
def _compile_patterns(patterns: tuple[str, ...]) -> list[Pattern[str]]:
    """Compile and cache regex patterns.

    Uses lru_cache to compile patterns once and reuse across worker processes.
    Patterns are passed as tuple for hashability.

    Args:
        patterns: Tuple of regex pattern strings

    Returns:
        List of compiled regex patterns
    """
    return [re.compile(pattern) for pattern in patterns]


def _scan_file(file_path: Path, patterns: tuple[str, ...]) -> set[str]:
    """Scan single file for container images.

    Uses memory-mapped I/O for files larger than 1MB. Handles encoding
    errors gracefully by trying multiple encodings.

    Args:
        file_path: Path to file to scan
        patterns: Tuple of regex pattern strings

    Returns:
        Set of discovered image references
    """
    compiled_patterns = _compile_patterns(patterns)
    images: set[str] = set()

    try:
        file_size = file_path.stat().st_size

        # Use memory-mapped I/O for large files
        if file_size > MMAP_THRESHOLD:
            with open(file_path, "r+b") as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmapped:
                    content = _decode_content(mmapped, file_path)
        else:
            content = _read_file_with_fallback(file_path)

        # Apply all patterns
        for pattern in compiled_patterns:
            matches = pattern.findall(content)
            images.update(matches)

    except (OSError, IOError) as exc:
        # Log but don't fail on individual file errors
        pass
    except Exception:
        # Gracefully handle any other errors
        pass

    return images


def _decode_content(data: bytes | mmap.mmap, file_path: Path) -> str:
    """Decode file content with fallback encodings.

    Tries UTF-8 first, then falls back to latin-1 which accepts all byte values.

    Args:
        data: Raw bytes or memory-mapped data
        file_path: Path to file (for error context)

    Returns:
        Decoded string content
    """
    if isinstance(data, mmap.mmap):
        data = data.read()

    # Try UTF-8 first
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass

    # Fall back to latin-1 (accepts all byte values)
    try:
        return data.decode("latin-1")
    except UnicodeDecodeError:
        # If even latin-1 fails, return empty string
        return ""


def _read_file_with_fallback(file_path: Path) -> str:
    """Read file with encoding fallback.

    Args:
        file_path: Path to file

    Returns:
        File content as string
    """
    # Try UTF-8 first
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        pass

    # Fall back to latin-1
    try:
        return file_path.read_text(encoding="latin-1")
    except UnicodeDecodeError:
        return ""


def _scan_repo_worker(repo_path: Path, patterns: tuple[str, ...]) -> tuple[str, set[str]]:
    """Worker function to scan single repository.

    Designed to be executed in worker process via ProcessPoolExecutor.

    Args:
        repo_path: Path to repository directory
        patterns: Tuple of regex pattern strings

    Returns:
        Tuple of (repo_path_str, discovered_images)
    """
    images: set[str] = set()

    if not repo_path.exists() or not repo_path.is_dir():
        return (str(repo_path), images)

    # Walk repository and scan files
    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue

        # Only scan files with relevant extensions
        if file_path.suffix.lower() not in SCANNABLE_EXTENSIONS:
            continue

        file_images = _scan_file(file_path, patterns)
        images.update(file_images)

    return (str(repo_path), images)


class RepositoryScanner:
    """Concurrent repository scanner for container image discovery.

    Scans Git repositories in parallel using ProcessPoolExecutor to discover
    container image references. Optimized for performance with:
    - Concurrent processing across multiple CPU cores
    - Cached regex pattern compilation
    - Memory-mapped I/O for large files
    - Graceful encoding error handling

    Example:
        >>> scanner = RepositoryScanner(
        ...     repos=[Path("kubespray"), Path("opencenter-gitops-base")],
        ...     max_workers=4
        ... )
        >>> results = scanner.scan_all()
        >>> for repo, images in results.items():
        ...     print(f"{repo}: {len(images)} images")
    """

    def __init__(
        self,
        repos: list[Path],
        max_workers: int | None = None,
        patterns: list[str] | None = None,
    ) -> None:
        """Initialize repository scanner.

        Args:
            repos: List of repository paths to scan
            max_workers: Number of worker processes (default: cpu_count)
            patterns: Custom regex patterns for image detection (optional)
        """
        self.repos = repos
        self.max_workers = max_workers or multiprocessing.cpu_count()
        self.patterns = tuple(patterns or DEFAULT_IMAGE_PATTERNS)

    def scan_all(self) -> dict[str, set[str]]:
        """Scan all repositories concurrently.

        Distributes repository scanning across worker processes for parallel
        execution. Returns results as they complete.

        Returns:
            Dictionary mapping repo paths to discovered images

        Raises:
            ScanError: If scanning fails catastrophically

        Example:
            >>> scanner = RepositoryScanner([Path("kubespray")])
            >>> results = scanner.scan_all()
            >>> print(f"Found {len(results['kubespray'])} images")
        """
        results: dict[str, set[str]] = {}

        try:
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all repository scan tasks
                future_to_repo = {
                    executor.submit(_scan_repo_worker, repo, self.patterns): repo
                    for repo in self.repos
                }

                # Collect results as they complete
                for future in as_completed(future_to_repo):
                    repo = future_to_repo[future]
                    try:
                        repo_path_str, images = future.result()
                        results[repo_path_str] = images
                    except Exception as exc:
                        # Log error but continue with other repos
                        results[str(repo)] = set()

        except Exception as exc:
            raise ScanError(f"Repository scanning failed: {exc}") from exc

        return results

    def scan_repo(self, repo: Path) -> set[str]:
        """Scan single repository for images.

        Convenience method for scanning a single repository without
        concurrent execution.

        Args:
            repo: Repository path to scan

        Returns:
            Set of discovered image references

        Example:
            >>> scanner = RepositoryScanner([])
            >>> images = scanner.scan_repo(Path("kubespray"))
            >>> print(f"Found {len(images)} images")
        """
        _, images = _scan_repo_worker(repo, self.patterns)
        return images
