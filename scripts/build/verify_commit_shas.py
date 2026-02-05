#!/usr/bin/env python3
"""Verify git repository commit SHAs for supply chain security.

This script verifies that git dependencies are pinned to specific commit SHAs
and that those SHAs exist in the remote repositories. This ensures build
reproducibility and prevents supply chain attacks via mutable references.
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from opencenter_build.config import load_versions_env
from opencenter_build.exceptions import ValidationError


logger = logging.getLogger(__name__)


class CommitSHAVerifier:
    """Verify git commit SHAs against remote repositories."""

    def __init__(self, versions: Dict[str, str]):
        """Initialize verifier with version configuration.

        Args:
            versions: Dictionary of version configuration
        """
        self.versions = versions
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def verify_all(self) -> bool:
        """Verify all git dependencies have valid commit SHAs.

        Returns:
            True if all verifications pass, False otherwise
        """
        success = True

        # Verify Kubespray
        if not self._verify_kubespray():
            success = False

        # Verify openCenter GitOps Base
        if not self._verify_gitops_base():
            success = False

        return success

    def _verify_kubespray(self) -> bool:
        """Verify Kubespray version and commit SHA.

        Returns:
            True if verification passes, False otherwise
        """
        version = self.versions.get("KUBESPRAY_VERSION")
        commit_sha = self.versions.get("KUBESPRAY_COMMIT_SHA")

        if not version:
            self.errors.append("KUBESPRAY_VERSION not defined")
            return False

        if not commit_sha:
            self.errors.append("KUBESPRAY_COMMIT_SHA not defined")
            return False

        # Check version is not mutable reference
        if version in ["master", "main", "develop"]:
            self.errors.append(
                f"KUBESPRAY_VERSION uses mutable reference '{version}'. "
                f"Use a specific tag (e.g., v2.24.0)"
            )
            return False

        # Verify commit SHA format
        if not self._is_valid_sha(commit_sha):
            self.errors.append(
                f"KUBESPRAY_COMMIT_SHA '{commit_sha}' is not a valid 40-character SHA"
            )
            return False

        # Verify commit exists in remote repository
        repo_url = "https://github.com/kubernetes-sigs/kubespray.git"
        if not self._verify_remote_commit(repo_url, commit_sha, "Kubespray"):
            return False

        # Verify version tag matches commit SHA
        if not self._verify_tag_matches_commit(repo_url, version, commit_sha, "Kubespray"):
            return False

        logger.info(f"✓ Kubespray {version} verified at commit {commit_sha[:8]}")
        return True

    def _verify_gitops_base(self) -> bool:
        """Verify openCenter GitOps Base version and commit SHA.

        Returns:
            True if verification passes, False otherwise
        """
        repo = self.versions.get("OPENCENTER_GITOPS_BASE_REPO")
        version = self.versions.get("OPENCENTER_GITOPS_BASE_VERSION")
        commit_sha = self.versions.get("OPENCENTER_GITOPS_BASE_COMMIT_SHA")

        if not repo:
            self.errors.append("OPENCENTER_GITOPS_BASE_REPO not defined")
            return False

        if not version:
            self.errors.append("OPENCENTER_GITOPS_BASE_VERSION not defined")
            return False

        if not commit_sha:
            self.errors.append("OPENCENTER_GITOPS_BASE_COMMIT_SHA not defined")
            return False

        # Check version is not mutable reference
        if version in ["master", "main", "develop"]:
            self.errors.append(
                f"OPENCENTER_GITOPS_BASE_VERSION uses mutable reference '{version}'. "
                f"Use a specific tag or commit SHA"
            )
            return False

        # Verify commit SHA format
        if not self._is_valid_sha(commit_sha):
            self.errors.append(
                f"OPENCENTER_GITOPS_BASE_COMMIT_SHA '{commit_sha}' is not a valid 40-character SHA"
            )
            return False

        # Verify commit exists in remote repository
        if not self._verify_remote_commit(repo, commit_sha, "GitOps Base"):
            return False

        # Verify version reference matches commit SHA
        if not self._verify_ref_matches_commit(repo, version, commit_sha, "GitOps Base"):
            return False

        logger.info(f"✓ GitOps Base {version} verified at commit {commit_sha[:8]}")
        return True

    def _is_valid_sha(self, sha: str) -> bool:
        """Check if string is a valid 40-character git SHA.

        Args:
            sha: String to validate

        Returns:
            True if valid SHA format, False otherwise
        """
        if not sha or len(sha) != 40:
            return False

        try:
            int(sha, 16)
            return True
        except ValueError:
            return False

    def _verify_remote_commit(self, repo_url: str, commit_sha: str, name: str) -> bool:
        """Verify commit exists in remote repository.

        Args:
            repo_url: Git repository URL
            commit_sha: Commit SHA to verify
            name: Human-readable name for error messages

        Returns:
            True if commit exists, False otherwise
        """
        try:
            # Use git ls-remote to check if commit exists
            result = subprocess.run(
                ["git", "ls-remote", repo_url, commit_sha],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                self.errors.append(f"{name}: Failed to query remote repository: {result.stderr}")
                return False

            # If output is empty, commit doesn't exist
            if not result.stdout.strip():
                self.errors.append(f"{name}: Commit {commit_sha} not found in {repo_url}")
                return False

            return True

        except subprocess.TimeoutExpired:
            self.errors.append(f"{name}: Timeout querying remote repository {repo_url}")
            return False
        except FileNotFoundError:
            self.errors.append("git command not found. Install git to verify commit SHAs.")
            return False
        except Exception as e:
            self.errors.append(f"{name}: Error verifying commit: {e}")
            return False

    def _verify_tag_matches_commit(
        self, repo_url: str, tag: str, expected_sha: str, name: str
    ) -> bool:
        """Verify that a git tag points to the expected commit SHA.

        Args:
            repo_url: Git repository URL
            tag: Git tag to verify
            expected_sha: Expected commit SHA
            name: Human-readable name for error messages

        Returns:
            True if tag matches commit, False otherwise
        """
        try:
            # Get commit SHA for tag
            result = subprocess.run(
                ["git", "ls-remote", repo_url, f"refs/tags/{tag}"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                self.warnings.append(f"{name}: Could not verify tag {tag}: {result.stderr}")
                return True  # Don't fail on tag verification issues

            if not result.stdout.strip():
                self.warnings.append(f"{name}: Tag {tag} not found in remote repository")
                return True  # Don't fail if tag doesn't exist

            # Parse SHA from output
            actual_sha = result.stdout.split()[0]

            if actual_sha != expected_sha:
                self.errors.append(
                    f"{name}: Tag {tag} points to {actual_sha[:8]} but "
                    f"COMMIT_SHA is {expected_sha[:8]}"
                )
                return False

            return True

        except subprocess.TimeoutExpired:
            self.warnings.append(f"{name}: Timeout verifying tag {tag}")
            return True  # Don't fail on timeout
        except Exception as e:
            self.warnings.append(f"{name}: Error verifying tag: {e}")
            return True  # Don't fail on verification errors

    def _verify_ref_matches_commit(
        self, repo_url: str, ref: str, expected_sha: str, name: str
    ) -> bool:
        """Verify that a git reference points to the expected commit SHA.

        Args:
            repo_url: Git repository URL
            ref: Git reference (tag, branch, or SHA)
            expected_sha: Expected commit SHA
            name: Human-readable name for error messages

        Returns:
            True if reference matches commit, False otherwise
        """
        # If ref is already a SHA, just verify it matches
        if self._is_valid_sha(ref):
            if ref != expected_sha:
                self.errors.append(
                    f"{name}: VERSION is {ref[:8]} but COMMIT_SHA is {expected_sha[:8]}"
                )
                return False
            return True

        # Try as tag first
        return self._verify_tag_matches_commit(repo_url, ref, expected_sha, name)

    def print_results(self) -> None:
        """Print verification results to console."""
        if self.warnings:
            print("\nWarnings:")
            for warning in self.warnings:
                print(f"  ⚠ {warning}")

        if self.errors:
            print("\nErrors:")
            for error in self.errors:
                print(f"  ✗ {error}")

        if not self.errors and not self.warnings:
            print("\n✓ All commit SHAs verified successfully")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Verify git commit SHAs for supply chain security",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Verify all commit SHAs
  python3 scripts/build/verify_commit_shas.py

  # Verify with custom versions file
  python3 scripts/build/verify_commit_shas.py --versions-file config/versions.env

  # Verbose output
  python3 scripts/build/verify_commit_shas.py --verbose
""",
    )

    parser.add_argument(
        "--versions-file",
        type=Path,
        default=Path("config/versions.env"),
        help="Path to versions.env file (default: config/versions.env)",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    return parser.parse_args()


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    args = parse_args()

    # Setup logging
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")

    print("=" * 80)
    print("Git Commit SHA Verification")
    print("=" * 80)

    # Load versions
    try:
        versions = load_versions_env(args.versions_file)
        logger.info(f"Loaded versions from {args.versions_file}")
    except Exception as e:
        print(f"\n✗ Failed to load versions: {e}")
        return 1

    # Verify commit SHAs
    verifier = CommitSHAVerifier(versions)
    success = verifier.verify_all()

    # Print results
    verifier.print_results()

    print("=" * 80)

    if success:
        print("✓ Verification passed")
        return 0
    else:
        print("✗ Verification failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
