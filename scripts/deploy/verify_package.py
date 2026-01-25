#!/usr/bin/env python3
"""
Verify Zarf package integrity before deployment.

This script verifies package checksums and optional Cosign signatures
to ensure no tampering occurred during transport.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


class VerificationError(Exception):
    """Raised when package verification fails."""
    pass


def calculate_md5(filepath: Path) -> str:
    """Calculate MD5 checksum of a file."""
    import hashlib
    
    md5_hash = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def calculate_sha256(filepath: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    import hashlib
    
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def load_manifest(manifest_path: Path) -> Dict[str, Any]:
    """
    Load checksum manifest from file.
    
    Args:
        manifest_path: Path to manifest file (JSON or text format)
        
    Returns:
        Dictionary with checksums
        
    Raises:
        VerificationError: If manifest cannot be loaded
    """
    if not manifest_path.exists():
        raise VerificationError(f"Manifest file not found: {manifest_path}")
    
    # Try JSON format first
    if manifest_path.suffix == ".json":
        try:
            with open(manifest_path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise VerificationError(f"Invalid JSON manifest: {e}") from e
    
    # Try text format
    checksums = {}
    try:
        with open(manifest_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("MD5:"):
                    checksums["md5"] = line.split(":", 1)[1].strip()
                elif line.startswith("SHA256:"):
                    checksums["sha256"] = line.split(":", 1)[1].strip()
        
        if not checksums:
            raise VerificationError("No checksums found in manifest")
        
        return {"checksums": checksums}
        
    except OSError as e:
        raise VerificationError(f"Failed to read manifest: {e}") from e


def verify_checksums(
    package_path: Path,
    manifest_path: Path = None,
    expected_md5: str = None,
    expected_sha256: str = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Verify package checksums against manifest or expected values.
    
    Args:
        package_path: Path to package file
        manifest_path: Path to manifest file (optional)
        expected_md5: Expected MD5 checksum (optional)
        expected_sha256: Expected SHA256 checksum (optional)
        
    Returns:
        Tuple of (success, results_dict)
        
    Raises:
        VerificationError: If verification fails
        
    Requirements: 3.1, 3.2, 3.4
    """
    if not package_path.exists():
        raise VerificationError(f"Package file not found: {package_path}")
    
    results = {
        "package": str(package_path),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "checksums": {},
        "status": "unknown"
    }
    
    # Load manifest if provided
    if manifest_path:
        manifest = load_manifest(manifest_path)
        expected_md5 = manifest.get("checksums", {}).get("md5")
        expected_sha256 = manifest.get("checksums", {}).get("sha256")
    
    if not expected_md5 and not expected_sha256:
        raise VerificationError("No expected checksums provided (need manifest or explicit values)")
    
    # Calculate actual checksums
    print(f"Calculating checksums for {package_path.name}...", file=sys.stderr)
    
    actual_md5 = None
    actual_sha256 = None
    
    if expected_md5:
        actual_md5 = calculate_md5(package_path)
        results["checksums"]["md5"] = {
            "expected": expected_md5,
            "actual": actual_md5,
            "match": actual_md5.lower() == expected_md5.lower()
        }
    
    if expected_sha256:
        actual_sha256 = calculate_sha256(package_path)
        results["checksums"]["sha256"] = {
            "expected": expected_sha256,
            "actual": actual_sha256,
            "match": actual_sha256.lower() == expected_sha256.lower()
        }
    
    # Check if all checksums match
    all_match = all(
        info["match"] 
        for info in results["checksums"].values()
    )
    
    results["status"] = "passed" if all_match else "failed"
    
    return all_match, results


