# Zarf Package Creation Guide

Quick reference for building openCenter AirGap packages.

## Prerequisites

- Ubuntu 24.04 build host
- Python 3.12+ with venv at project root
- Zarf CLI installed ([installation guide](https://docs.zarf.dev/getting-started/install/))
- Podman or Docker
- 50GB+ free disk space
- Internet connectivity (for asset download)

## Build Workflow

### Step 1: Setup Environment

```bash
# Clone repository
git clone <repo-url>
cd openCenter-airgap

# Create Python virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install pyyaml jinja2 requests
```

### Step 2: Collect Assets (kubespray-offline)

```bash
# Clone kubespray-offline
cd build
git clone -b main https://github.com/kubespray-offline/kubespray-offline.git
cd kubespray-offline

# Configure versions (edit if needed)
vim target-scripts/config.sh

# Add core services images
vim imagelists/additional_images.txt

# Run asset collection (10-30 minutes)
./download-all.sh

# Verify outputs
ls -lh outputs/
```

### Step 3: Organize Assets for Zarf

```bash
cd ../..  # Back to project root

# Organize kubespray-offline outputs
bash scripts/build/organize_assets_for_zarf.sh

# Verify organization
ls -lh assets/
```

### Step 4: Generate zarf.yaml

```bash
# Activate venv if not already active
source venv/bin/activate

# Generate zarf.yaml
python scripts/build/generate_zarf_yaml.py

# Review generated configuration
cat zarf.yaml
```

### Step 5: Create Package

```bash
# Build Zarf package (10-30 minutes)
bash scripts/build/create_zarf_package.sh

# Package will be created in dist/
ls -lh dist/
```

## Output Artifacts

After successful build:

```
dist/
├── zarf-package-openCenter-airgap-amd64-1.0.0.tar.zst  # Main package
├── zarf-package-openCenter-airgap-amd64-1.0.0.tar.zst.checksums  # MD5 + SHA256
├── package-inspection.txt  # Component details
├── package-sbom.txt  # Software Bill of Materials
└── sbom-verification-report.txt  # SBOM completeness verification
```

## Validation

### Validate Script Structure (without Zarf)

```bash
bash scripts/build/validate_package_script.sh
```

### Inspect Package

```bash
zarf package inspect dist/zarf-package-*.tar.zst
```

### View SBOM

```bash
zarf package inspect dist/zarf-package-*.tar.zst --sbom
```

### Verify SBOM Completeness

```bash
python3 scripts/build/verify_sbom.py dist/zarf-package-*.tar.zst -v
```

This verifies that all expected images, binaries, and packages are documented in the SBOM with version information.

### Verify Checksums

```bash
cd dist
md5sum -c <package>.checksums
sha256sum -c <package>.checksums
```

## Configuration

### Version Pinning

Edit `config/versions.env`:

```bash
KUBESPRAY_VERSION="master"
KUBERNETES_VERSION="v1.34.3"
FLUXCD_VERSION="v2.2.0"
# ... etc
```

### Additional Images

Edit `build/kubespray-offline/imagelists/additional_images.txt`:

```
ghcr.io/fluxcd/source-controller:v2.2.0
quay.io/jetstack/cert-manager-controller:v1.13.0
# ... etc
```

### Deployment Variables

Zarf variables (set during deployment):

- `DEPLOYMENT_MODE`: baremetal or openstack (default: baremetal)
- `BASTION_IP`: IP address of bastion host (prompted)
- `SSH_USER`: SSH user for nodes (default: deployer)
- `INSTALL_PATH`: Installation directory (default: /opt/opencenter)
- `REGISTRY_PORT`: Local registry port (default: 35000)
- `NGINX_PORT`: Nginx file server port (default: 80)

## Troubleshooting

### "Zarf CLI not found"

Install Zarf:
```bash
curl -sL https://raw.githubusercontent.com/defenseunicorns/zarf/main/install.sh | bash
```

### "kubespray-offline outputs not found"

Run kubespray-offline first:
```bash
cd build/kubespray-offline
./download-all.sh
```

### "Package size exceeds 10GB"

Reduce asset size:
- Remove unnecessary images from additional_images.txt
- Use smaller base images
- Exclude optional components

### "Insufficient disk space"

Free up space or use larger disk:
```bash
df -h .
# Need at least 15GB available
```

### "SBOM extraction failed"

Ensure Syft is available (bundled with Zarf):
```bash
zarf version
# Should show Zarf with Syft support
```

## Advanced Usage

### Sign Package (Optional)

```bash
# Generate signing key
cosign generate-key-pair

# Sign package
cosign sign --key cosign.key dist/zarf-package-*.tar.zst

# Verify signature
cosign verify --key cosign.pub dist/zarf-package-*.tar.zst
```

### Custom Component Selection

Edit `zarf.yaml` to mark components optional:

```yaml
components:
  - name: terraform-providers
    required: false  # Skip for bare-metal deployments
```

### Rebuild Single Component

```bash
# Modify component in zarf.yaml
vim zarf.yaml

# Recreate package
bash scripts/build/create_zarf_package.sh
```

## Integration with CI/CD

### GitLab CI Example

```yaml
build-package:
  stage: build
  script:
    - python3.12 -m venv venv
    - source venv/bin/activate
    - pip install pyyaml jinja2 requests
    - cd build/kubespray-offline && ./download-all.sh && cd ../..
    - bash scripts/build/organize_assets_for_zarf.sh
    - python scripts/build/generate_zarf_yaml.py
    - bash scripts/build/create_zarf_package.sh
  artifacts:
    paths:
      - dist/
    expire_in: 30 days
```

## Performance Tips

1. **Parallel Downloads:** kubespray-offline supports parallel downloads
2. **Local Cache:** Reuse kubespray-offline outputs/ for incremental builds
3. **SSD Storage:** Use SSD for build directory (faster compression)
4. **Resource Limits:** Zarf compression is CPU-intensive (use multi-core)

## Security Considerations

1. **Verify Sources:** All assets downloaded from official registries
2. **Checksum Validation:** kubespray-offline validates all downloads
3. **SBOM Review:** Review SBOM for unexpected components
4. **Signing:** Sign packages for production deployments
5. **Access Control:** Restrict access to signing keys

## Next Steps

After package creation:

1. Transfer package to air-gapped environment
2. Deploy to bastion host: `zarf package deploy <package>`
3. Follow deployment runbook for cluster bootstrap
4. Verify all services running

## References

- [Zarf Documentation](https://docs.zarf.dev/)
- [kubespray-offline GitHub](https://github.com/kubespray-offline/kubespray-offline)
- [Kubespray Documentation](https://kubespray.io/)
- [openCenter AirGap Design Document](design-document.md)
