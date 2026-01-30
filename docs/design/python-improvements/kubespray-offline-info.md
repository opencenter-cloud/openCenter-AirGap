# kubespray-offline: Architecture and Integration Guide

**doc_type**: explanation

**Purpose**: Understand how kubespray-offline works, its architecture, and integration patterns for air-gapped Kubernetes deployments.

---

## What is kubespray-offline

kubespray-offline is a collection of bash scripts that automate the download and packaging of all dependencies required to deploy Kubernetes clusters in completely disconnected environments using Kubespray.

The project solves a fundamental problem: Kubespray assumes internet connectivity to download container images, binaries, OS packages, and Python dependencies during deployment. kubespray-offline inverts this model by pre-downloading everything on an internet-connected machine, then transferring a single artifact bundle to the air-gapped environment.

## Core Architecture

### Two-Phase Model

**Phase 1: Build (Internet-Connected)**
- Must run on same OS as target Kubernetes nodes
- Downloads all dependencies into `outputs/` directory
- Creates local mirrors of package repositories
- Saves container images as tar.gz archives
- Packages everything for transfer

**Phase 2: Deploy (Air-Gapped)**
- Transfers `outputs/` directory to target bastion
- Starts local HTTP server (nginx) for file/package serving
- Starts local container registry for images
- Configures nodes to use local services
- Runs Kubespray with offline configuration

### Directory Structure

```
kubespray-offline/
├── config.sh                    # Version pinning and configuration
├── download-all.sh              # Orchestrator script
├── scripts/                     # Build-phase scripts
│   ├── prepare-pkgs.sh
│   ├── prepare-py.sh
│   ├── get-kubespray.sh
│   ├── pypi-mirror.sh
│   ├── download-kubespray-files.sh
│   ├── download-additional-containers.sh
│   ├── create-repo.sh
│   └── copy-target-scripts.sh
├── pkglist/                     # OS package manifests
│   ├── rhel/{8,9,10}/pkgs.txt
│   └── ubuntu/{20.04,22.04,24.04}/pkgs.txt
├── imagelists/                  # Container image lists
│   └── images.txt
└── outputs/                     # Generated artifacts (not in git)
    ├── files/                   # Kubernetes binaries
    ├── images/                  # Container images (tar.gz)
    ├── debs/ or rpms/           # OS package repository
    ├── pypi/                    # Python package mirror
    ├── playbook/                # Ansible playbook for node config
    └── scripts/                 # Deploy-phase scripts
```

## Asset Types Downloaded

### 1. Kubernetes Binaries (`outputs/files/`)

Organized by component and version:
- `kubernetes/v1.30.0/` - kubeadm, kubectl, kubelet
- `kubernetes/etcd/` - etcd tarball
- `kubernetes/cni/` - CNI plugins
- `kubernetes/cri-tools/` - crictl
- `kubernetes/calico/vX.X.X/` - calicoctl
- `runc/vX.X.X/` - runc binary
- `cilium-cli/vX.X.X/` - cilium CLI
- `gvisor/{ver}/{arch}/` - gvisor binaries

### 2. Container Images (`outputs/images/`)

All images saved as `.tar.gz` archives:
- Kubernetes control plane (kube-apiserver, kube-controller-manager, etc.)
- CNI plugins (Calico, Cilium, Flannel)
- DNS (CoreDNS)
- Ingress controllers
- Auxiliary services (nginx:1.29.2, registry:2.8.3)

### 3. OS Packages (`outputs/debs/` or `outputs/rpms/`)

Complete local repository with dependencies:
- Python 3.11/3.12 and build tools
- Container runtime dependencies
- System utilities
- SELinux tools (RHEL family)

### 4. Python Packages (`outputs/pypi/`)

PyPI mirror for Ansible and Kubespray:
- Ansible and dependencies
- Kubespray requirements.txt
- Binary wheels for Python 3.11 and 3.12
- Source packages as fallback
- Build dependencies (pip, setuptools, wheel, flit_core, cython<3)
- Additional tools (selinux, ruamel.yaml)

