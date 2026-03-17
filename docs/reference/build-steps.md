---
id: build-steps
title: "Build Steps"
sidebar_label: Build Steps
description: Detailed breakdown of the seven build phases and their operations, outputs, and failure modes.
doc_type: reference
audience: "platform engineers"
tags: [build, phases, pipeline, zarf, packaging]
---

# Build Steps

Detailed breakdown of build phases and operations.

## Overview

Build process has 7 phases executed sequentially:

1. Validation (1-2 min)
2. Repository Cloning (2-5 min)
3. Asset Collection (30-40 min)
4. Asset Staging (5-10 min)
5. Zarf Packaging (5-10 min)
6. SBOM Generation (2-5 min)
7. Signing (< 1 min)

Total: 45-73 minutes depending on network speed and component count.

## Phase 1: Validation

**Duration**: 1-2 minutes

**Operations**:
- Parse component manifest YAML
- Validate against JSON schema
- Check component name uniqueness
- Verify version format (semantic versioning)
- Validate URLs are reachable
- Check disk space (requires 100GB+ free)
- Verify required tools installed (git, python3, zarf)

**Outputs**:
- `build/.state.json` (build state tracking)
- `build/validation.log`

**Failure Modes**:
- Invalid YAML syntax → Fix manifest
- Schema validation error → Check component fields
- Insufficient disk space → Free space or use different volume
- Missing tools → Install prerequisites

## Phase 2: Repository Cloning

**Duration**: 2-5 minutes

**Operations**:
- Clone kubespray-offline to `build/kubespray-offline/`
- Clone kubespray to `build/kubespray/`
- Checkout specified refs (tags or commits)
- Verify commit SHAs match expected values

**Outputs**:
- `build/kubespray-offline/` (asset discovery tool)
- `build/kubespray/` (Kubernetes installer)

**Failure Modes**:
- Git clone timeout → Check network/firewall
- Invalid ref → Verify tag/branch exists
- Commit SHA mismatch → Update expected SHA or investigate tampering

## Phase 3: Asset Collection

**Duration**: 30-40 minutes (network-dependent)

**Operations**:

### 3.1: Container Images (15-20 min)
- Parse Helm charts and Kubespray defaults for image references
- Pull images by digest (if specified) or tag
- Save images as tar.gz: `build/images/<name>.tar.gz`
- Verify checksums

### 3.2: OS Packages (8-12 min)
- Download Ubuntu packages from apt repos
- Download dependencies recursively
- Create apt repository structure: `build/debs/`
- Generate Packages.gz index

### 3.3: Python Wheels (2-3 min)
- Download Python packages from PyPI
- Download dependencies from requirements.txt
- Create PyPI mirror structure: `build/pypi/`
- Generate simple index

### 3.4: Kubernetes Binaries (3-5 min)
- Download kubelet, kubectl, kubeadm
- Download runc, containerd, CNI plugins
- Verify SHA256 checksums
- Save to `build/files/`

### 3.5: Terraform Providers (OpenStack only, 2-3 min)
- Mirror providers to `build/terraform-mirror/`
- Generate filesystem mirror config
- Lock provider versions

**Outputs**:
- `build/images/` (container images as tar.gz)
- `build/debs/` (apt repository)
- `build/pypi/` (PyPI mirror)
- `build/files/` (binaries)
- `build/terraform-mirror/` (Terraform providers)

**Failure Modes**:
- Image pull timeout → Retry with backoff
- Package not found → Check version exists in upstream repo
- Checksum mismatch → Upstream changed, update manifest
- Rate limiting → Add delays between requests

## Phase 4: Asset Staging

**Duration**: 5-10 minutes

**Operations**:
- Copy assets from `build/` to `assets/` (Zarf staging area)
- Generate configuration files:
  - `assets/playbook/offline-repo.yml` (Ansible playbook for node config)
  - `assets/scripts/setup-all.sh` (bastion setup script)
  - `assets/scripts/start-registry.sh` (registry startup)
  - `assets/scripts/start-nginx.sh` (nginx startup)
- Template Zarf variables into configs
- Set file permissions

**Outputs**:
- `assets/` (complete staging directory)
- `assets/scripts/` (deployment scripts)
- `assets/playbook/` (Ansible playbooks)

**Failure Modes**:
- Disk space exhausted → Clean build directory
- Permission denied → Check file ownership
- Template rendering error → Fix variable references

## Phase 5: Zarf Packaging

**Duration**: 5-10 minutes

**Operations**:
- Read `zarf.yaml` manifest
- Compress assets with zstd (level 9)
- Create component layers
- Generate package metadata
- Write package to `dist/zarf-package-*.tar.zst`

