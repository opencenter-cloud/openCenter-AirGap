---
type: explanation
audience: platform-architect, platform-engineer
version: 1.0.0
last_updated: 2026-01-25
doc_type: explanation
---

# Why Zarf

Why openCenter uses Zarf as the packaging and delivery framework.

## The Packaging Problem

Air-gap deployments require bundling:
- Container images (multi-GB)
- OS packages (apt/yum)
- Binary files (kubelet, kubectl, etc.)
- Configuration files
- Scripts and playbooks
- Metadata (SBOM, checksums)

Traditional approaches:
- **Manual tarballs**: Error-prone, no structure, no validation
- **Helm charts**: Assume registry access, no binary/package support
- **Ansible roles**: No image handling, no atomic delivery
- **Custom scripts**: Fragile, not reusable, no standards

## What Zarf Provides

### 1. Declarative Package Schema

`zarf.yaml` defines components, dependencies, and actions:

```yaml
components:
  - name: kubespray-core
    required: true
    files:
      - source: kubespray/
        target: ###ZARF_VAR_INSTALL_PATH###/kubespray/
    images:
      - registry.k8s.io/kube-apiserver:v1.30.0
    actions:
      onDeploy:
        after:
          - cmd: ansible-playbook cluster.yml
```

**Benefit**: Reproducible, version-controlled, auditable.

### 2. Image Handling

Zarf automatically:
- Pulls images from upstream registries
- Retags for local registry
- Pushes to target registry
- Updates manifests with new tags

**Without Zarf**:
```bash
# Manual process (error-prone)
podman pull registry.k8s.io/kube-apiserver:v1.30.0
podman tag registry.k8s.io/kube-apiserver:v1.30.0 localhost:5000/kube-apiserver:v1.30.0
podman push localhost:5000/kube-apiserver:v1.30.0
# Update all YAML files with new registry...
```

**With Zarf**:
```yaml
images:
  - registry.k8s.io/kube-apiserver:v1.30.0
```

Zarf handles the rest.

### 3. Variable Substitution

Runtime configuration without rebuilding:

```yaml
variables:
  - name: BASTION_IP
    description: "Bastion host IP"

files:
  - source: offline.yml.tmpl
    target: offline.yml
```

Template:
```yaml
registry_host: "###ZARF_VAR_BASTION_IP###:35000"
```

Deploy:
```bash
zarf package deploy --set BASTION_IP=192.168.1.100
```

**Benefit**: Single artifact for multiple environments.

### 4. SBOM Generation

Zarf integrates Syft to generate SBOM automatically:

```bash
zarf package create .
# Generates SBOM in SPDX/CycloneDX format
```

**Without Zarf**: Manual SBOM creation, prone to drift.

### 5. Cryptographic Signing

Cosign integration for supply chain security:

```bash
zarf package create .
zarf package sign zarf-package-*.tar.zst --key cosign.key
```

Verify:
```bash
zarf package verify zarf-package-*.tar.zst --key cosign.pub
```

**Benefit**: Chain of custody, tamper detection.

### 6. Component Actions

Lifecycle hooks for setup and teardown:

```yaml
actions:
  onDeploy:
    before:
      - cmd: ./setup-registry.sh
    after:
      - cmd: ./verify-cluster.sh
  onRemove:
    before:
      - cmd: ./backup-data.sh
```

**Benefit**: Orchestration without external tools.

### 7. Idempotency

Zarf tracks deployed components:

```bash
zarf package deploy package.tar.zst  # First run
zarf package deploy package.tar.zst  # Re-run (safe)
```

Re-running skips already-deployed components.

## Alternatives Considered

### Option 1: Helm + Custom Scripts

**Approach**: Helm charts for K8s resources, scripts for images/binaries.

**Rejected**:
- Helm assumes registry access
- No binary/package handling
- No SBOM generation
- Fragmented tooling

### Option 2: Ansible Only

**Approach**: Ansible playbooks for everything.

**Rejected**:
- No image retagging
- No atomic packaging
- No SBOM/signing
- Complex variable management

### Option 3: Custom Packaging Tool

**Approach**: Build our own packaging framework.

**Rejected**:
- Reinventing the wheel
- Maintenance burden
- No community support
- Zarf already solves this

### Option 4: OCI Artifacts

**Approach**: Package everything as OCI artifacts.

**Rejected**:
- Requires registry in Zone C
- No binary/package support
- Complex multi-artifact coordination
- Zarf uses OCI internally anyway

## Tradeoffs

**Advantages**:
- Purpose-built for air-gap
- Handles images, files, and actions
- SBOM and signing built-in
- Active community and DoD backing
- Variable substitution
- Idempotent deployments

**Disadvantages**:
- Learning curve for zarf.yaml syntax
- Opinionated structure
- Go binary dependency (but static, no runtime deps)
- Package size (includes all images)

## Design Decisions

**Why not split images into separate package?**

Atomic delivery. Either you have everything or nothing. Splitting creates coordination overhead and version skew risk.

**Why not use Helm for K8s resources?**

Zarf supports Helm charts as components. We use both: Zarf for packaging, Helm for K8s resource templating.

**Why not use Kustomize?**

We do. FluxCD uses Kustomize for GitOps. Zarf handles the air-gap delivery; Kustomize handles the K8s configuration.

**Why not use Docker/Podman save/load?**

Zarf uses OCI internally but adds:
- Automatic retagging
- Manifest updates
- SBOM generation
- Variable substitution
- Component orchestration

## Integration with kubespray-offline

kubespray-offline provides asset discovery and collection. Zarf provides packaging and delivery.

**Division of labor**:
- **kubespray-offline**: What to download, where to get it
- **Zarf**: How to package it, how to deploy it

**Workflow**:
1. kubespray-offline downloads assets to `outputs/`
2. Zarf packages `outputs/` into single artifact
3. Zarf deploys artifact in Zone C

**Why not use kubespray-offline's packaging?**

kubespray-offline creates multiple tarballs. Zarf provides:
- Single artifact
- SBOM generation
- Cryptographic signing
- Variable substitution
- Component orchestration

## Real-World Impact

**Before Zarf**:
- 15+ manual steps to create package
- 3-5 hours to build
- Frequent missing dependencies
- No SBOM
- Manual checksum generation
- Fragile deployment scripts

**After Zarf**:
- Single command: `zarf package create`
- 30-60 minutes to build
- Comprehensive dependency capture
- Automatic SBOM
- Built-in checksums and signing
- Declarative deployment

## Implications

**For Platform Engineers**:
- Learn zarf.yaml schema
- Structure components logically
- Use variables for environment-specific config
- Test package creation in CI/CD

**For Field Operators**:
- Single command deployment
- Variable prompts guide configuration
- Idempotent re-runs
- Built-in verification

**For Security Officers**:
- SBOM for every package
- Cryptographic signing
- Checksum verification
- Audit trail

## Related Concepts

- [Three-Zone Model](../architecture/three-zone-model.md) - Where Zarf fits
- [Offline-First Design](offline-first-design.md) - Design philosophy
- [Why Kubespray](why-kubespray.md) - Cluster bootstrap tool
- [Package Integrity Model](../technical/package-integrity-model.md) - Verification approach
