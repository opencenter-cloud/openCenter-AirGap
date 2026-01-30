"""Package verification for integrity and signature validation.

This module provides functionality for verifying Zarf package integrity,
signatures, and comparing against artifact manifests.
"""

from dataclasses import dataclass
from pathlib import Path

from opencenter_build.exceptions import ValidationError


@dataclass
class VerificationResult:
    """Package verification result.

    Attributes:
        success: Whether verification passed
        signature_valid: Cosign signature validation result
        checksums_valid: Internal checksum validation result
        manifest_matches: Artifact manifest comparison result
        errors: List of error messages
        artifact_count: Number of artifacts verified
    """

    success: bool
    signature_valid: bool
    checksums_valid: bool
    manifest_matches: bool
    errors: list[str]
    artifact_count: int


class PackageVerifier:
    """Verify Zarf package integrity and signatures.

    Provides methods for verifying package integrity through:
    - Cosign signature validation
    - Internal checksum verification
    - Artifact manifest comparison
    """

    def verify(
        self,
        package_path: Path,
        manifest_path: Path | None = None,
    ) -> VerificationResult:
        """Verify package integrity.

        Performs multiple verification checks:
        1. Cosign signature validation (if available)
        2. Internal checksum verification
        3. Artifact manifest comparison (if manifest provided)

        Args:
            package_path: Path to Zarf package
            manifest_path: Optional path to artifact manifest

        Returns:
            VerificationResult with detailed status

        Raises:
            ValidationError: If package file not found
        """
        if not package_path.exists():
            raise ValidationError(f"Package not found: {package_path}")

        errors: list[str] = []

        # Verify signature
        signature_valid = self._verify_signature(package_path)
        if not signature_valid:
            errors.append("Signature verification failed or not available")

        # Verify checksums
        checksums_valid = self._verify_checksums(package_path)
        if not checksums_valid:
            errors.append("Checksum verification failed")

        # Compare manifest if provided
        manifest_matches = True
        artifact_count = 0

        if manifest_path:
            manifest_errors = self._compare_manifest(package_path, manifest_path)
            if manifest_errors:
                manifest_matches = False
                errors.extend(manifest_errors)
            else:
                # Count artifacts from manifest
                try:
                    import json

                    manifest_data = json.loads(manifest_path.read_text())
                    artifact_count = manifest_data.get("total_artifacts", 0)
                except Exception:
                    pass

        success = signature_valid and checksums_valid and manifest_matches

        return VerificationResult(
            success=success,
            signature_valid=signature_valid,
            checksums_valid=checksums_valid,
            manifest_matches=manifest_matches,
            errors=errors,
            artifact_count=artifact_count,
        )

    def _verify_signature(self, package_path: Path) -> bool:
        """Verify Cosign signature.

        Args:
            package_path: Path to package

        Returns:
            True if signature valid, False otherwise
        """
        import shutil
        import subprocess

        # Check if cosign is available
        if not shutil.which("cosign"):
            return False

        # Check if signature file exists
        sig_path = package_path.with_suffix(package_path.suffix + ".sig")
        if not sig_path.exists():
            return False

        try:
            # Verify signature using cosign
            # cosign verify-blob --signature <sig> --key <key> <package>
            # For keyless signing: cosign verify-blob --signature <sig> <package>
            result = subprocess.run(
                ["cosign", "verify-blob", "--signature", str(sig_path), str(package_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return False

    def _verify_checksums(self, package_path: Path) -> bool:
        """Verify internal checksums.

        Args:
            package_path: Path to package

        Returns:
            True if checksums valid, False otherwise
        """
        import shutil
        import subprocess

        # Check if zarf is available
        if not shutil.which("zarf"):
            # Fallback: verify package file integrity with basic checks
            try:
                # Check file is readable and has reasonable size
                stat = package_path.stat()
                if stat.st_size < 1024:  # Package should be at least 1KB
                    return False

                # Verify it's a valid tar.zst file by checking magic bytes
                with open(package_path, "rb") as f:
                    magic = f.read(4)
                    # Zstandard magic number: 0x28, 0xB5, 0x2F, 0xFD
                    if len(magic) < 4 or magic[:4] != b"\x28\xB5\x2F\xFD":
                        return False

                return True
            except Exception:
                return False

        try:
            # Use zarf to inspect package (validates internal structure)
            # Note: --insecure flag skips signature validation
            result = subprocess.run(
                ["zarf", "package", "inspect", str(package_path), "--insecure"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            # If zarf can inspect it, internal structure is valid
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return False

    def _compare_manifest(
        self,
        package_path: Path,
        manifest_path: Path,
    ) -> list[str]:
        """Compare artifact manifest against package contents.

        Args:
            package_path: Path to package
            manifest_path: Path to artifact manifest

        Returns:
            List of discrepancies (empty if match)
        """
        import json
        import shutil
        import subprocess

        errors: list[str] = []

        if not manifest_path.exists():
            errors.append(f"Manifest not found: {manifest_path}")
            return errors

        try:
            manifest_data = json.loads(manifest_path.read_text())

            # Basic validation
            if "total_artifacts" not in manifest_data:
                errors.append("Manifest missing total_artifacts field")
                return errors

            # If zarf is available, extract package metadata
            if shutil.which("zarf"):
                try:
                    result = subprocess.run(
                        [
                            "zarf",
                            "package",
                            "inspect",
                            str(package_path),
                            "--insecure",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )

                    if result.returncode == 0:
                        # Parse zarf inspect output to compare components
                        package_info = result.stdout

                        # Compare image counts
                        if "images" in manifest_data:
                            manifest_image_count = len(manifest_data["images"])
                            # Count images in zarf output (rough heuristic)
                            package_image_count = package_info.count("registry.k8s.io") + package_info.count(
                                "docker.io"
                            )

                            if manifest_image_count > 0 and package_image_count == 0:
                                errors.append(
                                    f"Manifest lists {manifest_image_count} images but package inspection found none"
                                )

                        # Compare repository counts
                        if "repositories" in manifest_data:
                            manifest_repo_count = len(manifest_data["repositories"])
                            package_repo_count = package_info.count("https://github.com")

                            if manifest_repo_count > 0 and package_repo_count == 0:
                                errors.append(
                                    f"Manifest lists {manifest_repo_count} repos but package inspection found none"
                                )

                        # Verify package metadata matches manifest
                        if "package_file" in manifest_data:
                            expected_name = manifest_data["package_file"]
                            actual_name = package_path.name
                            if expected_name != actual_name:
                                errors.append(
                                    f"Package name mismatch: manifest expects '{expected_name}', got '{actual_name}'"
                                )

                        # Verify package size if available
                        if "package_size" in manifest_data:
                            expected_size = manifest_data["package_size"]
                            actual_size = package_path.stat().st_size
                            # Allow 1% variance for compression differences
                            size_diff = abs(expected_size - actual_size) / expected_size
                            if size_diff > 0.01:
                                errors.append(
                                    f"Package size mismatch: manifest expects {expected_size} bytes, got {actual_size} bytes ({size_diff*100:.1f}% difference)"
                                )

                        # Verify package checksum if available
                        if "package_sha256" in manifest_data:
                            import hashlib

                            expected_sha = manifest_data["package_sha256"]
                            sha256 = hashlib.sha256()

                            with open(package_path, "rb") as f:
                                for chunk in iter(lambda: f.read(8192), b""):
                                    sha256.update(chunk)

                            actual_sha = sha256.hexdigest()
                            if expected_sha != actual_sha:
                                errors.append(
                                    f"Package checksum mismatch: manifest expects {expected_sha}, got {actual_sha}"
                                )

                except (subprocess.TimeoutExpired, subprocess.SubprocessError) as exc:
                    errors.append(f"Failed to inspect package: {exc}")
            else:
                # Without zarf, only do basic manifest validation
                errors.append("Zarf CLI not available - skipping detailed package comparison")

        except json.JSONDecodeError as exc:
            errors.append(f"Invalid manifest JSON: {exc}")
        except Exception as exc:
            errors.append(f"Failed to read manifest: {exc}")

        return errors
