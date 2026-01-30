# openCenter AirGap Build System

**doc_type: reference**

Build tool for creating air-gapped Kubernetes deployment packages. Collects container images, binaries, OS packages, and Python dependencies into a single cryptographically verifiable Zarf artifact.

## Quick Start

```bash
# Install binary
curl -LO https://github.com/rackerlabs/opencenter-airgap/releases/latest/download/opencenter-airgap
chmod +x opencenter-airgap
sudo mv opencenter-airgap /usr/local/bin/

# Initialize configuration
opencenter-airgap init --create-manifest

# Add components
opencenter-airgap add tool helm 3.14.0 https://get.helm.sh/helm-v3.14.0-linux-amd64.tar.gz
opencenter-airgap add repo kubespray https://github.com/kubernetes-sigs/kubespray.git master

# Build package
opencenter-airgap build

# Deploy (on air-gapped bastion)
opencenter-airgap serve dist/zarf-package-*.tar.zst
```

## Prerequisites

**Build Environment (Zone A - Connected)**:
- Ubuntu 24.04 AMD64
- 100GB+ free disk space
- Internet access
- Python 3.10+ (if running from source)

**Deployment Environment (Zone C - Air-Gapped)**:
- Ubuntu 24.04 AMD64 bastion host
- Docker or Podman runtime
- 100GB+ free disk space
- SSH access to target nodes

## Commands

### init

Initialize project configuration and optionally create component manifest.

```bash
opencenter-airgap init [OPTIONS]
```

**Options**:
- `--create-manifest`: Create config/components.yaml from template
- `--template TEXT`: Template name (baremetal, openstack)
- `--config-file PATH`: Configuration file path (default: config/versions.env)

**Example**:
```bash
opencenter-airgap init --create-manifest --template baremetal
```

### add

Add component to manifest.

```bash
opencenter-airgap add COMPONENT_TYPE NAME [OPTIONS]
```

**Arguments**:
- `COMPONENT_TYPE`: tool, repo, image, or chart
- `NAME`: Component name

**Options**:
- `--version TEXT`: Component version
- `--url TEXT`: Download URL (for tools)
- `--ref TEXT`: Git ref (for repos)
- `--repo TEXT`: Helm repository URL (for charts)

**Examples**:
```bash
# Add CLI tool
opencenter-airgap add tool k9s --version 0.32.4 \
  --url https://github.com/derailed/k9s/releases/download/v0.32.4/k9s_Linux_amd64.tar.gz

# Add Git repository
opencenter-airgap add repo opencenter-gitops-base \
  --url https://github.com/rackerlabs/opencenter-gitops-base.git \
  --ref v1.0.0

# Add container image
opencenter-airgap add image docker.io/grafana/grafana:10.2.0

# Add Helm chart
opencenter-airgap add chart cert-manager --version v1.13.0 \
  --repo https://charts.jetstack.io
```

### scan

Scan repositories for container images.

```bash
opencenter-airgap scan [OPTIONS]
```

**Options**:
- `--repos PATH`: Repository paths to scan (multiple allowed)
- `--discover-images`: Discover images from component manifest repos
- `--concurrency INTEGER`: Number of worker processes
- `--verbose`: Enable verbose output

**Example**:
```bash
opencenter-airgap scan --discover-images --concurrency 8
```

### generate-manifest

Generate Zarf manifest from component manifest.

```bash
opencenter-airgap generate-manifest [OPTIONS]
```

**Options**:
- `--output PATH`: Output path for Zarf manifest (default: zarf.yaml)

**Example**:
```bash
opencenter-airgap generate-manifest --output zarf.yaml
```

### build

Build air-gap package with all artifacts.

```bash
opencenter-airgap build [OPTIONS]
```

**Options**:
- `--clean`: Clean build (ignore checkpoints)
- `--resume/--no-resume`: Resume from checkpoint (default: true)
- `--verbose`: Enable verbose output

**Example**:
```bash
# Initial build
opencenter-airgap build

# Resume after failure
opencenter-airgap build --resume

# Clean build
opencenter-airgap build --clean
```

### serve

Deploy package and start bastion services.

```bash
opencenter-airgap serve PACKAGE [OPTIONS]
```

**Arguments**:
- `PACKAGE`: Zarf package path

**Options**:
- `--verify/--no-verify`: Verify package signature (default: true)

**Example**:
```bash
opencenter-airgap serve dist/zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
```

### validate

Validate configuration files and schemas.

```bash
opencenter-airgap validate [OPTIONS]
```

**Options**:
- `--strict`: Fail on warnings
- `--check-upstream`: Verify URLs are reachable
- `--config-file PATH`: Configuration file path (default: config/versions.env)

**Example**:
```bash
opencenter-airgap validate --strict --check-upstream
```

### verify

Verify package integrity and signatures.

```bash
opencenter-airgap verify PACKAGE [OPTIONS]
```

**Arguments**:
- `PACKAGE`: Package path to verify

**Options**:
- `--manifest PATH`: Artifact manifest path for comparison

