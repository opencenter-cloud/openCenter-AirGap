# Package Integrity Guide

This guide explains how to use the package integrity features for openCenter AirGap Zarf packages.

## Overview

Package integrity features ensure that Zarf packages have not been tampered with during transport from the Factory Zone (connected build environment) to the Field Zone (disconnected deployment environment).

**Features:**
- **Checksum Verification**: MD5 and SHA256 checksums detect any bit-level changes
- **Cryptographic Signing**: Optional Cosign signatures provide non-repudiation
- **Automated Verification**: Scripts halt deployment if integrity checks fail

**Requirements Satisfied:**
- 2.6: Generate MD5 and SHA256 checksums
- 2.7: Sign packages with Cosign (optional)
- 3.1: Validate MD5 checksum
- 3.2: Validate SHA256 checksum
- 3.3: Verify Cosign signature
- 3.4: Halt on checksum mismatch
- 3.5: Halt on signature verification failure

## Components

### 1. Checksum Manifest Generator

**Script:** `scripts/build/generate_checksum_manifest.py`

Generates a manifest file containing MD5 and SHA256 checksums for a Zarf package.

**Usage:**
```bash
# Generate JSON manifest (default)
python3 scripts/build/generate_checksum_manifest.py zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

# Generate text manifest
python3 scripts/build/generate_checksum_manifest.py --format text zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

# Specify output path
python3 scripts/build/generate_checksum_manifest.py -o checksums.json zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

# Print checksums to stdout
python3 scripts/build/generate_checksum_manifest.py --print zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
```

**Output (JSON format):**
```json
{
  "package": {
    "name": "zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst",
    "path": "/path/to/zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst",
    "size_bytes": 8589934592,
    "size_human": "8.00 GB"
  },
  "checksums": {
    "md5": "d41d8cd98f00b204e9800998ecf8427e",
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  },
  "metadata": {
    "generated_at": "2026-01-25T16:00:00.000000+00:00",
    "generator": "openCenter-AirGap checksum manifest generator v1.0"
  }
}
```

**Output (text format):**
```
# Checksum Manifest
# Package: zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
# Size: 8.00 GB
# Generated: 2026-01-25T16:00:00.000000+00:00

MD5:    d41d8cd98f00b204e9800998ecf8427e
SHA256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

### 2. Package Signing Script

**Script:** `scripts/build/sign_package.sh`

Signs a Zarf package using Cosign for cryptographic verification. Signing is optional but recommended for high-security environments.

**Prerequisites:**
```bash
# Install Cosign
# See: https://docs.sigstore.dev/cosign/installation/

# Generate key pair (one-time setup)
cosign generate-key-pair
# Creates: cosign.key (private), cosign.pub (public)
```

**Usage:**
```bash
# Sign with default key (cosign.key)
scripts/build/sign_package.sh zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

# Sign with specific key
scripts/build/sign_package.sh zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst /path/to/key.key

# Use environment variable for key
export COSIGN_KEY=/path/to/key.key
scripts/build/sign_package.sh zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
```

**Output:**
- `<package>.sig`: Detached signature file
- `<package>.cert`: Certificate (if available)

**Note:** If Cosign is not installed, the script will provide installation instructions and exit gracefully.

### 3. Package Verification Script

**Script:** `scripts/deploy/verify_package.py` (Python) or `scripts/deploy/verify_package.sh` (Bash wrapper)

Verifies package integrity before deployment by checking checksums and optional signatures.

**Usage:**
```bash
# Verify with auto-detected manifest
python3 scripts/deploy/verify_package.py zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

# Verify with explicit manifest
python3 scripts/deploy/verify_package.py -m checksums.json zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

# Verify with signature
python3 scripts/deploy/verify_package.py -k cosign.pub zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

# Skip signature verification
python3 scripts/deploy/verify_package.py --skip-signature zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

# Use bash wrapper
scripts/deploy/verify_package.sh zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
```

**Verification Steps:**
1. **Checksum Verification**: Calculates MD5 and SHA256, compares against manifest
2. **Signature Verification**: Verifies Cosign signature if present (optional)

**Output (success):**
```
============================================================
Package Verification
============================================================
Package: zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
============================================================

Step 1: Checksum Verification
------------------------------------------------------------
Calculating checksums for zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst...
MD5      ✓ PASS
SHA256   ✓ PASS

✓ Checksum verification PASSED

Step 2: Signature Verification
------------------------------------------------------------
Verifying signature with cosign...
✓ Signature verification PASSED

============================================================
✓ Package verification PASSED
============================================================
```

**Output (failure):**
```
============================================================
Package Verification
============================================================
Package: zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
============================================================

Step 1: Checksum Verification
------------------------------------------------------------
Calculating checksums for zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst...
MD5      ✗ FAIL
  Expected: d41d8cd98f00b204e9800998ecf8427e
  Actual:   098f6bcd4621d373cade4e832627b4f6
SHA256   ✗ FAIL
  Expected: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
  Actual:   9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08

✗ Checksum verification FAILED

Halting deployment due to checksum mismatch

