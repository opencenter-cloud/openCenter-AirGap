#!/usr/bin/env python3
"""
Version Pinning Validator

Validates that all version specifications in configuration files are pinned
to specific versions (no "latest", "stable", wildcards, or unpinned versions).

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.10
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class VersionType(Enum):
    """Types of version specifications"""
    PINNED = "pinned"
    LATEST = "latest"
    STABLE = "stable"
    WILDCARD = "wildcard"
    UNPINNED = "unpinned"
    INVALID = "invalid"


@dataclass
class VersionSpec:
    """Represents a version specification found in a file"""
    file_path: str
    line_number: int
    line_content: str
    version_string: str
    version_type: VersionType
    context: str  # Variable name or image name


class VersionParser:
    """Parse and classify version specifications"""
    
    # Semantic version pattern (strict)
    SEMVER_PATTERN = re.compile(
        r'^v?(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9\-\.]+))?(?:\+([a-zA-Z0-9\-\.]+))?$'
    )
    
    # Relaxed version pattern (allows v1.2, 1.2.3.4, etc.)
    VERSION_PATTERN = re.compile(
        r'^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?(?:-([a-zA-Z0-9\-\.]+))?$'
    )
    
    # Container image tag patterns (more specific to avoid URLs)
    IMAGE_TAG_PATTERN = re.compile(
        r'(?:[\w\-\.]+/)?(?:[\w\-\.]+/)?[\w\-\.]+:([a-zA-Z0-9\.\-_]+)(?:\s|$|"|\')' 
    )
    
    # Environment variable version patterns
    ENV_VERSION_PATTERN = re.compile(
        r'(\w+_VERSION)\s*=\s*["\']?([^"\']+)["\']?'
    )
    
    # YAML version patterns
    YAML_VERSION_PATTERN = re.compile(
        r'(?:version|tag|image):\s*["\']?([^"\']+)["\']?'
    )
    
    @classmethod
    def parse_version(cls, version_string: str) -> VersionType:
        """
        Classify a version string.
        
        Args:
            version_string: The version string to classify
            
        Returns:
            VersionType indicating the classification
        """
        if not version_string or version_string.strip() == "":
            return VersionType.UNPINNED
        
        version_lower = version_string.lower().strip()
        
        # Check for explicit unpinned tags
        if version_lower in ["latest", "stable", "edge", "dev", "master", "main"]:
            if version_lower == "latest":
                return VersionType.LATEST
            elif version_lower == "stable":
                return VersionType.STABLE
            else:
                return VersionType.UNPINNED
        
        # Check for wildcards
        if '*' in version_string or 'x' in version_lower or '?' in version_string:
            return VersionType.WILDCARD
        
        # Check for version ranges (unpinned)
        if any(op in version_string for op in ['>=', '<=', '>', '<', '^', '~', '||']):
            return VersionType.UNPINNED
        
        # Check if it's a valid semantic version
        if cls.SEMVER_PATTERN.match(version_string):
            return VersionType.PINNED
        
        # Check if it's a relaxed version (e.g., v1.2, 1.2.3.4)
        if cls.VERSION_PATTERN.match(version_string):
            return VersionType.PINNED
        
        # Check if it's a git commit SHA (40 hex chars)
        if re.match(r'^[a-f0-9]{40}$', version_lower):
            return VersionType.PINNED
        
        # Check if it's a short git SHA (7-12 hex chars)
        if re.match(r'^[a-f0-9]{7,12}$', version_lower):
            return VersionType.PINNED
        
        # If we can't classify it, it's invalid
        return VersionType.INVALID
    
    @classmethod
    def extract_image_tags(cls, line: str) -> List[Tuple[str, str]]:
        """
        Extract container image tags from a line.
        
        Args:
            line: Line of text to parse
            
        Returns:
            List of (image_name, tag) tuples
        """
        results = []
        for match in cls.IMAGE_TAG_PATTERN.finditer(line):
            tag = match.group(1)
            image_name = match.group(0).rsplit(':', 1)[0]
            results.append((image_name, tag))
        return results
    
    @classmethod
    def extract_env_versions(cls, line: str) -> List[Tuple[str, str]]:
        """
        Extract version specifications from environment variable assignments.
        
        Args:
            line: Line of text to parse
            
        Returns:
            List of (variable_name, version) tuples
        """
        results = []
        for match in cls.ENV_VERSION_PATTERN.finditer(line):
            var_name = match.group(1)
            version = match.group(2).strip()
            results.append((var_name, version))
        return results
    
    @classmethod
    def extract_yaml_versions(cls, line: str) -> List[Tuple[str, str]]:
        """
        Extract version specifications from YAML files.
        
        Args:
            line: Line of text to parse
            
        Returns:
            List of (key, version) tuples
        """
        results = []
        for match in cls.YAML_VERSION_PATTERN.finditer(line):
            version = match.group(1).strip()
            # Extract the key name
            key_match = re.search(r'(\w+):\s*["\']?' + re.escape(version), line)
            key = key_match.group(1) if key_match else "version"
            results.append((key, version))
        return results


class VersionValidator:
    """Validate version pinning across configuration files"""
    
    # File patterns to scan
    SCAN_PATTERNS = [
        "**/*.env",
        "**/*.yml",
        "**/*.yaml",
        "**/*.txt",
        "**/*.sh",
        "**/*.py",
        "**/*.tf",
        "**/*.hcl",
    ]
    
    # Directories to exclude
    EXCLUDE_DIRS = [
        ".git",
        ".kiro",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "build/kubespray-offline",
        "assets/kubespray",
        "dist",
    ]
    
    def __init__(self, root_dir: Path):
        """
        Initialize validator.
        
        Args:
            root_dir: Root directory to scan
        """
        self.root_dir = root_dir
        self.violations: List[VersionSpec] = []
    
    def should_skip_file(self, file_path: Path) -> bool:
        """
        Check if a file should be skipped.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file should be skipped
        """
        # Check if file is in excluded directory
        for exclude_dir in self.EXCLUDE_DIRS:
            if exclude_dir in file_path.parts:
                return True
        
        return False
    
    def scan_file(self, file_path: Path) -> List[VersionSpec]:
        """
        Scan a single file for version specifications.
        
        Args:
            file_path: Path to file to scan
            
        Returns:
            List of VersionSpec objects found in file
        """
        specs = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, start=1):
                    original_line = line.rstrip()
                    
                    # Remove inline comments for .env and shell files
                    if file_path.suffix in ['.env', '.sh']:
                        # Split on # but preserve quoted strings
                        if '#' in original_line:
                            # Simple approach: remove everything after first unquoted #
                            parts = original_line.split('#')
                            if len(parts) > 1:
                                # Keep only the part before the comment
                                line = parts[0].rstrip()
                            else:
                                line = original_line
                        else:
                            line = original_line
                    else:
                        line = original_line
                    
                    # Skip empty lines after comment removal
                    if not line.strip():
                        continue
                    
                    # Skip lines that start with comment markers
                    if line.strip().startswith('#'):
                        continue
                    
                    # Skip lines that look like URLs (http://, https://, etc.)
                    if 'http://' in line.lower() or 'https://' in line.lower():
                        continue
                    
                    # Extract image tags
                    for image_name, tag in VersionParser.extract_image_tags(line):
                        version_type = VersionParser.parse_version(tag)
                        if version_type != VersionType.PINNED:
                            specs.append(VersionSpec(
                                file_path=str(file_path.relative_to(self.root_dir)),
                                line_number=line_num,
                                line_content=line.strip(),
                                version_string=tag,
                                version_type=version_type,
                                context=f"image:{image_name}"
                            ))
                    
                    # Extract environment variable versions
                    for var_name, version in VersionParser.extract_env_versions(line):
                        version_type = VersionParser.parse_version(version)
                        if version_type != VersionType.PINNED:
                            specs.append(VersionSpec(
                                file_path=str(file_path.relative_to(self.root_dir)),
                                line_number=line_num,
                                line_content=line.strip(),
                                version_string=version,
                                version_type=version_type,
                                context=f"env:{var_name}"
                            ))
                    
                    # Extract YAML versions (only for .env, .txt, and our config files)
                    if file_path.suffix in ['.env', '.txt'] or 'config' in str(file_path):
                        for key, version in VersionParser.extract_yaml_versions(line):
                            version_type = VersionParser.parse_version(version)
                            if version_type != VersionType.PINNED:
                                specs.append(VersionSpec(
                                    file_path=str(file_path.relative_to(self.root_dir)),
                                    line_number=line_num,
                                    line_content=line.strip(),
                                    version_string=version,
                                    version_type=version_type,
                                    context=f"yaml:{key}"
                                ))
        
        except Exception as e:
            print(f"Warning: Failed to scan {file_path}: {e}", file=sys.stderr)
        
        return specs
    
    def scan_directory(self) -> List[VersionSpec]:
        """
        Scan all configuration files in directory tree.
        
        Returns:
            List of all VersionSpec violations found
        """
        all_specs = []
        
        for pattern in self.SCAN_PATTERNS:
            for file_path in self.root_dir.glob(pattern):
                if file_path.is_file() and not self.should_skip_file(file_path):
                    specs = self.scan_file(file_path)
                    all_specs.extend(specs)
        
        return all_specs
    
    def validate(self) -> bool:
        """
        Run validation and collect violations.
        
        Returns:
            True if all versions are pinned, False otherwise
        """
        self.violations = self.scan_directory()
        return len(self.violations) == 0
    
    def report_violations(self) -> str:
        """
        Generate a report of all violations.
        
        Returns:
            Formatted report string
        """
        if not self.violations:
            return "✓ All versions are properly pinned"
        
        report_lines = [
            f"✗ Found {len(self.violations)} version pinning violations:",
            ""
        ]
        
        # Group by file
        by_file: Dict[str, List[VersionSpec]] = {}
        for spec in self.violations:
            if spec.file_path not in by_file:
                by_file[spec.file_path] = []
            by_file[spec.file_path].append(spec)
        
        # Generate report
        for file_path in sorted(by_file.keys()):
            report_lines.append(f"File: {file_path}")
            for spec in by_file[file_path]:
                report_lines.append(
                    f"  Line {spec.line_number}: {spec.version_type.value} version "
                    f"'{spec.version_string}' in {spec.context}"
                )
                report_lines.append(f"    {spec.line_content}")
            report_lines.append("")
        
        return "\n".join(report_lines)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Validate version pinning in configuration files"
    )
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=Path.cwd(),
        help="Root directory to scan (default: current directory)"
    )
    parser.add_argument(
        "--fail-on-violations",
        action="store_true",
        help="Exit with non-zero status if violations found"
    )
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="Only scan config/ directory"
    )
    
    args = parser.parse_args()
    
    # Determine root directory
    root_dir = args.root_dir
    if args.config_only:
        root_dir = args.root_dir / "config"
        if not root_dir.exists():
            print(f"Error: Config directory not found: {root_dir}", file=sys.stderr)
            sys.exit(1)
    
    validator = VersionValidator(root_dir)
    is_valid = validator.validate()
    
    print(validator.report_violations())
    
    if not is_valid and args.fail_on_violations:
        print("\n✗ Build failed due to version pinning violations", file=sys.stderr)
        sys.exit(1)
    
    sys.exit(0 if is_valid else 0)


if __name__ == "__main__":
    main()