## Key Scripts and Workflow

### Build Phase Scripts

#### `download-all.sh` - Orchestrator
Executes all build steps in sequence:
1. `precheck.sh` - Verify prerequisites
2. `prepare-pkgs.sh` - Install podman/containerd, python
3. `prepare-py.sh` - Setup Python venv, install packages
4. `get-kubespray.sh` - Download/extract Kubespray tarball
5. `pypi-mirror.sh` - Create PyPI mirror
6. `download-kubespray-files.sh` - Download binaries and images
7. `download-additional-containers.sh` - Download custom images
8. `create-repo.sh` - Create OS package repository
9. `copy-target-scripts.sh` - Copy deployment scripts to outputs/

#### `download-kubespray-files.sh` - Core Asset Collection
- Runs Kubespray's `contrib/offline/generate_list.sh` to discover dependencies
- Generates `files.list` (binaries) and `images.list` (containers)
- Downloads all items to `outputs/files/` and `outputs/images/`
- Uses podman or nerdctl to pull and save container images

#### `pypi-mirror.sh` - Python Package Mirror
- Reads Kubespray's `requirements.txt`
- Downloads packages for Python 3.11 and 3.12
- Includes both binary wheels and source distributions
- Creates pip-compatible directory structure in `outputs/pypi/`

#### `create-repo.sh` - OS Repository Builder
- Auto-detects OS (RHEL family vs Ubuntu)
- Reads package lists from `pkglist/{os}/{version}/pkgs.txt`
- Downloads packages with all dependencies
- Creates repository metadata (repodata for RPM, Packages.gz for DEB)
- Output: `outputs/rpms/local/` or `outputs/debs/local/`

### Deploy Phase Scripts

#### `setup-all.sh` - Target Node Orchestrator
Runs on air-gapped bastion after transferring `outputs/`:
1. `setup-container.sh` - Install containerd, load nginx/registry images
2. `start-nginx.sh` - Start nginx on port 80 (configurable)
3. `setup-offline.sh` - Configure yum/apt/pip to use localhost
4. `setup-py.sh` - Install Python from local repo
5. `start-registry.sh` - Start registry on port 35000 (configurable)
6. `load-push-all-images.sh` - Load images to containerd, push to registry

#### `setup-offline.sh` - Repository Configuration
**RHEL/AlmaLinux/Rocky:**
- Disables existing yum repos (renames to `.original`)
- Creates `/etc/yum.repos.d/offline.repo` pointing to `http://localhost/rpms/local/`

**Ubuntu:**
- Disables default apt sources
- Creates `/etc/apt/sources.list.d/offline.list` pointing to `http://localhost/debs/local/`
- Configures apt to allow unsigned packages

**PyPI:**
- Creates `~/.config/pip/pip.conf` pointing to `http://localhost/pypi/`

#### `start-nginx.sh` - HTTP Server
- Starts nginx container from local image
- Mounts `outputs/` directory as web root
- Serves files, OS packages, and PyPI mirror
- Default port: 80 (configurable via `config.sh`)

#### `start-registry.sh` - Container Registry
- Starts registry:2.8.3 container from local image
- Stores images in local directory
- Default port: 35000 (configurable via `config.sh`)
- No authentication (internal use only)

#### `load-push-all-images.sh` - Image Distribution
- Loads all `.tar.gz` images from `outputs/images/` into containerd
- Re-tags images for local registry
- Pushes to `localhost:35000`
- Strips original registry prefixes (configurable via `ADDITIONAL_CONTAINER_REGISTRY_LIST`)

## Configuration Management

### `config.sh` - Version Pinning

Central configuration file defining all component versions:

```bash
# Kubespray version
KUBESPRAY_VERSION=2.29.1

# Container runtime versions (must match kubespray checksums.yml)
RUNC_VERSION=1.3.4
CONTAINERD_VERSION=2.1.5
NERDCTL_VERSION=2.1.6
CNI_VERSION=1.8.0

# Auxiliary container versions (must match imagelists/images.txt)
NGINX_VERSION=1.29.2
REGISTRY_VERSION=2.8.3

# Service ports
REGISTRY_PORT=35000

# Registry stripping
ADDITIONAL_CONTAINER_REGISTRY_LIST="myregistry.io"
```

