"""Unit tests for package verification."""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from opencenter_build.exceptions import ValidationError
from opencenter_build.verifier import PackageVerifier, VerificationResult


class TestPackageVerifier:
    """Test PackageVerifier class."""

    def test_verify_nonexistent_package(self, tmp_path: Path) -> None:
        """Test verification of non-existent package raises error."""
        verifier = PackageVerifier()
        nonexistent = tmp_path / "nonexistent.tar.zst"

        with pytest.raises(ValidationError, match="Package not found"):
            verifier.verify(nonexistent)

    def test_verify_without_manifest(self, tmp_path: Path) -> None:
        """Test basic verification without manifest."""
        verifier = PackageVerifier()
        package = tmp_path / "test.tar.zst"

        # Create valid zstd file
        package.write_bytes(b"\x28\xB5\x2F\xFD" + b"data" * 300)

        with patch("shutil.which", return_value=None):
            result = verifier.verify(package)

        assert isinstance(result, VerificationResult)
        assert not result.signature_valid  # No signature file
        assert result.checksums_valid  # Valid magic bytes
        assert result.manifest_matches  # No manifest to compare
        assert result.artifact_count == 0

    def test_verify_with_manifest(self, tmp_path: Path) -> None:
        """Test verification with artifact manifest."""
        verifier = PackageVerifier()
        package = tmp_path / "test.tar.zst"
        manifest = tmp_path / "manifest.json"

        # Create valid package
        package.write_bytes(b"\x28\xB5\x2F\xFD" + b"data" * 300)

        # Create manifest
        manifest_data = {
            "build_id": "test-123",
            "timestamp": "2026-01-30T00:00:00Z",
            "total_artifacts": 42,
            "package_file": "test.tar.zst",
            "package_size": package.stat().st_size,
            "images": [],
            "repositories": [],
        }
        manifest.write_text(json.dumps(manifest_data))

        # Mock zarf as available for detailed comparison
        mock_result = Mock(returncode=0, stdout="package info")

        with patch("shutil.which") as mock_which:
            mock_which.side_effect = lambda x: "/usr/bin/zarf" if x == "zarf" else None

            with patch("subprocess.run", return_value=mock_result):
                result = verifier.verify(package, manifest)

        # Without cosign, signature will fail but manifest should be compared
        assert result.artifact_count == 42
        assert result.manifest_matches

    def test_verify_signature_with_cosign(self, tmp_path: Path) -> None:
        """Test signature verification with cosign available."""
        verifier = PackageVerifier()
        package = tmp_path / "test.tar.zst"
        sig_file = tmp_path / "test.tar.zst.sig"

        package.write_bytes(b"\x28\xB5\x2F\xFD" + b"data" * 300)
        sig_file.write_text("fake signature")

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/cosign"):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                result = verifier._verify_signature(package)

        assert result is True
        # Should try multiple verification strategies
        assert mock_run.call_count >= 1

    def test_verify_signature_with_env_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test signature verification with public key from environment."""
        verifier = PackageVerifier()
        package = tmp_path / "test.tar.zst"
        sig_file = tmp_path / "test.tar.zst.sig"

        package.write_bytes(b"\x28\xB5\x2F\xFD" + b"data" * 300)
        sig_file.write_text("fake signature")

        # Set environment variable
        monkeypatch.setenv(
            "COSIGN_PUBLIC_KEY", "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----"
        )

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/cosign"):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                result = verifier._verify_signature(package)

        assert result is True
        # Should use env://COSIGN_PUBLIC_KEY
        call_args = mock_run.call_args[0][0]
        assert "env://COSIGN_PUBLIC_KEY" in call_args

    def test_verify_signature_without_cosign(self, tmp_path: Path) -> None:
        """Test signature verification without cosign."""
        verifier = PackageVerifier()
        package = tmp_path / "test.tar.zst"

        with patch("shutil.which", return_value=None):
            result = verifier._verify_signature(package)

        assert result is False

    def test_verify_signature_no_sig_file(self, tmp_path: Path) -> None:
        """Test signature verification without signature file."""
        verifier = PackageVerifier()
        package = tmp_path / "test.tar.zst"
        package.write_bytes(b"data")

        with patch("shutil.which", return_value="/usr/bin/cosign"):
            result = verifier._verify_signature(package)

        assert result is False

    def test_verify_checksums_valid_magic_bytes(self, tmp_path: Path) -> None:
        """Test checksum verification with valid zstd magic bytes."""
        verifier = PackageVerifier()
        package = tmp_path / "test.tar.zst"

        # Valid zstd magic: 0x28, 0xB5, 0x2F, 0xFD
        package.write_bytes(b"\x28\xB5\x2F\xFD" + b"data" * 300)

        with patch("shutil.which", return_value=None):
            result = verifier._verify_checksums(package)

        assert result is True

    def test_verify_checksums_invalid_magic_bytes(self, tmp_path: Path) -> None:
        """Test checksum verification with invalid magic bytes."""
        verifier = PackageVerifier()
        package = tmp_path / "test.tar.zst"

        package.write_bytes(b"INVALID" + b"data" * 300)

        with patch("shutil.which", return_value=None):
            result = verifier._verify_checksums(package)

        assert result is False

    def test_verify_checksums_too_small(self, tmp_path: Path) -> None:
        """Test checksum verification with file too small."""
        verifier = PackageVerifier()
        package = tmp_path / "test.tar.zst"

        package.write_bytes(b"\x28\xB5\x2F\xFD")  # Only 4 bytes

        with patch("shutil.which", return_value=None):
            result = verifier._verify_checksums(package)

        assert result is False

    def test_verify_checksums_with_zarf(self, tmp_path: Path) -> None:
        """Test checksum verification using zarf CLI."""
        verifier = PackageVerifier()
        package = tmp_path / "test.tar.zst"
        package.write_bytes(b"\x28\xB5\x2F\xFD" + b"data" * 300)

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/zarf"):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                result = verifier._verify_checksums(package)

        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "zarf"
        assert args[1] == "package"
        assert args[2] == "inspect"
        assert "--insecure" in args

    def test_compare_manifest_missing_file(self, tmp_path: Path) -> None:
        """Test manifest comparison with missing manifest."""
        verifier = PackageVerifier()
        package = tmp_path / "test.tar.zst"
        manifest = tmp_path / "nonexistent.json"

        package.write_bytes(b"data")

        errors = verifier._compare_manifest(package, manifest)

        assert len(errors) == 1
        assert "not found" in errors[0]

    def test_compare_manifest_invalid_json(self, tmp_path: Path) -> None:
        """Test manifest comparison with invalid JSON."""
        verifier = PackageVerifier()
        package = tmp_path / "test.tar.zst"
        manifest = tmp_path / "manifest.json"

        package.write_bytes(b"data")
        manifest.write_text("invalid json{")

        errors = verifier._compare_manifest(package, manifest)

        assert len(errors) > 0
        assert any("JSON" in err for err in errors)

    def test_compare_manifest_missing_required_field(self, tmp_path: Path) -> None:
        """Test manifest comparison with missing required field."""
        verifier = PackageVerifier()
        package = tmp_path / "test.tar.zst"
        manifest = tmp_path / "manifest.json"

        package.write_bytes(b"data")
        manifest.write_text(json.dumps({"build_id": "test"}))

        errors = verifier._compare_manifest(package, manifest)

        assert len(errors) == 1
        assert "total_artifacts" in errors[0]

    def test_compare_manifest_package_name_mismatch(self, tmp_path: Path) -> None:
        """Test manifest comparison with package name mismatch."""
        verifier = PackageVerifier()
        package = tmp_path / "actual.tar.zst"
        manifest = tmp_path / "manifest.json"

        package.write_bytes(b"\x28\xB5\x2F\xFD" + b"data" * 300)

        manifest_data = {
            "total_artifacts": 10,
            "package_file": "expected.tar.zst",
            "images": [],
            "repositories": [],
        }
        manifest.write_text(json.dumps(manifest_data))

        with patch("shutil.which", return_value="/usr/bin/zarf"):
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "package info"

            with patch("subprocess.run", return_value=mock_result):
                errors = verifier._compare_manifest(package, manifest)

        assert any("name mismatch" in err for err in errors)

    def test_compare_manifest_size_mismatch(self, tmp_path: Path) -> None:
        """Test manifest comparison with size mismatch."""
        verifier = PackageVerifier()
        package = tmp_path / "test.tar.zst"
        manifest = tmp_path / "manifest.json"

        package.write_bytes(b"\x28\xB5\x2F\xFD" + b"data" * 300)

        manifest_data = {
            "total_artifacts": 10,
            "package_file": "test.tar.zst",
            "package_size": 999999999,  # Wrong size
            "images": [],
            "repositories": [],
        }
        manifest.write_text(json.dumps(manifest_data))

        with patch("shutil.which", return_value="/usr/bin/zarf"):
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "package info"

            with patch("subprocess.run", return_value=mock_result):
                errors = verifier._compare_manifest(package, manifest)

        assert any("size mismatch" in err for err in errors)

    def test_compare_manifest_checksum_mismatch(self, tmp_path: Path) -> None:
        """Test manifest comparison with checksum mismatch."""
        verifier = PackageVerifier()
        package = tmp_path / "test.tar.zst"
        manifest = tmp_path / "manifest.json"

        package.write_bytes(b"\x28\xB5\x2F\xFD" + b"data" * 300)

        manifest_data = {
            "total_artifacts": 10,
            "package_file": "test.tar.zst",
            "package_size": package.stat().st_size,
            "package_sha256": "0" * 64,  # Wrong checksum
            "images": [],
            "repositories": [],
        }
        manifest.write_text(json.dumps(manifest_data))

        with patch("shutil.which", return_value="/usr/bin/zarf"):
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "package info"

            with patch("subprocess.run", return_value=mock_result):
                errors = verifier._compare_manifest(package, manifest)

        assert any("checksum mismatch" in err for err in errors)

    def test_verification_result_dataclass(self) -> None:
        """Test VerificationResult dataclass."""
        result = VerificationResult(
            success=True,
            signature_valid=True,
            checksums_valid=True,
            manifest_matches=True,
            errors=[],
            artifact_count=42,
        )

        assert result.success is True
        assert result.signature_valid is True
        assert result.checksums_valid is True
        assert result.manifest_matches is True
        assert result.errors == []
        assert result.artifact_count == 42

    def test_full_verification_success(self, tmp_path: Path) -> None:
        """Test full verification with all checks passing."""
        verifier = PackageVerifier()
        package = tmp_path / "test.tar.zst"
        sig_file = tmp_path / "test.tar.zst.sig"
        manifest = tmp_path / "manifest.json"

        # Create valid package and signature
        package.write_bytes(b"\x28\xB5\x2F\xFD" + b"data" * 300)
        sig_file.write_text("signature")

        # Create matching manifest
        manifest_data = {
            "total_artifacts": 10,
            "package_file": "test.tar.zst",
            "package_size": package.stat().st_size,
            "images": [],
            "repositories": [],
        }
        manifest.write_text(json.dumps(manifest_data))

        # Mock cosign and zarf as available and successful
        mock_cosign_result = Mock(returncode=0)
        mock_zarf_result = Mock(returncode=0, stdout="package info")

        with patch("shutil.which") as mock_which:
            mock_which.side_effect = lambda x: f"/usr/bin/{x}" if x in ["cosign", "zarf"] else None

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = [mock_cosign_result, mock_zarf_result, mock_zarf_result]

                result = verifier.verify(package, manifest)

        assert result.success is True
        assert result.signature_valid is True
        assert result.checksums_valid is True
        assert result.manifest_matches is True
        assert len(result.errors) == 0
        assert result.artifact_count == 10
