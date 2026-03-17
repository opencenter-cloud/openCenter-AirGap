---
id: verify-package
title: "Verify Package Integrity"
sidebar_label: Verify Package
description: Check that a Zarf package has not been tampered with and contains expected components.
doc_type: how-to
audience: "security officers, platform engineers"
tags: [verification, checksum, signature, sbom, security]
---

# Verify Package Integrity

Check that a Zarf package hasn't been tampered with and contains expected components.

## Prerequisites

- Zarf package file (`.tar.zst`)
- Corresponding `.sha256` and `-sbom.json` files
- Public key for signature verification (if package is signed)
- `opencenter-build` CLI or `zarf` CLI installed

## Verify Checksum

Compare package hash against published checksum:

```bash
sha256sum -c zarf-package-opencenter-airgap-amd64-1.0.0.sha256
```

Expected output:
```
zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst: OK
```

If checksum fails, package was corrupted or modified. Do not deploy.

## Verify Cryptographic Signature

Requires public key from package maintainer.

Install cosign:
```bash
curl -sL https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64 -o /usr/local/bin/cosign
chmod +x /usr/local/bin/cosign
```

Verify signature:
```bash
cosign verify --key cosign.pub zarf-package-*.tar.zst
```

Expected output:
```
Verification for zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst --
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key
```

If verification fails, package was signed with different key or modified after signing. Do not deploy.

## Inspect SBOM

View bill of materials:

```bash
zarf package inspect zarf-package-*.tar.zst --sbom
```

Or read SBOM file directly:
```bash
jq '.' zarf-package-*-sbom.json | less
```

### Check for Specific Components

Verify kubectl is included:
```bash
jq '.artifacts[] | select(.name == "kubectl")' zarf-package-*-sbom.json
```

Expected output:
```json
{
  "name": "kubectl",
  "version": "1.34.3",
  "type": "binary",
  "checksum": "sha256:abc123..."
}
```

List all container images:
```bash
jq '.artifacts[] | select(.type == "image") | .name' zarf-package-*-sbom.json
```

Count total artifacts:
```bash
jq '.artifacts | length' zarf-package-*-sbom.json
```

### Check for CVEs

If SBOM includes vulnerability scan results:

```bash
jq '.vulnerabilities[] | select(.severity == "CRITICAL" or .severity == "HIGH")' zarf-package-*-sbom.json
```

No output means no HIGH or CRITICAL CVEs.

## Verify Package Contents

Extract package metadata without deploying:

```bash
zarf package inspect zarf-package-*.tar.zst
```

Output shows:
- Package name and version
- Components included
- Required Zarf variables
- Deployment order

Check specific component:
```bash
zarf package inspect zarf-package-*.tar.zst | grep -A 10 "Component: kubespray"
```

## Verify Against Policy

### Check Version Pins

Ensure no `latest` tags:
```bash
jq '.artifacts[] | select(.type == "image") | select(.version == "latest")' zarf-package-*-sbom.json
```

No output means all images are pinned.

### Check Allowed Registries

Verify images come from approved registries:
```bash
jq -r '.artifacts[] | select(.type == "image") | .name' zarf-package-*-sbom.json | cut -d/ -f1 | sort -u
```

Compare against your approved registry list.

### Check License Compliance

If SBOM includes license data:
```bash
jq '.artifacts[] | select(.licenses != null) | {name, licenses}' zarf-package-*-sbom.json
```

Flag any GPL or AGPL licenses if your policy prohibits them.

## Automated Verification Script

```bash
#!/bin/bash
set -euo pipefail

PACKAGE="$1"
PUBLIC_KEY="${2:-cosign.pub}"

echo "==> Verifying checksum..."
sha256sum -c "${PACKAGE}.sha256"

echo "==> Verifying signature..."
cosign verify --key "$PUBLIC_KEY" "$PACKAGE"

echo "==> Checking for latest tags..."
LATEST_COUNT=$(jq '[.artifacts[] | select(.type == "image") | select(.version == "latest")] | length' "${PACKAGE%.tar.zst}-sbom.json")
if [ "$LATEST_COUNT" -gt 0 ]; then
    echo "ERROR: Found $LATEST_COUNT images with 'latest' tag"
    exit 1
fi

echo "==> Checking for HIGH/CRITICAL CVEs..."
CVE_COUNT=$(jq '[.vulnerabilities[]? | select(.severity == "CRITICAL" or .severity == "HIGH")] | length' "${PACKAGE%.tar.zst}-sbom.json")
if [ "$CVE_COUNT" -gt 0 ]; then
    echo "WARNING: Found $CVE_COUNT HIGH/CRITICAL CVEs"
    jq '.vulnerabilities[]? | select(.severity == "CRITICAL" or .severity == "HIGH")' "${PACKAGE%.tar.zst}-sbom.json"
fi

echo "==> Verification complete"
```

Usage:
```bash
chmod +x verify.sh
./verify.sh zarf-package-*.tar.zst cosign.pub
```

## Troubleshooting

**Checksum file not found**: Ensure `.sha256` file is in same directory as package.

**Signature verification fails**: Verify you have correct public key. Key must match private key used to sign package.

**SBOM missing**: Package was built with `--skip-sbom`. Rebuild with SBOM generation enabled.

**CVE data missing**: Package was built without Trivy scanning. Rebuild with `--scan` flag.

## See Also

- [Security Scanning Reference](../reference/security-scanning.md)
- [Secrets Management](../reference/secrets-management.md)
- [Troubleshooting](../reference/troubleshooting.md)