**Critical constraint**: Container runtime versions must exactly match Kubespray's `roles/kubespray_defaults/vars/main/checksums.yml` to ensure checksum validation passes.

### `offline.yml` - Kubespray Integration

Copied to Kubespray inventory at `group_vars/all/offline.yml`:

```yaml
# File server (nginx)
http_server: "http://YOUR_HOST"
files_repo: "{{ http_server }}/files"

# Container registry
registry_host: "YOUR_HOST:35000"
containerd_registries_mirrors:
  - prefix: docker.io
    mirrors:
      - host: "http://{{ registry_host }}"
        capabilities: ["pull", "resolve"]
        skip_verify: true

# Binary download URLs
runc_download_url: "{{ files_repo }}/runc/{{ runc_version }}/runc.{{ image_arch }}"
# ... (additional download URLs)

# OS package repositories
ubuntu_repo: "{{ http_server }}/debs/local"
# or
yum_repo: "{{ http_server }}/rpms/local"
```

**Key difference from standard Kubespray**: `runc_download_url` must include `runc_version` in path.

## Integration Points

### Kubespray Integration

kubespray-offline acts as a dependency provider for Kubespray:

1. **Asset Discovery**: Uses Kubespray's `contrib/offline/generate_list.sh` to determine required files and images
2. **Version Alignment**: Reads Kubespray's `requirements.txt` and `checksums.yml` to ensure version compatibility
3. **Configuration Override**: Provides `offline.yml` that overrides Kubespray's default download URLs and registry settings
4. **Playbook Extension**: Includes `offline-repo.yml` playbook to configure all nodes before running Kubespray's `cluster.yml`

### Container Runtime Integration

Supports both podman and containerd/nerdctl:

**Build Phase:**
- Default: podman (auto-installed by `prepare-pkgs.sh`)
- Alternative: containerd + nerdctl (run `install-containerd.sh`, edit `config.sh`)

**Deploy Phase:**
- Always uses containerd on target nodes (Kubernetes requirement)
- Loads images via `ctr` or `nerdctl`

### Zarf Integration Considerations

kubespray-offline's `outputs/` directory is designed for direct packaging:

**Alignment:**
- Single artifact bundle (outputs/ directory)
- Cryptographic verification possible (add checksums)
- Self-contained with all dependencies
- Includes deployment scripts

**Gaps:**
- No SBOM generation
- No cryptographic signing
- No component-level versioning
- Scripts not idempotent by default

**Integration Strategy:**
- Zarf component wraps `outputs/` directory
- Zarf actions call kubespray-offline scripts
- Zarf variables replace hardcoded paths
- SBOM generated from `files.list`, `images.list`, package manifests

## Workflow Summary

### Complete Deployment Flow

**Zone A (Factory - Internet-Connected):**
```bash
git clone https://github.com/kubespray-offline/kubespray-offline.git
cd kubespray-offline
vim config.sh                    # Configure versions
./download-all.sh                # Download all assets (30-60 min)
tar czf outputs.tar.gz outputs/  # Package for transfer
```

**Zone B (Airlock - Transfer):**
```bash
# Copy outputs.tar.gz to removable media
# Transport to air-gapped environment
```

**Zone C (Field - Air-Gapped):**
```bash
# On bastion node
tar xzf outputs.tar.gz
cd outputs
./setup-all.sh                   # Start local services (5-10 min)

# Verify services
curl http://localhost/files/
curl http://localhost:35000/v2/_catalog

# Setup Kubespray
python3.11 -m venv ~/.venv/kubespray
source ~/.venv/kubespray/bin/activate
./extract-kubespray.sh
cd kubespray-2.29.1
pip install -r requirements.txt

# Configure inventory
cp -r inventory/sample inventory/mycluster
vim inventory/mycluster/hosts.yaml
cp ../offline.yml inventory/mycluster/group_vars/all/
vim inventory/mycluster/group_vars/all/offline.yml  # Set YOUR_HOST

# Deploy offline repo config to all nodes
ansible-playbook -i inventory/mycluster/hosts.yaml ../playbook/offline-repo.yml

# Deploy Kubernetes
ansible-playbook -i inventory/mycluster/hosts.yaml --become cluster.yml
```

