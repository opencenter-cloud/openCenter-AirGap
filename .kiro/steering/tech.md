# Technology Stack

## Target Environment

- **Operating System**: Ubuntu Linux 24.04 LTS
- **Architecture**: AMD64 (x86_64)
- **Python Version**: 3.12
- **Container Runtime**: runc 1.3.4
- **CNI Plugin**: Calico

## Core Technologies

### Packaging & Delivery
- **Zarf**: Air-gap packaging framework, SBOM generation, cryptographic signing
- **Compression**: tar.zst format for single artifact delivery

### Infrastructure Provisioning
- **Terraform**: v1.6.6 (OpenStack deployments only)
- **Filesystem Mirror**: Offline provider resolution

### Kubernetes Deployment
- **Kubespray**: master branch (Ansible-based K8s installer)
- **kubespray-offline**: Asset discovery and offline dependency collection
- **Kubernetes**: v1.34.3

### Container Infrastructure
- **RUNC**: 1.3.4
- **runc**: 1.3.4
- **CNI**: 1.8.0
- **Registry**: registry:2.8.3 (local image registry on bastion)
- **Nginx**: 1.29.2 (serves apt/pip repositories)

### GitOps & Core Services
- **FluxCD**: v2.2.0
- **Gitea**: 1.21.0 (in-cluster Git server)
- **cert-manager**: v1.13.0
- **ingress-nginx**: v1.9.0
- **Keycloak**: 21.1.1
- **Prometheus**: v2.48.0
- **Grafana**: 10.2.0

## Build System

### Build Phase (Zone A - Connected Environment)

**Prerequisites**:
- Ubuntu 24.04 build host with podman/Podman
- 100GB+ free disk space
- Internet access
- Git, Python3, Terraform installed

**Build Process**:
```bash
# 1. Clone kubespray-offline for asset discovery
git clone -b main https://github.com/kubespray-offline/kubespray-offline.git

# 2. Configure versions in config/versions.env

# 3. Run asset collection
cd kubespray-offline
./download-all.sh  # Downloads K8s binaries, images, apt packages, Python wheels

# 4. Collect Terraform providers (OpenStack only)
terraform providers mirror -platform=linux_amd64 <mirror-dir>
terraform providers lock -platform=linux_amd64

# 5. Build Zarf package
zarf package create --confirm --output-dir=./dist

# 6. Verify integrity
zarf package inspect dist/zarf-package-*.tar.zst --sbom
```

### Deployment Phase (Zone C - Air-Gapped Environment)

**Prerequisites**:
- Bastion host with Ubuntu 24.04
- podman/runc runtime
- SSH access to target nodes
- 100GB+ free disk space
- Ports 5000 (registry) and 8080 (nginx) open

**Deployment Process**:
```bash
# 1. Transfer package to bastion
scp zarf-package-*.tar.zst bastion:/opt/

# 2. Deploy package
cd /opt
zarf package deploy zarf-package-*.tar.zst --confirm

# 3. Verify cluster
export KUBECONFIG=/opt/opencenter/kubespray/inventory/mycluster/artifacts/admin.conf
kubectl get nodes
kubectl get pods -A
```

## Common Commands

### Build Commands
```bash
# Collect offline assets
./scripts/build/collect_assets.sh

# Build Zarf package
./scripts/build/create_package.sh

# Verify package integrity
zarf package inspect <package-file> --sbom
```

### Deployment Commands
```bash
# Deploy cluster
./scripts/deploy/deploy_cluster.sh

# Verify package integrity
./scripts/deploy/verify_package.sh

# Check local services
curl http://localhost:8080/files/          # Nginx serving binaries
curl http://localhost:5000/v2/_catalog     # Registry catalog
```

### Testing Commands
```bash
# Unit tests
pytest tests/unit/

# Property-based tests
pytest tests/property/

# Integration tests
./tests/integration/run_all.sh
```

## Configuration Files

- **config/versions.env**: Version pinning for all components
- **zarf.yaml**: Zarf package definition (to be created)
- **.terraformrc**: Terraform filesystem mirror configuration
- **offline.yml**: Kubespray offline inventory variables

## Scripting Standards

- **Languages**: Bash or Python only (no compiled code for transparency)
- **Error Handling**: Use `set -euo pipefail` in all bash scripts
- **Idempotency**: All scripts must be safe to re-run
- **Logging**: Capture all deployment logs on bastion

## Version Management

All versions are strictly pinned in `config/versions.env`. No `latest` tags allowed. Version updates require:
1. Update versions.env
2. Re-run asset collection
3. Rebuild Zarf package
4. Verify SBOM includes new versions