**Outputs**:
- `dist/zarf-package-opencenter-airgap-amd64-<version>.tar.zst`

**Compression Ratios**:
- Images: ~30% (already compressed)
- Packages: ~40% (gzip → zstd)
- Binaries: ~50% (ELF compression)
- Overall: ~35-40% (25GB → 15-18GB)

**Failure Modes**:
- Compression error → Check disk space
- Invalid zarf.yaml → Validate manifest syntax
- Component missing → Verify asset staging completed

## Phase 6: SBOM Generation

**Duration**: 2-5 minutes

**Operations**:
- Scan package with syft
- Extract component metadata (name, version, type)
- Scan for vulnerabilities with Trivy
- Generate CycloneDX JSON
- Write to `dist/zarf-package-*-sbom.json`

**SBOM Contents**:
- Artifact list (images, binaries, packages)
- Version information
- Checksums
- Vulnerability scan results (if enabled)
- License data (if available)

**Outputs**:
- `dist/zarf-package-*-sbom.json`

**Failure Modes**:
- syft not found → Install syft
- Trivy scan timeout → Increase timeout or skip scanning
- CVE policy violation → Fix vulnerabilities or update policy

## Phase 7: Signing

**Duration**: < 1 minute

**Operations**:
- Generate SHA256 checksum
- Write to `dist/zarf-package-*.sha256`
- Sign package with Cosign (if key provided)
- Write signature to `dist/zarf-package-*.sig`

**Outputs**:
- `dist/zarf-package-*.sha256` (checksum)
- `dist/zarf-package-*.sig` (signature, optional)

**Failure Modes**:
- Private key not found → Provide key path or skip signing
- Key password incorrect → Re-enter password
- Cosign not installed → Install cosign

## State Management

Build state tracked in `build/.state.json`:

```json
{
  "phase": "ASSET_COLLECTION",
  "started_at": "2026-02-01T14:30:00Z",
  "completed_phases": ["VALIDATION", "REPOSITORY_CLONING"],
  "current_operation": "Downloading images (45/120)",
  "progress": 0.38,
  "checkpoints": {
    "images": ["nginx:1.25.0", "registry:2.8.3", ...],
    "packages": ["kubelet", "kubectl", ...]
  }
}
```

Resume from checkpoint:
```bash
opencenter-build build --config components.yaml --resume
```

## Parallelization

**Parallel Operations**:
- Image pulls (4 concurrent by default)
- Package downloads (4 concurrent)
- Checksum verification (CPU-bound, all cores)

**Sequential Operations**:
- Repository cloning (git limitation)
- Zarf packaging (compression is sequential)
- SBOM generation (scanning is sequential)

**Tuning**:
```bash
# Increase parallel workers
opencenter-build build --parallel 8

# Reduce compression level (faster, larger file)
opencenter-build build --compression-level 6
```

## Disk Usage

**Peak Usage** (during build):
- `build/`: 60-70GB
- `assets/`: 25-30GB
- `dist/`: 15-18GB
- Total: ~100-120GB

**After Cleanup**:
- `dist/`: 15-18GB (package + SBOM + checksum)
- `build/`: 0GB (removed)
- `assets/`: 0GB (removed)

**Cleanup**:
```bash
# Automatic after successful build
rm -rf build/ assets/

# Manual cleanup
opencenter-build clean
```

## Logging

**Log Levels**:
- `DEBUG`: All operations, network requests, file I/O
- `INFO`: Phase transitions, progress updates
- `WARNING`: Retries, non-fatal errors
- `ERROR`: Fatal errors, build failures

**Log Locations**:
- `stdout`: Human-readable, colored
- `build.log`: Machine-readable, plain text
- `build/phase-*.log`: Per-phase detailed logs

**Example Log Entry**:
```
2026-02-01 14:32:15 INFO [build] Phase: ASSET_COLLECTION
2026-02-01 14:32:16 DEBUG [images] Pulling docker.io/library/nginx:1.25.0
2026-02-01 14:32:45 INFO [images] Collected 45/120 images (38%)
2026-02-01 14:33:10 WARNING [images] Retry 1/3 for registry.k8s.io/pause:3.9
2026-02-01 14:33:15 INFO [images] Collected 46/120 images (38%)
```

## Metrics

**Collected Metrics**:
- Phase duration
- Download speed (MB/s)
- Compression ratio
- Artifact count by type
- Disk usage by phase

**Export**:
```bash
# JSON format
opencenter-build build --metrics-output metrics.json

# Prometheus format
opencenter-build build --metrics-output metrics.prom
```

## See Also

- [CLI Commands](cli-commands.md)
- [Component Manifest Schema](component-manifest-schema.md)
- [Troubleshooting](troubleshooting.md)
