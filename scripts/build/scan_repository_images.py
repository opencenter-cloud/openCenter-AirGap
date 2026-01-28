#!/usr/bin/env python3
"""
Scan Git Repositories for Container Images and URLs

Scans cloned repositories for:
- Container image references (docker.io, quay.io, gcr.io, etc.)
- HTTP/HTTPS URLs
- GitHub release URLs

Repositories scanned:
- kubespray: https://github.com/kubernetes-sigs/kubespray
- kubespray-offline: https://github.com/kubespray-offline/kubespray-offline
- opencenter-gitops-base: https://github.com/rackerlabs/openCenter-gitops-base
- genestack: https://github.com/rackerlabs/genestack

Outputs structured lists for offline packaging.
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict

# Image reference patterns
IMAGE_PATTERNS = [
    # Full registry/repo:tag format
    r"(?:(?P<registry>[\w\-\.]+(?::\d+)?)/)?(?P<repo>[\w\-\.]+(?:/[\w\-\.]+)+):(?P<tag>[\w\-\.]+)",
    # Docker Hub shorthand (repo:tag)
    r"\b(?P<repo>[\w\-]+/[\w\-]+):(?P<tag>[\w\-\.]+)\b",
    # Image field in YAML/JSON
    r'image:\s*["\']?(?P<full>[\w\-\.:/]+)["\']?',
    # Helm values.yaml repository field
    r'repository:\s*["\']?(?P<registry>[\w\-\.]+(?::\d+)?/)?(?P<repo>[\w\-\.]+(?:/[\w\-\.]+)+)["\']?',
]

# URL patterns
URL_PATTERNS = [
    r'https?://[^\s\'"<>]+',
]

# File extensions to scan
SCANNABLE_EXTENSIONS = {
    ".yaml",
    ".yml",
    ".json",
    ".sh",
    ".py",
    ".md",
    ".txt",
    ".j2",
    ".tmpl",
    ".tpl",
    ".conf",
    ".cfg",
    ".ini",
    ".env",
}

# Directories to skip
SKIP_DIRS = {
    ".git",
    ".github",
    "__pycache__",
    "node_modules",
    "vendor",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "venv",
    ".venv",
}


class RepositoryScanner:
    """Scan repository for container images and URLs."""

    def __init__(self, repo_path: Path, repo_name: str):
        self.repo_path = repo_path
        self.repo_name = repo_name
        self.images: Set[str] = set()
        self.urls: Set[str] = set()
        self.image_sources: Dict[str, List[str]] = defaultdict(list)
        self.url_sources: Dict[str, List[str]] = defaultdict(list)
        self.logger = logging.getLogger(f"scanner.{repo_name}")

    def scan(self) -> Tuple[Set[str], Set[str]]:
        """Scan repository and return (images, urls)."""
        if not self.repo_path.exists():
            self.logger.error(f"Repository not found: {self.repo_path}")
            return set(), set()

        self.logger.info(f"Scanning {self.repo_path}")

        for file_path in self._walk_files():
            self._scan_file(file_path)

        self.logger.info(f"Found {len(self.images)} images, {len(self.urls)} URLs")
        return self.images, self.urls

    def _walk_files(self):
        """Walk repository files, skipping ignored directories."""
        for path in self.repo_path.rglob("*"):
            if not path.is_file():
                continue

            # Skip ignored directories
            if any(skip in path.parts for skip in SKIP_DIRS):
                continue

            # Only scan text files
            if path.suffix not in SCANNABLE_EXTENSIONS:
                continue

            yield path

    def _scan_file(self, file_path: Path):
        """Scan single file for images and URLs."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            self.logger.debug(f"Skip {file_path}: {e}")
            return

        relative_path = file_path.relative_to(self.repo_path)

        # Extract images
        for pattern in IMAGE_PATTERNS:
            for match in re.finditer(pattern, content, re.MULTILINE):
                image = self._normalize_image(match)
                if image and self._is_valid_image(image):
                    self.images.add(image)
                    self.image_sources[image].append(str(relative_path))

        # Extract URLs
        for pattern in URL_PATTERNS:
            for match in re.finditer(pattern, content):
                url = match.group(0).rstrip(".,;)")
                if self._is_valid_url(url):
                    self.urls.add(url)
                    self.url_sources[url].append(str(relative_path))

    def _normalize_image(self, match: re.Match) -> str:
        """Normalize image reference to full format."""
        groups = match.groupdict()

        # Handle 'full' group from image: field
        if "full" in groups and groups["full"]:
            return groups["full"]

        registry = (groups.get("registry") or "").strip("/")
        repo = (groups.get("repo") or "").strip("/")
        tag = (groups.get("tag") or "").strip()

        if not repo:
            return ""

        # Default registry for Docker Hub
        if not registry and "/" in repo:
            registry = "docker.io"

        # Build full image reference
        if registry:
            image = f"{registry}/{repo}"
        else:
            image = repo

        if tag:
            image = f"{image}:{tag}"

        return image

    def _is_valid_image(self, image: str) -> bool:
        """Validate image reference."""
        if not image or len(image) < 3:
            return False

        # Must contain at least one /
        if "/" not in image:
            return False

        # Skip obvious false positives
        false_positives = [
            "http://",
            "https://",
            "file://",
            "ftp://",
            "example.com",
            "localhost",
            "127.0.0.1",
            ".git",
            ".md",
            ".txt",
            ".yaml",
            ".yml",
        ]

        for fp in false_positives:
            if fp in image.lower():
                return False

        return True

    def _is_valid_url(self, url: str) -> bool:
        """Validate URL."""
        if not url or len(url) < 10:
            return False

        # Skip localhost and examples
        skip_patterns = [
            "localhost",
            "127.0.0.1",
            "example.com",
            "example.org",
            "your-domain.com",
            "mydomain.com",
            "<",
            ">",
        ]

        for pattern in skip_patterns:
            if pattern in url.lower():
                return False

        return True

    def export_results(self, output_dir: Path):
        """Export scan results to files."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Export images
        images_file = output_dir / f"{self.repo_name}-images.txt"
        with images_file.open("w") as f:
            f.write(f"# Container Images from {self.repo_name}\n")
            f.write(f"# Total: {len(self.images)}\n\n")
            for image in sorted(self.images):
                f.write(f"{image}\n")

        # Export URLs
        urls_file = output_dir / f"{self.repo_name}-urls.txt"
        with urls_file.open("w") as f:
            f.write(f"# URLs from {self.repo_name}\n")
            f.write(f"# Total: {len(self.urls)}\n\n")
            for url in sorted(self.urls):
                f.write(f"{url}\n")

        # Export detailed JSON
        details_file = output_dir / f"{self.repo_name}-scan-details.json"
        details = {
            "repository": self.repo_name,
            "path": str(self.repo_path),
            "images": {
                "count": len(self.images),
                "list": sorted(list(self.images)),
                "sources": {img: srcs for img, srcs in self.image_sources.items()},
            },
            "urls": {
                "count": len(self.urls),
                "list": sorted(list(self.urls)),
                "sources": {url: srcs for url, srcs in self.url_sources.items()},
            },
        }

        with details_file.open("w") as f:
            json.dump(details, f, indent=2)

        self.logger.info(f"Exported to {output_dir}")


def scan_all_repositories(project_root: Path, output_dir: Path):
    """Scan all configured repositories."""
    repos_to_scan = [
        ("kubespray", project_root / "assets/kubespray/kubespray-master"),
        ("kubespray-offline", project_root / "build/kubespray-offline"),
        ("opencenter-gitops-base", project_root / "assets/opencenter-gitops-base"),
        ("genestack", project_root / "assets/genestack"),
    ]

    all_images = set()
    all_urls = set()

    for repo_name, repo_path in repos_to_scan:
        scanner = RepositoryScanner(repo_path, repo_name)
        images, urls = scanner.scan()
        scanner.export_results(output_dir)

        all_images.update(images)
        all_urls.update(urls)

    # Export combined results
    combined_images = output_dir / "all-repositories-images.txt"
    with combined_images.open("w") as f:
        f.write("# Combined Container Images from All Repositories\n")
        f.write(f"# Total: {len(all_images)}\n\n")
        for image in sorted(all_images):
            f.write(f"{image}\n")

    combined_urls = output_dir / "all-repositories-urls.txt"
    with combined_urls.open("w") as f:
        f.write("# Combined URLs from All Repositories\n")
        f.write(f"# Total: {len(all_urls)}\n\n")
        for url in sorted(all_urls):
            f.write(f"{url}\n")

    logging.info(f"Combined: {len(all_images)} images, {len(all_urls)} URLs")


def main():
    parser = argparse.ArgumentParser(
        description="Scan git repositories for container images and URLs"
    )
    parser.add_argument(
        "--project-root", type=Path, default=Path.cwd(), help="Project root directory"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("build/repository-scans"),
        help="Output directory for scan results",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s: %(message)s"
    )

    scan_all_repositories(args.project_root, args.output_dir)


if __name__ == "__main__":
    main()
