# Project Structure

## Directory Organization

```
.
├── assets/                    # Assets for Zarf packaging
├── build/                     # Build artifacts and outputs
│   └── kubespray-offline/     # kubespray-offline integration outputs
├── config/                    # Configuration files
│   └── versions.env           # Version pinning for all components
├── dist/                      # Distribution packages (Zarf artifacts)
├── docs/                      # Documentation
│   ├── product-requirements.md
│   └── design-document.md
├── scripts/
│   ├── build/                 # Build orchestration scripts
│   └── deploy/                # Deployment scripts
└── tests/
    ├── unit/                  # Unit tests
    ├── property/              # Property-based tests
    └── integration/           # Integration tests
```

## Key Directories

### `/assets`
Staging area for Zarf package components:
- Terraform binaries and provider mirrors
- Python wheels
- Kubernetes binaries
- Container images
- Configuration templates

### `/build`
Build artifacts and intermediate outputs:
- `kubespray-offline/outputs/`: Downloaded offline assets (files, images, debs, pypi)
- Temporary build files
- Generated manifests

### `/config`
Configuration and version management:
- `versions.env`: Single source of truth for all component versions
- Environment-specific configurations
- Inventory templates

### `/dist`
Final distribution artifacts:
- Zarf packages: `zarf-package-openCenter-airgap-amd64-<version>.tar.zst`
- SBOM files
- Checksum manifests
- Signature files (Cosign)

### `/docs`
Project documentation:
- Product requirements
- Design documents
- Architecture diagrams
- Runbooks and operational guides

### `/scripts/build`
Build automation scripts:
- Asset collection (kubespray-offline integration)
- Terraform provider mirroring
- Python wheel collection
- Zarf package creation
- SBOM generation

### `/scripts/deploy`
Deployment automation scripts:
- Package verification
- Cluster deployment orchestration
- Post-deployment validation
- Recovery procedures

### `/tests`
Test suites:
- `unit/`: Component-level tests
- `property/`: Property-based tests for correctness
- `integration/`: End-to-end deployment tests

## Zarf Package Structure (Runtime)

When deployed, Zarf extracts to `/opt/opencenter/` on bastion:

```
/opt/opencenter/
├── files/          # K8s binaries (kubelet, kubectl, kubeadm, runc, containerd, etc.)
├── images/         # Container images as tar.gz
├── debs/           # Ubuntu package repository
├── pypi/           # PyPI mirror
├── playbook/       # offline-repo.yml for node configuration
├── scripts/        # setup-all.sh, start-nginx.sh, start-registry.sh, etc.
├── kubespray/      # Kubespray playbooks and inventory
└── terraform/      # Terraform modules (OpenStack only)
```

## File Naming Conventions

### Scripts
- Build scripts: `collect_*.sh`, `create_*.sh`
- Deployment scripts: `deploy_*.sh`, `verify_*.sh`
- Setup scripts: `setup_*.sh`, `start_*.sh`

### Configuration
- Environment files: `*.env`
- Terraform configs: `*.tf`, `.terraformrc`
- Ansible inventories: `inventory.yml`, `offline.yml`

### Packages
- Zarf packages: `zarf-package-<name>-<arch>-<version>.tar.zst`
- SBOM files: `<package-name>-sbom.json`
- Checksums: `<package-name>.sha256`

## Integration Points

### kubespray-offline Integration
- Clone to `build/kubespray-offline/`
- Execute `download-all.sh` to populate `outputs/`
- Zarf packages `outputs/` directory into artifact

### Terraform Integration (OpenStack Only)
- Modules in `assets/terraform/`
- Provider mirror in `assets/terraform-mirror/`
- Configuration in `assets/terraform-config/.terraformrc`

### Kubespray Integration
- Playbooks extracted to `/opt/opencenter/kubespray/`
- Offline configuration in `offline.yml`
- Inventory templates in `config/inventory-templates/`

## Spec Files

Specifications for feature development:
- Location: `.kiro/specs/<feature-name>/`
- Files: `requirements.md`, `design.md`, `tasks.md`
- Current spec: `.kiro/specs/opencenter-airgap/`

## Steering Files

AI assistant guidance documents:
- Location: `.kiro/steering/`
- Files: `product.md`, `tech.md`, `structure.md`, `python-environment.md`
- Always included in AI context

## Conventions

### Directory Creation
- Build artifacts go in `build/`
- Final packages go in `dist/`
- Never commit build artifacts or dist packages to git

### Path References
- Use relative paths from project root
- Zarf variables: `###ZARF_VAR_INSTALL_PATH###`
- Ansible variables: `{{ http_server }}`, `{{ registry_host }}`

### Asset Organization
- Group by type: binaries, images, packages, wheels
- Maintain kubespray-offline directory structure
- Keep checksums with assets
