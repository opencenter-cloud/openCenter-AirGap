# openCenter AirGap

**doc_type: reference**

Build tool for creating air-gapped Kubernetes deployment packages. Collects container images, binaries, OS packages, and Python dependencies into a single cryptographically verifiable Zarf artifact.

## What This Is

A build system that collects every dependency needed to deploy a production Kubernetes cluster without internet access:

- Container images (registry:2, kubelet, calico, flux, etc.)
- OS packages (apt repository for Ubuntu 24.04)
- Python wheels (Ansible, kubespray dependencies)
- Kubernetes binaries (kubectl, kubeadm, kubelet, runc, containerd)
- Terraform providers (OpenStack only)
- GitOps tooling (FluxCD, Gitea, cert-manager, ingress-nginx)

The output is a single `.tar.zst` file with an SBOM and cryptographic signature. Transfer it to a disconnected site, deploy to a bastion host, and run the installer. The bastion serves as a local registry and package repository for the target cluster nodes.

## Who This Is For

- **Platform Engineers**: Build and version air-gap artifacts for edge deployments
- **Field Operators**: Deploy clusters at disconnected sites without troubleshooting dependencies
- **Security Officers**: Verify SBOM and artifact integrity before deployment
- **Architects**: Standardize operating environments across regulated or edge locations

## Three-Zone Model

1. **Zone A (Factory)**: Connected build host downloads and packages all dependencies
2. **Zone B (Airlock)**: Physical media transfer (USB, DVD, secure courier)
3. **Zone C (Field)**: Disconnected deployment with bastion serving local registry/repos

## Quick Start

### Prerequisites

- Python 3.10+
- Git
- 100GB+ free disk space
- Internet access (Zone A only)

### Installation

```bash
# Clone repository
git clone <repo-url>
cd opencenter-airgap

# Install package in development mode
pip install -e .

# Verify installation
python3 -m opencenter_build.cli --help
```

### Build Package (Zone A - Connected)

```bash
# Initialize build environment with component manifest
python3 -m opencenter_build.cli init --create-manifest

# Create versions.env (required)
cat > config/versions.env << 'EOF'
KUBERNETES_VERSION=1.34.3
CALICO_VERSION=3.27.0
CONTAINERD_VERSION=2.1.5
RUNC_VERSION=1.3.4
EOF

# Optional: Customize components
# Edit config/components.yaml to add/remove images, charts, repos, tools

# Scan repositories for images (if repos configured)
python3 -m opencenter_build.cli scan

# Build package (generates manifest and Zarf config)
python3 -m opencenter_build.cli build

# Check build status
python3 -m opencenter_build.cli status

# Verify generated artifacts
ls -lh dist/
```

**Current Limitations:**
- Full build requires kubespray-offline integration (in progress)
- Zarf package creation requires Zarf CLI installed
- Component manifest auto-discovery under development

Output: `dist/artifact-manifest.json`, `zarf.yaml` (Zarf package creation requires `zarf package create`)

### Transfer (Zone B - Airlock)

```bash
# Copy package to removable media
cp dist/zarf-package-*.tar.zst /media/usb/

# Verify checksum
sha256sum dist/zarf-package-*.tar.zst > package.sha256
```

### Deploy (Zone C - Disconnected)

```bash
# On bastion host (requires Zarf CLI)
zarf package deploy zarf-package-*.tar.zst --confirm

# Verify deployment
kubectl get nodes
kubectl get pods -A
```

See [First Deployment Tutorial](docs/tutorials/01-first-deployment.md) for complete walkthrough.

## Documentation

