# openCenter AirGap

Production-grade Kubernetes deployment for completely disconnected environments. Single cryptographically verifiable artifact containing all dependencies for infrastructure provisioning, cluster bootstrap, and core services.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│ ZONE A: FACTORY (Connected Build Environment)                      │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐          │
│  │ kubespray-   │──▶│ Asset        │──▶│ Zarf Package │          │
│  │ offline      │   │ Collection   │   │ Creation     │          │
│  │              │   │              │   │              │          │
│  │ • K8s images │   │ • Organize   │   │ • Compress   │          │
│  │ • Binaries   │   │ • Validate   │   │ • SBOM       │          │
│  │ • Packages   │   │ • Terraform  │   │ • Sign       │          │
│  └──────────────┘   └──────────────┘   └──────────────┘          │
│                                              │                      │
└──────────────────────────────────────────────┼──────────────────────┘
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ZONE B: AIRLOCK (Secure Transport)                                 │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │ openCenter-airgap-amd64-1.0.0.tar.zst                     │    │
│  │ • Immutable, signed artifact                              │    │
│  │ • SBOM embedded                                           │    │
│  │ • Checksum manifest                                       │    │
│  └───────────────────────────────────────────────────────────┘    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ZONE C: FIELD (Disconnected Deployment)                            │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────┐      │
│  │ BASTION HOST (192.168.1.5)                              │      │
│  │                                                          │      │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐             │      │
│  │  │ Registry │  │ Nginx    │  │ Kubespray│             │      │
│  │  │ :35000   │  │ :80      │  │ Ansible  │             │      │
│  │  └──────────┘  └──────────┘  └──────────┘             │      │
│  │       │              │              │                   │      │
│  └───────┼──────────────┼──────────────┼───────────────────┘      │
│          │              │              │                           │
│          │              │              ▼                           │
│  ┌───────┼──────────────┼──────────────────────────────────┐     │
│  │       │              │         KUBERNETES CLUSTER        │     │
│  │       │              │                                   │     │
│  │  ┌────▼────┐    ┌───▼────┐    ┌──────────┐            │     │
│  │  │ Control │    │ Control│    │ Control  │            │     │
│  │  │ Plane 1 │    │ Plane 2│    │ Plane 3  │            │     │
│  │  └─────────┘    └────────┘    └──────────┘            │     │
│  │       │              │              │                   │     │
│  │  ┌────▼────┐    ┌───▼────┐    ┌───▼──────┐           │     │
│  │  │ Worker 1│    │ Worker 2│    │ Worker N │           │     │
│  │  └─────────┘    └─────────┘    └──────────┘           │     │
│  │       │              │              │                   │     │
│  │       └──────────────┴──────────────┘                   │     │
│  │                      │                                   │     │
│  │              Pull images from                            │     │
│  │              bastion:35000                               │     │
│  │              Install packages from                       │     │
│  │              bastion:80                                  │     │
│  └──────────────────────────────────────────────────────────┘     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

**Zone A (Build)**:
- Ubuntu 24.04 with internet access
- Python 3.12+
- Podman or Docker
- Zarf CLI
- 100GB+ disk space

**Zone C (Deploy)**:
- Bastion host: Ubuntu 24.04, 100GB disk, podman
- Target nodes: Ubuntu 24.04, SSH access
- Network connectivity between bastion and nodes

### Build (Zone A)

```bash
# 1. Clone repository
git clone <repo-url>
cd opencenter-airgap

# 2. Setup Python environment
python3.12 -m venv venv
source venv/bin/activate
pip install pyyaml jinja2 requests

# 3. Setup GitHub token for openCenter assets
./scripts/build/setup_github_token.sh
# Follow interactive prompts to create and validate token

# 4. Clone kubespray-offline
git clone -b main https://github.com/tmurakam/kubespray-offline.git build/kubespray-offline

# 5. Configure versions (optional - defaults are production-ready)
# Edit build/kubespray-offline/target-scripts/config.sh
# Edit build/kubespray-offline/imagelists/additional_images.txt

# 6. Run build (30-60 minutes)
./scripts/build/build.sh

# Output: dist/zarf-package-openCenter-airgap-amd64-1.0.0.tar.zst
```

### Transfer (Zone B)

```bash
# Copy package to removable media or secure transfer mechanism
cp dist/zarf-package-openCenter-airgap-*.tar.zst /media/usb/

# Verify checksums
cat dist/zarf-package-openCenter-airgap-*.tar.zst.checksums
```

### Deploy (Zone C)