**Example**:
```bash
opencenter-airgap verify dist/zarf-package-*.tar.zst \
  --manifest dist/artifact-manifest.json
```

### status

Show current build status and progress.

```bash
opencenter-airgap status
```

**Example**:
```bash
opencenter-airgap status
```

### clean

Clean build artifacts and state.

```bash
opencenter-airgap clean
```

**Example**:
```bash
opencenter-airgap clean
```

### version

Display tool version and dependencies.

```bash
opencenter-airgap version
```

**Example**:
```bash
opencenter-airgap version
```

## Component Manifest

The component manifest (`config/components.yaml`) declares what to collect. It supports version templates, auto-discovery, and explicit additions.

### Schema

```yaml
# Kubernetes core
kubernetes:
  version: "1.34.3"
  binaries:
    - name: kubectl
      url: "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubectl"
    - name: kubelet
      url: "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubelet"

# CLI tools
tools:
  - name: helm
    version: "3.14.0"
    url: "https://get.helm.sh/helm-v{{version}}-linux-amd64.tar.gz"
    extract: true
    binary: linux-amd64/helm

# Git repositories
repositories:
  - name: kubespray
    url: "https://github.com/kubernetes-sigs/kubespray.git"
    ref: "master"

# Container images
images:
  auto_discover:
    - source: repositories.kubespray
      patterns:
        - "roles/*/defaults/main.yml"
        - "inventory/*/group_vars/*.yml"
  additional:
    - "docker.io/grafana/grafana:10.2.0"

# Helm charts
charts:
  - name: cert-manager
    repo: "https://charts.jetstack.io"
    version: "v1.13.0"

# OS packages (collected by kubespray-offline)
os_packages:
  ubuntu_24_04: true

# Python packages (collected by kubespray-offline)
python_packages:
  requirements_file: "requirements.txt"

# Terraform providers (OpenStack only)
terraform_providers:
  - name: openstack
    version: "1.54.1"
    platform: "linux_amd64"
```

### Template Variables

Use `{{variable}}` syntax for version interpolation:

```yaml
tools:
  - name: kubectl
    version: "1.34.3"
    url: "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubectl"
```

Resolves to: `https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl`

### Auto-Discovery

Discover images from repository files:

```yaml
images:
  auto_discover:
    - source: repositories.kubespray
      patterns:
        - "roles/*/defaults/main.yml"
        - "inventory/*/group_vars/*.yml"
```

Scans matching files for image references like:
- `image: quay.io/calico/node:v3.27.0`
- `kube_image_repo: registry.k8s.io`

## Manifest Taxonomy

Three distinct manifests at different lifecycle stages:

### 1. Component Manifest (Input)

**File**: `config/components.yaml`
**Phase**: Pre-build (Zone A)
**Purpose**: Declarative specification of what to collect
**Owner**: Platform engineer (manually edited)

Contains:
- Version templates (`{{version}}`)
- Auto-discovery directives
- No checksums (URLs not yet fetched)
- Human-readable, version-controlled

### 2. Zarf Manifest (Build Instructions)

**File**: `zarf.yaml`
**Phase**: Build (Zone A)
**Purpose**: Zarf package definition - how to collect and bundle
**Owner**: Generated by `opencenter-airgap generate-manifest`

Contains:
- Templates resolved
- Auto-discovery expanded
- Full image list (115+ images)
- Zarf-native format

### 3. Artifact Manifest (Output Inventory)

**Files**: `dist/artifact-manifest.json`, `dist/artifact-manifest.md`
**Phase**: Post-build (Zone A) / Pre-deploy (Zone B/C)
**Purpose**: Cryptographic inventory of what was actually collected
**Owner**: Generated by `opencenter-airgap build`

Contains:
- SHA256 checksums for every artifact
- Actual sizes (bytes collected)
- Resolved Git commit SHAs
- Image digests (immutable content-addressable IDs)
- Collection timestamps

## Build Pipeline

```
Phase 1: Initialization
  ├─ Load config/versions.env
  ├─ Validate configuration
  └─ Initialize state manager

Phase 2: Asset Discovery
  ├─ Scan repositories (concurrent)
  ├─ Discover container images
  └─ Write config/all-images.txt

Phase 3: Asset Collection
  ├─ Execute kubespray-offline (bash)
  ├─ Collect OS packages → build/kubespray-offline/outputs/debs/
  ├─ Collect PyPI mirror → build/kubespray-offline/outputs/pypi/
  └─ Collect K8s binaries → build/kubespray-offline/outputs/files/

Phase 4: Asset Organization
  ├─ Copy to assets/ directory
  ├─ Organize by type (images, files, debs, pypi)
  └─ Generate checksums

Phase 5: Zarf Package Creation
  ├─ Generate zarf.yaml from versions.env
  ├─ Execute zarf package create
  └─ Output to dist/

Phase 6: Manifest Generation
  ├─ Inventory all artifacts
  ├─ Calculate sizes and checksums
  ├─ Export JSON manifest
  └─ Export Markdown summary
```

## Checkpoint/Resume

Build state persists to `build/state.json` after each step. Resume automatically skips completed steps.

