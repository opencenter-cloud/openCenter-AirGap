# CLI Command Reference

**doc_type: reference**

Complete reference for all `opencenter-airgap` commands.

## Global Options

Available for all commands:

```
--help          Show help message and exit
--version       Show version and exit
```

## init

Initialize project configuration and optionally create component manifest.

### Syntax

```bash
opencenter-airgap init [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--create-manifest` | flag | false | Create config/components.yaml from template |
| `--template` | string | None | Template name: baremetal, openstack |
| `--config-file` | path | config/versions.env | Configuration file path |

### Examples

```bash
# Initialize with default config
opencenter-airgap init

# Create component manifest from baremetal template
opencenter-airgap init --create-manifest --template baremetal

# Initialize with custom config file
opencenter-airgap init --config-file custom.env
```

### Exit Codes

- `0`: Success
- `1`: Configuration file not found
- `2`: Invalid template name

## add

Add component to manifest.

### Syntax

```bash
opencenter-airgap add COMPONENT_TYPE NAME [OPTIONS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `COMPONENT_TYPE` | Yes | Component type: tool, repo, image, chart |
| `NAME` | Yes | Component name |

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--version` | string | None | Component version (required for tools and charts) |
| `--url` | string | None | Download URL (required for tools) |
| `--ref` | string | None | Git ref (required for repos) |
| `--repo` | string | None | Helm repository URL (required for charts) |

### Examples

```bash
# Add CLI tool
opencenter-airgap add tool helm --version 3.14.0 \
  --url https://get.helm.sh/helm-v3.14.0-linux-amd64.tar.gz

# Add Git repository
opencenter-airgap add repo kubespray \
  --url https://github.com/kubernetes-sigs/kubespray.git \
  --ref master

# Add container image
opencenter-airgap add image docker.io/grafana/grafana:10.2.0

# Add Helm chart
opencenter-airgap add chart cert-manager \
  --version v1.13.0 \
  --repo https://charts.jetstack.io
```

### Exit Codes

- `0`: Success
- `1`: Invalid component type
- `2`: Missing required option
- `3`: Component manifest not found

## scan

Scan repositories for container images.

### Syntax

```bash
opencenter-airgap scan [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--repos` | path | None | Repository paths to scan (multiple allowed) |
| `--discover-images` | flag | false | Discover images from component manifest repos |
| `--concurrency` | integer | cpu_count() | Number of worker processes |
| `--verbose` | flag | false | Enable verbose output |

### Examples

```bash
# Scan specific repositories
opencenter-airgap scan --repos /path/to/repo1 --repos /path/to/repo2

# Discover images from component manifest
opencenter-airgap scan --discover-images

# Scan with custom concurrency
opencenter-airgap scan --discover-images --concurrency 8

# Verbose output
opencenter-airgap scan --discover-images --verbose
```

### Output

Writes discovered images to `config/all-images.txt`.

### Exit Codes

- `0`: Success
- `1`: No repositories specified
- `2`: Repository not found
- `3`: Scan failed

## generate-manifest

Generate Zarf manifest from component manifest.

### Syntax

```bash
opencenter-airgap generate-manifest [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--output` | path | zarf.yaml | Output path for Zarf manifest |

### Examples

```bash
# Generate to default location
opencenter-airgap generate-manifest

# Generate to custom location
opencenter-airgap generate-manifest --output custom-zarf.yaml
```

### Process

1. Read `config/components.yaml`
2. Resolve version templates (`{{version}}`)
3. Expand auto-discovery directives
4. Create Zarf components
5. Write `zarf.yaml`

### Exit Codes

- `0`: Success
- `1`: Component manifest not found
- `2`: Invalid component manifest
- `3`: Template resolution failed

## build

Build air-gap package with all artifacts.

### Syntax

```bash
opencenter-airgap build [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--clean` | flag | false | Clean build (ignore checkpoints) |
| `--resume` / `--no-resume` | flag | true | Resume from checkpoint |
| `--verbose` | flag | false | Enable verbose output |

### Examples

```bash
# Initial build
opencenter-airgap build

# Resume after failure
opencenter-airgap build --resume

# Clean build (ignore checkpoints)
opencenter-airgap build --clean

# Verbose output
opencenter-airgap build --verbose
```

### Build Steps

1. `scan_repositories`: Discover container images
2. `collect_kubespray_offline`: Collect OS packages, PyPI mirror, K8s binaries
3. `mirror_terraform_providers`: Mirror Terraform providers (OpenStack only)
4. `organize_assets`: Copy artifacts to staging directory
5. `create_zarf_package`: Generate zarf.yaml and create package
6. `generate_manifest`: Create artifact manifest

### Output

- `dist/zarf-package-*.tar.zst`: Zarf package
- `dist/artifact-manifest.json`: Machine-readable manifest
- `dist/artifact-manifest.md`: Human-readable manifest
- `build/state.json`: Build state for resume

