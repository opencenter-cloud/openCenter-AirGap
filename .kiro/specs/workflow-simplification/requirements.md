# Requirements: Workflow Simplification

## Overview

Simplify the build workflow to use `versions.env` as the single source of truth, with automatic component manifest generation during build. Remove redundant configuration steps and make the workflow more intuitive.

## Current Problems

1. **Redundant configuration**: Both `versions.env` and `components.yaml` must be maintained
2. **Confusing workflow**: `init --create-manifest` flag is non-obvious
3. **Manual manifest management**: Users must explicitly generate `components.yaml`
4. **No auto-discovery**: Scanning requires manual repo cloning

## Target Workflow

```bash
# 1. Initialize project (creates default versions.env)
opencenter-airgap init

# 2. Edit versions (single source of truth)
vim config/versions.env

# 3. Build (auto-generates components.yaml from versions.env)
opencenter-airgap build

# 4. Optional: Auto-discover images/charts from repos
opencenter-airgap scan --repos
```

## Requirements

### 1. Init Command Simplification

**1.1** `init` command creates default `versions.env` with all required fields
**1.2** `init` command creates directory structure (config/, build/, dist/, assets/)
**1.3** `init` command does NOT create `components.yaml`
**1.4** Remove `--create-manifest` flag from `init` command
**1.5** `init` displays next steps: edit versions.env, run build

### 2. Build Command Auto-Generation

**2.1** `build` command validates `versions.env` exists before proceeding
**2.2** `build` command auto-generates `components.yaml` from `versions.env` if missing
**2.3** `build` command regenerates `components.yaml` if `versions.env` is newer (mtime check)
**2.4** `build` command displays message when regenerating manifest
**2.5** `build` command preserves manual additions to `components.yaml` (merge strategy)
**2.6** Generated `components.yaml` includes header comment explaining it's auto-generated

### 3. Scan Command Enhancement

**3.1** `scan` command accepts `--repos` flag to clone repositories from `versions.env`
**3.2** `scan --repos` clones all repositories defined in `versions.env` to `build/` directory
**3.3** `scan --repos` discovers container images from cloned repositories
**3.4** `scan --repos` discovers Helm charts from cloned repositories
**3.5** `scan --repos` updates `components.yaml` with discovered images (adds to `images.additional`)
**3.6** `scan --repos` updates `components.yaml` with discovered charts (adds to `charts`)
**3.7** `scan --repos` displays summary of discovered artifacts
**3.8** `scan --repos` skips cloning if repository already exists in `build/`
**3.9** `scan` command without `--repos` flag scans existing `build/` directories (current behavior)

### 4. Component Manifest Management

**4.1** `components.yaml` is treated as a generated artifact (like `zarf.yaml`)
**4.2** `components.yaml` can be manually edited for customization
**4.3** Manual edits to `components.yaml` are preserved during regeneration
**4.4** `add` command remains available for manual component additions
**4.5** `components.yaml` includes metadata: generation timestamp, source file

### 5. Versions.env as Source of Truth

**5.1** `versions.env` defines all component versions
**5.2** `versions.env` defines repository URLs and refs
**5.3** `versions.env` defines Helm chart repositories and versions
**5.4** `versions.env` defines tool download URLs (with `{{version}}` templates)
**5.5** `create_default_manifest()` reads `versions.env` and generates complete manifest

### 6. Backward Compatibility

**6.1** Existing `components.yaml` files continue to work
**6.2** If `components.yaml` exists and is newer than `versions.env`, use it as-is
**6.3** Display warning if `components.yaml` exists but `versions.env` is newer
**6.4** Provide `--force-regenerate` flag to override existing `components.yaml`

### 7. Documentation Updates

**7.1** Update README.md with new workflow
**7.2** Update CLI command reference
**7.3** Add migration guide for existing users
**7.4** Update quick start guide

## Success Criteria

1. User can initialize, configure, and build with 3 commands (init, edit, build)
2. `versions.env` is the only file users must edit for version management
3. `components.yaml` is automatically generated and kept in sync
4. `scan --repos` provides one-command auto-discovery
5. All existing tests pass
6. New workflow is documented in README

## Non-Goals

- Changing the structure of `versions.env`
- Changing the structure of `components.yaml`
- Removing the `add` command (kept for manual overrides)
- Automatic version updates from upstream sources