============================================================
✗ Package verification FAILED
============================================================
```

**Exit Codes:**
- `0`: Verification passed
- `1`: Verification failed
- `130`: Interrupted by user

### 4. Complete Workflow Script

**Script:** `scripts/build/package_integrity.sh`

Orchestrates the complete package integrity workflow: generate checksums, sign (optional), and verify.

**Usage:**
```bash
# Complete workflow (generate + sign + verify)
scripts/build/package_integrity.sh all zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

# Complete workflow with signing
scripts/build/package_integrity.sh all zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst -k cosign.key

# Generate checksums only
scripts/build/package_integrity.sh generate zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

# Sign only
scripts/build/package_integrity.sh sign zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst -k cosign.key

# Verify only
scripts/build/package_integrity.sh verify zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
```

## Workflow Integration

### Build Phase (Zone A - Connected Environment)

After creating the Zarf package:

```bash
# 1. Create Zarf package
zarf package create --confirm --output-dir=./dist

# 2. Generate checksums and sign (complete workflow)
scripts/build/package_integrity.sh all dist/zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst -k cosign.key

# 3. Verify package was created correctly
scripts/build/package_integrity.sh verify dist/zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
```

**Artifacts to transfer:**
- `zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst` (package)
- `zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst.checksums.json` (manifest)
- `zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst.sig` (signature, if signed)
- `cosign.pub` (public key, if signed)

### Deployment Phase (Zone C - Disconnected Environment)

Before deploying the package:

```bash
# 1. Transfer artifacts to bastion
scp zarf-package-*.tar.zst* bastion:/opt/packages/
scp cosign.pub bastion:/opt/packages/  # If signed

# 2. Verify package integrity on bastion
ssh bastion
cd /opt/packages

# Verify (will halt if integrity check fails)
python3 /path/to/verify_package.py zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

# 3. Deploy package (only if verification passed)
zarf package deploy zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst --confirm
```

## Security Considerations

### Checksum Algorithms

- **MD5**: Fast but cryptographically weak. Detects accidental corruption but not intentional tampering.
- **SHA256**: Cryptographically strong. Detects both accidental and intentional tampering.

**Recommendation:** Always verify both checksums. SHA256 is the primary security control.

### Signature Verification

Cosign signatures provide:
- **Authentication**: Verifies package was signed by holder of private key
- **Non-repudiation**: Signer cannot deny signing the package
- **Integrity**: Detects any changes after signing

**Key Management:**
- **Private Key**: Keep secure in Factory Zone. Never transfer to Field Zone.
- **Public Key**: Transfer with package. Used for verification only.
- **Key Rotation**: Generate new key pair periodically. Update public key on bastion.

### Threat Model

**Threats Mitigated:**
- Accidental corruption during transfer (checksums)
- Intentional tampering during transport (checksums + signature)
- Package substitution (signature)
- Man-in-the-middle attacks (signature)

**Threats NOT Mitigated:**
- Compromise of build environment (sign at source)
- Compromise of private key (rotate keys, use HSM)
- Side-channel attacks (physical security)

## Troubleshooting

### Checksum Mismatch

**Symptom:** Verification fails with different MD5/SHA256 values.

**Causes:**
- Package corrupted during transfer
- Wrong manifest file
- Package modified after manifest generation

**Resolution:**
1. Re-transfer package from Factory Zone
2. Verify manifest matches package name
3. Regenerate manifest if package is correct

### Signature Verification Failure

**Symptom:** Cosign verification fails.

**Causes:**
- Wrong public key
- Package modified after signing
- Signature file missing or corrupted

**Resolution:**
1. Verify public key matches private key used for signing
2. Re-transfer signature file
3. Re-sign package in Factory Zone if needed

### Cosign Not Available

**Symptom:** Signature verification skipped with "cosign not available" message.

**Impact:** Checksums still verified. Signature verification optional.

**Resolution:**
- Install Cosign if signature verification required
- Use `--skip-signature` flag to explicitly skip

### Manifest Not Found

**Symptom:** "No checksum manifest found" error.

**Resolution:**
1. Ensure manifest file transferred with package
2. Use `-m` flag to specify manifest path
3. Regenerate manifest if missing

## References

- **Cosign Documentation**: https://docs.sigstore.dev/cosign/
- **Zarf Documentation**: https://docs.zarf.dev/
- **NIST Hash Functions**: https://csrc.nist.gov/projects/hash-functions

## Requirements Traceability

| Requirement | Component | Status |
|:------------|:----------|:-------|
| 2.6 | `generate_checksum_manifest.py` | ✓ Implemented |
| 2.7 | `sign_package.sh` | ✓ Implemented |
| 3.1 | `verify_package.py` (MD5) | ✓ Implemented |
| 3.2 | `verify_package.py` (SHA256) | ✓ Implemented |
| 3.3 | `verify_package.py` (Cosign) | ✓ Implemented |
| 3.4 | `verify_package.py` (halt on checksum fail) | ✓ Implemented |
| 3.5 | `verify_package.py` (halt on signature fail) | ✓ Implemented |