### Exit Codes

- `0`: Success
- `1`: Configuration invalid
- `2`: Build step failed
- `3`: Disk space insufficient

## serve

Deploy package and start bastion services.

### Syntax

```bash
opencenter-airgap serve PACKAGE [OPTIONS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `PACKAGE` | Yes | Zarf package path |

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--verify` / `--no-verify` | flag | true | Verify package signature |

### Examples

```bash
# Deploy with verification
opencenter-airgap serve dist/zarf-package-*.tar.zst

# Deploy without verification (not recommended)
opencenter-airgap serve dist/zarf-package-*.tar.zst --no-verify
```

### Process

1. Verify package signature (if `--verify`)
2. Execute `zarf package deploy`
3. Start registry container (port 5000)
4. Start git server container (port 3000)
5. Start nginx container (port 80)
6. Verify service health (HTTP 200 checks)
7. Display service URLs

### Services

- **Registry**: `http://localhost:5000` - Container image registry
- **Git Server**: `http://localhost:3000` - Git repository server
- **Nginx**: `http://localhost` - File server (binaries, packages)

### Exit Codes

- `0`: Success
- `1`: Package not found
- `2`: Signature verification failed
- `3`: Deployment failed
- `4`: Service startup failed

## validate

Validate configuration files and schemas.

### Syntax

```bash
opencenter-airgap validate [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--strict` | flag | false | Fail on warnings |
| `--check-upstream` | flag | false | Verify URLs are reachable |
| `--config-file` | path | config/versions.env | Configuration file path |

### Examples

```bash
# Basic validation
opencenter-airgap validate

# Strict validation (fail on warnings)
opencenter-airgap validate --strict

# Validate with upstream checks
opencenter-airgap validate --check-upstream

# Validate custom config
opencenter-airgap validate --config-file custom.env
```

### Checks

- Configuration file exists
- Required variables defined
- Component manifest syntax valid
- Required fields present
- Version format valid
- URL format valid
- Repository paths exist (if local)
- Zarf installed and accessible
- URLs reachable (if `--check-upstream`)

### Exit Codes

- `0`: Success (all checks passed)
- `1`: Validation failed
- `2`: Warnings present (with `--strict`)

## verify

Verify package integrity and signatures.

### Syntax

```bash
opencenter-airgap verify PACKAGE [OPTIONS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `PACKAGE` | Yes | Package path to verify |

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--manifest` | path | None | Artifact manifest path for comparison |

### Examples

```bash
# Verify package signature and checksums
opencenter-airgap verify dist/zarf-package-*.tar.zst

# Verify with artifact manifest comparison
opencenter-airgap verify dist/zarf-package-*.tar.zst \
  --manifest dist/artifact-manifest.json
```

### Checks

- Cosign signature validation
- Internal checksum verification
- Artifact manifest comparison (if `--manifest`)

### Exit Codes

- `0`: Success (verification passed)
- `1`: Package not found
- `2`: Signature invalid
- `3`: Checksums invalid
- `4`: Manifest mismatch

## status

Show current build status and progress.

### Syntax

```bash
opencenter-airgap status
```

### Output

Displays:
- Build ID
- Start time
- Step statuses (pending, running, completed, failed)
- Progress percentage
- Error messages (if any)

### Example Output

```
Build Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Build ID: 20260130-143022
Started: 2026-01-30 14:30:22

Step                          Status      Duration
────────────────────────────────────────────────────────────────────────────────
scan_repositories             ✓ completed 1m 53s
collect_kubespray_offline     ✗ failed    13m 15s
mirror_terraform_providers    ○ pending   -
organize_assets               ○ pending   -
create_zarf_package           ○ pending   -
generate_manifest             ○ pending   -

Progress: 16% (1/6 steps completed)

Error: Network timeout downloading kubernetes-cni

Resume with: opencenter-airgap build --resume
```

### Exit Codes

- `0`: Success
- `1`: No build state found

## clean

Clean build artifacts and state.

### Syntax

```bash
opencenter-airgap clean
```

### Process

1. Prompt for confirmation
2. Remove `build/` directory
3. Remove `dist/` directory
4. Remove `build/state.json`

### Example

```bash
opencenter-airgap clean
```

Prompts:
```
Remove build artifacts? [y/N]: y
Removing build/
Removing dist/
Removing build/state.json
Done.
```

### Exit Codes

- `0`: Success
- `1`: User cancelled

## version

Display tool version and dependencies.

### Syntax

```bash
opencenter-airgap version
```

### Output

Displays:
- Tool version
- Python version
- Dependency versions (typer, rich, hypothesis, pyyaml)

### Example Output

```
opencenter-airgap version 1.0.0

Python: 3.10.12
Dependencies:
  typer: 0.9.0
  rich: 13.7.0
  hypothesis: 6.92.1
  pyyaml: 6.0.1
```

### Exit Codes

- `0`: Success
