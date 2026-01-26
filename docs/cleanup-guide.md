# Cleanup Guide

**doc_type**: how-to

Guide for reclaiming disk space by removing build artifacts, downloaded assets, and distribution packages.

## When to Clean Up

- Between builds when switching Kubernetes versions
- After successful package creation and transfer
- When disk space is low (build requires 100GB+)
- Before archiving or backing up the repository

## Quick Reference

```bash
# Preview what would be deleted
./scripts/cleanup.sh --dry-run --all

# Clean everything
./scripts/cleanup.sh --all

# Clean specific targets
./scripts/cleanup.sh --build --assets
./scripts/cleanup.sh --dist
```

## Cleanup Targets

### Build Artifacts (`--build`)

**Removes**:
- `build/kubespray-offline/outputs/` - Downloaded K8s images, binaries, packages (50-80GB)
- `build/kubespray-offline/.download/` - Download cache
- `build/kubespray-offline/kubespray/` - Extracted Kubespray

**Preserves**:
- `build/kubespray-offline/.git/` - Git repository
- `build/kubespray-offline/target-scripts/config.sh` - Configuration
- `build/kubespray-offline/imagelists/` - Image lists

**Impact**: Next build will re-download all assets (30-60 minutes with fast connection).

### Organized Assets (`--assets`)

**Removes**:
- `assets/k8s-binaries/` - Organized Kubernetes binaries (5-10GB)
- `assets/kubespray/` - Extracted Kubespray playbooks (500MB)
- `assets/playbook/` - Ansible playbooks
- `assets/python-wheels/` - PyPI mirror (200MB)
- `assets/repos/` - Apt repository (10-20GB)
- `assets/target-scripts/` - Bastion setup scripts
- `assets/terraform-mirror/` - Terraform providers (100MB)

**Preserves**:
- `assets/terraform/` - Terraform configuration files

**Impact**: Next build will re-organize assets from kubespray-offline outputs (5-10 minutes).

### Distribution Packages (`--dist`)

**Removes**:
- `dist/*.tar.zst` - Zarf packages (3-8GB each)
- `dist/*.checksums` - Checksum manifests
- `dist/*.sig` - Cosign signatures
- `dist/*.txt` - Inspection and SBOM outputs

**Preserves**: Nothing (entire dist/ directory contents removed)

**Impact**: Cannot deploy without rebuilding package. Transfer existing packages to safe location before cleanup.

### Python Virtual Environment (`--venv`)

**Removes**:
- `venv/` - Python virtual environment with build dependencies (500MB)

**Preserves**:
- Build scripts that reference venv
- Python requirements specifications

**Impact**: Next build will recreate venv and reinstall dependencies (2-5 minutes).

## Usage Examples

### Clean After Successful Build

```bash
# Package created and transferred to air-gapped environment
# Clean everything except the package

./scripts/cleanup.sh --build --assets --venv

# Keep dist/ for local testing or backup
```

### Clean Before Version Update

```bash
# Switching from K8s 1.34.3 to 1.35.0
# Remove all artifacts to ensure clean build

./scripts/cleanup.sh --all

# Update config/versions.env
# Run fresh build
```

### Reclaim Maximum Disk Space

```bash
# Need disk space urgently
# Remove everything

./scripts/cleanup.sh --all

# Frees 80-120GB depending on build state
```

### Preview Before Cleanup

```bash
# See what would be removed and how much space freed

./scripts/cleanup.sh --dry-run --all

# Output shows:
# - Files/directories to be removed
# - Size of each target
# - Total space to be freed
```

## Disk Space Impact

| Target | Typical Size | Recovery Time |
|:-------|:-------------|:--------------|
| Build artifacts | 50-80GB | 30-60 min (re-download) |
| Organized assets | 20-40GB | 5-10 min (re-organize) |
| Distribution packages | 3-8GB per package | 10-30 min (rebuild) |
| Python venv | 500MB | 2-5 min (recreate) |
| **Total (--all)** | **80-120GB** | **45-90 min** |

## What Gets Preserved

Cleanup never removes:

