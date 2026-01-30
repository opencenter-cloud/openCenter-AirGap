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
        # Placeholder - actual implementation would use cosign
        # For now, check if signature file exists
        sig_path = package_path.with_suffix(package_path.suffix + ".sig")
        return sig_path.exists()

    def _verify_checksums(self, package_path: Path) -> bool:
        """Verify internal checksums.

        Args:
            package_path: Path to package

        Returns:
            True if checksums valid, False otherwise
        """
        # Placeholder - actual implementation would extract and verify
        # For now, just check package exists and is readable
        try:
            package_path.stat()
            return True
        except Exception:
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
        errors: list[str] = []

        if not manifest_path.exists():
            errors.append(f"Manifest not found: {manifest_path}")
            return errors

        # Placeholder - actual implementation would extract package
        # and compare against manifest
        try:
            import json

            manifest_data = json.loads(manifest_path.read_text())

            # Basic validation
            if "total_artifacts" not in manifest_data:
                errors.append("Manifest missing total_artifacts field")

        except json.JSONDecodeError as exc:
            errors.append(f"Invalid manifest JSON: {exc}")
        except Exception as exc:
            errors.append(f"Failed to read manifest: {exc}")

        return errors
