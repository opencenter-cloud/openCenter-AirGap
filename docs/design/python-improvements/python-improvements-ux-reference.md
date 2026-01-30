# Python Improvements: Comprehensive UX Command Reference

doc_type: reference

Audience: Platform engineers using opencenter-airgap CLI for air-gap package builds.

---

## Command Overview

```
opencenter-airgap - Build tool for openCenter AirGap packages

COMMANDS:
  init        Initialize project configuration
  scan        Scan repositories for container images
  build       Build air-gap package with all dependencies
  package     Create Zarf package from collected assets
  validate    Validate configuration files and schemas
  status      Show current build status and progress
  clean       Clean build artifacts and state
  config      Manage configuration
  version     Show version information
  completion  Generate shell completion scripts

GLOBAL FLAGS:
  --config PATH       Configuration file (default: .opencenter-airgap.yaml)
  --verbose, -v       Verbose output
  --quiet, -q         Suppress non-error output
  --no-color          Disable colored output
  --log-file PATH     Write logs to file
  --help, -h          Show help
```

---

## Command Reference

### init

Initialize project with default configuration.

**Syntax:**
```bash
opencenter-airgap init [OPTIONS]
```

**Options:**
- `--force`: Overwrite existing configuration
- `--template PATH`: Use custom config template
- `--discover-repos`: Auto-discover repositories in assets/

**Examples:**

```bash
# Basic initialization
opencenter-airgap init

# Force overwrite existing config
opencenter-airgap init --force

# Initialize with auto-discovery
opencenter-airgap init --discover-repos
```

**Output:**
```
Initializing openCenter AirGap project...

✓ Created configuration: .opencenter-airgap.yaml
✓ Created directories:
  - build/
  - dist/
  - config/
✓ Discovered 3 repositories:
  - assets/kubespray/kubespray-master
  - assets/opencenter-gitops-base
  - assets/genestack

Next steps:
  1. Review configuration: .opencenter-airgap.yaml
  2. Scan repositories: opencenter-airgap scan
  3. Validate config: opencenter-airgap validate
```

**Transaction:** Creates config file, directories. Idempotent unless `--force`.

---

### scan

Scan Git repositories for container images and URLs.

**Syntax:**
```bash
opencenter-airgap scan [OPTIONS] [REPOS...]
```

**Options:**
- `--repo PATH, -r PATH`: Repository path (repeatable)
- `--output-dir PATH, -o PATH`: Output directory (default: config/)
- `--concurrency N, -j N`: Worker processes (default: CPU count)
- `--include-sources`: Include source file comments in output
- `--format FORMAT`: Output format (txt|json|yaml, default: txt)
- `--filter PATTERN`: Filter images by pattern
- `--exclude PATTERN`: Exclude images by pattern

**Examples:**

```bash
# Scan all configured repos
opencenter-airgap scan

# Scan specific repos
opencenter-airgap scan --repo assets/kubespray --repo assets/genestack

# Scan with 8 workers
opencenter-airgap scan -j 8

# Include source file references
opencenter-airgap scan --include-sources

# Export as JSON
opencenter-airgap scan --format json --output-dir build/

# Filter only k8s.io images
opencenter-airgap scan --filter "registry.k8s.io/*"

# Exclude test images
opencenter-airgap scan --exclude "*:test" --exclude "*:dev"
```

**Output:**
```
Scanning 3 repositories...

[████████████████████] 100% kubespray (245 files, 2.1s)
[████████████████████] 100% opencenter-gitops-base (89 files, 0.8s)
[████████████████████] 100% genestack (156 files, 1.3s)

┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric            ┃ Value ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Repositories      │ 3     │
│ Files Scanned     │ 490   │
│ Images Found      │ 127   │
│ Unique Images     │ 115   │
│ Registries        │ 8     │
│ Duration          │ 4.2s  │
└───────────────────┴───────┘

Output files:
  config/all-images.txt (115 images)
  config/git-repositories.txt (3 repos)

✓ Scan complete
```

**Transaction:** Read repos → extract images → write output files atomically.

---

### build

Build complete air-gap package with all dependencies.

**Syntax:**
```bash
opencenter-airgap build [OPTIONS]
```

