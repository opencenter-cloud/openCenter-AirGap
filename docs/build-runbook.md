# openCenter AirGap Build Runbook

**doc_type**: how-to

**Purpose**: Step-by-step instructions for building the openCenter AirGap package in a connected environment (Zone A).

**Audience**: Platform engineers responsible for creating air-gap deployment artifacts.

## Prerequisites

Verify these requirements before starting:

- **Operating System**: Ubuntu 24.04 LTS (AMD64)
- **Python**: Version 3.12 or higher
- **Container Runtime**: Podman or Docker
- **Git**: For cloning repositories
- **Disk Space**: Minimum 100GB free (150GB recommended)
- **Network**: Internet connectivity required
- **Memory**: 8GB RAM minimum
- **CPU**: 4 cores recommended

Check Python version:
```bash
python3.12 --version
# Expected: Python 3.12.x or higher
```

Check podman:
```bash
podman --version
# Expected: podman version 4.x or higher
```

## Environment Setup

### 1. Clone Repository

```bash
git clone <repository-url> opencenter-airgap
cd opencenter-airgap
```

### 2. Create Python Virtual Environment

```bash
python3.12 -m venv venv
source venv/bin/activate
```

Verify activation:
```bash
which python
# Expected: /path/to/opencenter-airgap/venv/bin/python
```

### 3. Install Build Dependencies

```bash
pip install --upgrade pip
pip install pyyaml jinja2 requests hypothesis pytest
```

Verify installation:
```bash
pip list | grep -E "pyyaml|jinja2|requests"
```

## Configuration

### 1. Configure Runtime Versions

Edit `build/kubespray-offline/target-scripts/config.sh`:

```bash
# Kubespray version (use "master" for latest)
KUBESPRAY_VERSION=master

# Container runtime versions
RUNC_VERSION=1.3.4
CONTAINERD_VERSION=2.1.5
NERDCTL_VERSION=2.1.6
CNI_VERSION=1.8.0

# Service container versions
NGINX_VERSION=1.29.2
REGISTRY_VERSION=2.8.3

# Registry port
REGISTRY_PORT=35000
```

**Important**: These versions must match kubespray's checksums file. Do not change unless you've verified compatibility.

### 2. Add Core Services Images

Edit `build/kubespray-offline/imagelists/additional_images.txt`:

```
# FluxCD
ghcr.io/fluxcd/source-controller:v1.4.1
ghcr.io/fluxcd/kustomize-controller:v1.4.0
ghcr.io/fluxcd/helm-controller:v1.1.0
ghcr.io/fluxcd/notification-controller:v1.4.0

# Cert-Manager
quay.io/jetstack/cert-manager-controller:v1.13.0
quay.io/jetstack/cert-manager-webhook:v1.13.0
quay.io/jetstack/cert-manager-cainjector:v1.13.0

# Ingress-NGINX
registry.k8s.io/ingress-nginx/controller:v1.9.0
registry.k8s.io/ingress-nginx/kube-webhook-certgen:v20231011-8b53cabe0

# Keycloak
quay.io/keycloak/keycloak:21.1.1

# Kube-Prometheus-Stack
quay.io/prometheus/prometheus:v2.48.0
quay.io/prometheus/alertmanager:v0.26.0
grafana/grafana:10.2.0
quay.io/prometheus-operator/prometheus-operator:v0.69.0
quay.io/kube-state-metrics/kube-state-metrics:v2.10.0
```

Add any additional images your deployment requires.

## Build Process

### 1. Run Build Script

Execute the master build script:

```bash
./scripts/build/build.sh
```

This orchestrates:
- Python environment verification
- kubespray-offline asset collection
- Asset organization for Zarf
- Terraform provider collection (if enabled)
- Version validation
- Zarf package creation
- SBOM generation
- Checksum calculation
- Package signing (if configured)

Expected duration: 30-60 minutes depending on network speed.

### 2. Monitor Progress

The build script outputs progress to stdout and logs to `build/build.log`.

Watch for these phases:
```
==> Step 0: Verify Python environment
==> Step 1: Run kubespray-offline asset collection
==> Step 2: Organize assets for Zarf
==> Step 3: Collect Terraform providers (OpenStack mode)
==> Step 4: Validate version pinning
==> Step 5: Create Zarf package
==> Step 6: Generate SBOM
==> Step 7: Generate checksums
==> Step 8: Sign package (optional)
```

