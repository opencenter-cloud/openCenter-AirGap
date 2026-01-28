# Version Management and Commit SHA Pinning

**doc_type**: how-to
**audience**: Platform Engineers, Security Engineers

## Purpose

Pin all git dependencies to specific commit SHAs for supply chain security and build reproducibility.

## Why Commit SHA Pinning

### Security Benefits
- **Immutable references**: Commit SHAs cannot be changed or moved
- **Supply chain protection**: Prevents tag/branch hijacking attacks
- **Audit trail**: Exact source code version is verifiable
- **Reproducible builds**: Same inputs always produce same outputs

### Mutable References (Avoid)
- `master`, `main`, `develop` - branches can be force-pushed
- `latest` - tag can be moved to different commits
- `v1.x` - floating version tags

### Immutable References (Use)
- Full 40-character commit SHA: `8a5d3d0c8e9f7b6a5c4d3e2f1a0b9c8d7e6f5a4b`
- Specific version tags verified against commit SHA: `v2.24.0` + SHA

## Configuration Files

### versions.env

All git dependencies must specify both version and commit SHA:

```bash
# Kubespray
KUBESPRAY_VERSION="v2.24.0"  # Specific tag, not "master"
KUBESPRAY_COMMIT_SHA="8a5d3d0c8e9f7b6a5c4d3e2f1a0b9c8d7e6f5a4b"

# openCenter GitOps Base
OPENCENTER_GITOPS_BASE_REPO="https://github.com/rackerlabs/openCenter-gitops-base"
OPENCENTER_GITOPS_BASE_VERSION="v1.0.0"  # Specific tag or SHA
OPENCENTER_GITOPS_BASE_COMMIT_SHA="1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b"
```

### versions.schema.json

Schema enforces commit SHA fields:

```json
{
  "required": [
    "KUBESPRAY_VERSION",
    "KUBESPRAY_COMMIT_SHA",
    "OPENCENTER_GITOPS_BASE_COMMIT_SHA"
  ],
  "properties": {
    "KUBESPRAY_COMMIT_SHA": {
      "type": "string",
      "pattern": "^[0-9a-f]{40}$",
      "description": "Full 40-character commit SHA"
    }
  }
}
```

## Version Update Procedure

### 1. Identify New Version

Determine the target version (tag or branch):

```bash
# List available tags
git ls-remote --tags https://github.com/kubernetes-sigs/kubespray.git

# Find latest release
git ls-remote --tags https://github.com/kubernetes-sigs/kubespray.git | \
  grep -v '\^{}' | \
  sort -V | \
  tail -n 5
```

### 2. Get Commit SHA for Version

Retrieve the commit SHA for the target version:

```bash
# For a specific tag
git ls-remote https://github.com/kubernetes-sigs/kubespray.git refs/tags/v2.24.0

# Output: 8a5d3d0c8e9f7b6a5c4d3e2f1a0b9c8d7e6f5a4b	refs/tags/v2.24.0
```

### 3. Update versions.env

Edit `config/versions.env`:

```bash
# Before
KUBESPRAY_VERSION="master"

# After
KUBESPRAY_VERSION="v2.24.0"
KUBESPRAY_COMMIT_SHA="8a5d3d0c8e9f7b6a5c4d3e2f1a0b9c8d7e6f5a4b"
```

### 4. Verify Commit SHA

Run verification script:

```bash
python3 scripts/build/verify_commit_shas.py

# Expected output:
# ================================================================================
# Git Commit SHA Verification
# ================================================================================
# ✓ Kubespray v2.24.0 verified at commit 8a5d3d0c
# ✓ GitOps Base v1.0.0 verified at commit 1a2b3c4d
#
# ✓ All commit SHAs verified successfully
# ================================================================================
# ✓ Verification passed
```

### 5. Test Build

Run a test build to ensure the new version works:

```bash
# Clean build
python3 scripts/build/build.py --clean

# Verify assets collected correctly
ls -lh build/kubespray-offline/outputs/
```

### 6. Update Documentation

Document the version change:

```bash
# Add entry to CHANGELOG.md
## [Unreleased]
### Changed
- Updated Kubespray from master to v2.24.0 (commit 8a5d3d0c)
```

### 7. Commit Changes

```bash
git add config/versions.env
git commit -m "chore: pin Kubespray to v2.24.0 (8a5d3d0c)"
```

## Verification Script

### Usage

```bash
# Verify all commit SHAs
python3 scripts/build/verify_commit_shas.py

# Verify with custom versions file
python3 scripts/build/verify_commit_shas.py --versions-file config/versions.env

# Verbose output
python3 scripts/build/verify_commit_shas.py --verbose
```

### What It Checks

1. **Version format**: Rejects mutable references (master, main, develop)
2. **SHA format**: Validates 40-character hexadecimal format
3. **Remote existence**: Verifies commit exists in remote repository
4. **Tag consistency**: Confirms version tag points to specified commit SHA

### Exit Codes

