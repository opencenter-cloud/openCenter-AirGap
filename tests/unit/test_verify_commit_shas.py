"""Unit tests for commit SHA verification."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import subprocess

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "build"))

from verify_commit_shas import CommitSHAVerifier


class TestCommitSHAVerifier:
    """Test CommitSHAVerifier class."""

    def test_initialization(self):
        """Test verifier initialization."""
        versions = {"KUBESPRAY_VERSION": "v2.24.0"}
        verifier = CommitSHAVerifier(versions)

        assert verifier.versions == versions
        assert verifier.errors == []
        assert verifier.warnings == []

    def test_is_valid_sha_valid(self):
        """Test valid SHA recognition."""
        verifier = CommitSHAVerifier({})

        valid_sha = "a" * 40
        assert verifier._is_valid_sha(valid_sha) is True

        valid_sha_hex = "1234567890abcdef" * 2 + "12345678"
        assert verifier._is_valid_sha(valid_sha_hex) is True

    def test_is_valid_sha_invalid_length(self):
        """Test invalid SHA length detection."""
        verifier = CommitSHAVerifier({})

        assert verifier._is_valid_sha("abc123") is False
        assert verifier._is_valid_sha("a" * 39) is False
        assert verifier._is_valid_sha("a" * 41) is False
        assert verifier._is_valid_sha("") is False
        assert verifier._is_valid_sha(None) is False

    def test_is_valid_sha_invalid_characters(self):
        """Test invalid SHA character detection."""
        verifier = CommitSHAVerifier({})

        invalid_sha = "g" * 40  # 'g' is not hex
        assert verifier._is_valid_sha(invalid_sha) is False

        invalid_sha = "z" * 40
        assert verifier._is_valid_sha(invalid_sha) is False

    def test_verify_kubespray_missing_version(self):
        """Test Kubespray verification with missing version."""
        verifier = CommitSHAVerifier({})

        result = verifier._verify_kubespray()

        assert result is False
        assert any("KUBESPRAY_VERSION not defined" in e for e in verifier.errors)

    def test_verify_kubespray_missing_commit_sha(self):
        """Test Kubespray verification with missing commit SHA."""
        verifier = CommitSHAVerifier({"KUBESPRAY_VERSION": "v2.24.0"})

        result = verifier._verify_kubespray()

        assert result is False
        assert any("KUBESPRAY_COMMIT_SHA not defined" in e for e in verifier.errors)

    def test_verify_kubespray_mutable_reference(self):
        """Test Kubespray verification rejects mutable references."""
        for mutable_ref in ["master", "main", "develop"]:
            verifier = CommitSHAVerifier(
                {"KUBESPRAY_VERSION": mutable_ref, "KUBESPRAY_COMMIT_SHA": "a" * 40}
            )

            result = verifier._verify_kubespray()

            assert result is False
            assert any("mutable reference" in e for e in verifier.errors)

    def test_verify_kubespray_invalid_sha_format(self):
        """Test Kubespray verification with invalid SHA format."""
        verifier = CommitSHAVerifier(
            {"KUBESPRAY_VERSION": "v2.24.0", "KUBESPRAY_COMMIT_SHA": "invalid"}
        )

        result = verifier._verify_kubespray()

        assert result is False
        assert any("not a valid 40-character SHA" in e for e in verifier.errors)

    @patch("subprocess.run")
    def test_verify_remote_commit_success(self, mock_run):
        """Test successful remote commit verification."""
        mock_run.return_value = Mock(
            returncode=0, stdout="abc123def456\trefs/heads/main\n", stderr=""
        )

        verifier = CommitSHAVerifier({})
        result = verifier._verify_remote_commit(
            "https://github.com/test/repo.git", "abc123def456" + "0" * 28, "Test"
        )

        assert result is True
        assert len(verifier.errors) == 0

    @patch("subprocess.run")
    def test_verify_remote_commit_not_found(self, mock_run):
        """Test remote commit not found."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        verifier = CommitSHAVerifier({})
        result = verifier._verify_remote_commit(
            "https://github.com/test/repo.git", "a" * 40, "Test"
        )

        assert result is False
        assert any("not found" in e for e in verifier.errors)

    @patch("subprocess.run")
    def test_verify_remote_commit_command_failure(self, mock_run):
        """Test remote commit verification with command failure."""
        mock_run.return_value = Mock(
            returncode=1, stdout="", stderr="fatal: could not read from remote repository"
        )

        verifier = CommitSHAVerifier({})
        result = verifier._verify_remote_commit(
            "https://github.com/test/repo.git", "a" * 40, "Test"
        )

        assert result is False
        assert any("Failed to query remote repository" in e for e in verifier.errors)

    @patch("subprocess.run")
    def test_verify_remote_commit_timeout(self, mock_run):
        """Test remote commit verification timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("git", 30)

        verifier = CommitSHAVerifier({})
        result = verifier._verify_remote_commit(
            "https://github.com/test/repo.git", "a" * 40, "Test"
        )

        assert result is False
        assert any("Timeout" in e for e in verifier.errors)

    @patch("subprocess.run")
    def test_verify_remote_commit_git_not_found(self, mock_run):
        """Test remote commit verification when git not installed."""
        mock_run.side_effect = FileNotFoundError()

        verifier = CommitSHAVerifier({})
        result = verifier._verify_remote_commit(
            "https://github.com/test/repo.git", "a" * 40, "Test"
        )

        assert result is False
        assert any("git command not found" in e for e in verifier.errors)

    def test_verify_gitops_base_missing_repo(self):
        """Test GitOps Base verification with missing repo."""
        verifier = CommitSHAVerifier({})

        result = verifier._verify_gitops_base()

        assert result is False
        assert any("OPENCENTER_GITOPS_BASE_REPO not defined" in e for e in verifier.errors)

    def test_verify_gitops_base_missing_version(self):
        """Test GitOps Base verification with missing version."""
        verifier = CommitSHAVerifier(
            {"OPENCENTER_GITOPS_BASE_REPO": "https://github.com/test/repo"}
        )

        result = verifier._verify_gitops_base()

        assert result is False
        assert any("OPENCENTER_GITOPS_BASE_VERSION not defined" in e for e in verifier.errors)

    def test_verify_gitops_base_missing_commit_sha(self):
        """Test GitOps Base verification with missing commit SHA."""
        verifier = CommitSHAVerifier(
            {
                "OPENCENTER_GITOPS_BASE_REPO": "https://github.com/test/repo",
                "OPENCENTER_GITOPS_BASE_VERSION": "v1.0.0",
            }
        )

        result = verifier._verify_gitops_base()

        assert result is False
        assert any("OPENCENTER_GITOPS_BASE_COMMIT_SHA not defined" in e for e in verifier.errors)

    def test_verify_gitops_base_mutable_reference(self):
        """Test GitOps Base verification rejects mutable references."""
        for mutable_ref in ["master", "main", "develop"]:
            verifier = CommitSHAVerifier(
                {
                    "OPENCENTER_GITOPS_BASE_REPO": "https://github.com/test/repo",
                    "OPENCENTER_GITOPS_BASE_VERSION": mutable_ref,
                    "OPENCENTER_GITOPS_BASE_COMMIT_SHA": "a" * 40,
                }
            )

            result = verifier._verify_gitops_base()

            assert result is False
            assert any("mutable reference" in e for e in verifier.errors)

    @patch("subprocess.run")
    def test_verify_tag_matches_commit_success(self, mock_run):
        """Test successful tag to commit verification."""
        expected_sha = "a" * 40
        mock_run.return_value = Mock(
            returncode=0, stdout=f"{expected_sha}\trefs/tags/v1.0.0\n", stderr=""
        )

        verifier = CommitSHAVerifier({})
        result = verifier._verify_tag_matches_commit(
            "https://github.com/test/repo.git", "v1.0.0", expected_sha, "Test"
        )

        assert result is True
        assert len(verifier.errors) == 0

    @patch("subprocess.run")
    def test_verify_tag_matches_commit_mismatch(self, mock_run):
        """Test tag to commit verification with SHA mismatch."""
        mock_run.return_value = Mock(
            returncode=0, stdout=f"{'b' * 40}\trefs/tags/v1.0.0\n", stderr=""
        )

        verifier = CommitSHAVerifier({})
        result = verifier._verify_tag_matches_commit(
            "https://github.com/test/repo.git", "v1.0.0", "a" * 40, "Test"
        )

        assert result is False
        assert any("points to" in e and "but" in e for e in verifier.errors)

    @patch("subprocess.run")
    def test_verify_tag_matches_commit_tag_not_found(self, mock_run):
        """Test tag to commit verification when tag doesn't exist."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        verifier = CommitSHAVerifier({})
        result = verifier._verify_tag_matches_commit(
            "https://github.com/test/repo.git", "v1.0.0", "a" * 40, "Test"
        )

        # Should not fail, just warn
        assert result is True
        assert any("not found" in w for w in verifier.warnings)

    def test_verify_ref_matches_commit_with_sha(self):
        """Test reference verification when ref is already a SHA."""
        sha = "a" * 40
        verifier = CommitSHAVerifier({})

        result = verifier._verify_ref_matches_commit(
            "https://github.com/test/repo.git", sha, sha, "Test"
        )

        assert result is True
        assert len(verifier.errors) == 0

    def test_verify_ref_matches_commit_sha_mismatch(self):
        """Test reference verification with SHA mismatch."""
        verifier = CommitSHAVerifier({})

        result = verifier._verify_ref_matches_commit(
            "https://github.com/test/repo.git", "a" * 40, "b" * 40, "Test"
        )

        assert result is False
        assert any("VERSION is" in e and "but COMMIT_SHA is" in e for e in verifier.errors)

    def test_print_results_no_issues(self, capsys):
        """Test printing results with no issues."""
        verifier = CommitSHAVerifier({})
        verifier.print_results()

        captured = capsys.readouterr()
        assert "All commit SHAs verified successfully" in captured.out

    def test_print_results_with_warnings(self, capsys):
        """Test printing results with warnings."""
        verifier = CommitSHAVerifier({})
        verifier.warnings.append("Test warning")
        verifier.print_results()

        captured = capsys.readouterr()
        assert "Warnings:" in captured.out
        assert "Test warning" in captured.out

    def test_print_results_with_errors(self, capsys):
        """Test printing results with errors."""
        verifier = CommitSHAVerifier({})
        verifier.errors.append("Test error")
        verifier.print_results()

        captured = capsys.readouterr()
        assert "Errors:" in captured.out
        assert "Test error" in captured.out
