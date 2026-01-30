doc_type: how-to

# Verify Package Integrity

Verify Zarf package integrity through signature validation, checksum verification, and manifest comparison.

## Prerequisites

- Built Zarf package (`dist/zarf-package-*.tar.zst`)
- Optional: Cosign CLI for signature verification
- Optional: Artifact manifest (`dist/artifact-manifest.json`)

## Basic Verification

Verify package structure and checksums:

```bash
opencenter-airgap verify dist/zarf-package-opencenter-airgap-amd64-1.34.3.tar.zst
```

Output shows:
- Signature status (requires Cosign and `.sig` file)
- Checksum validation (via Zarf inspect or magic bytes)
- Overall verification result

## Verification with Manifest

Compare package contents against artifact manifest:

```bash
opencenter-airgap verify \
  dist/zarf-package-opencenter-airgap-amd64-1.34.3.tar.zst \
  --manifest dist/artifact-manifest.json
```

Validates:
- Package filename matches manifest
- Package size matches manifest (within 1%)
- Package SHA256 checksum matches manifest
- Image and repository counts match

## Signature Verification

Generate and verify Cosign signature:

```bash
# Sign package (build phase)
cosign sign-blob \
  --key cosign.key \
  --output-signature dist/zarf-package-*.tar.zst.sig \
  dist/zarf-package-*.tar.zst

# Verify signature (deploy phase)
opencenter-airgap verify dist/zarf-package-*.tar.zst
```

Verification automatically detects `.sig` file and validates if Cosign available.

## Verification Checks

| Check | Tool | Fallback |
|-------|------|----------|
| Signature | Cosign CLI | Skip if unavailable |
| Checksums | Zarf inspect | Zstandard magic bytes |
| Manifest | Zarf inspect + SHA256 | Basic validation |

## Exit Codes

- `0`: Verification passed
- `1`: Verification failed (see error output)

## Troubleshooting

**Signature verification skipped**
- Install Cosign: `brew install cosign` or `apt install cosign`
- Ensure `.sig` file exists alongside package

**Checksum verification failed**
- Package corrupted during transfer
- Re-download or rebuild package

**Manifest mismatch**
- Package rebuilt without updating manifest
- Rebuild both: `opencenter-airgap build --clean`

**Zarf CLI not available**
- Install Zarf: `brew install zarf` or download from releases
- Verification falls back to basic magic byte check
