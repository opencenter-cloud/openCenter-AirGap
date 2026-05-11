# Architecture Improvements - Requirements

**Feature**: Implement architecture review recommendations to improve maintainability, testability, and operational resilience

**Priority**: Critical
**Timeline**: 8 weeks
**Effort**: 12 engineer-weeks

## User Stories

### Epic 1: Critical Infrastructure (Weeks 1-2)

#### US-1.0: Container Tooling Standardization
**As a** platform engineer
**I want** standardized container image operations using Skopeo and Podman
**So that** image handling is consistent, daemonless, and Docker-free

**Acceptance Criteria**:
- Skopeo used for all image copy/sync operations (registry-to-dir, dir-to-registry)
- Podman used for image load/save operations (tar archives)
- No Docker dependencies in build or deployment scripts
- Image operations work without daemon or root privileges
- `skopeo copy` used for air-gap image collection to directories
- `podman load` used for loading images from tar archives
- `podman save` used for creating tar archives
- All scripts tested on Ubuntu 24.04
- Documentation updated to reflect Skopeo-first approach

**Technical Details**:
- Skopeo advantages: daemonless, no root required, direct registry-to-directory copies
- Podman advantages: Docker-compatible CLI, daemonless, rootless operation
- Image workflow: `skopeo copy docker://image dir:/path` → `podman load -i image.tar`
- Supported transports: docker://, dir://, oci://, docker-archive:, containers-storage:

#### US-1.1: Python Package Structure
**As a** platform engineer
**I want** a proper Python package structure with dependency management
**So that** I can reliably install, test, and maintain build scripts

**Acceptance Criteria**:
- `pyproject.toml` exists with project metadata and dependencies
- `src/opencenter_build/` package structure created
- All reusable Python code moved to package modules
- `pip install -e .` installs package successfully
- `mypy --strict src/` passes with no errors
- All existing scripts remain functional

#### US-1.2: Configuration Schema Validation
**As a** platform engineer
**I want** JSON schema validation for all configuration files
**So that** invalid configurations are caught early in the build process

**Acceptance Criteria**:
- JSON schemas exist for: versions.env, nodes.yaml, openstack-config.yaml
- `ConfigValidator` class validates all config files
- Build fails fast with clear error messages on invalid config
- Validation integrated into build pipeline
- Tests cover valid and invalid config scenarios

#### US-1.3: Atomic State Management
**As a** platform engineer
**I want** atomic state file operations with recovery
**So that** build state never corrupts even during crashes

**Acceptance Criteria**:
- `StateManager` class implements atomic writes
- File locking prevents concurrent access issues
- Backup created before state updates
- Recovery mechanism restores from backup on corruption
- All state operations migrated to new system
- Stress tests verify atomicity under concurrent access

#### US-1.4: Language Boundary Documentation
**As a** developer
**I want** clear guidelines on when to use Python vs Bash
**So that** I make consistent technology choices

**Acceptance Criteria**:
- `docs/reference/coding-standards.md` created
- Language decision matrix documented
- Rationale for each language choice explained
- Migration plan for mixed-responsibility scripts
- Team trained on guidelines

### Epic 2: Error Handling & Logging (Week 3)

#### US-2.1: Exception Hierarchy
**As a** developer
**I want** a well-defined exception hierarchy
**So that** I can handle errors appropriately and provide context

**Acceptance Criteria**:
- `OpenCenterError` base exception defined
- Specific exceptions for build, deployment, validation errors
- No bare `except:` blocks in codebase
- All exceptions include context and error chaining
- Error messages are actionable

#### US-2.2: Centralized Logging
**As an** operator
**I want** structured, centralized logging
**So that** I can troubleshoot issues efficiently

**Acceptance Criteria**:
- `setup_logging()` function configures logging
- All Python scripts use `logging` module
- All Bash scripts use logging functions
- Logs aggregated to single file per run
- Log rotation configured (10MB, 5 backups)
- No `print()` statements in production code

### Epic 3: Security & Recovery (Week 4)

#### US-3.1: Secure Secrets Management
**As a** security engineer
**I want** file-based secrets with permission validation
**So that** credentials are never exposed in shell history or logs

**Acceptance Criteria**:
- `.secrets/` directory for sensitive files
- Permission checks enforce 0600 on secret files
- Secrets never logged or printed
- Documentation for secret rotation
- Pre-commit hook prevents secret commits

#### US-3.2: Rollback Mechanisms
**As an** operator
**I want** automatic rollback on operation failures
**So that** I can recover quickly from errors

**Acceptance Criteria**:
- `Transaction` context manager for rollback
- Critical operations use transactional semantics
- Rollback actions execute in reverse order
- State snapshots created before changes
- Recovery procedures documented