### 3. Verify Outputs

Check the `dist/` directory:

```bash
ls -lh dist/
```

Expected files:
- `zarf-package-opencenter-airgap-amd64-<version>.tar.zst` (main package)
- `zarf-package-opencenter-airgap-amd64-<version>.tar.zst.sha256` (checksum)
- `zarf-package-opencenter-airgap-amd64-<version>.tar.zst.sig` (signature, if signing enabled)
- `sbom-<version>.json` (software bill of materials)

Verify package size:
```bash
du -h dist/zarf-package-*.tar.zst
# Expected: 5-10GB
```

### 4. Verify SBOM

Inspect the SBOM:

```bash
zarf package inspect dist/zarf-package-*.tar.zst --sbom
```

Check that all expected components are listed with pinned versions.

### 5. Verify Checksums

Recompute and compare:

```bash
sha256sum dist/zarf-package-*.tar.zst
cat dist/zarf-package-*.tar.zst.sha256
```

Values must match exactly.

## Troubleshooting

### Python Version Mismatch

**Symptom**: Build fails with "Python 3.12+ required"

**Solution**:
```bash
# Install Python 3.12
sudo apt update
sudo apt install python3.12 python3.12-venv

# Recreate venv
rm -rf venv
python3.12 -m venv venv
source venv/bin/activate
```

### kubespray-offline Download Failures

**Symptom**: Asset collection fails with network errors

**Causes**:
- Transient network issues
- Rate limiting from upstream registries
- Invalid image tags in additional_images.txt

**Solution**:
```bash
# Re-run download-all.sh (idempotent)
cd build/kubespray-offline
./download-all.sh

# Check logs
tail -f outputs/download.log
```

For persistent failures, verify image tags exist:
```bash
# Test image pull manually
podman pull registry.k8s.io/kube-apiserver:v1.30.0
```

### Podman Image Load Failures

**Symptom**: "Error loading image" during asset organization

**Causes**:
- Corrupted tar.gz files
- Insufficient disk space
- Podman storage issues

**Solution**:
```bash
# Check disk space
df -h

# Clean podman storage
podman system prune -a -f

# Re-run organize script
./scripts/build/organize_assets_for_zarf.sh
```

### Package Size Exceeded

**Symptom**: Package larger than 10GB

**Causes**:
- Too many images in additional_images.txt
- Duplicate images with different tags
- Large base images

**Solution**:
```bash
# Analyze image sizes
podman images --format "{{.Repository}}:{{.Tag}} {{.Size}}"

# Remove unnecessary images from additional_images.txt
# Rebuild package
```

Consider splitting into multiple packages if size cannot be reduced.

### Version Validation Failures

**Symptom**: Build fails at "Step 4: Validate version pinning"

**Cause**: Unpinned versions detected (e.g., "latest", "stable")

**Solution**:
```bash
# Check validation output
cat build/version-validation.log

# Fix unpinned versions in configuration files
# Re-run build
```

### Zarf Package Creation Failures

**Symptom**: "zarf package create" fails

**Causes**:
- Missing Zarf CLI
- Invalid zarf.yaml syntax
- Missing assets

**Solution**:
```bash
# Install Zarf CLI
curl -sL https://get.zarf.dev | bash

# Validate zarf.yaml
zarf package create --confirm --dry-run

# Check for missing assets
ls -R assets/
```

## Post-Build Validation

Run validation checks:

```bash
# 1. Verify package integrity
./scripts/deploy/verify_package.sh dist/zarf-package-*.tar.zst

# 2. Check SBOM completeness
python scripts/build/verify_sbom.py dist/zarf-package-*.tar.zst

# 3. Verify all images present
zarf package inspect dist/zarf-package-*.tar.zst --list-images
```

## Transfer to Air-Gap Environment

Once validated, transfer the package to Zone B (Airlock):

```bash
# Copy to removable media
cp dist/zarf-package-*.tar.zst /media/usb/
cp dist/zarf-package-*.tar.zst.sha256 /media/usb/
cp dist/zarf-package-*.tar.zst.sig /media/usb/  # if signed

# Verify copy
cd /media/usb
sha256sum -c zarf-package-*.tar.zst.sha256
```

## Next Steps

Proceed to deployment runbook:
- Bare-metal: `docs/deployment-runbook-baremetal.md`
- OpenStack: `docs/deployment-runbook-openstack.md`
