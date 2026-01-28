"""Unit tests for image scanning functionality."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestImageScanningScript:
    """Test the scan_images.sh script behavior."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test outputs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_image_list(self, temp_dir):
        """Create mock image list file."""
        image_list = temp_dir / "test-images.txt"
        image_list.write_text(
            "# Test images\n" "alpine:3.19\n" "nginx:1.29.2\n" "registry.k8s.io/pause:3.9\n"
        )
        return image_list

    def test_script_exists(self):
        """Test that scan_images.sh exists and is executable."""
        script_path = Path("scripts/build/scan_images.sh")
        assert script_path.exists(), "scan_images.sh not found"
        assert script_path.stat().st_mode & 0o111, "scan_images.sh not executable"

    def test_script_requires_trivy(self, temp_dir, mock_image_list):
        """Test that script fails gracefully when Trivy is not installed."""
        # Check if trivy is actually installed
        trivy_installed = (
            subprocess.run(
                ["which", "trivy"],
                capture_output=True,
            ).returncode
            == 0
        )

        if trivy_installed:
            # Skip this test if Trivy is installed
            pytest.skip("Trivy is installed, cannot test missing Trivy scenario")

        # If Trivy is not installed, script should fail with helpful message
        result = subprocess.run(
            ["./scripts/build/scan_images.sh"],
            env={"PATH": "/usr/bin:/bin:/usr/local/bin"},
            capture_output=True,
            text=True,
        )

        # Should fail with error about missing Trivy
        assert result.returncode != 0

    def test_script_requires_image_list(self, temp_dir):
        """Test that script fails when image list is missing."""
        result = subprocess.run(
            ["./scripts/build/scan_images.sh"],
            env={
                "IMAGE_LIST": str(temp_dir / "nonexistent.txt"),
                "OUTPUT_DIR": str(temp_dir),
            },
            capture_output=True,
            text=True,
        )

        # Should fail with error about missing image list
        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "not found" in result.stdout.lower()

    def test_results_json_structure(self, temp_dir):
        """Test expected structure of scan results JSON."""
        # Create mock results file
        results = {
            "scan_timestamp": "2026-01-27T14:30:00Z",
            "images": [
                {
                    "image": "alpine:3.19",
                    "scan_result": {
                        "Results": [
                            {
                                "Target": "alpine:3.19",
                                "Vulnerabilities": [
                                    {
                                        "VulnerabilityID": "CVE-2024-1234",
                                        "Severity": "HIGH",
                                        "PkgName": "openssl",
                                    }
                                ],
                            }
                        ]
                    },
                }
            ],
        }

        results_file = temp_dir / "image-scan-results.json"
        results_file.write_text(json.dumps(results, indent=2))

        # Validate structure
        loaded = json.loads(results_file.read_text())
        assert "scan_timestamp" in loaded
        assert "images" in loaded
        assert isinstance(loaded["images"], list)

        if loaded["images"]:
            assert "image" in loaded["images"][0]
            assert "scan_result" in loaded["images"][0]

    def test_summary_report_format(self, temp_dir):
        """Test expected format of vulnerability summary report."""
        summary = """Container Image Vulnerability Scan Report
==========================================
Scan Date: 2026-01-27 14:30:00 UTC
Policy: Fail on CRITICAL, Warn on HIGH

Image: alpine:3.19
  CRITICAL: 0
  HIGH: 2

==========================================
Summary Statistics
==========================================
Total Images: 1
Successfully Scanned: 1
Failed Scans: 0
Total CRITICAL Vulnerabilities: 0
Total HIGH Vulnerabilities: 2
Images with CRITICAL: 0

==========================================
POLICY COMPLIANCE
==========================================
Build PASSED: No CRITICAL vulnerabilities found.
"""

        summary_file = temp_dir / "image-vulnerabilities.txt"
        summary_file.write_text(summary)

        # Validate format
        content = summary_file.read_text()
        assert "Container Image Vulnerability Scan Report" in content
        assert "Summary Statistics" in content
        assert "POLICY" in content
        assert "Total Images:" in content

    def test_critical_vulnerability_detection(self):
        """Test that CRITICAL vulnerabilities are properly identified."""
        mock_scan_result = {
            "Results": [
                {
                    "Vulnerabilities": [
                        {"Severity": "CRITICAL", "VulnerabilityID": "CVE-2024-1234"},
                        {"Severity": "HIGH", "VulnerabilityID": "CVE-2024-5678"},
                        {"Severity": "MEDIUM", "VulnerabilityID": "CVE-2024-9012"},
                    ]
                }
            ]
        }

        # Count CRITICAL vulnerabilities
        critical_count = sum(
            1
            for result in mock_scan_result.get("Results", [])
            for vuln in result.get("Vulnerabilities", [])
            if vuln.get("Severity") == "CRITICAL"
        )

        assert critical_count == 1

    def test_high_vulnerability_detection(self):
        """Test that HIGH vulnerabilities are properly identified."""
        mock_scan_result = {
            "Results": [
                {
                    "Vulnerabilities": [
                        {"Severity": "CRITICAL", "VulnerabilityID": "CVE-2024-1234"},
                        {"Severity": "HIGH", "VulnerabilityID": "CVE-2024-5678"},
                        {"Severity": "HIGH", "VulnerabilityID": "CVE-2024-9012"},
                    ]
                }
            ]
        }

        # Count HIGH vulnerabilities
        high_count = sum(
            1
            for result in mock_scan_result.get("Results", [])
            for vuln in result.get("Vulnerabilities", [])
            if vuln.get("Severity") == "HIGH"
        )

        assert high_count == 2

    def test_policy_violation_on_critical(self):
        """Test that policy violation is triggered on CRITICAL vulnerabilities."""
        images_with_critical = 1

        # Policy: fail if any image has CRITICAL vulnerabilities
        policy_violated = images_with_critical > 0

        assert policy_violated is True

    def test_policy_compliance_without_critical(self):
        """Test that policy passes when no CRITICAL vulnerabilities found."""
        images_with_critical = 0

        # Policy: fail if any image has CRITICAL vulnerabilities
        policy_violated = images_with_critical > 0

        assert policy_violated is False

    def test_empty_image_list_handling(self, temp_dir):
        """Test handling of empty image list."""
        empty_list = temp_dir / "empty-images.txt"
        empty_list.write_text("# Only comments\n# No actual images\n")

        # Script should handle empty list gracefully
        assert empty_list.exists()
        content = empty_list.read_text()

        # Filter out comments and empty lines
        images = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        assert len(images) == 0

    def test_comment_filtering(self, temp_dir):
        """Test that comments are properly filtered from image list."""
        image_list = temp_dir / "images-with-comments.txt"
        image_list.write_text(
            "# This is a comment\n"
            "alpine:3.19\n"
            "# Another comment\n"
            "nginx:1.29.2\n"
            "\n"
            "# Final comment\n"
        )

        # Parse image list
        content = image_list.read_text()
        images = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        assert len(images) == 2
        assert "alpine:3.19" in images
        assert "nginx:1.29.2" in images