**Options:**
- `--clean`: Clean build directory before starting
- `--resume / --no-resume`: Resume from checkpoint (default: true)
- `--skip-scan`: Skip repository scanning phase
- `--skip-step STEP`: Skip specific build step
- `--parallel / --sequential`: Parallel execution (default: true)
- `--output-dir PATH`: Build output directory (default: build/)
- `--dry-run`: Show what would be done without executing
- `--metrics-file PATH`: Export metrics to file

**Examples:**
```bash
# Standard build
opencenter-airgap build

# Clean build from scratch
opencenter-airgap build --clean

# Resume after failure
opencenter-airgap build --resume

# Skip scanning (use existing image lists)
opencenter-airgap build --skip-scan

# Skip specific step
opencenter-airgap build --skip-step mirror_terraform_providers

# Dry run to preview
opencenter-airgap build --dry-run

# Build with metrics export
opencenter-airgap build --metrics-file build/metrics.json
```

**Output:**
```
Starting build...

[1/5] scan_repositories
  Scanning 3 repositories...
  [████████████████████] 100% (2.1s)
  Found 115 unique images
✓ scan_repositories completed (2.1s)

[2/5] collect_kubespray_offline
  Downloading Kubernetes binaries...
  [████████░░░░░░░░░░░░] 45% (12.3 GB / 27.5 GB)
  ETA: 8m 23s

  Downloading container images...
  [██████░░░░░░░░░░░░░░] 30% (45 / 150 images)
  ETA: 15m 12s

  Downloading apt packages...
  [████████████████████] 100% (2,341 packages)

  Downloading Python wheels...
  [████████████████████] 100% (487 wheels)

✓ collect_kubespray_offline completed (23m 45s)

[3/5] mirror_terraform_providers
  Mirroring providers...
  [████████████████████] 100% (5 providers)
✓ mirror_terraform_providers completed (1m 12s)

[4/5] organize_assets
  Organizing files...
  [████████████████████] 100% (3,245 files)
✓ organize_assets completed (45s)

[5/5] create_zarf_package
  Creating Zarf package...
  [████████████████████] 100%
  Generating SBOM...
  Signing package...
✓ create_zarf_package completed (8m 34s)

┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Build Summary     ┃           ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ Status            │ Success   │
│ Duration          │ 36m 17s   │
│ Package Size      │ 18.4 GB   │
│ Images            │ 115       │
│ Apt Packages      │ 2,341     │
│ Python Wheels     │ 487       │
└───────────────────┴───────────┘

Package: dist/zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
SBOM: dist/zarf-package-opencenter-airgap-amd64-1.0.0-sbom.json
Checksum: dist/zarf-package-opencenter-airgap-amd64-1.0.0.sha256

✓ Build complete
```

**Transaction:** Multi-phase with checkpoints. Each phase commits on success, rolls back on failure.

---

### package

Create Zarf package from collected assets (standalone packaging step).

**Syntax:**
```bash
opencenter-airgap package [OPTIONS]
```

**Options:**
- `--template PATH`: Zarf template file (default: zarf.yaml.template)
- `--output-dir PATH`: Package output directory (default: dist/)
- `--sign`: Sign package with Cosign
- `--key PATH`: Cosign private key path
- `--sbom`: Generate SBOM (default: true)
- `--compress LEVEL`: Compression level (1-22, default: 3)

**Examples:**

```bash
# Create package with defaults
opencenter-airgap package

# Create and sign package
opencenter-airgap package --sign --key cosign.key

# Custom template and output
opencenter-airgap package --template custom-zarf.yaml --output-dir /mnt/packages

# Maximum compression
opencenter-airgap package --compress 22
```

**Output:**
```
Creating Zarf package...

Validating assets...
  ✓ Files: 3,245 files (27.5 GB)
  ✓ Images: 115 images (12.8 GB)
  ✓ Packages: 2,341 debs (8.2 GB)
  ✓ Wheels: 487 wheels (1.1 GB)

Generating package...
  [████████████████████] 100% (8m 34s)

Generating SBOM...
  ✓ 3,245 components cataloged

Signing package...
  ✓ Signature created

Package created:
  File: dist/zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
  Size: 18.4 GB
  Checksum: sha256:a3f2b8c9d1e4f5a6b7c8d9e0f1a2b3c4...
  Signature: dist/zarf-package-opencenter-airgap-amd64-1.0.0.sig

✓ Package complete
```