**State File**:
```json
{
  "build_id": "20260130-143022",
  "start_time": "2026-01-30T14:30:22Z",
  "config_hash": "a1b2c3d4...",
  "steps": [
    {
      "name": "scan_repositories",
      "status": "completed",
      "start_time": "2026-01-30T14:30:22Z",
      "end_time": "2026-01-30T14:32:15Z"
    },
    {
      "name": "collect_kubespray_offline",
      "status": "failed",
      "start_time": "2026-01-30T14:32:15Z",
      "end_time": "2026-01-30T14:45:30Z",
      "error": "Network timeout downloading kubernetes-cni"
    }
  ]
}
```

**Resume**:
```bash
# Fix network issue, then resume
opencenter-airgap build --resume
```

Skips `scan_repositories`, retries `collect_kubespray_offline`.

## Troubleshooting

### Build fails with "Network timeout"

**Symptom**: Asset collection fails downloading artifacts.

**Cause**: Transient network issues or rate limiting.

**Solution**:
```bash
# Resume build after network recovers
opencenter-airgap build --resume
```

### Build fails with "Disk space"

**Symptom**: Build fails with "No space left on device".

**Cause**: Insufficient disk space (requires 100GB+).

**Solution**:
```bash
# Check available space
df -h

# Clean previous builds
opencenter-airgap clean

# Retry
opencenter-airgap build
```

### Image discovery misses images

**Symptom**: Expected images not in `config/all-images.txt`.

**Cause**: Images not in scanned file patterns.

**Solution**:
```bash
# Add explicit images to component manifest
opencenter-airgap add image docker.io/missing/image:tag

# Or expand discovery patterns in config/components.yaml
```

### Zarf package deploy fails

**Symptom**: `zarf package deploy` fails with signature error.

**Cause**: Package signature verification failed.

**Solution**:
```bash
# Verify package integrity
opencenter-airgap verify dist/zarf-package-*.tar.zst

# Deploy without verification (not recommended)
opencenter-airgap serve dist/zarf-package-*.tar.zst --no-verify
```

### Services not accessible after deploy

**Symptom**: Cannot access registry or nginx after deployment.

**Cause**: Services not started or port conflicts.

**Solution**:
```bash
# Check service status
docker ps

# Check logs
docker logs <container-id>

# Verify ports
netstat -tlnp | grep -E '(80|5000|3000)'

# Restart services
docker restart <container-id>
```

### Build state corrupted

**Symptom**: Resume fails with "Invalid state file".

**Cause**: Corrupted `build/state.json`.

**Solution**:
```bash
# Clean state and rebuild
opencenter-airgap clean
opencenter-airgap build
```

## Migration from Bash Scripts

### Key Differences

| Aspect | Bash Scripts | Python Tool |
|--------|--------------|-------------|
| **Entry Point** | `./scripts/build/create_package.sh` | `opencenter-airgap build` |
| **Configuration** | `config/versions.env` | `config/versions.env` + `config/components.yaml` |
| **Scanning** | Sequential (8.5 min) | Concurrent (2.1 min) |
| **Resume** | Manual checkpoint scripts | Automatic checkpoint/resume |
| **Progress** | Text logs | Rich progress bars |
| **Validation** | Manual verification | Built-in `validate` and `verify` commands |

### Migration Steps

1. **Install Python tool**:
```bash
pip install -e .
# or use binary
curl -LO https://github.com/rackerlabs/opencenter-airgap/releases/latest/download/opencenter-airgap
chmod +x opencenter-airgap
```

2. **Create component manifest**:
```bash
opencenter-airgap init --create-manifest
```

3. **Migrate version pins**:
```bash
# Existing config/versions.env is compatible
# No changes needed
```

4. **Add custom components**:
```bash
# If you added custom tools/images in bash scripts
opencenter-airgap add tool mytool 1.0.0 https://example.com/mytool.tar.gz
opencenter-airgap add image docker.io/myorg/myimage:1.0.0
```

5. **Build with Python tool**:
```bash
opencenter-airgap build
```

6. **Verify output compatibility**:
```bash
# Check artifact paths match
ls -la dist/
ls -la build/kubespray-offline/outputs/
```

### Backward Compatibility

The Python tool maintains compatibility:
- Reads existing `config/versions.env` without modification
- Outputs artifacts to same paths as bash scripts
- Preserves `kubespray-offline` directory structure
- Produces byte-identical Zarf packages

Both systems can run in parallel during migration.

## Development

### Running from Source

```bash
# Clone repository
git clone https://github.com/rackerlabs/opencenter-airgap.git
cd opencenter-airgap

# Install dependencies
pip install -e .

# Run tests
pytest tests/

# Run tool
python -m opencenter_build.cli build
```

### Building Binary

```bash
# Install PyInstaller
pip install pyinstaller

# Build binary
pyinstaller opencenter-airgap.spec

# Test binary
./dist/opencenter-airgap version
```

## License

Apache License 2.0

## Support

- Issues: https://github.com/rackerlabs/opencenter-airgap/issues
- Documentation: https://github.com/rackerlabs/opencenter-airgap/docs
