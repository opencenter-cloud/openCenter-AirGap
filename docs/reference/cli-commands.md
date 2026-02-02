**doc_type: reference**

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

Build a Zarf package from component manifest.

```
opencenter-build build [OPTIONS]
```

**Options**:

`--config PATH`
Path to component manifest YAML. Required.

`--output-dir PATH`
Directory for build artifacts. Default: `dist/`.

`--work-dir PATH`
Directory for intermediate build files. Default: `build/`.

`--resume`
Resume from last checkpoint if previous build failed.

`--clean`
Remove work directory before starting.

`--skip-validation`
Skip component manifest schema validation. Not recommended.

`--skip-sbom`
Skip SBOM generation. Not recommended.

`--skip-signing`
Skip cryptographic signing. Not recommended for production.

`--parallel N`
Number of parallel workers for asset collection. Default: `4`.

**Examples**:

```bash
# Basic build
opencenter-build build --config config/components.yaml

# Clean build with custom output directory
opencenter-build build --config config/components.yaml --clean --output-dir /mnt/artifacts

# Resume failed build
opencenter-build build --config config/components.yaml --resume

# Debug build with verbose logging
opencenter-build --log-level DEBUG build --config config/components.yaml
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

Add a component to the manifest.

```
opencenter-build add [OPTIONS] TYPE NAME
```

**Arguments**:

`TYPE`
Component type. Choices: `image`, `chart`, `binary`, `file`.

`NAME`
Component identifier (image tag, chart name, binary name, file path).

**Options**:

`--manifest PATH`
Path to component manifest. Default: `config/components.yaml`.

`--version VERSION`
Component version. Required for charts and binaries.

`--source URL`
Source URL for charts or files.

`--arch ARCH`
Architecture for binaries. Default: `amd64`.

**Examples**:

```bash
# Add container image
opencenter-build add image docker.io/library/nginx:1.25.0

# Add Helm chart
opencenter-build add chart ingress-nginx --version 4.7.0 --source https://kubernetes.github.io/ingress-nginx

# Add binary
opencenter-build add binary kubectl --version 1.34.3 --arch amd64

# Add file
opencenter-build add file /path/to/config.yaml --source https://example.com/config.yaml
```

### init

Initialize a new project structure.

```
opencenter-build init [OPTIONS] PATH
```

**Arguments**:

`PATH`
Directory to initialize.

**Options**:

`--template NAME`
Template to use. Choices: `minimal`, `standard`, `full`. Default: `standard`.

`--force`
Overwrite existing files.

**Examples**:

```bash
# Initialize new project
opencenter-build init my-airgap-project

# Initialize with minimal template
opencenter-build init my-airgap-project --template minimal
```

**Created Files**:

```
my-airgap-project/
├── config/
│   ├── components.yaml
│   └── versions.env
├── .secrets/
│   └── README.md
├── assets/
└── dist/
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