**Transaction:** Read assets → create package → sign → write atomically.

---

### validate

Validate configuration files and schemas.

**Syntax:**
```bash
opencenter-airgap validate [OPTIONS]
```

**Options:**
- `--config-dir PATH`: Configuration directory (default: config/)
- `--schema-dir PATH`: Schema directory (default: config/schemas/)
- `--strict`: Fail on warnings
- `--check CHECK`: Run specific check only
- `--format FORMAT`: Output format (text|json, default: text)

**Available checks:**
- `versions_env`: Validate versions.env syntax
- `schemas`: Validate JSON schemas
- `image_manifest`: Validate image list
- `version_consistency`: Check version consistency
- `file_references`: Validate file references

**Examples:**

```bash
# Validate all configs
opencenter-airgap validate

# Strict validation (fail on warnings)
opencenter-airgap validate --strict

# Validate specific check
opencenter-airgap validate --check versions_env

# Export validation report as JSON
opencenter-airgap validate --format json > validation-report.json
```

**Output (success):**
```
Validating configuration...

✓ versions.env syntax
  - 24 version variables
  - All formats valid

✓ JSON schemas
  - nodes.schema.json: valid
  - openstack-config.schema.json: valid
  - zarf-variables.schema.json: valid

✓ Image manifest
  - 115 images
  - All references valid
  - No duplicates

✓ Version consistency
  - Kubernetes: v1.34.3 (consistent)
  - Containerd: 1.7.13 (consistent)
  - All versions aligned

✓ File references
  - All paths exist
  - No broken symlinks

All checks passed (5/5)
```

**Output (failure):**
```
Validating configuration...

✓ versions.env syntax

✗ JSON schemas
  config/nodes.yaml:
    Line 12: Missing required field 'control_plane'
    Expected: array of node objects
    See: config/schemas/nodes.schema.json

  config/openstack-config.yaml:
    Line 8: Invalid value for 'flavor': 'invalid-flavor'
    Must be one of: m1.small, m1.medium, m1.large

✗ Image manifest
  config/all-images.txt:
    Line 45: Invalid image reference 'nginx:latest'
    Use pinned tags only (e.g., 'nginx:1.29.2')

    Line 67: Invalid registry format 'bad..registry.io/image:tag'
    Registry must be valid DNS name

✓ Version consistency
✓ File references

Validation failed (2/5 checks failed)

Fix errors and run: opencenter-airgap validate
```

**Transaction:** Read-only validation, no state changes.

---

### status

Show current build status and progress.

**Syntax:**
```bash
opencenter-airgap status [OPTIONS]
```

**Options:**
- `--state-file PATH`: State file path (default: build/.build-state.json)
- `--format FORMAT`: Output format (text|json, default: text)
- `--watch, -w`: Watch mode (refresh every 2s)
- `--show-artifacts`: Show artifact paths

**Examples:**

```bash
# Show current status
opencenter-airgap status

# Watch mode (live updates)
opencenter-airgap status --watch

# Show with artifact paths
opencenter-airgap status --show-artifacts

# Export as JSON
opencenter-airgap status --format json
```

**Output (in progress):**
```
Build Status

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
┃ Step                       ┃ Status    ┃ Duration ┃ Progress ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
│ scan_repositories          │ completed │ 2.1s     │ 100%     │
│ collect_kubespray_offline  │ running   │ 12m 34s  │ 45%      │
│ mirror_terraform_providers │ pending   │ -        │ -        │
│ organize_assets            │ pending   │ -        │ -        │
│ create_zarf_package        │ pending   │ -        │ -        │
└────────────────────────────┴───────────┴──────────┴──────────┘

Current: Downloading container images (45/115)
ETA: 15m 23s

Last checkpoint: 2026-01-28 14:23:45
State file: build/.build-state.json
```

