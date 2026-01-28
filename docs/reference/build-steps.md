# Build Steps Reference

**doc_type**: reference
**audience**: Platform engineers
**scope**: Complete build pipeline step definitions

## Overview

Build system executes steps in dependency order with automatic resume capability. Each step is idempotent and checkpointed.

## Step Definitions

### validate_versions

**Purpose**: Verify all version pins in `config/versions.env`
**Dependencies**: None
**Checkpoint**: Yes
**Duration**: <5s

Validates:
- Kubernetes version format
- Terraform version format
- All service versions are pinned (no `latest`)
- Version consistency across components

**Failure modes**:
- Missing version variable
- Invalid version format
- Unpinned version detected

### clone_kubespray_offline

**Purpose**: Clone/update kubespray-offline repository
**Dependencies**: `validate_versions`
**Checkpoint**: Yes
**Duration**: 10-30s

Clones `https://github.com/kubespray-offline/kubespray-offline` to `build/kubespray-offline/`.

**Failure modes**:
- Network connectivity
- Git authentication
- Disk space

### collect_kubespray_assets

**Purpose**: Run kubespray-offline asset collection
**Dependencies**: `clone_kubespray_offline`
**Checkpoint**: Yes
**Duration**: 20-40 minutes

Executes `download-all.sh` to collect:
- Kubernetes binaries (kubelet, kubectl, kubeadm)
- Container runtime (containerd, runc, nerdctl)
- CNI plugins
- Container images
- Debian packages
- Python wheels

**Failure modes**:
- Network timeouts
- Disk space exhaustion
- Registry rate limits

### collect_opencenter_assets

**Purpose**: Clone openCenter gitops-base repository
**Dependencies**: `validate_versions`
**Checkpoint**: Yes
**Duration**: 30-60s

Clones gitops-base to extract Helm charts and image references.

**Failure modes**:
- GitHub authentication (requires `GITHUB_TOKEN`)
- Network connectivity

### extract_opencenter_images

**Purpose**: Extract image references from Helm charts
**Dependencies**: `collect_opencenter_assets`
**Checkpoint**: Yes
**Duration**: 5-10s

Parses Helm charts in `assets/gitops-base/` to extract all container image references.

**Failure modes**:
- Malformed Helm charts
- Missing values files

### generate_image_lists

**Purpose**: Merge kubespray and openCenter image lists
**Dependencies**: `collect_kubespray_assets`, `extract_opencenter_images`
**Checkpoint**: Yes
**Duration**: <5s

Generates:
- `config/kubespray-images.txt`
- `config/opencenter-images.txt`
- `config/all-images.txt`

Deduplicates and sorts images.

**Failure modes**:
- Missing source image lists
- Write permission errors

### generate_zarf_yaml

**Purpose**: Generate final zarf.yaml from template
**Dependencies**: `generate_image_lists`
**Checkpoint**: Yes
**Duration**: <5s

Reads `zarf.yaml.template`, generates images block from `config/all-images.txt`, replaces `###IMAGES_BLOCK###` placeholder.

**Failure modes**:
- Template missing
- Placeholder not found
- Invalid image references

### collect_operator_tools

**Purpose**: Download operator CLI tools
**Dependencies**: `validate_versions`
**Checkpoint**: Yes
**Duration**: 30-60s

Downloads:
- k9s
- helm
- stern
- kubectx/kubens

**Failure modes**:
- GitHub rate limits
- Invalid release URLs
- Network connectivity

### mirror_terraform_providers

**Purpose**: Mirror Terraform providers for offline use
**Dependencies**: `validate_versions`
**Checkpoint**: Yes
**Duration**: 2-5 minutes

Mirrors providers:
- terraform-provider-openstack/openstack
- hashicorp/local
- hashicorp/null
- hashicorp/random
- hashicorp/tls

**Failure modes**:
- Terraform not installed
- Network connectivity
- Disk space

### organize_assets

**Purpose**: Organize collected assets into Zarf structure
**Dependencies**: `collect_kubespray_assets`, `collect_opencenter_assets`, `collect_operator_tools`, `mirror_terraform_providers`
**Checkpoint**: Yes
**Duration**: 5-10 minutes

Copies assets from `build/kubespray-offline/outputs/` to `assets/` directory structure.

**Failure modes**:
- Missing source assets
- Disk space
- File permissions

### create_zarf_package

**Purpose**: Build final Zarf package
**Dependencies**: `organize_assets`, `generate_zarf_yaml`
**Checkpoint**: Yes
**Duration**: 10-20 minutes

Executes `zarf package create --confirm`.

**Failure modes**:
- Zarf not installed
- Invalid zarf.yaml
- Disk space
- Image pull failures

### generate_sbom

**Purpose**: Generate Software Bill of Materials
**Dependencies**: `create_zarf_package`
**Checkpoint**: Yes
**Duration**: 10-30s

Extracts SBOM from Zarf package.

**Failure modes**:
- Package not found
- Zarf version incompatibility

### sign_package

**Purpose**: Cryptographically sign package with Cosign
**Dependencies**: `create_zarf_package`
**Checkpoint**: No (optional)
**Duration**: 5-10s

Signs package if `COSIGN_KEY` environment variable is set.

**Failure modes**:
- Cosign not installed
- Invalid signing key
- Key passphrase incorrect

## Dependency Graph

```
validate_versions
├── clone_kubespray_offline
│   └── collect_kubespray_assets
│       └── generate_image_lists
│           └── generate_zarf_yaml
│               └── create_zarf_package
│                   ├── generate_sbom
│                   └── sign_package
├── collect_opencenter_assets
│   └── extract_opencenter_images
│       └── generate_image_lists
├── collect_operator_tools
│   └── organize_assets
└── mirror_terraform_providers
    └── organize_assets
        └── create_zarf_package
```

## Resume Behavior

Build state tracked in `build/.build-state.json`:

```json
{
  "last_step": "collect_kubespray_assets",
  "completed_steps": [
    "validate_versions",
    "clone_kubespray_offline"
  ],
  "failed_step": null,
  "timestamp": "2026-01-27T10:30:45Z"
}
```

Resume from last incomplete step:
```bash
python3 scripts/build/build.py
```

Resume from specific step:
```bash
python3 scripts/build/build.py --from-step generate_image_lists
```

Force re-run step:
```bash
python3 scripts/build/build.py --force --from-step collect_kubespray_assets
```

## Parallel Execution

Independent steps execute in parallel:
- `collect_opencenter_assets` || `clone_kubespray_offline`
- `collect_operator_tools` || `mirror_terraform_providers`

Parallelism controlled by `--workers` flag (default: 4).

## Checkpoints

Checkpoint files in `build/.completed/`:
```
build/.completed/
├── validate_versions.done
├── clone_kubespray_offline.done
├── collect_kubespray_assets.done
└── ...
```

Clear checkpoints:
```bash
rm -rf build/.completed/
```

## Logging

Logs written to `build/build-YYYYMMDD-HHMMSS.log`.

View real-time:
```bash
tail -f build/build-*.log
```

Filter errors:
```bash
grep ERROR build/build-*.log
```
