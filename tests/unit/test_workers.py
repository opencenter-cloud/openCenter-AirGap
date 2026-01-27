"""Unit tests for Python worker functions."""

import pytest
from pathlib import Path
import tempfile
import os
import sys
import subprocess

# Add scripts/build to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "build"))

from workers.prerequisites import check_prerequisites_worker
from workers.python_env import setup_python_env_worker, validate_python_env
from workers.github_token import check_github_token_worker
from workers.validation import (
    validate_versions_worker,
    validate_zarf_yaml_worker,
    validate_build_outputs_worker
)
from workers.checksums import generate_checksums_worker


class TestPrerequisitesWorker:
    """Tests for check_prerequisites_worker."""
    
    def test_check_prerequisites_with_all_tools(self, tmp_path):
        """Test prerequisites check when all tools are available."""
        # This test will pass if running in a properly configured environment
        # In CI/CD, ensure all prerequisites are installed
        result = check_prerequisites_worker(tmp_path)
        # Result depends on environment, so we just verify it returns a boolean
        assert isinstance(result, bool)
    
    def test_check_prerequisites_returns_boolean(self, tmp_path):
        """Test that prerequisites check always returns a boolean."""
        result = check_prerequisites_worker(tmp_path)
        assert isinstance(result, bool)


class TestPythonEnvWorker:
    """Tests for Python environment setup and validation."""
    
    def test_setup_python_env_creates_venv(self, tmp_path):
        """Test that setup creates a venv directory."""
        result = setup_python_env_worker(tmp_path)
        
        # Should create venv directory
        venv_dir = tmp_path / "venv"
        assert venv_dir.exists()
        assert venv_dir.is_dir()
        
        # Should have bin directory
        bin_dir = venv_dir / "bin"
        assert bin_dir.exists()
    
    def test_setup_python_env_idempotent(self, tmp_path):
        """Test that setup is idempotent (can run multiple times)."""
        # First run
        result1 = setup_python_env_worker(tmp_path)
        assert result1 is True
        
        # Second run should also succeed
        result2 = setup_python_env_worker(tmp_path)
        assert result2 is True
    
    def test_validate_python_env_fails_without_venv(self, tmp_path):
        """Test that validation fails if venv doesn't exist."""
        result = validate_python_env(tmp_path)
        assert result is False
    
    def test_validate_python_env_succeeds_after_setup(self, tmp_path):
        """Test that validation succeeds after setup."""
        # Setup environment
        setup_result = setup_python_env_worker(tmp_path)
        assert setup_result is True
        
        # Validate should succeed
        validate_result = validate_python_env(tmp_path)
        assert validate_result is True


class TestGitHubTokenWorker:
    """Tests for GitHub token validation."""
    
    def test_check_github_token_with_token_set(self, tmp_path, monkeypatch):
        """Test token check when GITHUB_TOKEN is set."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test1234567890abcdefghijklmnopqrstuvwxyz")
        monkeypatch.setenv("NON_INTERACTIVE", "1")
        
        result = check_github_token_worker(tmp_path)
        assert result is True
    
    def test_check_github_token_without_token_non_interactive(self, tmp_path, monkeypatch):
        """Test token check fails in non-interactive mode without token."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("NON_INTERACTIVE", "1")
        
        result = check_github_token_worker(tmp_path)
        assert result is False
    
    def test_check_github_token_masks_token_in_output(self, tmp_path, monkeypatch, capsys):
        """Test that token is masked in output."""
        token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        monkeypatch.setenv("GITHUB_TOKEN", token)
        monkeypatch.setenv("NON_INTERACTIVE", "1")
        
        result = check_github_token_worker(tmp_path)
        
        captured = capsys.readouterr()
        # Token should not appear in full in output
        assert token not in captured.out
        # But masked version should appear
        assert "ghp_" in captured.out
        assert "..." in captured.out


