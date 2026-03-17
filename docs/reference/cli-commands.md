---
id: cli-commands
title: "CLI Commands"
sidebar_label: CLI Commands
description: Complete reference for the opencenter-build command-line interface with all commands, options, and examples.
doc_type: reference
audience: "platform engineers"
tags: [cli, commands, reference, opencenter-build]
---

# CLI Commands

Complete reference for the `opencenter-build` command-line interface.

## Synopsis

```
opencenter-build [GLOBAL_OPTIONS] COMMAND [COMMAND_OPTIONS]
```

## Global Options

`--version`
Show version and exit.

`--help`
Show help message and exit.

`--log-level LEVEL`
Set logging verbosity. Choices: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Default: `INFO`.

`--log-file PATH`
Write logs to file in addition to stdout. Default: `build.log`.

`--no-color`
Disable colored output.

## Commands

### build

Build a Zarf package from component manifest. Auto-generates `components.yaml` from `versions.env` if missing or outdated.

```
opencenter-build build [OPTIONS]
```

**Options**:

`--config PATH`
Path to versions.env configuration file. Default: `config/versions.env`.

`--output-dir PATH`
Directory for build artifacts. Default: `dist/`.

`--work-dir PATH`
Directory for intermediate build files. Default: `build/`.

`--resume`
Resume from last checkpoint if previous build failed.

`--clean`
Remove work directory before starting.

`--force-regenerate`
Force regeneration of `components.yaml` from `versions.env`, discarding any manual edits. Use with caution.

`--skip-validation`
Skip component manifest schema validation. Not recommended.

`--skip-sbom`
Skip SBOM generation. Not recommended.

`--skip-signing`
Skip cryptographic signing. Not recommended for production.

`--parallel N`
Number of parallel workers for asset collection. Default: `4`.

**Behavior**:

The `build` command automatically manages `components.yaml`:
- If `components.yaml` doesn't exist, generates it from `versions.env`
- If `versions.env` is newer than `components.yaml`, regenerates while preserving manual additions
- If `--force-regenerate` is used, creates clean manifest (loses manual edits)

**Examples**:

```bash
# Basic build (auto-generates components.yaml)
opencenter-build build

# Build with custom config location
opencenter-build build --config config/versions.env

# Force clean regeneration of components.yaml
opencenter-build build --force-regenerate

# Clean build with custom output directory
opencenter-build build --clean --output-dir /mnt/artifacts

# Resume failed build
opencenter-build build --resume

# Debug build with verbose logging
opencenter-build --log-level DEBUG build
```

**Exit Codes**:
- `0`: Success
- `1`: Configuration error
- `2`: Validation error
- `3`: Build error
- `4`: Network error

### verify

Verify package integrity and SBOM.

```
opencenter-build verify [OPTIONS] PACKAGE
```

**Arguments**:

`PACKAGE`
Path to Zarf package file (`.tar.zst`).

**Options**:

`--sbom`
Display SBOM summary.

`--signature`
Verify cryptographic signature. Requires public key in `~/.opencenter/cosign.pub`.

`--checksum`
Verify SHA256 checksum against `.sha256` file.

`--all`
Run all verification checks (sbom + signature + checksum).

**Examples**:

```bash
# Verify checksum
opencenter-build verify dist/zarf-package-*.tar.zst --checksum

# Verify signature
opencenter-build verify dist/zarf-package-*.tar.zst --signature

# Full verification
opencenter-build verify dist/zarf-package-*.tar.zst --all
```

**Exit Codes**:
- `0`: Verification passed
- `1`: File not found
- `2`: Checksum mismatch
- `3`: Signature verification failed
- `4`: SBOM validation failed

### status

Show build status and progress.

```
opencenter-build status [OPTIONS]
```

**Options**:

`--work-dir PATH`
Path to work directory. Default: `build/`.

`--json`
Output in JSON format.

**Examples**:

```bash
# Show current build status
opencenter-build status

# Get status as JSON
opencenter-build status --json
```

**Output**:

```
Build Status: IN_PROGRESS
Phase: ASSET_COLLECTION
Progress: 45/120 components
Elapsed: 15m 32s
Estimated Remaining: 18m 10s

Completed:
  ✓ Validation
  ✓ Kubespray Clone
  ✓ Image Collection (45/120)

In Progress:
  ⋯ Package Collection (12/80)

Pending:
  ○ Python Wheels
  ○ Kubernetes Binaries
  ○ Zarf Packaging
```

### add

Add a component to the manifest. Use this to customize the auto-generated `components.yaml` with additional images, charts, or tools.

```
opencenter-build add [OPTIONS] TYPE NAME
```

**Arguments**:

`TYPE`
Component type. Choices: `image`, `chart`, `binary`, `file`, `tool`, `repo`.

`NAME`
Component identifier (image tag, chart name, binary name, file path).

**Options**:

`--manifest PATH`
Path to component manifest. Default: `config/components.yaml`.

`--version VERSION`
Component version. Required for charts, binaries, and tools.

`--source URL` or `--url URL`
Source URL for charts, files, or tool downloads.

`--arch ARCH`
Architecture for binaries. Default: `amd64`.

**Examples**:

```bash
# Add container image
opencenter-build add image docker.io/library/nginx:1.25.0

# Add Helm chart
opencenter-build add chart ingress-nginx --version 4.7.0 --source https://kubernetes.github.io/ingress-nginx

# Add tool
opencenter-build add tool --name kubectl --version v1.34.3 --url https://dl.k8s.io/release/v1.34.3/bin/linux/amd64/kubectl

# Add repository
opencenter-build add repo https://github.com/kubernetes-sigs/kubespray.git

# Add file
opencenter-build add file /path/to/config.yaml --source https://example.com/config.yaml
```

