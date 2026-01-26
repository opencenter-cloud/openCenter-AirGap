---
type: how-to
audience: platform-engineer
difficulty: intermediate
version: 1.0.0
last_updated: 2026-01-25
doc_type: how-to
---

# Build Air-Gap Package

Create the openCenter deployment artifact in a connected environment.

## Prerequisites

- Ubuntu 24.04 LTS (AMD64)
- Python 3.12+
- Podman 4.x+
- 100GB+ free disk
- Internet access

Verify:
```bash
python3.12 --version && podman --version && df -h .
```

## Build

```bash
# Clone and setup
git clone <repo-url> opencenter-airgap
cd opencenter-airgap
python3.12 -m venv venv
source venv/bin/activate
pip install pyyaml jinja2 requests

# Build package
./scripts/build/build.sh
```

Duration: 30-60 minutes.

Output: `dist/zarf-package-opencenter-airgap-amd64-<version>.tar.zst`

## Verify

```bash
# Check package exists
ls -lh dist/zarf-package-*.tar.zst

# Verify integrity
sha256sum -c dist/zarf-package-*.tar.zst.sha256

# Inspect SBOM
zarf package inspect dist/zarf-package-*.tar.zst --sbom
```

## Troubleshooting

**Python version mismatch**
```bash
sudo apt install python3.12 python3.12-venv
rm -rf venv && python3.12 -m venv venv
```

**Asset download failures**
```bash
# Re-run (idempotent)
cd build/kubespray-offline
./download-all.sh
```

**Disk space exhausted**
```bash
# Clean podman cache
podman system prune -a -f
```

**Package size > 10GB**
```bash
# Check image sizes
podman images --format "{{.Repository}}:{{.Tag}} {{.Size}}"
# Remove unnecessary images from additional_images.txt
```

## Next Steps

- [Transfer package](../deploy/deploy-baremetal-cluster.md#package-transfer)
- [Verify package integrity](../verify/verify-package-integrity.md)