**Output (completed):**
```
Build Status

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Step                       ┃ Status    ┃ Duration ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━┩
│ scan_repositories          │ completed │ 2.1s     │
│ collect_kubespray_offline  │ completed │ 23m 45s  │
│ mirror_terraform_providers │ completed │ 1m 12s   │
│ organize_assets            │ completed │ 45s      │
│ create_zarf_package        │ completed │ 8m 34s   │
└────────────────────────────┴───────────┴──────────┘

Build completed: 2026-01-28 14:45:12
Total duration: 36m 17s
Package: dist/zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
```

**Output (failed):**
```
Build Status

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Step                       ┃ Status    ┃ Duration ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━┩
│ scan_repositories          │ completed │ 2.1s     │
│ collect_kubespray_offline  │ failed    │ 12m 34s  │
│ mirror_terraform_providers │ pending   │ -        │
│ organize_assets            │ pending   │ -        │
│ create_zarf_package        │ pending   │ -        │
└────────────────────────────┴───────────┴──────────┘

Error: collect_kubespray_offline failed
  Command 'download-all.sh' returned non-zero exit status 1

  Failed to download: registry.k8s.io/kube-apiserver:v1.34.3
  Network timeout after 3 retries

Recovery:
  1. Check network connectivity
  2. Resume: opencenter-airgap build --resume
  3. Skip step: opencenter-airgap build --skip-step collect_kubespray_offline

Logs: build/build.log
State: build/.build-state.json
```

**Transaction:** Read-only, displays current state.

---

### clean

Clean build artifacts and state.

**Syntax:**
```bash
opencenter-airgap clean [OPTIONS]
```

**Options:**
- `--all`: Clean everything (build/, dist/, state)
- `--build`: Clean build directory only
- `--dist`: Clean dist directory only
- `--state`: Clean state file only
- `--cache`: Clean download cache
- `--dry-run`: Show what would be deleted
- `--force`: Skip confirmation prompt

**Examples:**

```bash
# Clean build directory (with confirmation)
opencenter-airgap clean --build

# Clean everything
opencenter-airgap clean --all

# Dry run to preview
opencenter-airgap clean --all --dry-run

# Force clean without confirmation
opencenter-airgap clean --all --force

# Clean only state file
opencenter-airgap clean --state
```

**Output:**
```
Cleaning build artifacts...

The following will be deleted:
  build/ (27.5 GB)
  build/.build-state.json (12 KB)
  build/.build-state.backup (12 KB)

Continue? [y/N]: y

Deleting build/...
  ✓ Deleted 3,245 files (27.5 GB)
  ✓ Deleted state files

✓ Clean complete
```

**Transaction:** Deletes files/directories. Prompts for confirmation unless `--force`.

---

### config

Manage configuration.

**Syntax:**
```bash
opencenter-airgap config SUBCOMMAND [OPTIONS]
```

**Subcommands:**
- `show`: Display current configuration
- `get KEY`: Get configuration value
- `set KEY VALUE`: Set configuration value
- `edit`: Open config in editor
- `validate`: Validate config syntax

**Examples:**
```bash
# Show full config
opencenter-airgap config show

# Get specific value
opencenter-airgap config get build.concurrency

# Set value
opencenter-airgap config set build.concurrency 8

# Edit in $EDITOR
opencenter-airgap config edit

# Validate config syntax
opencenter-airgap config validate
```

**Output:**
```
# opencenter-airgap config show
version: "1.0"
project_root: "."

repositories:
  - name: kubespray
    path: assets/kubespray/kubespray-master
    enabled: true
  - name: opencenter-gitops-base
    path: assets/opencenter-gitops-base
    enabled: true

build:
  output_dir: build/
  concurrency: 4
  clean: false

terraform:
  enabled: true
  mirror_path: assets/terraform-mirror

zarf:
  template: zarf.yaml.template
  output: zarf.yaml
```

**Transaction:** `show`/`get` are read-only. `set` writes config atomically.

---

### version

Show version information.

**Syntax:**
```bash
opencenter-airgap version [OPTIONS]
```

**Options:**
- `--short`: Show version number only
- `--json`: Output as JSON

**Examples:**

```bash
# Full version info
opencenter-airgap version

# Version number only
opencenter-airgap version --short

# JSON output
opencenter-airgap version --json
```