def verify_signature(
    package_path: Path,
    public_key_path: Path = None,
    signature_path: Path = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Verify Cosign signature for package.
    
    Args:
        package_path: Path to package file
        public_key_path: Path to Cosign public key (optional, auto-detect)
        signature_path: Path to signature file (optional, auto-detect)
        
    Returns:
        Tuple of (success, results_dict)
        
    Requirements: 3.3, 3.5
    """
    results = {
        "package": str(package_path),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "signature": {},
        "status": "unknown"
    }
    
    # Check if cosign is available
    try:
        subprocess.run(
            ["cosign", "version"],
            capture_output=True,
            check=True,
            timeout=5
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        results["status"] = "skipped"
        results["signature"]["error"] = "cosign not available"
        return True, results  # Not a failure if cosign isn't installed
    
    # Auto-detect signature file
    if signature_path is None:
        signature_path = package_path.with_suffix(package_path.suffix + ".sig")
    
    if not signature_path.exists():
        results["status"] = "skipped"
        results["signature"]["error"] = f"Signature file not found: {signature_path}"
        return True, results  # Not a failure if no signature
    
    # Auto-detect public key
    if public_key_path is None:
        # Try common locations
        for candidate in [
            Path("cosign.pub"),
            Path("/etc/opencenter/cosign.pub"),
            Path.home() / ".cosign" / "cosign.pub"
        ]:
            if candidate.exists():
                public_key_path = candidate
                break
    
    if public_key_path is None or not public_key_path.exists():
        results["status"] = "failed"
        results["signature"]["error"] = "Public key not found"
        return False, results
    
    # Verify signature with cosign
    print(f"Verifying signature with cosign...", file=sys.stderr)
    
    try:
        result = subprocess.run(
            [
                "cosign", "verify-blob",
                "--key", str(public_key_path),
                "--signature", str(signature_path),
                str(package_path)
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            results["status"] = "passed"
            results["signature"]["public_key"] = str(public_key_path)
            results["signature"]["signature_file"] = str(signature_path)
            return True, results
        else:
            results["status"] = "failed"
            results["signature"]["error"] = result.stderr.strip()
            return False, results
            
    except subprocess.TimeoutExpired:
        results["status"] = "failed"
        results["signature"]["error"] = "Verification timeout"
        return False, results
    except Exception as e:
        results["status"] = "failed"
        results["signature"]["error"] = str(e)
        return False, results


def verify_package(
    package_path: Path,
    manifest_path: Path = None,
    public_key_path: Path = None,
    skip_signature: bool = False,
    halt_on_failure: bool = True
) -> bool:
    """
    Perform complete package verification.
    
    Args:
        package_path: Path to package file
        manifest_path: Path to checksum manifest
        public_key_path: Path to Cosign public key
        skip_signature: Skip signature verification
        halt_on_failure: Exit with error code on failure
        
    Returns:
        True if verification passed, False otherwise
        
    Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
    """
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Package Verification", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"Package: {package_path}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)
    
    all_passed = True
    
    # Step 1: Verify checksums
    print("Step 1: Checksum Verification", file=sys.stderr)
    print("-" * 60, file=sys.stderr)
    
    try:
        checksum_passed, checksum_results = verify_checksums(
            package_path=package_path,
            manifest_path=manifest_path
        )
        
        for algo, info in checksum_results["checksums"].items():
            status = "✓ PASS" if info["match"] else "✗ FAIL"
            print(f"{algo.upper():8} {status}", file=sys.stderr)
            if not info["match"]:
                print(f"  Expected: {info['expected']}", file=sys.stderr)
                print(f"  Actual:   {info['actual']}", file=sys.stderr)
        
        if not checksum_passed:
            all_passed = False
            print(f"\n✗ Checksum verification FAILED", file=sys.stderr)
            if halt_on_failure:
                print(f"\nHalting deployment due to checksum mismatch", file=sys.stderr)
                return False
        else:
            print(f"\n✓ Checksum verification PASSED", file=sys.stderr)
            
    except VerificationError as e:
        print(f"✗ Checksum verification ERROR: {e}", file=sys.stderr)
        all_passed = False
        if halt_on_failure:
            return False
    
    # Step 2: Verify signature (if not skipped)
    if not skip_signature:
        print(f"\nStep 2: Signature Verification", file=sys.stderr)
        print("-" * 60, file=sys.stderr)
        
        sig_passed, sig_results = verify_signature(
            package_path=package_path,
            public_key_path=public_key_path
        )
        
        if sig_results["status"] == "skipped":
            print(f"⊘ Signature verification SKIPPED", file=sys.stderr)
            if "error" in sig_results["signature"]:
                print(f"  Reason: {sig_results['signature']['error']}", file=sys.stderr)
        elif sig_passed:
            print(f"✓ Signature verification PASSED", file=sys.stderr)
        else:
            print(f"✗ Signature verification FAILED", file=sys.stderr)
            if "error" in sig_results["signature"]:
                print(f"  Error: {sig_results['signature']['error']}", file=sys.stderr)
            all_passed = False
            if halt_on_failure:
                print(f"\nHalting deployment due to signature verification failure", file=sys.stderr)
                return False
    
    # Final result
    print(f"\n{'='*60}", file=sys.stderr)
    if all_passed:
        print(f"✓ Package verification PASSED", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        return True
    else:
        print(f"✗ Package verification FAILED", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        return False


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description="Verify Zarf package integrity before deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Verify with auto-detected manifest
  %(prog)s zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
  
  # Verify with explicit manifest
  %(prog)s -m checksums.json zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
  
  # Verify with signature
  %(prog)s -k cosign.pub zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
  
  # Skip signature verification
  %(prog)s --skip-signature zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
        """
    )
    
    parser.add_argument(
        "package",
        type=Path,
        help="Path to Zarf package file"
    )
    
    parser.add_argument(
        "-m", "--manifest",
        type=Path,
        help="Path to checksum manifest (default: auto-detect)"
    )
    
    parser.add_argument(
        "-k", "--public-key",
        type=Path,
        help="Path to Cosign public key (default: auto-detect)"
    )
    
    parser.add_argument(
        "--skip-signature",
        action="store_true",
        help="Skip signature verification"
    )
    
    parser.add_argument(
        "--no-halt",
        action="store_true",
        help="Don't halt on verification failure (for testing)"
    )
    
    args = parser.parse_args()
    
    # Auto-detect manifest if not provided
    manifest_path = args.manifest
    if manifest_path is None:
        # Try common patterns
        for candidate in [
            args.package.with_suffix(args.package.suffix + ".checksums.json"),
            args.package.with_suffix(args.package.suffix + ".checksums.txt"),
            args.package.parent / "checksums.json",
            args.package.parent / "checksums.txt"
        ]:
            if candidate.exists():
                manifest_path = candidate
                break
    
    if manifest_path is None:
        print("Error: No checksum manifest found", file=sys.stderr)
        print("Provide manifest with -m or create one with generate_checksum_manifest.py", file=sys.stderr)
        return 1
    
    try:
        success = verify_package(
            package_path=args.package,
            manifest_path=manifest_path,
            public_key_path=args.public_key,
            skip_signature=args.skip_signature,
            halt_on_failure=not args.no_halt
        )
        
        return 0 if success else 1
        
    except VerificationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