- Source code (`scripts/`, `docs/`, `config/`)
- Git repository (`.git/`)
- Configuration files (`config/versions.env`, `zarf.yaml`)
- kubespray-offline git repository and configuration
- Documentation (`docs/`, `README.md`)
- Test files (`tests/`)

## Recovery After Cleanup

### After `--build` Cleanup

```bash
# Re-run asset collection
cd build/kubespray-offline
./download-all.sh

# Or use master build script
./scripts/build/build.sh
```

### After `--assets` Cleanup

```bash
# Re-organize assets from kubespray-offline outputs
./scripts/build/organize_assets_for_zarf.sh

# Or use master build script
./scripts/build/build.sh --skip-download
```

### After `--dist` Cleanup

```bash
# Rebuild package from organized assets
./scripts/build/create_zarf_package.sh

# Or use master build script
./scripts/build/build.sh --skip-download
```

### After `--venv` Cleanup

```bash
# Recreate virtual environment
python3.12 -m venv venv
source venv/bin/activate
pip install pyyaml jinja2 requests hypothesis pytest

# Or let build script recreate it
./scripts/build/build.sh
```

### After `--all` Cleanup

```bash
# Full rebuild from scratch
./scripts/build/build.sh

# Takes 45-90 minutes depending on network speed
```

## Automation

### Clean After Each Build

```bash
# Add to CI/CD pipeline
./scripts/build/build.sh
./scripts/cleanup.sh --build --assets --venv

# Keep only dist/ packages for artifact storage
```

### Scheduled Cleanup

```bash
# Cron job to clean old builds weekly
0 2 * * 0 cd /path/to/opencenter-airgap && ./scripts/cleanup.sh --all
```

### Conditional Cleanup

```bash
# Clean if disk usage exceeds threshold
USAGE=$(df -h /opt | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $USAGE -gt 80 ]; then
    ./scripts/cleanup.sh --build --assets
fi
```

## Safety Features

- **Confirmation prompt**: Requires explicit confirmation before deletion (unless `--dry-run`)
- **Dry run mode**: Preview deletions without making changes
- **Selective cleanup**: Choose specific targets instead of all
- **Preserved configs**: Never removes configuration or source code
- **Size reporting**: Shows space to be freed before deletion

## Troubleshooting

### Cleanup Fails with Permission Error

```bash
# Run with sudo if files owned by root
sudo ./scripts/cleanup.sh --all

# Or fix ownership first
sudo chown -R $USER:$USER build/ assets/ dist/ venv/
./scripts/cleanup.sh --all
```

### Cleanup Doesn't Free Expected Space

```bash
# Check actual disk usage
du -sh build/kubespray-offline/outputs/
du -sh assets/
du -sh dist/

# Verify cleanup completed
ls -la build/kubespray-offline/outputs/  # Should not exist
ls -la assets/k8s-binaries/              # Should not exist
```

### Need to Preserve Specific Package

```bash
# Move package before cleanup
mkdir -p ~/packages
cp dist/zarf-package-openCenter-airgap-*.tar.zst ~/packages/

# Clean dist/
./scripts/cleanup.sh --dist

# Restore if needed
cp ~/packages/zarf-package-openCenter-airgap-*.tar.zst dist/
```

## Best Practices

1. **Always use `--dry-run` first** to preview deletions
2. **Transfer packages before cleanup** if needed for deployment
3. **Clean incrementally** during development (build → assets → dist)
4. **Clean completely** before version updates or major changes
5. **Document cleanup in runbooks** for team consistency
6. **Automate cleanup** in CI/CD pipelines to prevent disk exhaustion
7. **Monitor disk usage** and clean proactively before builds fail

## Integration with Build Process

```bash
# Typical workflow
./scripts/build/build.sh                    # Build package
cp dist/*.tar.zst /media/usb/               # Transfer to removable media
./scripts/cleanup.sh --build --assets       # Clean intermediate artifacts
# Keep dist/ for local testing

# After successful field deployment
./scripts/cleanup.sh --dist                 # Remove old packages
```
