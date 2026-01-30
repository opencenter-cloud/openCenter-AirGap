# Migrate from Bash Scripts to Python Tool

**doc_type: how-to**

For platform engineers migrating from bash-based build scripts to the Python tool.

## Task Summary

Replace bash script invocations with Python CLI commands while maintaining output compatibility.

## Prerequisites

- Existing bash-based build working
- Python 3.10+ installed
- Write access to project directory

## Steps

### 1. Install Python Tool

**Option A: From source**:
```bash
cd /path/to/opencenter-airgap
pip install -e .
```

**Option B: Binary**:
```bash
curl -LO https://github.com/rackerlabs/opencenter-airgap/releases/latest/download/opencenter-airgap
chmod +x opencenter-airgap
sudo mv opencenter-airgap /usr/local/bin/
```

Verify:
```bash
opencenter-airgap version
```

### 2. Create Component Manifest

```bash
opencenter-airgap init --create-manifest --template baremetal
```

Creates `config/components.yaml` with defaults.

### 3. Verify Configuration Compatibility

Existing `config/versions.env` is compatible. No changes needed.

```bash
opencenter-airgap validate
```

### 4. Add Custom Components

If you added custom tools or images in bash scripts, add them to the component manifest:

```bash
# Example: Custom tool
opencenter-airgap add tool mytool 1.0.0 https://example.com/mytool.tar.gz

# Example: Custom image
opencenter-airgap add image docker.io/myorg/myimage:1.0.0
```

### 5. Run Parallel Builds

Test Python tool alongside bash scripts:

```bash
# Bash build (existing)
./scripts/build/create_package.sh

# Python build (new)
opencenter-airgap build --clean
```

### 6. Compare Outputs

```bash
# Check artifact paths
ls -la dist/
ls -la build/kubespray-offline/outputs/

# Compare package contents
zarf package inspect dist/zarf-package-*.tar.zst --sbom > python-sbom.txt
zarf package inspect dist-bash/zarf-package-*.tar.zst --sbom > bash-sbom.txt
diff python-sbom.txt bash-sbom.txt
```

### 7. Validate Deployment

Deploy Python-built package to test environment:

```bash
# Transfer to bastion
scp dist/zarf-package-*.tar.zst bastion:/opt/

# Deploy
ssh bastion
opencenter-airgap serve /opt/zarf-package-*.tar.zst
```

Verify services:
```bash
curl http://localhost/files/
curl http://localhost:5000/v2/_catalog
```

### 8. Update CI/CD

Replace bash script invocations:

**Before**:
```yaml
- name: Build package
  run: ./scripts/build/create_package.sh
```

**After**:
```yaml
- name: Build package
  run: opencenter-airgap build
```

### 9. Update Documentation

Update runbooks and deployment guides to reference Python CLI:

**Before**:
```bash
./scripts/build/create_package.sh
./scripts/deploy/deploy_cluster.sh
```

**After**:
```bash
opencenter-airgap build
opencenter-airgap serve dist/zarf-package-*.tar.zst
```

### 10. Archive Bash Scripts

Once validated, archive bash scripts:

```bash
mkdir -p archive/bash-scripts
mv scripts/build/*.sh archive/bash-scripts/
git add archive/
git commit -m "Archive bash scripts, migrated to Python tool"
```

## Command Mapping

| Bash Script | Python Command |
|-------------|----------------|
| `./scripts/build/create_package.sh` | `opencenter-airgap build` |
| `./scripts/build/scan_repos.sh` | `opencenter-airgap scan --discover-images` |
| `./scripts/deploy/deploy_cluster.sh` | `opencenter-airgap serve <package>` |
| `./scripts/deploy/verify_package.sh` | `opencenter-airgap verify <package>` |
| `cat build/state.txt` | `opencenter-airgap status` |
| `rm -rf build/ dist/` | `opencenter-airgap clean` |

## Troubleshooting

### "Command not found: opencenter-airgap"

Binary not in PATH.

**Solution**:
```bash
# Check installation
which opencenter-airgap

# Add to PATH if needed
export PATH=$PATH:/path/to/binary

# Or install to system location
sudo mv opencenter-airgap /usr/local/bin/
```

### "Different artifact counts"

Python tool may discover more images via auto-discovery.

**Solution**:
```bash
# Check discovered images
opencenter-airgap scan --discover-images
cat config/all-images.txt

# Compare with bash script output
diff config/all-images.txt config/all-images-bash.txt
```

### "Build slower than bash"

First build includes repository cloning. Subsequent builds use cache.

**Solution**:
```bash
# Time first build
time opencenter-airgap build --clean

# Time second build (with cache)
time opencenter-airgap build --clean
```

Expect 4x speedup on repository scanning (8.5min → 2.1min).

### "Package size different"

Python tool may include additional artifacts from auto-discovery.

**Solution**:
```bash
# Compare manifests
opencenter-airgap verify dist/zarf-package-*.tar.zst
cat dist/artifact-manifest.md

# Check for unexpected artifacts
grep -v "^#" dist/artifact-manifest.md | sort > python-artifacts.txt
grep -v "^#" dist-bash/artifact-manifest.md | sort > bash-artifacts.txt
diff python-artifacts.txt bash-artifacts.txt
```

## Rollback Plan

If issues arise, revert to bash scripts:

```bash
# Restore bash scripts
git checkout HEAD~1 -- scripts/

# Run bash build
./scripts/build/create_package.sh
```

Both systems can coexist during migration.

## Benefits After Migration

- **4x faster scanning**: Concurrent repository processing (8.5min → 2.1min)
- **Automatic resume**: Build failures resume from checkpoint
- **Progress visibility**: Rich progress bars and status indicators
- **Validation**: Built-in configuration and package verification
- **Maintainability**: Component manifest replaces scattered bash variables