Documentation follows the [Diátaxis framework](https://diataxis.fr/):

| I want to... | Start here |
|--------------|------------|
| Learn by doing | [First Deployment Tutorial](docs/tutorials/01-first-deployment.md) |
| Complete a specific task | [How-to Guides](docs/taxonomy.md#how-to-guides) |
| Look up technical details | [Reference Docs](docs/taxonomy.md#reference) |
| Understand the design | [Architecture Review](docs/architecture-review.md) |

Full navigation: [Documentation Taxonomy](docs/taxonomy.md)

## CLI Commands

```bash
# Initialize new build environment
python3 -m opencenter_build.cli init [--template baremetal|openstack]

# Add components to manifest
python3 -m opencenter_build.cli add tool --name kubectl --version v1.34.3 --url <url>
python3 -m opencenter_build.cli add image registry.k8s.io/kube-apiserver:v1.34.3
python3 -m opencenter_build.cli add repo https://github.com/kubernetes-sigs/kubespray.git

# Scan repositories for images
python3 -m opencenter_build.cli scan

# Build package
python3 -m opencenter_build.cli build [--clean] [--resume]

# Check build status
python3 -m opencenter_build.cli status

# Verify package integrity
python3 -m opencenter_build.cli verify <package> [--manifest <manifest>]

# Validate configuration
python3 -m opencenter_build.cli validate
```

See [CLI Reference](docs/reference/cli-commands.md) for complete command documentation.

## Key Concepts

**Air-gap**: No internet connectivity during deployment. All dependencies bundled at build time.

**Bastion**: A single node in the target environment that runs local registry (port 5000) and package repositories (port 8080). Target nodes pull from bastion instead of internet.

**Zarf**: Packaging framework that handles compression, SBOM generation, and cryptographic signing. Provides declarative manifest for components.

**Kubespray**: Ansible-based Kubernetes installer. We use kubespray-offline to discover and collect all dependencies.

**Component Manifest**: YAML file defining what to include in the build (images, charts, binaries). See [Component Manifest Schema](docs/reference/component-manifest-schema.md).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Zone A: Factory (Connected)                                 │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │ kubespray-   │───▶│ opencenter-  │───▶│ Zarf Package │ │
│  │ offline      │    │ build        │    │ (.tar.zst)   │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│        │                     │                              │
│        ▼                     ▼                              │
│  Download from          Collect into                        │
│  internet               single artifact                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ Physical Transfer
┌─────────────────────────────────────────────────────────────┐
│ Zone C: Field (Disconnected)                                │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │ Bastion      │───▶│ Target Nodes │───▶│ K8s Cluster  │ │
│  │ (registry +  │    │ (kubelet +   │    │ (workloads)  │ │
│  │  repos)      │    │  containerd) │    │              │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│        │                     │                              │
│        ▼                     ▼                              │
│  Serves images          Pulls from                          │
│  and packages           bastion only                        │
└─────────────────────────────────────────────────────────────┘
```

See [Architecture Overview](docs/explanation/architecture/architecture-overview.md) for details.

## Technology Stack

- **Kubernetes**: v1.34.3 (via Kubespray)
- **Container Runtime**: runc 1.3.4
- **CNI**: Calico
- **GitOps**: FluxCD v2.2.0 + Gitea 1.21.0
- **Ingress**: ingress-nginx v1.9.0
- **Auth**: Keycloak 21.1.1
- **Monitoring**: Prometheus v2.48.0, Grafana 10.2.0
- **Certificates**: cert-manager v1.13.0

All versions pinned in `config/versions.env`. See [Version Management](docs/reference/version-management.md).

## Project Status

Active development. Python CLI migration in progress.

**Completed:**
- Python CLI framework (init, add, scan, build, verify, status)
- Component manifest management
- Repository scanning and image discovery
- Build state management with checkpoint/resume
- Package verification (Cosign + Zarf)
- Structured logging and metrics
- Comprehensive test suite (96.8% coverage)

**In Progress:**
- kubespray-offline integration for OS packages and PyPI
- Zarf package creation automation
- Terraform provider mirroring
- Full end-to-end build workflow

**Planned:**
- Binary distribution (PyInstaller)
- Enhanced SBOM generation
- Build determinism validation
- Multi-architecture support

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## Requirements

**Build Host (Zone A)**:
- Ubuntu 24.04 (or compatible Linux)
- 100GB+ free disk space
- Internet access
- Python 3.10+
- Git 2.30+
- Optional: Zarf CLI (for package creation)

**Bastion (Zone C)**:
- Ubuntu 24.04
- 100GB+ free disk space
- SSH access to target nodes
- Ports 5000 (registry), 8080 (repos) open to target nodes
- Zarf CLI installed

**Target Nodes (Zone C)**:
- Ubuntu 24.04
- Network access to bastion
- SSH access from bastion
- Minimum 4 CPU, 8GB RAM per node

See [System Requirements](docs/reference/system-requirements.md) for detailed specifications.

## Security

- All artifacts cryptographically signed (Cosign)
- SBOM generated for every build
- Secrets managed via file-based injection (never in git)
- Trivy scanning for CVEs (policy: fail on HIGH/CRITICAL)

See [SECURITY.md](SECURITY.md) for vulnerability reporting and [Secrets Management](docs/reference/secrets-management.md) for handling credentials.

## License

See [LICENSE](LICENSE) file.

## Support

- Issues: GitHub Issues
- Security: See [SECURITY.md](SECURITY.md)
- Contributing: See [CONTRIBUTING.md](CONTRIBUTING.md)