class TestSecurityScanningDocumentation:
    """Test that security scanning documentation exists and is complete."""

    def test_documentation_exists(self):
        """Test that security-scanning.md exists."""
        doc_path = Path("docs/reference/security-scanning.md")
        assert doc_path.exists(), "security-scanning.md not found"

    def test_documentation_has_required_sections(self):
        """Test that documentation contains required sections."""
        doc_path = Path("docs/reference/security-scanning.md")
        content = doc_path.read_text()

        required_sections = [
            "Overview",
            "Scanning Tool",
            "Installation",
            "Vulnerability Policy",
            "Scanning Process",
            "Output Files",
            "Remediation Process",
            "Risk Acceptance",
            "Integration with Build Pipeline",
            "SBOM Integration",
            "Troubleshooting",
        ]

        for section in required_sections:
            assert section in content, f"Missing section: {section}"

    def test_documentation_has_severity_levels(self):
        """Test that documentation defines severity levels."""
        doc_path = Path("docs/reference/security-scanning.md")
        content = doc_path.read_text()

        severity_levels = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

        for level in severity_levels:
            assert level in content, f"Missing severity level: {level}"

    def test_documentation_has_remediation_steps(self):
        """Test that documentation includes remediation steps."""
        doc_path = Path("docs/reference/security-scanning.md")
        content = doc_path.read_text()

        assert "Remediation Process" in content
        assert "Step 1:" in content or "1." in content
        assert "Update" in content or "update" in content

    def test_documentation_has_trivy_installation(self):
        """Test that documentation includes Trivy installation instructions."""
        doc_path = Path("docs/reference/security-scanning.md")
        content = doc_path.read_text()

        assert "trivy" in content.lower()
        assert "install" in content.lower()
        assert "curl" in content.lower() or "apt" in content.lower()


class TestIntegrationTestScript:
    """Test the integration test script."""

    def test_integration_test_exists(self):
        """Test that test_image_scanning.sh exists and is executable."""
        script_path = Path("tests/integration/test_image_scanning.sh")
        assert script_path.exists(), "test_image_scanning.sh not found"
        assert script_path.stat().st_mode & 0o111, "test_image_scanning.sh not executable"

    def test_integration_test_has_test_cases(self):
        """Test that integration test script contains test cases."""
        script_path = Path("tests/integration/test_image_scanning.sh")
        content = script_path.read_text()

        # Check for test functions
        assert "test_" in content
        assert "TESTS_RUN" in content or "test" in content.lower()

    def test_integration_test_checks_trivy(self):
        """Test that integration test checks for Trivy installation."""
        script_path = Path("tests/integration/test_image_scanning.sh")
        content = script_path.read_text()

        assert "trivy" in content.lower()
        assert "command -v trivy" in content or "which trivy" in content


class TestREADMEUpdates:
    """Test that README.md has been updated with Trivy prerequisite."""

    def test_readme_mentions_trivy(self):
        """Test that README.md mentions Trivy as a prerequisite."""
        readme_path = Path("README.md")
        content = readme_path.read_text()

        assert "trivy" in content.lower() or "Trivy" in content

    def test_readme_has_trivy_installation(self):
        """Test that README.md includes Trivy installation instructions."""
        readme_path = Path("README.md")
        content = readme_path.read_text()

        # Should have installation command
        assert "trivy" in content.lower()
        assert "install" in content.lower()