- `0`: All verifications passed
- `1`: One or more verifications failed

## Integration with Build Pipeline

### Pre-build Validation

Add to build script:

```bash
#!/bin/bash
set -euo pipefail

# Verify commit SHAs before starting build
python3 scripts/build/verify_commit_shas.py || {
    echo "ERROR: Commit SHA verification failed"
    exit 1
}

# Continue with build
python3 scripts/build/build.py
```

### CI/CD Integration

Add to `.github/workflows/ci.yml`:

```yaml
jobs:
  verify-versions:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: pip install -e .

      - name: Verify commit SHAs
        run: python3 scripts/build/verify_commit_shas.py
```

## Troubleshooting

### Error: "mutable reference"

```
✗ KUBESPRAY_VERSION uses mutable reference 'master'
```

**Solution**: Use a specific tag instead:
```bash
KUBESPRAY_VERSION="v2.24.0"
```

### Error: "not a valid 40-character SHA"

```
✗ KUBESPRAY_COMMIT_SHA 'abc123' is not a valid 40-character SHA
```

**Solution**: Use full 40-character commit SHA:
```bash
# Get full SHA
git ls-remote https://github.com/kubernetes-sigs/kubespray.git refs/tags/v2.24.0

# Use complete SHA (40 characters)
KUBESPRAY_COMMIT_SHA="8a5d3d0c8e9f7b6a5c4d3e2f1a0b9c8d7e6f5a4b"
```

### Error: "Commit not found in remote repository"

```
✗ Kubespray: Commit 8a5d3d0c... not found in https://github.com/...
```

**Causes**:
1. Typo in commit SHA
2. Commit was force-pushed or deleted
3. Network connectivity issues

**Solution**:
```bash
# Verify commit exists
git ls-remote https://github.com/kubernetes-sigs/kubespray.git 8a5d3d0c...

# If not found, get correct SHA
git ls-remote https://github.com/kubernetes-sigs/kubespray.git refs/tags/v2.24.0
```

### Error: "Tag points to different commit"

```
✗ Kubespray: Tag v2.24.0 points to abc123 but COMMIT_SHA is def456
```

**Solution**: Update commit SHA to match tag:
```bash
# Get correct SHA for tag
git ls-remote https://github.com/kubernetes-sigs/kubespray.git refs/tags/v2.24.0

# Update versions.env with correct SHA
KUBESPRAY_COMMIT_SHA="<sha_from_above>"
```

### Warning: "git command not found"

```
✗ git command not found. Install git to verify commit SHAs.
```

**Solution**: Install git:
```bash
# Ubuntu/Debian
sudo apt-get install git

# macOS
brew install git
```

## Best Practices

### 1. Always Verify After Updates

```bash
# After editing versions.env
python3 scripts/build/verify_commit_shas.py
```

### 2. Document Version Changes

Include rationale in commit messages:

```bash
git commit -m "chore: update Kubespray to v2.24.0

- Fixes CVE-2024-XXXXX
- Adds support for Kubernetes 1.34
- Improves air-gap deployment reliability"
```

### 3. Test Before Merging

Always run a full build after version updates:

```bash
python3 scripts/build/build.py --clean
```

### 4. Pin Transitive Dependencies

If a dependency has its own dependencies, pin those too:

```bash
# Kubespray uses specific Ansible version
ANSIBLE_VERSION="2.16.0"
ANSIBLE_COMMIT_SHA="..."
```

### 5. Regular Security Audits

Schedule periodic reviews of pinned versions:

```bash
# Check for security updates
# Kubespray
git ls-remote --tags https://github.com/kubernetes-sigs/kubespray.git | tail -n 5

# Compare with current version
grep KUBESPRAY_VERSION config/versions.env
```

## Security Considerations

### Supply Chain Attack Vectors

1. **Tag hijacking**: Attacker moves tag to malicious commit
   - **Mitigation**: Pin commit SHA, verify tag matches SHA

2. **Branch poisoning**: Attacker force-pushes to branch
   - **Mitigation**: Never use branches, only tags + SHAs

3. **Dependency confusion**: Attacker creates similar repo name
   - **Mitigation**: Use full repository URLs, verify ownership

### Verification Frequency

- **Pre-build**: Every build verifies commit SHAs
- **CI/CD**: Every commit triggers verification
- **Scheduled**: Weekly audit of available updates
- **Security alerts**: Immediate verification after CVE disclosure

### Audit Trail

Maintain record of version changes:

```bash
# View version history
git log --oneline --all --grep="KUBESPRAY_VERSION" -- config/versions.env

# View specific version change
git show <commit-sha>:config/versions.env
```

## References

- [SLSA Supply Chain Security](https://slsa.dev/)
- [Sigstore for Artifact Signing](https://www.sigstore.dev/)
- [NIST SP 800-218: Secure Software Development Framework](https://csrc.nist.gov/publications/detail/sp/800-218/final)
- [Kubespray Releases](https://github.com/kubernetes-sigs/kubespray/releases)
