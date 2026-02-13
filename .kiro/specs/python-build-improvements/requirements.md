# Requirements Document: Python Build Improvements

## Introduction

This specification defines requirements for improving the openCenter AirGap build system through Python enhancements and Zarf integration. The improvements target performance, user experience, reliability, and maintainability while reducing bash script complexity by 60%.

## Glossary

- **Build_System**: Python orchestrator that collects artifacts and creates Zarf packages
- **Zarf**: Packaging framework for air-gap artifact bundling and deployment
- **kubespray-offline**: Bash-based tool for collecting Kubernetes offline assets (OS packages, PyPI mirror, binaries)
- **Bastion**: Air-gapped deployment host that serves artifacts to downstream consumers
- **Artifact_Manifest**: Complete inventory of collected artifacts with checksums and metadata
- **Checkpoint**: Persistent build state snapshot enabling resume after failure
- **Zone_A**: Connected build environment with internet access
- **Zone_C**: Disconnected deployment environment (air-gapped)
- **Repository_Scanner**: Component that discovers container images in Git repositories
- **State_Manager**: Component that persists and restores build progress

## Requirements

### Requirement 1: Concurrent Repository Scanning

**User Story:** As a platform engineer, I want repository scanning to complete in under 3 minutes, so that I can iterate quickly during development.

#### Acceptance Criteria

1. WHEN scanning 4 repositories, THE Repository_Scanner SHALL complete within 3 minutes
2. THE Repository_Scanner SHALL utilize multiple CPU cores via ProcessPoolExecutor
3. WHEN max_workers is not specified, THE Repository_Scanner SHALL default to cpu_count()
4. WHEN scanning completes, THE Repository_Scanner SHALL return all discovered container images
5. THE Repository_Scanner SHALL compile regex patterns once and cache them

### Requirement 2: Optimized File Processing

**User Story:** As a platform engineer, I want efficient file reading, so that large YAML/JSON files don't consume excessive memory.

#### Acceptance Criteria

1. WHEN reading files larger than 1MB, THE Build_System SHALL use memory-mapped I/O
2. WHEN reading files smaller than 1MB, THE Build_System SHALL use standard file I/O
3. THE Build_System SHALL handle encoding errors gracefully without crashing
4. WHEN processing 1000 YAML files, THE Build_System SHALL complete within 15 seconds

### Requirement 3: Modern CLI Interface

**User Story:** As a platform engineer, I want a professional CLI with progress indicators, so that I can monitor build progress.

#### Acceptance Criteria

1. THE Build_System SHALL provide a CLI using the Typer framework
2. WHEN executing long-running operations, THE Build_System SHALL display progress bars
3. WHEN operations complete successfully, THE Build_System SHALL display success indicators with green checkmarks
4. WHEN operations fail, THE Build_System SHALL display error messages with red indicators
5. THE Build_System SHALL support verbose output mode via --verbose flag
6. THE Build_System SHALL provide these commands: init, scan, build, serve, validate, status, clean, version

### Requirement 4: Build State Persistence

**User Story:** As a platform engineer, I want to resume builds after failures, so that I don't waste time re-downloading artifacts.

#### Acceptance Criteria

1. WHEN a build step completes, THE State_Manager SHALL persist a checkpoint to disk
2. WHEN a build fails, THE State_Manager SHALL record the failure reason and timestamp
3. WHEN resuming a build, THE Build_System SHALL skip completed steps
4. WHEN resuming a build, THE Build_System SHALL start from the first failed or pending step
5. THE State_Manager SHALL store checkpoints in JSON format
6. WHEN the --resume flag is provided, THE Build_System SHALL read existing state
7. WHEN the --clean flag is provided, THE Build_System SHALL delete existing state

### Requirement 5: Zarf Package Generation

**User Story:** As a platform engineer, I want automatic Zarf package creation, so that I don't manually maintain zarf.yaml.

#### Acceptance Criteria

1. THE Build_System SHALL generate zarf.yaml from config/versions.env
2. WHEN container images are discovered, THE Build_System SHALL add them to the images component
3. WHEN Helm charts are specified, THE Build_System SHALL add them to the charts component
4. WHEN Git repositories are specified, THE Build_System SHALL add them to the repos component
5. WHEN Kubernetes binaries are collected, THE Build_System SHALL add them to the files component
6. THE Build_System SHALL invoke zarf package create after generating zarf.yaml
7. WHEN package creation completes, THE Build_System SHALL output the package path

### Requirement 6: Artifact Manifest Generation

**User Story:** As a security officer, I want a complete artifact inventory, so that I can verify package contents before deployment.

#### Acceptance Criteria

1. WHEN a build completes, THE Build_System SHALL generate an Artifact_Manifest
2. THE Artifact_Manifest SHALL include container image names, tags, and total size
3. THE Artifact_Manifest SHALL include Helm chart names, versions, and URLs
4. THE Artifact_Manifest SHALL include Git repository URLs, refs, and sizes
5. THE Artifact_Manifest SHALL include Kubernetes binary names, versions, paths, sizes, and SHA256 checksums
6. THE Artifact_Manifest SHALL include OS package names, versions, architectures, and total size
7. THE Artifact_Manifest SHALL include PyPI package names, versions, types (wheel/source), and total size
8. THE Artifact_Manifest SHALL include Terraform provider names, versions, platforms, and count
9. THE Artifact_Manifest SHALL include total artifact count and total size
10. THE Build_System SHALL export the Artifact_Manifest in JSON format
11. THE Build_System SHALL export the Artifact_Manifest in Markdown format

