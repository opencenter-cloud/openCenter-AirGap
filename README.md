# openCenter AirGap

**doc_type: explanation**

Single-artifact Kubernetes deployment for air-gapped environments. Packages infrastructure provisioning, cluster bootstrapping, and core services into one cryptographically verifiable Zarf archive.

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

```bash
# Zone A: Build the package
git clone <repo-url>
cd opencenter-airgap
python3 -m opencenter_build build --config config/components.yaml

# Zone B: Transfer
# Copy dist/zarf-package-*.tar.zst to removable media

# Zone C: Deploy
zarf package deploy zarf-package-*.tar.zst --confirm
```

See [First Deployment Tutorial](docs/tutorials/01-first-deployment.md) for a complete walkthrough.

## Documentation

Documentation follows the [Diátaxis framework](https://diataxis.fr/). Pick your path:

| I want to... | Start here |
|--------------|------------|
| Learn by doing | [First Deployment Tutorial](docs/tutorials/01-first-deployment.md) |
| Complete a specific task | [How-to Guides](docs/taxonomy.md#how-to-guides) |
| Look up technical details | [Reference Docs](docs/taxonomy.md#reference) |
| Understand the design | [Architecture Explanation](docs/explanation/architecture/architecture-overview.md) |

Full navigation: [Documentation Taxonomy](docs/taxonomy.md)

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

Active development. Current focus:

- Python CLI migration (replacing bash orchestration)
- Component manifest schema validation
- Build determinism and reproducibility
- Enhanced SBOM generation

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## Requirements

**Build Host (Zone A)**:
- Ubuntu 24.04
- 100GB+ free disk
- Internet access
- Python 3.10+, Git, Zarf CLI

**Bastion (Zone C)**:
- Ubuntu 24.04
- 100GB+ free disk
- SSH access to target nodes
- Ports 5000, 8080 open to target nodes

**Target Nodes (Zone C)**:
- Ubuntu 24.04
- Network access to bastion
- SSH access from bastion

See [System Requirements](docs/reference/system-requirements.md) for details.

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
