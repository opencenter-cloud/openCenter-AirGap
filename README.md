# openCenter AirGap

![Test Coverage](https://img.shields.io/badge/coverage-72%25-yellow)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)

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
- Python 3.10+
- **Skopeo** (container image operations) - `sudo apt-get install skopeo`
- **Podman** (container runtime) - `sudo apt-get install podman`
- **Trivy** (vulnerability scanning) - See installation below
- Zarf CLI
- 100GB+ disk space

**Zone C (Deploy)**:
- Bastion host: Ubuntu 24.04, 100GB disk, podman
- Target nodes: Ubuntu 24.04, SSH access
- Network connectivity between bastion and nodes

**Container Tools**:
```bash
# Install Skopeo and Podman (Ubuntu 24.04)
sudo apt-get update
sudo apt-get install -y skopeo podman

# Verify installation
skopeo --version  # Should show 1.13.x+
podman --version  # Should show 4.3.x+

# Install Trivy (vulnerability scanner)
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

# Verify Trivy installation
trivy --version  # Should show latest stable version
```

**Why Skopeo and Podman?**
- **Daemonless**: No background services required
- **Rootless**: Can run without root privileges
- **Air-gap optimized**: Direct registry-to-directory copies
- **Docker-free**: No Docker daemon dependency

### Build (Zone A)

```bash
# 1. Clone repository
git clone <repo-url>
cd opencenter-airgap

# 2. Setup GitHub token for openCenter assets
export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
# Or create .env file: echo "GITHUB_TOKEN=ghp_xxxxxxxxxxxx" > .env

# 3. Run build (30-60 minutes, Python environment created automatically)
python3 scripts/build/build.py --clean

# Output: dist/zarf-package-openCenter-airgap-amd64-1.0.0.tar.zst
```

Build system features:
- Automatic resume after failures
- Parallel execution of independent steps
- State tracking and progress reporting
- Comprehensive logging

Resume after interruption:
```bash
# Resume from last incomplete step
python3 scripts/build/build.py

# Resume from specific step
python3 scripts/build/build.py --from-step validate_versions

# View build state
cat build/.build-state.json | python3 -m json.tool
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
│   │   ├── build.py          # Main build orchestrator
│   │   ├── build_state.py    # State management
│   │   ├── build_steps.py    # Step definitions
│   │   ├── build_executor.py # Execution engine
│   │   ├── workers/          # Python worker functions
│   │   ├── organize_assets_for_zarf.sh
│   │   ├── collect_kubespray_offline.sh
│   │   └── collect_opencenter_assets.sh
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

**Build fails at specific step**:
```bash
# Check logs
tail -100 build/build-*.log | grep ERROR

# Resume after fixing issue
python3 scripts/build/build.py

# Skip problematic step temporarily
python3 scripts/build/build.py --skip-step problematic_step
```

**Prerequisites check fails**:
```bash
# Check what's missing
python3 scripts/build/build.py --clean 2>&1 | grep "✗"

# Install missing tools
sudo apt-get install git jq skopeo podman zarf
```

**kubespray-offline download fails**:
```bash
# Check network connectivity
curl -I https://github.com

# Resume (will retry failed downloads)
python3 scripts/build/build.py

# Force re-download
python3 scripts/build/build.py --force --from-step clone_kubespray_offline
```

**Build state corrupted**:
```bash
# Start fresh
python3 scripts/build/build.py --clean

# Or manually delete state
rm build/.build-state.json
rm -rf build/.completed/
```

**Package size exceeds 10GB**:
```bash
# Check asset sizes
du -sh build/kubespray-offline/outputs/*

# Remove unnecessary images from config/opencenter-images.txt
```

**Disk space exhausted during build**:
```bash
# Clean container cache
podman system prune -a -f

# Clean build artifacts
rm -rf build/kubespray-offline/outputs
python3 scripts/build/build.py --clean

# Check available space (need 100GB+)
df -h .
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