**Output:**
```
opencenter-airgap version 1.0.0

Build: 2026-01-28T14:23:45Z
Commit: a3f2b8c
Python: 3.10.12
Platform: Linux-6.5.0-x86_64

Dependencies:
  typer: 0.9.0
  rich: 13.7.0
  pyyaml: 6.0.1
  jsonschema: 4.20.0
```

---

### completion

Generate shell completion scripts.

**Syntax:**
```bash
opencenter-airgap completion SHELL
```

**Shells:**
- `bash`
- `zsh`
- `fish`

**Examples:**
```bash
# Bash completion
opencenter-airgap completion bash > /etc/bash_completion.d/opencenter-airgap

# Zsh completion
opencenter-airgap completion zsh > ~/.zsh/completion/_opencenter-airgap

# Fish completion
opencenter-airgap completion fish > ~/.config/fish/completions/opencenter-airgap.fish
```

---

## Workflow Scenarios

### Scenario 1: First-Time Build

```bash
# 1. Clone repository
git clone https://github.com/rackerlabs/openCenter-AirGap.git
cd openCenter-AirGap

# 2. Initialize project
opencenter-airgap init --discover-repos

# 3. Review and edit configuration
opencenter-airgap config show
opencenter-airgap config edit  # Adjust settings if needed

# 4. Validate configuration
opencenter-airgap validate --strict

# 5. Scan repositories
opencenter-airgap scan --verbose

# 6. Review scanned images
cat config/all-images.txt
# Edit if needed to add/remove images

# 7. Build package
opencenter-airgap build --clean

# 8. Verify package
ls -lh dist/
zarf package inspect dist/zarf-package-*.tar.zst --sbom
```

**Timeline:** ~45 minutes (depending on network speed)

---

### Scenario 2: Incremental Update

```bash
# 1. Update version pins
vim config/versions.env
# Change KUBERNETES_VERSION=v1.34.3 to v1.34.4

# 2. Validate changes
opencenter-airgap validate

# 3. Rescan repositories (if repos changed)
opencenter-airgap scan

# 4. Build with existing assets (resume)
opencenter-airgap build --resume

# 5. Compare packages
diff <(zarf package inspect dist/old-package.tar.zst --sbom) \
     <(zarf package inspect dist/new-package.tar.zst --sbom)
```

**Timeline:** ~20 minutes (reuses cached assets)

---

### Scenario 3: Recovery from Failure

```bash
# Build fails at step 2
opencenter-airgap build
# ✗ collect_kubespray_offline failed: Network timeout

# 1. Check status
opencenter-airgap status
# Shows: step 1 completed, step 2 failed

# 2. Investigate logs
tail -f build/build.log

# 3. Fix issue (e.g., network connectivity)
ping registry.k8s.io

# 4. Resume from checkpoint
opencenter-airgap build --resume
# Skips step 1, retries step 2

# Alternative: Skip problematic step
opencenter-airgap build --skip-step collect_kubespray_offline
```

**Timeline:** Immediate resume, no wasted work

---

### Scenario 4: Custom Repository Scanning

```bash
# 1. Scan only specific repos
opencenter-airgap scan \
  --repo assets/custom-app \
  --repo assets/custom-services \
  --output-dir custom-config/

# 2. Filter images by registry
opencenter-airgap scan \
  --filter "ghcr.io/*" \
  --filter "quay.io/*"

# 3. Exclude development images
opencenter-airgap scan \
  --exclude "*:dev" \
  --exclude "*:test" \
  --exclude "*:latest"

# 4. Export with source references
opencenter-airgap scan \
  --include-sources \
  --format json \
  --output-dir audit/

# 5. Review JSON output
jq '.images[] | select(.registry == "ghcr.io")' audit/all-images.json
```

---

### Scenario 5: CI/CD Integration

```bash
#!/bin/bash
# .github/workflows/build-airgap-package.sh

set -euo pipefail

# 1. Validate before build
opencenter-airgap validate --strict || {
  echo "Validation failed"
  exit 1
}

# 2. Build with metrics
opencenter-airgap build \
  --clean \
  --metrics-file build/metrics.json \
  --log-file build/build.log

# 3. Export metrics for monitoring
opencenter-airgap status --format json > build/status.json

# 4. Upload artifacts
aws s3 cp dist/zarf-package-*.tar.zst s3://packages/
aws s3 cp build/metrics.json s3://metrics/

# 5. Notify on completion
curl -X POST https://slack.com/webhook \
  -d "Build complete: $(opencenter-airgap version --short)"
```

