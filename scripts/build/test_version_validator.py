#!/usr/bin/env python3
"""
Test suite for version_validator.py

Tests version parsing and validation logic.
"""

import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.build.version_validator import (
    VersionParser,
    VersionType,
    VersionValidator,
    VersionSpec
)


def test_version_parser():
    """Test version parsing logic"""
    print("Testing VersionParser...")
    
    test_cases = [
        # Pinned versions
        ("v1.2.3", VersionType.PINNED),
        ("1.2.3", VersionType.PINNED),
        ("v1.2", VersionType.PINNED),
        ("1.2", VersionType.PINNED),
        ("v1.2.3-alpha", VersionType.PINNED),
        ("1.2.3-rc.1", VersionType.PINNED),
        ("2.8.3", VersionType.PINNED),
        ("1.29.2", VersionType.PINNED),
        ("abc123def456", VersionType.PINNED),  # Short git SHA
        ("abc123def456789012345678901234567890abcd", VersionType.PINNED),  # Full git SHA
        
        # Latest tag
        ("latest", VersionType.LATEST),
        ("LATEST", VersionType.LATEST),
        
        # Stable tag
        ("stable", VersionType.STABLE),
        ("STABLE", VersionType.STABLE),
        
        # Unpinned versions
        ("master", VersionType.UNPINNED),
        ("main", VersionType.UNPINNED),
        ("dev", VersionType.UNPINNED),
        ("edge", VersionType.UNPINNED),
        
        # Wildcards
        ("1.2.*", VersionType.WILDCARD),
        ("1.x", VersionType.WILDCARD),
        ("*", VersionType.WILDCARD),
        
        # Version ranges (unpinned)
        (">=1.2.3", VersionType.UNPINNED),
        ("~1.2.3", VersionType.UNPINNED),
        ("^1.2.3", VersionType.UNPINNED),
        (">1.0.0", VersionType.UNPINNED),
        
        # Empty/invalid
        ("", VersionType.UNPINNED),
        ("   ", VersionType.UNPINNED),
    ]
    
    passed = 0
    failed = 0
    
    for version, expected in test_cases:
        result = VersionParser.parse_version(version)
        if result == expected:
            passed += 1
            print(f"  ✓ '{version}' -> {result.value}")
        else:
            failed += 1
            print(f"  ✗ '{version}' -> {result.value} (expected: {expected.value})")
    
    print(f"\nVersion parser: {passed} passed, {failed} failed")
    return failed == 0


def test_image_tag_extraction():
    """Test container image tag extraction"""
    print("\nTesting image tag extraction...")
    
    test_cases = [
        ("registry.k8s.io/kube-apiserver:v1.28.6", [("registry.k8s.io/kube-apiserver", "v1.28.6")]),
        ("nginx:1.29.2", [("nginx", "1.29.2")]),
        ("quay.io/keycloak/keycloak:21.1.1", [("quay.io/keycloak/keycloak", "21.1.1")]),
        ("image: nginx:latest", [("nginx", "latest")]),
        ("  - registry:2", [("registry", "2")]),
    ]
    
    passed = 0
    failed = 0
    
    for line, expected in test_cases:
        result = VersionParser.extract_image_tags(line)
        if result == expected:
            passed += 1
            print(f"  ✓ '{line}' -> {result}")
        else:
            failed += 1
            print(f"  ✗ '{line}' -> {result} (expected: {expected})")
    
    print(f"\nImage tag extraction: {passed} passed, {failed} failed")
    return failed == 0


def test_env_version_extraction():
    """Test environment variable version extraction"""
    print("\nTesting environment variable extraction...")
    
    test_cases = [
        ('KUBERNETES_VERSION="v1.34.3"', [("KUBERNETES_VERSION", "v1.34.3")]),
        ('KUBESPRAY_VERSION="master"', [("KUBESPRAY_VERSION", "master")]),
        ("TERRAFORM_VERSION=1.6.6", [("TERRAFORM_VERSION", "1.6.6")]),
        ('NGINX_VERSION="1.29.2"', [("NGINX_VERSION", "1.29.2")]),
    ]
    
    passed = 0
    failed = 0
    
    for line, expected in test_cases:
        result = VersionParser.extract_env_versions(line)
        if result == expected:
            passed += 1
            print(f"  ✓ '{line}' -> {result}")
        else:
            failed += 1
            print(f"  ✗ '{line}' -> {result} (expected: {expected})")
    
    print(f"\nEnv version extraction: {passed} passed, {failed} failed")
    return failed == 0


def test_validator_with_files():
    """Test validator with actual files"""
    print("\nTesting validator with files...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create test files
        config_dir = tmppath / "config"
        config_dir.mkdir()
        
        # Good file (all pinned)
        good_file = config_dir / "good.env"
        good_file.write_text("""
KUBERNETES_VERSION="v1.34.3"
TERRAFORM_VERSION="1.6.6"
NGINX_VERSION="1.29.2"
""")
        
        # Bad file (unpinned versions)
        bad_file = config_dir / "bad.env"
        bad_file.write_text("""
KUBESPRAY_VERSION="master"
FLUXCD_VERSION="latest"
GITEA_VERSION="stable"
""")
        
        # Test good file
        validator = VersionValidator(tmppath)
        validator.violations = validator.scan_file(good_file)
        
        if len(validator.violations) == 0:
            print("  ✓ Good file: no violations found")
            good_passed = True
        else:
            print(f"  ✗ Good file: {len(validator.violations)} violations found")
            good_passed = False
        
        # Test bad file
        validator.violations = validator.scan_file(bad_file)
        
        if len(validator.violations) == 3:
            print("  ✓ Bad file: 3 violations found")
            bad_passed = True
        else:
            print(f"  ✗ Bad file: {len(validator.violations)} violations found (expected 3)")
            bad_passed = False
        
        # Check violation types
        types_correct = True
        expected_types = {
            "master": VersionType.UNPINNED,
            "latest": VersionType.LATEST,
            "stable": VersionType.STABLE,
        }
        
        for violation in validator.violations:
            expected_type = expected_types.get(violation.version_string)
            if expected_type and violation.version_type == expected_type:
                print(f"  ✓ Violation type correct: {violation.version_string} -> {violation.version_type.value}")
            else:
                print(f"  ✗ Violation type incorrect: {violation.version_string} -> {violation.version_type.value}")
                types_correct = False
        
        return good_passed and bad_passed and types_correct


def main():
    """Run all tests"""
    print("=" * 60)
    print("Version Validator Test Suite")
    print("=" * 60)
    
    results = []
    
    results.append(("Version Parser", test_version_parser()))
    results.append(("Image Tag Extraction", test_image_tag_extraction()))
    results.append(("Env Version Extraction", test_env_version_extraction()))
    results.append(("File Validator", test_validator_with_files()))
    
    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