**Note**: Manual additions are preserved when `build` regenerates `components.yaml` from `versions.env`.

### init

Initialize a new project structure with default `versions.env`.

```
opencenter-build init [OPTIONS] [PATH]
```

**Arguments**:

`PATH`
Directory to initialize. Default: current directory.

**Options**:

`--template NAME`
Template to use. Choices: `baremetal`, `openstack`. Default: `baremetal`.

`--force`
Overwrite existing files.

**Behavior**:

Creates project structure with default `versions.env`. Does NOT create `components.yaml` - this is auto-generated by the `build` command.

**Examples**:

```bash
# Initialize in current directory
opencenter-build init

# Initialize new project directory
opencenter-build init my-airgap-project

# Initialize with OpenStack template
opencenter-build init --template openstack
```

**Created Files**:

```
my-airgap-project/
├── config/
│   └── versions.env          # Single source of truth for versions
├── .secrets/
│   └── README.md
├── assets/                    # Empty, populated during build
├── build/                     # Empty, populated during build
└── dist/                      # Empty, populated during build
```

**Next Steps**:

After initialization:
1. Edit `config/versions.env` to set component versions
2. Run `opencenter-build build` to generate `components.yaml` and build package
3. Optionally run `opencenter-build scan --repos` to discover additional components

### scan

Scan repositories for container images and Helm charts. Auto-discovers components and updates `components.yaml`.

```
opencenter-build scan [OPTIONS]
```

**Options**:

`--repos`
Clone repositories from `versions.env` before scanning. Clones to `build/` directory and discovers images and charts.

`--repo PATH`
Scan specific repository directory. Can be specified multiple times.

`--discover-images`
Discover container images. Default: enabled.

`--discover-charts`
Discover Helm charts. Default: enabled.

`--update-manifest`
Update `components.yaml` with discoveries. Default: enabled.

`--manifest PATH`
Path to component manifest. Default: `config/components.yaml`.

**Behavior**:

- With `--repos`: Clones repositories defined in `versions.env` (kubespray, opencenter-gitops-base) to `build/`, then scans for images and charts
- With `--repo`: Scans specified directories only
- Without flags: Scans existing `build/` directories
- Discovered images added to `images.additional`
- Discovered charts added to `charts` section
- Skips duplicates automatically

**Examples**:

```bash
# Clone repos from versions.env and scan
opencenter-build scan --repos

# Scan specific directory
opencenter-build scan --repo build/kubespray

# Scan multiple directories
opencenter-build scan --repo build/kubespray --repo build/opencenter-gitops-base

# Scan without updating manifest (dry run)
opencenter-build scan --repos --no-update-manifest
```

**Output**:

```
Cloning repositories...
  ✓ kubespray (https://github.com/kubernetes-sigs/kubespray.git)
  ✓ opencenter-gitops-base (https://github.com/opencenter-cloud/openCenter-gitops-base.git)

Scanning for images...
  Found 247 images

Scanning for charts...
  Found 12 charts

Updating components.yaml...
  Added 15 new images
  Added 3 new charts
  Skipped 232 duplicates
```

## Environment Variables

`OPENCENTER_CONFIG`
Default path to component manifest. Overridden by `--config`.

`OPENCENTER_WORK_DIR`
Default work directory. Overridden by `--work-dir`.

`OPENCENTER_LOG_LEVEL`
Default log level. Overridden by `--log-level`.

`OPENCENTER_NO_COLOR`
Disable colored output if set to `1`, `true`, or `yes`.

`COSIGN_KEY`
Path to Cosign private key for signing. Default: `~/.opencenter/cosign.key`.

`COSIGN_PASSWORD`
Password for Cosign private key. If not set, prompts interactively.

## Configuration Files

`~/.opencenter/config.yaml`
User-level configuration. Overrides defaults.

Example:

```yaml
log_level: INFO
work_dir: /tmp/opencenter-build
output_dir: /mnt/artifacts
parallel_workers: 8
```

`.opencenter/config.yaml`
Project-level configuration. Overrides user-level config.

## Exit Codes

All commands use consistent exit codes:

- `0`: Success
- `1`: General error
- `2`: Configuration or validation error
- `3`: Build or operation error
- `4`: Network error
- `130`: Interrupted by user (Ctrl+C)

## Logging

Logs are written to:
- `stdout` (colored, human-readable)
- `build.log` (plain text, machine-readable)

Log format:

```
2026-02-01 14:32:15 INFO [build] Starting asset collection
2026-02-01 14:32:16 DEBUG [kubespray] Cloning repository: https://github.com/kubespray-offline/kubespray-offline.git
2026-02-01 14:32:45 INFO [images] Collected 45/120 images
2026-02-01 14:33:10 ERROR [network] Failed to download image: connection timeout
```

## Shell Completion

Generate shell completion scripts:

```bash
# Bash
opencenter-build --completion bash > /etc/bash_completion.d/opencenter-build

# Zsh
opencenter-build --completion zsh > ~/.zsh/completion/_opencenter-build

# Fish
opencenter-build --completion fish > ~/.config/fish/completions/opencenter-build.fish
```

## See Also

- [Component Manifest Schema](component-manifest-schema.md)
- [Build Steps Reference](build-steps.md)
- [Troubleshooting](troubleshooting.md)