### Epic 4: Testing & Observability (Weeks 5-6)

#### US-4.1: Integration Test Suite
**As a** QA engineer
**I want** comprehensive integration tests
**So that** I can verify end-to-end functionality

**Acceptance Criteria**:
- `tests/integration/test_full_pipeline.py` exists
- Tests cover build → package → verify workflow
- Tests run in CI pipeline
- Test fixtures for common scenarios
- Tests complete in <30 minutes

#### US-4.2: Metrics Collection
**As an** SRE
**I want** build and deployment metrics
**So that** I can monitor system health and performance

**Acceptance Criteria**:
- `BuildMetrics` class collects metrics
- Metrics exported in Prometheus format
- Metrics include: duration, success rate, package size
- Metrics written to `build/metrics.json`
- Grafana dashboard template provided

#### US-4.3: Immutable Version Pinning
**As a** security engineer
**I want** all dependencies pinned to commit SHAs
**So that** builds are reproducible and supply chain is secure

**Acceptance Criteria**:
- All git dependencies use commit SHAs
- `verify_commit_shas.py` validates references
- Verification runs in build pipeline
- Documentation for version updates
- No mutable references (master, main, latest)

### Epic 5: CI/CD & Tooling (Week 7)

#### US-5.1: Continuous Integration Pipeline
**As a** developer
**I want** automated testing and linting on every commit
**So that** code quality is maintained

**Acceptance Criteria**:
- `.github/workflows/ci.yml` exists
- CI runs: linting, type checking, unit tests, integration tests
- Branch protection requires CI pass
- Status badges in README.md
- CI completes in <15 minutes

#### US-5.2: Developer Tooling
**As a** developer
**I want** convenient commands for common tasks
**So that** I can work efficiently

**Acceptance Criteria**:
- `Makefile` with targets: install-dev, lint, test, build, clean
- `.pre-commit-config.yaml` with hooks
- Pre-commit hooks validate generated files
- Pre-commit hooks detect secrets
- Documentation in CONTRIBUTING.md

### Epic 6: Security Validation (Week 8)

#### US-6.1: Asset Checksum Verification
**As a** security engineer
**I want** checksum verification for all assets
**So that** tampering is detected

**Acceptance Criteria**:
- Checksum manifest generated during collection
- Verification runs before package creation
- Checksums stored in `build/asset-checksums.json`
- Build fails on checksum mismatch
- Documentation for checksum updates

#### US-6.2: Container Image Scanning
**As a** security engineer
**I want** vulnerability scanning for all container images
**So that** critical CVEs are identified before deployment

**Acceptance Criteria**:
- Trivy integrated into build process
- All 139 images scanned for HIGH/CRITICAL vulnerabilities
- Scan results in `build/image-scan-results.json`
- Build fails if critical vulnerabilities found
- Vulnerability threshold policy documented

## Non-Functional Requirements

### Performance
- Build duration P95 < 45 minutes
- State operations < 100ms
- CI pipeline < 15 minutes

### Reliability
- Build success rate > 95%
- No state corruption under concurrent access
- MTTR < 30 minutes

### Security
- Zero critical CVEs in packaged images
- No secrets in git history
- 100% dependency pinning

### Maintainability
- Test coverage > 80%
- 100% linter compliance
- 90% type coverage (mypy)
- 95% documentation coverage

## Dependencies

### External
- Python 3.12+
- Skopeo (container image operations)
- Podman (container runtime)
- GitHub Actions
- Trivy (image scanning)
- Grafana (dashboards)

### Internal
- Existing build system
- Zarf package structure
- Deployment scripts

## Risks & Mitigation

### High Risk
1. **State Migration**: Backup existing state before migration
2. **Logging Changes**: Gradual rollout with monitoring
3. **CI Integration**: Test in feature branch first

### Medium Risk
1. **Test Coverage**: Incremental addition of tests
2. **Documentation Drift**: Pre-commit hooks enforce consistency

## Success Metrics

| Metric | Current | Target | Timeline |
|--------|---------|--------|----------|
| Test Coverage | ~20% | 80% | 8 weeks |
| Build Success Rate | Unknown | 95% | 4 weeks |
| Critical CVEs | Unknown | 0 | 4 weeks |
| MTTR | Unknown | <30min | 8 weeks |

## Out of Scope

- Rewriting build system in different language
- Changing Zarf package structure
- Modifying deployment workflows
- Adding new features beyond architecture improvements

## References

- Architecture Review: `docs/architecture-review.md`
- Implementation Plan: `docs/implementation-plan-summary.md`
- Sprint 0 Checklist: `docs/sprint-0-checklist.md`
