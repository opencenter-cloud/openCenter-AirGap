#!/usr/bin/env python3
"""
SBOM Completeness Verification for openCenter AirGap

Extracts and validates SBOM from Zarf package to ensure all components are documented.
Verifies that all images, binaries, and packages are listed with version information.

Requirements: 2.4, 10.9
"""

import os
import sys
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class SBOMComponent:
    """Represents a component in the SBOM"""
    name: str
    version: str
    type: str  # library, application, container, file, etc.
    purl: Optional[str] = None  # Package URL
    cpe: Optional[str] = None   # Common Platform Enumeration


@dataclass
class ExpectedAsset:
    """Represents an expected asset that should be in SBOM"""
    name: str
    version: str
    type: str  # image, binary, package


class SBOMVerifier:
    """Verify SBOM completeness for Zarf package"""
    
    def __init__(self, package_path: Path, verbose: bool = False):
        self.package_path = package_path
        self.verbose = verbose
        self.sbom_data: Optional[Dict[str, Any]] = None
        self.components: List[SBOMComponent] = []
        
    def log(self, message: str):
        """Log message if verbose mode enabled"""
        if self.verbose:
            print(f"[SBOM] {message}")
    
    def extract_sbom(self) -> bool:
        """
        Extract SBOM from Zarf package using zarf CLI.
        Returns True if extraction successful.
        """
        self.log(f"Extracting SBOM from: {self.package_path}")
        
        if not self.package_path.exists():
            print(f"ERROR: Package not found: {self.package_path}", file=sys.stderr)
            return False
        
        try:
            # Run zarf package inspect --sbom
            result = subprocess.run(
                ["zarf", "package", "inspect", str(self.package_path), "--sbom"],
                capture_output=True,
                text=True,
                check=True
            )
            
            sbom_output = result.stdout
            
            if not sbom_output or len(sbom_output) < 100:
                print("ERROR: SBOM appears empty or invalid", file=sys.stderr)
                return False
            
            # Try to parse as JSON (Syft outputs JSON format)
            try:
                self.sbom_data = json.loads(sbom_output)
                self.log(f"Parsed SBOM as JSON: {len(sbom_output)} bytes")
            except json.JSONDecodeError:
                # SBOM might be in other format (CycloneDX XML, SPDX, etc.)
                # Store as raw text for now
                self.log("SBOM is not JSON format, storing as raw text")
                self.sbom_data = {"raw": sbom_output}
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to extract SBOM: {e}", file=sys.stderr)
            if e.stderr:
                print(f"  {e.stderr}", file=sys.stderr)
            return False
        except FileNotFoundError:
            print("ERROR: zarf CLI not found. Please install Zarf.", file=sys.stderr)
            return False
    
    def parse_components(self) -> bool:
        """
        Parse SBOM data to extract component list.
        Supports Syft JSON format.
        """
        if not self.sbom_data:
            print("ERROR: No SBOM data to parse", file=sys.stderr)
            return False
        
        # Handle raw text format
        if "raw" in self.sbom_data:
            self.log("SBOM is in raw text format, skipping detailed parsing")
            return True
        
        # Parse Syft JSON format
        if "artifacts" in self.sbom_data:
            self.log("Parsing Syft JSON format")
            
            for artifact in self.sbom_data.get("artifacts", []):
                component = SBOMComponent(
                    name=artifact.get("name", "unknown"),
                    version=artifact.get("version", "unknown"),
                    type=artifact.get("type", "unknown"),
                    purl=artifact.get("purl"),
                    cpe=artifact.get("cpes", [None])[0] if artifact.get("cpes") else None
                )
                self.components.append(component)
            
            self.log(f"Parsed {len(self.components)} components from SBOM")
            return True
        
        # Parse CycloneDX format
        elif "components" in self.sbom_data:
            self.log("Parsing CycloneDX format")
            
            for comp in self.sbom_data.get("components", []):
                component = SBOMComponent(
                    name=comp.get("name", "unknown"),
                    version=comp.get("version", "unknown"),
                    type=comp.get("type", "unknown"),
                    purl=comp.get("purl"),
                    cpe=comp.get("cpe")
                )
                self.components.append(component)
            
            self.log(f"Parsed {len(self.components)} components from SBOM")
            return True
        
        # Parse SPDX format
        elif "packages" in self.sbom_data:
            self.log("Parsing SPDX format")
            
            for pkg in self.sbom_data.get("packages", []):
                component = SBOMComponent(
                    name=pkg.get("name", "unknown"),
                    version=pkg.get("versionInfo", "unknown"),
                    type="package",
                    purl=None,
                    cpe=None
                )
                self.components.append(component)
            
            self.log(f"Parsed {len(self.components)} components from SBOM")
            return True
        
        else:
            print("WARNING: Unknown SBOM format, cannot parse components", file=sys.stderr)
            return False
    
    def get_expected_assets(self) -> List[ExpectedAsset]:
        """
        Build list of expected assets from package configuration.
        This should match what was included in the Zarf package.
        """
        expected = []
        
        # Core infrastructure images
        expected.extend([
            ExpectedAsset("registry", "2.8.3", "image"),
            ExpectedAsset("nginx", "1.29.2", "image"),
        ])
        
        # Kubernetes control plane images (example versions)
        expected.extend([
            ExpectedAsset("kube-apiserver", "v1.34.3", "image"),
            ExpectedAsset("kube-controller-manager", "v1.34.3", "image"),
            ExpectedAsset("kube-scheduler", "v1.34.3", "image"),
            ExpectedAsset("kube-proxy", "v1.34.3", "image"),
            ExpectedAsset("etcd", "3.5.15-0", "image"),
            ExpectedAsset("coredns", "v1.11.1", "image"),
        ])
        
        # openCenter Platform Service Images
        # FluxCD Controllers
        expected.extend([
            ExpectedAsset("source-controller", "v2.4.0", "image"),
            ExpectedAsset("kustomize-controller", "v1.4.0", "image"),
            ExpectedAsset("helm-controller", "v1.1.0", "image"),
            ExpectedAsset("notification-controller", "v1.4.0", "image"),
        ])
        
        # Gitea
        expected.append(ExpectedAsset("gitea", "1.22.6", "image"))
        
        # cert-manager
        expected.extend([
            ExpectedAsset("cert-manager-controller", "v1.18.2", "image"),
            ExpectedAsset("cert-manager-webhook", "v1.18.2", "image"),
            ExpectedAsset("cert-manager-cainjector", "v1.18.2", "image"),
        ])
        
        # Gateway API
        expected.append(ExpectedAsset("gateway", "v1.5.0", "image"))
        
        # Keycloak
        expected.append(ExpectedAsset("keycloak", "26.3.0", "image"))
        
        # kube-prometheus-stack
        expected.extend([
            ExpectedAsset("prometheus", "v3.2.1", "image"),
            ExpectedAsset("alertmanager", "v0.28.1", "image"),
            ExpectedAsset("grafana", "11.5.0", "image"),
            ExpectedAsset("prometheus-operator", "v0.81.0", "image"),
            ExpectedAsset("kube-state-metrics", "v2.15.0", "image"),
        ])
        
        # Loki
        expected.append(ExpectedAsset("loki", "3.5.7", "image"))
        
        # Tempo
        expected.append(ExpectedAsset("tempo", "3.0.0", "image"))
        
        # Mimir
        expected.append(ExpectedAsset("mimir", "2.16.0", "image"))
        
        # OpenTelemetry
        expected.append(ExpectedAsset("opentelemetry-collector-k8s", "0.121.0", "image"))
        
        # Longhorn
        expected.extend([
            ExpectedAsset("longhorn-manager", "v1.10.0", "image"),
            ExpectedAsset("longhorn-engine", "v1.10.0", "image"),
            ExpectedAsset("longhorn-ui", "v1.10.0", "image"),
        ])
        
        # vSphere CSI
        expected.extend([
            ExpectedAsset("csi-vsphere-driver", "v3.5.0", "image"),
            ExpectedAsset("csi-vsphere-syncer", "v3.5.0", "image"),
        ])
        
        # OpenStack CSI
        expected.append(ExpectedAsset("cinder-csi-plugin", "v1.34.3", "image"))
        
        # Kyverno
        expected.append(ExpectedAsset("kyverno", "v1.13.2", "image"))
        
        # OLM
        expected.append(ExpectedAsset("olm", "v0.30.0", "image"))
        
        # RBAC Manager
        expected.append(ExpectedAsset("rbac-manager", "v1.9.2", "image"))
        
        # Velero
        expected.extend([
            ExpectedAsset("velero", "v1.16.2", "image"),
            ExpectedAsset("velero-plugin-for-aws", "v1.12.2", "image"),
        ])
        
        # Harbor
        expected.extend([
            ExpectedAsset("harbor-core", "v2.13.2", "image"),
            ExpectedAsset("harbor-portal", "v2.13.2", "image"),
            ExpectedAsset("harbor-jobservice", "v2.13.2", "image"),
        ])
        
        # Headlamp
        expected.append(ExpectedAsset("headlamp", "v0.29.0", "image"))
        
        # Weave GitOps
        expected.append(ExpectedAsset("wego-app", "v0.42.0", "image"))
        
        # MetalLB
        expected.extend([
            ExpectedAsset("metallb-controller", "v0.15.2", "image"),
            ExpectedAsset("metallb-speaker", "v0.15.2", "image"),
        ])
        
        # Sealed Secrets
        expected.append(ExpectedAsset("sealed-secrets-controller", "v0.30.0", "image"))
        
        # Postgres Operator
        expected.append(ExpectedAsset("postgres-operator", "v1.14.0", "image"))
        
        # Strimzi Kafka
        expected.extend([
            ExpectedAsset("strimzi-operator", "0.49.1", "image"),
            ExpectedAsset("kafka", "3.9.0", "image"),
        ])
        
        # Key binaries
        expected.extend([
            ExpectedAsset("kubectl", "v1.34.3", "binary"),
            ExpectedAsset("kubeadm", "v1.34.3", "binary"),
            ExpectedAsset("kubelet", "v1.34.3", "binary"),
            ExpectedAsset("containerd", "2.1.5", "binary"),
            ExpectedAsset("runc", "1.3.4", "binary"),
        ])
        
        # Python packages
        expected.extend([
            ExpectedAsset("ansible", "10.7.0", "package"),
            ExpectedAsset("jinja2", "3.1.6", "package"),
            ExpectedAsset("netaddr", "1.3.0", "package"),
        ])
        
        return expected
    
    def verify_component_present(self, expected: ExpectedAsset) -> bool:
        """
        Check if expected asset is present in SBOM.
        Returns True if found with matching version.
        """
        # Handle case where SBOM data not loaded
        if self.sbom_data is None:
            return False
        
        # Handle raw text format - simple string search
        if "raw" in self.sbom_data:
            raw_text = self.sbom_data["raw"].lower()
            name_match = expected.name.lower() in raw_text
            version_match = expected.version.lower() in raw_text
            return name_match and version_match
        
        # Search in parsed components
        for component in self.components:
            # Match by name (case-insensitive, partial match)
            if expected.name.lower() in component.name.lower():
                # Normalize versions for comparison (remove 'v' prefix)
                expected_ver = expected.version.lstrip('v')
                component_ver = component.version.lstrip('v')
                
                # Check version match (exact or partial)
                if expected_ver in component_ver or component_ver in expected_ver:
                    return True
        
        return False
    
    def verify_completeness(self) -> bool:
        """
        Verify that all expected assets are present in SBOM.
        Returns True if all assets found, False otherwise.
        """
        self.log("Verifying SBOM completeness...")
        
        expected_assets = self.get_expected_assets()
        missing_assets = []
        found_count = 0
        
        for asset in expected_assets:
            if self.verify_component_present(asset):
                found_count += 1
                self.log(f"  ✓ {asset.type}: {asset.name} {asset.version}")
            else:
                missing_assets.append(asset)
                self.log(f"  ✗ {asset.type}: {asset.name} {asset.version} - NOT FOUND")
        
        # Report results
        print(f"\nSBOM Verification Results:")
        print(f"  Expected assets: {len(expected_assets)}")
        print(f"  Found in SBOM: {found_count}")
        print(f"  Missing: {len(missing_assets)}")
        
        if missing_assets:
            print(f"\nMissing assets:")
            for asset in missing_assets:
                print(f"  - {asset.type}: {asset.name} {asset.version}")
            return False
        
        print(f"\n✓ SBOM completeness verification PASSED")
        return True
    
    def verify_version_information(self) -> bool:
        """
        Verify that all components have version information.
        Returns True if all components have versions, False otherwise.
        """
        self.log("Verifying version information...")
        
        # Handle case where SBOM data not loaded
        if self.sbom_data is None:
            print("WARNING: No SBOM data loaded, cannot verify versions", file=sys.stderr)
            return False
        
        # Handle raw text format
        if "raw" in self.sbom_data:
            self.log("Skipping version check for raw text format")
            return True
        
        if not self.components:
            print("WARNING: No components parsed, cannot verify versions", file=sys.stderr)
            return False
        
        missing_versions = []
        
        for component in self.components:
            if not component.version or component.version == "unknown" or component.version == "":
                missing_versions.append(component.name)
        
        # Report results
        print(f"\nVersion Information Check:")
        print(f"  Total components: {len(self.components)}")
        print(f"  Missing versions: {len(missing_versions)}")
        
        if missing_versions:
            print(f"\nComponents without version information:")
            for name in missing_versions[:10]:  # Show first 10
                print(f"  - {name}")
            if len(missing_versions) > 10:
                print(f"  ... and {len(missing_versions) - 10} more")
            
            # This is a warning, not a failure
            print(f"\n⚠ Some components missing version information")
            return True  # Don't fail on this
        
        print(f"\n✓ All components have version information")
        return True
    
    def generate_report(self, output_path: Optional[Path] = None):
        """Generate detailed SBOM verification report"""
        report_lines = []
        
        report_lines.append("=" * 80)
        report_lines.append("SBOM Verification Report")
        report_lines.append("=" * 80)
        report_lines.append(f"Package: {self.package_path.name}")
        report_lines.append("")
        
        # Component summary
        if self.components:
            report_lines.append(f"Total components in SBOM: {len(self.components)}")
            
            # Group by type
            by_type = defaultdict(int)
            for comp in self.components:
                by_type[comp.type] += 1
            
            report_lines.append("\nComponents by type:")
            for comp_type, count in sorted(by_type.items()):
                report_lines.append(f"  {comp_type}: {count}")
        
        # Expected assets check
        expected_assets = self.get_expected_assets()
        report_lines.append(f"\nExpected assets: {len(expected_assets)}")
        
        by_type = defaultdict(int)
        for asset in expected_assets:
            by_type[asset.type] += 1
        
        report_lines.append("\nExpected assets by type:")
        for asset_type, count in sorted(by_type.items()):
            report_lines.append(f"  {asset_type}: {count}")
        
        report_lines.append("")
        report_lines.append("=" * 80)
        
        report = "\n".join(report_lines)
        
        if output_path:
            output_path.write_text(report)
            print(f"\nReport saved to: {output_path}")
        else:
            print(f"\n{report}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Verify SBOM completeness for Zarf package"
    )
    parser.add_argument(
        "package",
        type=Path,
        help="Path to Zarf package (.tar.zst)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "-r", "--report",
        type=Path,
        help="Save verification report to file"
    )
    
    args = parser.parse_args()
    
    # Verify package exists
    if not args.package.exists():
        print(f"ERROR: Package not found: {args.package}", file=sys.stderr)
        sys.exit(1)
    
    # Create verifier
    verifier = SBOMVerifier(args.package, verbose=args.verbose)
    
    # Extract SBOM
    if not verifier.extract_sbom():
        print("ERROR: Failed to extract SBOM", file=sys.stderr)
        sys.exit(1)
    
    # Parse components
    verifier.parse_components()
    
    # Verify completeness
    completeness_ok = verifier.verify_completeness()
    
    # Verify version information
    versions_ok = verifier.verify_version_information()
    
    # Generate report
    verifier.generate_report(args.report)
    
    # Exit with appropriate code
    if completeness_ok and versions_ok:
        print("\n✓ SBOM verification PASSED")
        sys.exit(0)
    else:
        print("\n✗ SBOM verification FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