class TestValidationWorkers:
    """Tests for validation workers."""
    
    def test_validate_versions_fails_without_config_dir(self, tmp_path):
        """Test version validation fails if config/ doesn't exist."""
        result = validate_versions_worker(tmp_path)
        assert result is False
    
    def test_validate_versions_with_empty_config(self, tmp_path):
        """Test version validation with empty config directory."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        # Should pass with no files (no violations)
        result = validate_versions_worker(tmp_path)
        assert result is True
    
    def test_validate_zarf_yaml_fails_without_file(self, tmp_path):
        """Test zarf.yaml validation fails if file doesn't exist."""
        result = validate_zarf_yaml_worker(tmp_path)
        assert result is False
    
    def test_validate_zarf_yaml_with_valid_file(self, tmp_path):
        """Test zarf.yaml validation with valid file."""
        zarf_yaml = tmp_path / "zarf.yaml"
        zarf_yaml.write_text("""
kind: ZarfPackageConfig
metadata:
  name: test-package
  version: 1.0.0
components:
  - name: test-component
    required: true
""")
        
        result = validate_zarf_yaml_worker(tmp_path)
        assert result is True
    
    def test_validate_zarf_yaml_with_invalid_yaml(self, tmp_path):
        """Test zarf.yaml validation fails with invalid YAML."""
        zarf_yaml = tmp_path / "zarf.yaml"
        zarf_yaml.write_text("invalid: yaml: syntax:")
        
        result = validate_zarf_yaml_worker(tmp_path)
        assert result is False
    
    def test_validate_zarf_yaml_with_missing_required_fields(self, tmp_path):
        """Test zarf.yaml validation fails with missing required fields."""
        zarf_yaml = tmp_path / "zarf.yaml"
        zarf_yaml.write_text("""
kind: ZarfPackageConfig
metadata:
  name: test-package
# Missing version and components
""")
        
        result = validate_zarf_yaml_worker(tmp_path)
        assert result is False
    
    def test_validate_build_outputs_fails_without_dist(self, tmp_path):
        """Test build outputs validation fails if dist/ doesn't exist."""
        result = validate_build_outputs_worker(tmp_path)
        assert result is False
    
    def test_validate_build_outputs_fails_without_package(self, tmp_path):
        """Test build outputs validation fails if no Zarf package exists."""
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        
        result = validate_build_outputs_worker(tmp_path)
        assert result is False
    
    def test_validate_build_outputs_with_package(self, tmp_path):
        """Test build outputs validation succeeds with Zarf package."""
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        
        # Create a dummy Zarf package
        package = dist_dir / "zarf-package-test-amd64-1.0.0.tar.zst"
        package.write_bytes(b"dummy package content" * 1000)  # Make it > 100 bytes
        
        result = validate_build_outputs_worker(tmp_path)
        assert result is True


class TestChecksumsWorker:
    """Tests for checksum generation."""
    
    def test_generate_checksums_fails_without_dist(self, tmp_path):
        """Test checksum generation fails if dist/ doesn't exist."""
        result = generate_checksums_worker(tmp_path)
        assert result is False
    
    def test_generate_checksums_fails_without_package(self, tmp_path):
        """Test checksum generation fails if no Zarf package exists."""
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        
        result = generate_checksums_worker(tmp_path)
        assert result is False
    
    def test_generate_checksums_creates_files(self, tmp_path):
        """Test checksum generation creates SHA256 and MD5 files."""
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        
        # Create a dummy Zarf package
        package = dist_dir / "zarf-package-test-amd64-1.0.0.tar.zst"
        package.write_bytes(b"test content for checksums")
        
        result = generate_checksums_worker(tmp_path)
        assert result is True
        
        # Check that checksum files were created
        sha256_file = dist_dir / f"{package.name}.sha256"
        md5_file = dist_dir / f"{package.name}.md5"
        
        assert sha256_file.exists()
        assert md5_file.exists()
        
        # Verify file format
        sha256_content = sha256_file.read_text()
        assert package.name in sha256_content
        assert len(sha256_content.split()[0]) == 64  # SHA256 is 64 hex chars
        
        md5_content = md5_file.read_text()
        assert package.name in md5_content
        assert len(md5_content.split()[0]) == 32  # MD5 is 32 hex chars
    
    def test_generate_checksums_deterministic(self, tmp_path):
        """Test that checksums are deterministic for same content."""
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        
        # Create a dummy Zarf package
        package = dist_dir / "zarf-package-test-amd64-1.0.0.tar.zst"
        content = b"test content for deterministic checksums"
        package.write_bytes(content)
        
        # Generate checksums first time
        result1 = generate_checksums_worker(tmp_path)
        assert result1 is True
        
        sha256_file = dist_dir / f"{package.name}.sha256"
        md5_file = dist_dir / f"{package.name}.md5"
        
        checksum1_sha256 = sha256_file.read_text()
        checksum1_md5 = md5_file.read_text()
        
        # Delete checksum files
        sha256_file.unlink()
        md5_file.unlink()
        
        # Generate checksums second time
        result2 = generate_checksums_worker(tmp_path)
        assert result2 is True
        
        checksum2_sha256 = sha256_file.read_text()
        checksum2_md5 = md5_file.read_text()
        
        # Checksums should be identical
        assert checksum1_sha256 == checksum2_sha256
        assert checksum1_md5 == checksum2_md5