```bash
# 1. Transfer package to bastion
scp zarf-package-openCenter-airgap-*.tar.zst bastion:/opt/

# 2. Deploy Zarf package (extracts and configures bastion)
ssh bastion
cd /opt
zarf package deploy zarf-package-openCenter-airgap-*.tar.zst --confirm

# 3. Create node inventory
cat > nodes.yaml <<EOF
control_plane:
  - hostname: control-01
    ip: 192.168.1.10
  - hostname: control-02
    ip: 192.168.1.11
  - hostname: control-03
    ip: 192.168.1.12
workers:
  - hostname: worker-01
    ip: 192.168.1.20
  - hostname: worker-02
    ip: 192.168.1.21
EOF

# 4. Deploy cluster (20-30 minutes)
/opt/opencenter/scripts/deploy.sh \
  --mode baremetal \
  --bastion-ip 192.168.1.5 \
  --nodes nodes.yaml

# 5. Verify cluster
export KUBECONFIG=/opt/opencenter/outputs/kubespray-master/inventory/mycluster/artifacts/admin.conf
kubectl get nodes
kubectl get pods -A
```

## Deployment Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Package Verification                                         │
│    • Validate checksums (MD5, SHA256)                           │
│    • Verify Cosign signature (if signed)                        │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Bastion Setup (kubespray-offline)                           │
│    • Install containerd runtime                                 │
│    • Start nginx:1.29.2 on port 80 (file/package server)      │
│    • Start registry:2.8.3 on port 35000                        │
│    • Load and push all K8s images to registry                  │
│    • Create Python venv with Ansible                            │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Infrastructure Provisioning (OpenStack only)                 │
│    • Terraform init with filesystem mirror                      │
│    • Provision control plane and worker VMs                     │
│    • Generate Ansible inventory from outputs                    │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Inventory Generation                                         │
│    • Create Ansible hosts.yaml (bare-metal: from file)         │
│    • Generate offline.yml with bastion IP                       │
│    • Configure nodes to use bastion for packages/images         │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Cluster Bootstrap (Kubespray)                               │
│    • Extract kubespray-master tarball                           │
│    • Run offline-repo.yml (configure apt/pip on nodes)         │
│    • Run cluster.yml (install K8s)                             │
│    • Export kubeconfig                                          │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. Cluster Verification                                         │
│    • Check control plane components healthy                     │
│    • Verify all nodes in Ready state                            │
│    • Generate deployment summary                                │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration

### Version Pinning

All versions strictly pinned in `config/versions.env`:

| Component | Version | Source |
|:----------|:--------|:-------|
| Kubernetes | v1.34.3 | kubespray@master |
| Kubespray | master | git branch |
| RUNC | 1.3.4 | kubespray-offline |
| Containerd | 2.1.5 | kubespray-offline |
| Nerdctl | 2.1.6 | kubespray-offline |
| CNI | 1.8.0 | kubespray-offline |
| Nginx | 1.29.2 | kubespray-offline |
| Registry | 2.8.3 | kubespray-offline |
| Calico | v3.29.1 | kubespray |

### Bastion Services

| Service | Port | Purpose | Data Location |
|:--------|:-----|:--------|:--------------|
| Registry | 35000 | Container image registry | /var/lib/registry |
| Nginx | 80 | File/package server | /opt/opencenter/outputs |
| Python venv | - | Ansible/Kubespray execution | ~/.venv/kubespray |

### Network Requirements

**Bastion → Nodes**:
- SSH (22): Ansible execution
- HTTP (80): Package downloads (optional, for verification)

**Nodes → Bastion**:
- HTTP (80): Apt packages, Python wheels, K8s binaries
- HTTP (35000): Container image pulls

**Nodes ↔ Nodes**:
- Kubernetes API (6443)
- etcd (2379-2380)
- Kubelet (10250)
- NodePort range (30000-32767)

## Deployment Modes

### Bare-metal

Pre-provisioned nodes with Ubuntu 24.04. Provide inventory file with node IPs.

```bash
/opt/opencenter/scripts/deploy.sh \
  --mode baremetal \
  --bastion-ip 192.168.1.5 \
  --nodes nodes.yaml
```

### OpenStack

Terraform provisions VMs, generates inventory automatically.

```bash
# Create OpenStack config
cat > openstack-config.yaml <<EOF
auth_url: https://openstack.example.com:5000/v3
project_name: my-project
username: admin
region: RegionOne
control_plane_count: 3
worker_count: 3
flavor: m1.large
image: ubuntu-24.04
network: internal-net
EOF

# Deploy
/opt/opencenter/scripts/deploy.sh \
  --mode openstack \
  --bastion-ip 192.168.1.5 \
  --config openstack-config.yaml
```