## Requirements and Constraints

### Build Machine Requirements
- OS: Same as target nodes (RHEL 9, AlmaLinux 9, Rocky 9, Ubuntu 22.04/24.04)
- Internet: Full connectivity
- Disk: 50-100GB free space (varies by Kubernetes version)
- Tools: git, bash, curl, wget
- Runtime: podman or containerd+nerdctl (auto-installed)

### Target Node Requirements
- OS: RHEL 9, AlmaLinux 9, Rocky 9, Ubuntu 22.04/24.04
- Network: No internet, but nodes must reach bastion
- Disk: 20GB+ per node
- Ports: 80 (nginx), 35000 (registry) on bastion

### Version Constraints
- Kubespray: 2.29.0+ (RHEL 8 dropped)
- Python: 3.11 or 3.12
- Container runtime versions must match Kubespray checksums
- All versions pinned in `config.sh`

## Design Rationale

### Why Bash Scripts
- Transparency: No compiled binaries, easy to audit
- Portability: Works on any Linux with bash
- Simplicity: No build toolchain required
- Debuggability: Easy to trace execution

### Why Local Services (nginx + registry)
- Kubespray expects HTTP URLs for binaries
- Container runtime expects registry protocol for images
- Avoids modifying Kubespray playbooks
- Mimics internet-connected behavior

### Why OS-Specific Package Lists
- Different OS versions have different package names
- Dependency resolution varies by OS
- Ensures complete dependency closure
- Prevents missing packages at deploy time

### Why Separate PyPI Mirror
- Ansible requires Python packages
- pip expects specific directory structure
- Binary wheels are platform-specific
- Source packages provide fallback

## Common Misconceptions

**"kubespray-offline is a fork of Kubespray"**
- False. It's a separate tool that generates inputs for standard Kubespray.

**"You can use different OS for build and deploy"**
- False. OS packages and binary wheels are platform-specific. Build machine must match target OS.

**"You can update versions independently"**
- False. Container runtime versions must match Kubespray's checksums.yml exactly.

**"The outputs/ directory is portable across architectures"**
- False. Binaries and images are architecture-specific (amd64 vs arm64).

**"You can skip the local registry and use tar files directly"**
- False. Kubespray's container runtime roles expect a registry. Direct tar loading would require playbook modifications.

## Trade-offs and Alternatives

### kubespray-offline vs Manual Offline Preparation
**kubespray-offline advantages:**
- Automated asset discovery via Kubespray's generate_list.sh
- Complete dependency closure
- Tested script workflow

**Manual advantages:**
- More control over what's included
- Can optimize for specific deployment (skip unused CNI plugins)
- Smaller artifact size

### kubespray-offline vs Zarf
**kubespray-offline:**
- Kubespray-specific
- Bash scripts
- No SBOM or signing
- Manual version management

**Zarf:**
- Generic Kubernetes packaging
- Declarative YAML
- Built-in SBOM and signing
- Component-level versioning

**Hybrid approach (openCenter):**
- Use kubespray-offline for asset collection
- Wrap in Zarf for packaging, SBOM, signing
- Best of both: Kubespray compatibility + Zarf features

---

## References

- [kubespray-offline GitHub](https://github.com/kubespray-offline/kubespray-offline)
- [Kubespray Offline Documentation](https://github.com/kubernetes-sigs/kubespray/blob/master/docs/offline-environment.md)
- [Kubespray Project](https://github.com/kubernetes-sigs/kubespray)

Content rephrased for compliance with licensing restrictions. Original documentation consulted via Context7 and GitHub.