### Requirement 7: Structured Logging

**User Story:** As a platform engineer, I want structured logs, so that I can parse and analyze build failures programmatically.

#### Acceptance Criteria

1. THE Build_System SHALL output logs in JSON format when --json flag is provided
2. WHEN logging in JSON format, THE Build_System SHALL include timestamp, level, message, and trace_id
3. THE Build_System SHALL support log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
4. WHEN --verbose flag is provided, THE Build_System SHALL set log level to DEBUG
5. WHEN --verbose flag is not provided, THE Build_System SHALL set log level to INFO

### Requirement 8: Build Metrics Export

**User Story:** As a platform architect, I want build metrics in Prometheus format, so that I can monitor build performance over time.

#### Acceptance Criteria

1. WHEN a build completes, THE Build_System SHALL export metrics in Prometheus format
2. THE Build_System SHALL record build duration in seconds
3. THE Build_System SHALL record build success/failure status
4. THE Build_System SHALL record per-step duration in seconds
5. THE Build_System SHALL record artifact counts by type
6. THE Build_System SHALL write metrics to dist/build-metrics.prom

### Requirement 9: Bastion Service Deployment

**User Story:** As a field operator, I want single-command deployment, so that I can quickly start bastion services.

#### Acceptance Criteria

1. WHEN the serve command is invoked, THE Build_System SHALL execute zarf package deploy
2. WHEN Zarf deployment completes, THE Build_System SHALL start nginx container
3. THE Build_System SHALL configure nginx to serve files at /files/, debs at /debs/, and pypi at /pypi/
4. WHEN nginx starts, THE Build_System SHALL verify HTTP 200 response on port 80
5. WHEN service startup fails, THE Build_System SHALL clean up partial deployments
6. THE Build_System SHALL display service URLs after successful deployment

### Requirement 10: Configuration Validation

**User Story:** As a platform engineer, I want configuration validation, so that I catch errors before starting long-running builds.

#### Acceptance Criteria

1. THE Build_System SHALL validate config/versions.env exists
2. THE Build_System SHALL validate all required version variables are defined
3. WHEN --strict flag is provided, THE Build_System SHALL fail on any validation warnings
4. THE Build_System SHALL validate repository paths exist
5. THE Build_System SHALL validate Zarf is installed and accessible
6. THE Build_System SHALL display validation results with pass/fail indicators

### Requirement 11: Binary Distribution

**User Story:** As a field operator, I want a standalone binary, so that I don't need to install Python dependencies.

#### Acceptance Criteria

1. THE Build_System SHALL be packaged as a standalone binary using PyInstaller
2. THE binary SHALL be named opencenter-airgap
3. THE binary SHALL be executable on Ubuntu 24.04 AMD64
4. THE binary SHALL include all Python dependencies
5. THE binary size SHALL be less than 25MB

### Requirement 12: Backward Compatibility

**User Story:** As a platform engineer, I want to run old and new systems in parallel, so that I can validate behavior before switching.

#### Acceptance Criteria

1. THE Build_System SHALL read existing config/versions.env format without modification
2. THE Build_System SHALL output artifacts to the same paths as bash scripts
3. THE Build_System SHALL preserve kubespray-offline directory structure
4. WHEN both systems run, THE Build_System SHALL produce byte-identical Zarf packages
5. THE Build_System SHALL not delete or modify bash scripts during execution

### Requirement 13: Component Manifest Management

**User Story:** As a platform engineer, I want to declaratively specify components to collect, so that I can version-control build requirements.

#### Acceptance Criteria

1. THE Build_System SHALL support a component manifest file at config/components.yaml
2. THE component manifest SHALL support tool definitions with name, version, and URL
3. THE component manifest SHALL support repository definitions with name, URL, and ref
4. THE component manifest SHALL support image auto-discovery directives
5. THE component manifest SHALL support explicit image additions
6. THE component manifest SHALL support Helm chart definitions with name, repo, and version
7. THE Build_System SHALL provide an add command to append components to the manifest
8. THE Build_System SHALL validate component manifest against JSON schema

### Requirement 14: Manifest Generation

**User Story:** As a platform engineer, I want automatic Zarf manifest generation from component manifest, so that I don't manually maintain zarf.yaml.

#### Acceptance Criteria

1. THE Build_System SHALL provide a generate-manifest command
2. WHEN generate-manifest is invoked, THE Build_System SHALL read config/components.yaml
3. WHEN generate-manifest is invoked, THE Build_System SHALL resolve version templates
4. WHEN generate-manifest is invoked, THE Build_System SHALL expand auto-discovery directives
5. WHEN generate-manifest is invoked, THE Build_System SHALL write zarf.yaml
6. THE generated zarf.yaml SHALL be valid according to Zarf schema

### Requirement 15: Package Verification

**User Story:** As a security officer, I want to verify package integrity before deployment, so that I can detect tampering.

#### Acceptance Criteria

1. THE Build_System SHALL provide a verify command
2. WHEN verify is invoked with a package path, THE Build_System SHALL check Cosign signature
3. WHEN verify is invoked with a package path, THE Build_System SHALL validate checksums
4. WHEN verify is invoked with --manifest flag, THE Build_System SHALL compare artifact manifest against package contents
5. WHEN verification fails, THE Build_System SHALL exit with non-zero code and display specific failures
6. WHEN verification succeeds, THE Build_System SHALL display success message with artifact count
