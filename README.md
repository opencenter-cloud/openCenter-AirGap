# openCenter AirGap

Comprehensive solution for deploying High Availability Kubernetes clusters in completely disconnected (air-gapped) environments.

## Project Structure

```
.
├── assets/                    # Assets for Zarf packaging
├── build/                     # Build artifacts
│   └── kubespray-offline/     # kubespray-offline integration
├── config/                    # Configuration files
│   └── versions.env           # Version pinning
├── dist/                      # Distribution packages
├── docs/                      # Documentation
├── scripts/
│   ├── build/                 # Build orchestration scripts
│   └── deploy/                # Deployment scripts
└── tests/
    ├── unit/                  # Unit tests
    ├── property/              # Property-based tests
    └── integration/           # Integration tests
```

## Quick Start

### Build Phase (Zone A - Connected Environment)

1. Configure versions in `config/versions.env`
2. Run asset collection: `./scripts/build/collect_assets.sh`
3. Build Zarf package: `./scripts/build/create_package.sh`

### Deploy Phase (Zone C - Air-Gapped Environment)

1. Transfer package to bastion host
2. Verify package integrity: `./scripts/deploy/verify_package.sh`
3. Deploy cluster: `./scripts/deploy/deploy_cluster.sh`

## Integration with kubespray-offline

This project leverages [kubespray-offline](https://github.com/tmurakam/kubespray-offline) for Kubernetes asset collection:

- **K8s Images**: Container images for control plane, CNI, add-ons
- **Binaries**: kubeadm, kubectl, kubelet, etcd, CNI plugins
- **Python Wheels**: Ansible, Jinja2, netaddr dependencies
- **Apt Packages**: Complete Ubuntu 24.04 repository mirror

The kubespray-offline outputs are packaged by Zarf into a single cryptographically signed artifact.

## Configuration

### Runtime Versions (config/versions.env)

- **Kubespray**: master branch
- **Kubernetes**: Determined by Kubespray master
- **RUNC**: 1.3.4
- **Containerd**: 2.1.5
- **CNI**: 1.8.0

### Core Services

- FluxCD v1.4.x (GitOps)
- Gitea 1.21.0 (Git server)
- cert-manager v1.13.0
- ingress-nginx v1.9.0
- Keycloak 21.1.1
- kube-prometheus-stack (Prometheus v2.48.0, Grafana 10.2.0)

## Deployment Modes

- **Bare-metal**: Deploy to pre-provisioned nodes
- **OpenStack**: Provision VMs with Terraform, then deploy

## Documentation

- [Product Requirements](docs/product-requirements.md)
- [Design Document](docs/design-document.md)
- [Implementation Spec](.kiro/specs/opencenter-airgap/)

## Testing

```bash
# Unit tests
pytest tests/unit/

# Property-based tests
pytest tests/property/

# Integration tests
./tests/integration/run_all.sh
```

## License

See LICENSE file for details.