---

### Scenario 6: Debugging Build Issues

```bash
# 1. Enable verbose logging
opencenter-airgap build --verbose --log-file debug.log

# 2. Watch status in another terminal
watch -n 2 opencenter-airgap status

# 3. Monitor resource usage
htop  # CPU/memory
df -h  # Disk space
iotop  # I/O

# 4. Inspect state file
jq . build/.build-state.json

# 5. Check specific step artifacts
ls -lh build/kubespray-offline/outputs/

# 6. Validate intermediate outputs
opencenter-airgap validate --config-dir build/

# 7. Test individual steps
opencenter-airgap build --skip-step scan_repositories
```

---

### Scenario 7: Multi-Environment Builds

```bash
# Production environment
opencenter-airgap build \
  --config prod.opencenter-airgap.yaml \
  --output-dir build/prod/

# Staging environment
opencenter-airgap build \
  --config staging.opencenter-airgap.yaml \
  --output-dir build/staging/

# Development environment (minimal)
opencenter-airgap build \
  --config dev.opencenter-airgap.yaml \
  --skip-step mirror_terraform_providers \
  --output-dir build/dev/
```

---

## Environment Variables

```bash
# Configuration
OPENCENTER_CONFIG=.opencenter-airgap.yaml
OPENCENTER_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
OPENCENTER_NO_COLOR=1      # Disable colored output

# Build settings
OPENCENTER_BUILD_DIR=build/
OPENCENTER_DIST_DIR=dist/
OPENCENTER_CONCURRENCY=4

# Network settings
HTTP_PROXY=http://proxy:8080
HTTPS_PROXY=http://proxy:8080
NO_PROXY=localhost,127.0.0.1

# Zarf settings
ZARF_CACHE_DIR=~/.zarf-cache
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 3 | Validation error |
| 4 | Build error |
| 5 | Network error |
| 6 | Disk space error |
| 7 | Permission error |
| 130 | Interrupted (Ctrl+C) |

---

## Tips & Best Practices

### Performance

```bash
# Use all CPU cores
opencenter-airgap scan -j $(nproc)

# Build on fast disk (SSD)
opencenter-airgap build --output-dir /mnt/nvme/build

# Enable parallel execution
opencenter-airgap build --parallel
```

### Reliability

```bash
# Always validate before build
opencenter-airgap validate --strict && opencenter-airgap build

# Use resume for long builds
opencenter-airgap build --resume

# Export metrics for monitoring
opencenter-airgap build --metrics-file metrics.json
```

### Debugging

```bash
# Verbose output
opencenter-airgap --verbose build

# Separate log file
opencenter-airgap --log-file debug.log build

# Dry run to preview
opencenter-airgap build --dry-run

# Watch status
watch -n 2 opencenter-airgap status
```

### Automation

```bash
# Non-interactive mode
opencenter-airgap build --force --no-color

# JSON output for parsing
opencenter-airgap status --format json | jq .

# Exit on any error
set -euo pipefail
opencenter-airgap validate --strict
opencenter-airgap build
```

---

## Troubleshooting

### "Insufficient disk space"

```bash
# Check available space
df -h

# Clean old builds
opencenter-airgap clean --all

# Use different output directory
opencenter-airgap build --output-dir /mnt/large-disk/build
```

### "Network timeout"

```bash
# Check connectivity
ping registry.k8s.io

# Configure proxy
export HTTP_PROXY=http://proxy:8080
opencenter-airgap build --resume

# Increase timeout (in config)
opencenter-airgap config set network.timeout 600
```

### "Validation failed"

```bash
# Show detailed errors
opencenter-airgap validate --verbose

# Fix specific check
opencenter-airgap validate --check versions_env

# Skip validation (not recommended)
opencenter-airgap build --skip-validation
```

### "State file corrupted"

```bash
# Recover from backup
opencenter-airgap clean --state
cp build/.build-state.backup build/.build-state.json

# Start fresh
opencenter-airgap clean --state
opencenter-airgap build --no-resume
```
