#!/usr/bin/env python3
"""
Unit tests for SBOM verification script

Tests the core logic of verify_sbom.py without requiring actual Zarf packages.
"""

import sys
import json
from pathlib import Path

# Add scripts/build to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "build"))

from verify_sbom import SBOMVerifier, SBOMComponent, ExpectedAsset


def test_component_matching():
    """Test that component matching works correctly"""
    
    # Create a mock verifier
    verifier = SBOMVerifier(Path("dummy.tar.zst"), verbose=False)
    
    # Initialize sbom_data (not raw format)
    verifier.sbom_data = {}
    
    # Add some mock components
    verifier.components = [
        SBOMComponent("kube-apiserver", "v1.34.3", "image"),
        SBOMComponent("registry", "2.8.3", "image"),
        SBOMComponent("ansible", "10.7.0", "package"),
    ]
    
    # Test exact matches
    assert verifier.verify_component_present(
        ExpectedAsset("kube-apiserver", "v1.34.3", "image")
    ), "Should find exact match for kube-apiserver"
    
    assert verifier.verify_component_present(
        ExpectedAsset("registry", "2.8.3", "image")
    ), "Should find exact match for registry"
    
    # Test version without 'v' prefix
    assert verifier.verify_component_present(
        ExpectedAsset("kube-apiserver", "1.34.3", "image")
    ), "Should match version without 'v' prefix"
    
    # Test partial name match
    assert verifier.verify_component_present(
        ExpectedAsset("apiserver", "v1.34.3", "image")
    ), "Should match partial name"
    
    # Test missing component
    assert not verifier.verify_component_present(
        ExpectedAsset("missing-component", "1.0.0", "image")
    ), "Should not find missing component"
    
    print("✓ Component matching tests passed")


def test_raw_text_format():
    """Test SBOM verification with raw text format"""
    
    verifier = SBOMVerifier(Path("dummy.tar.zst"), verbose=False)
    
    # Simulate raw text SBOM
    verifier.sbom_data = {
        "raw": """
        kube-apiserver v1.34.3
        registry 2.8.3
        ansible 10.7.0
        """
    }
    
    # Test matching in raw text
    assert verifier.verify_component_present(
        ExpectedAsset("kube-apiserver", "v1.34.3", "image")
    ), "Should find component in raw text"
    
    assert verifier.verify_component_present(
        ExpectedAsset("registry", "2.8.3", "image")
    ), "Should find registry in raw text"
    
    assert not verifier.verify_component_present(
        ExpectedAsset("missing", "1.0.0", "image")
    ), "Should not find missing component in raw text"
    
    print("✓ Raw text format tests passed")


def test_syft_json_parsing():
    """Test parsing of Syft JSON format"""
    
    verifier = SBOMVerifier(Path("dummy.tar.zst"), verbose=False)
    
    # Simulate Syft JSON format
    verifier.sbom_data = {
        "artifacts": [
            {
                "name": "kube-apiserver",
                "version": "v1.34.3",
                "type": "image",
                "purl": "pkg:oci/kube-apiserver@v1.34.3"
            },
            {
                "name": "registry",
                "version": "2.8.3",
                "type": "image"
            }
        ]
    }
    
    # Parse components
    assert verifier.parse_components(), "Should parse Syft JSON successfully"
    assert len(verifier.components) == 2, "Should parse 2 components"
    
    # Check first component
    comp1 = verifier.components[0]
    assert comp1.name == "kube-apiserver"
    assert comp1.version == "v1.34.3"
    assert comp1.type == "image"
    assert comp1.purl == "pkg:oci/kube-apiserver@v1.34.3"
    
    print("✓ Syft JSON parsing tests passed")


def test_cyclonedx_parsing():
    """Test parsing of CycloneDX format"""
    
    verifier = SBOMVerifier(Path("dummy.tar.zst"), verbose=False)
    
    # Simulate CycloneDX format
    verifier.sbom_data = {
        "components": [
            {
                "name": "nginx",
                "version": "1.29.2",
                "type": "container",
                "purl": "pkg:docker/nginx@1.29.2"
            }
        ]
    }
    
    # Parse components
    assert verifier.parse_components(), "Should parse CycloneDX successfully"
    assert len(verifier.components) == 1, "Should parse 1 component"
    
    comp = verifier.components[0]
    assert comp.name == "nginx"
    assert comp.version == "1.29.2"
    
    print("✓ CycloneDX parsing tests passed")


def test_version_information_check():
    """Test version information verification"""
    
    verifier = SBOMVerifier(Path("dummy.tar.zst"), verbose=False)
    verifier.sbom_data = {}  # Initialize sbom_data
    
    # All components have versions
    verifier.components = [
        SBOMComponent("comp1", "1.0.0", "image"),
        SBOMComponent("comp2", "2.0.0", "package"),
    ]
    
    assert verifier.verify_version_information(), "Should pass when all have versions"
    
    # Some components missing versions (should still pass with warning)
    verifier.components = [
        SBOMComponent("comp1", "1.0.0", "image"),
        SBOMComponent("comp2", "unknown", "package"),
        SBOMComponent("comp3", "", "binary"),
    ]
    
    assert verifier.verify_version_information(), "Should pass with warning for missing versions"
    
    print("✓ Version information tests passed")


def test_expected_assets_list():
    """Test that expected assets list is reasonable"""
    
    verifier = SBOMVerifier(Path("dummy.tar.zst"), verbose=False)
    expected = verifier.get_expected_assets()
    
    # Should have multiple asset types
    types = set(asset.type for asset in expected)
    assert "image" in types, "Should expect images"
    assert "binary" in types, "Should expect binaries"
    assert "package" in types, "Should expect packages"
    
    # Should have key components
    names = [asset.name for asset in expected]
    assert "kube-apiserver" in names, "Should expect kube-apiserver"
    assert "registry" in names, "Should expect registry"
    assert "ansible" in names, "Should expect ansible"
    
    # All should have versions
    for asset in expected:
        assert asset.version, f"Asset {asset.name} should have version"
        assert asset.version != "unknown", f"Asset {asset.name} should have real version"
    
    print("✓ Expected assets list tests passed")


def run_all_tests():
    """Run all unit tests"""
    print("Running SBOM verifier unit tests...\n")
    
    try:
        test_component_matching()
        test_raw_text_format()
        test_syft_json_parsing()
        test_cyclonedx_parsing()
        test_version_information_check()
        test_expected_assets_list()
        
        print("\n" + "=" * 60)
        print("✓ All SBOM verifier tests PASSED")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
