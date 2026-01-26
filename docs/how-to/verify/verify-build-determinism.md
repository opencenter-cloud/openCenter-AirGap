# Verify Build Determinism

**doc_type:** how-to

Verify that building the openCenter AirGap package twice with identical configuration produces identical image lists.

## Prerequisites

- Python 3.12+
- Zarf CLI installed
- Two Zarf packages built with identical configuration
- Sufficient disk space for snapshots

## Steps

### 1. Build Package Twice

Build the package twice with identical configuration:

```bash
# First build
./scripts/build/build.sh

# Move package to safe location
mv dist/zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst dist/package1.tar.zst

# Second build (with same configuration)
./scripts/build/build.sh

# Rename second package
mv dist/zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst dist/package2.tar.zst
```

### 2. Create Image List Snapshots

Extract image lists from both packages:

```bash
# Snapshot from first build
python3 scripts/build/snapshot_image_list.py \
    dist/package1.tar.zst \
    build/snapshot1.json

# Snapshot from second build
python3 scripts/build/snapshot_image_list.py \
    dist/package2.tar.zst \
    build/snapshot2.json
```

### 3. Compare Snapshots

Compare the two snapshots:

```bash
python3 scripts/build/compare_image_lists.py \
    build/snapshot1.json \
    build/snapshot2.json
```

**Expected output (deterministic build):**
```
Loading snapshot 1: build/snapshot1.json
  Images: 150
Loading snapshot 2: build/snapshot2.json
  Images: 150

✓ Snapshots are identical
  No differences in images, tags, or digests
```

**Exit code:** 0 (success)

### 4. Automated Test

Run the automated test script:

```bash
./tests/integration/test_build_determinism.sh \
    --skip-build \
    --package1 dist/package1.tar.zst \
    --package2 dist/package2.tar.zst
```

## Interpreting Results

### Identical Builds (Deterministic)

```
✓ Snapshots are identical
  No differences in images, tags, or digests
```

**Meaning:** Build is deterministic. Same configuration produces identical image lists.

**Action:** None required. Build process is working correctly.

### Different Builds (Non-Deterministic)

```
✗ Snapshots differ

Added Images (2):
  + registry.k8s.io/new-image:v1.0.0
  + ghcr.io/another-image:latest

Removed Images (1):
  - registry.k8s.io/old-image:v0.9.0

Changed Digests (3):
  ~ registry.k8s.io/kube-apiserver:v1.28.6
  ~ registry.k8s.io/etcd:3.5.10
  ~ ghcr.io/fluxcd/source-controller:v1.4.1

Total differences: 6
```

**Meaning:** Build is non-deterministic. Different image lists produced.

**Possible causes:**
1. Configuration changed between builds
2. Upstream image tags updated (e.g., "latest" tag)
3. kubespray-offline pulled different versions
4. Time-based version resolution

**Action:** Investigate differences and fix root cause.

## Troubleshooting

### Added/Removed Images

**Symptom:** Snapshot shows added or removed images

**Cause:** Image list changed between builds

**Solution:**
1. Check `config/opencenter-images.txt` for changes
2. Verify kubespray-offline configuration unchanged
3. Ensure no "latest" tags in image lists
4. Check kubespray version pinning

### Changed Digests

**Symptom:** Same image name/tag but different digest

**Cause:** Upstream image updated with same tag

**Solution:**
1. Pin images by digest instead of tag
2. Use immutable tags (e.g., v1.28.6 not latest)
3. Mirror images to prevent upstream changes
4. Document expected digest values

### Missing Zarf CLI

**Symptom:** `Error: Zarf CLI not found`

**Solution:**
```bash
# Install Zarf
curl -sL https://get.zarf.dev | bash

# Verify installation
zarf version
```

### Python Version Mismatch

**Symptom:** `Error: Python 3.12+ required`

**Solution:**
```bash
# Check Python version
python3 --version

# Install Python 3.12+ if needed
# (method depends on OS)
```

## Advanced Usage

### Verbose Comparison

Show full digest values:

```bash
python3 scripts/build/compare_image_lists.py \
    -v \
    build/snapshot1.json \
    build/snapshot2.json
```

### JSON Output

Get machine-readable comparison:

```bash
python3 scripts/build/compare_image_lists.py \
    --json \
    build/snapshot1.json \
    build/snapshot2.json > comparison.json
```

### Keep Test Artifacts

Preserve snapshots for inspection:

```bash
./tests/integration/test_build_determinism.sh \
    --keep-artifacts
```

Artifacts saved to: `build/determinism-test-<timestamp>/`

## Best Practices

1. **Pin All Versions:** Use explicit versions, never "latest"
2. **Test Regularly:** Run determinism test in CI/CD
3. **Document Changes:** Track expected differences in version updates
4. **Snapshot Baseline:** Keep baseline snapshot for comparison
5. **Automate Verification:** Include in build pipeline

## Related Documentation

- [Build Runbook](../build/build-package.md)
- [Version Pinning](../../reference/configuration/version-pinning.md)
- [Troubleshooting Guide](../troubleshooting.md)