## Project Structure

```
.
├── assets/                    # Zarf package assets
│   ├── k8s-binaries/         # Kubernetes binaries
│   ├── kubespray/            # Kubespray playbooks
│   ├── playbook/             # offline-repo.yml
│   ├── python-wheels/        # PyPI mirror
│   ├── repos/                # Apt repository
│   ├── target-scripts/       # Bastion setup scripts
│   └── terraform-mirror/     # Terraform providers (OpenStack)
├── build/
│   └── kubespray-offline/    # Asset collection (git clone)
├── config/
│   └── versions.env          # Version pinning
├── dist/                      # Built packages
├── docs/                      # Documentation
│   ├── build-runbook.md
│   ├── deployment-runbook-baremetal.md
│   ├── deployment-runbook-openstack.md
│   └── troubleshooting-guide.md
├── scripts/
│   ├── build/
│   │   ├── build.sh          # Master build script
│   │   ├── organize_assets_for_zarf.sh
│   │   ├── generate_zarf_yaml.py
│   │   └── verify_sbom.py
│   └── deploy/
│       ├── deploy.sh         # Master deployment script
│       ├── generate_inventory_baremetal.py
│       ├── generate_offline_yml.py
│       ├── verify_cluster_health.sh
│       └── verify_bastion_services.sh
├── tests/
│   ├── integration/
│   │   ├── test_kubespray_idempotency.sh
│   │   └── test_kubespray_offline_idempotency.sh
│   └── test_verify_sbom.py
└── zarf.yaml                  # Zarf package definition
```

## Documentation

Documentation organized by purpose using the [Diátaxis framework](docs/taxonomy.md).

**New to openCenter?** Start with the [First Deployment Tutorial](docs/tutorials/01-first-deployment.md).

### By Purpose

**Learning (Tutorials)**
- [First Deployment](docs/tutorials/01-first-deployment.md) - Deploy your first cluster in 30 minutes

**Problem-Solving (How-To Guides)**
- [Build Air-Gap Package](docs/how-to/build/build-air-gap-package.md)
- [Deploy Bare-Metal Cluster](docs/how-to/deploy/deploy-baremetal-cluster.md)
- [Verify Cluster Health](docs/how-to/verify/verify-cluster-health.md)

**Reference (Lookup)**
- [Zarf Variables](docs/reference/configuration/zarf-variables.md)
- [Service Endpoints](docs/reference/architecture/service-endpoints.md)

**Understanding (Explanations)**
- [Three-Zone Model](docs/explanation/architecture/three-zone-model.md)
- [Why Zarf](docs/explanation/design-decisions/why-zarf.md)

**Full documentation index**: [docs/README.md](docs/README.md)

## Troubleshooting

### Build Issues

**kubespray-offline download fails**:
```bash
# Check network connectivity
curl -I https://github.com

# Retry with verbose logging
cd build/kubespray-offline
bash -x download-all.sh
```

**Package size exceeds 10GB**:
```bash
# Check asset sizes
du -sh build/kubespray-offline/outputs/*

# Remove unnecessary images from additional_images.txt
```

**Disk space exhausted during build**:
```bash
# Clean build artifacts
./scripts/cleanup.sh --build --assets

# Check available space (need 100GB+)
df -h /opt
```

### Deployment Issues

**Registry startup fails (port conflict)**:
```bash
# Check existing containers
podman ps -a | grep registry

# Stop conflicting container
podman stop <container-id>

# Re-run setup
cd /opt/opencenter/outputs
./target-scripts/setup-all.sh
```

**Kubespray fails (node unreachable)**:
```bash
# Verify SSH access
ansible -i inventory/mycluster/hosts.yaml all -m ping

# Check SSH keys
ssh-copy-id deployer@192.168.1.10
```

**Image pull fails on nodes**:
```bash
# Verify registry accessible from node
ssh worker-01 "curl http://192.168.1.5:35000/v2/_catalog"

# Check containerd config
ssh worker-01 "cat /etc/containerd/config.toml | grep registry"
```

## Testing

```bash
# Unit tests
pytest tests/test_verify_sbom.py

# Integration tests
./tests/integration/test_kubespray_idempotency.sh
./tests/integration/test_kubespray_offline_idempotency.sh
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow and coding standards.

## License

See [LICENSE](LICENSE) for details.
