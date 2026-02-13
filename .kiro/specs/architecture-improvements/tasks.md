# Architecture Improvements - Implementation Tasks

**Status**: In Progress
**Total Duration**: 8 weeks
**Total Effort**: 12 engineer-weeks

## Week 1: Critical Infrastructure - Python Package & Config Validation

- [x] **Task 1.1: Quick Wins** (Day 1, 4 hours) - P0
  Create governance files: `.editorconfig`, `CODEOWNERS`, `SECURITY.md`, GitHub issue templates (bug_report.yml, feature_request.yml), and `CONTRIBUTING.md`. Commit all files and prepare team notification.
  **Owner**: Platform Engineer | **Dependencies**: None
  **Acceptance**: All governance files committed, team notified

- [x] **Task 1.2: Python Package Structure** (Days 2-3, 12 hours) - P0
  Create `pyproject.toml` with project metadata and dev dependencies (pytest, black, mypy, pylint, hypothesis). Configure black (line-length=100), mypy (strict mode), and pytest. Create `src/opencenter_build/` package with modules: `__init__.py`, `exceptions.py`, `logging.py`, `state.py`, `config.py`, `image_utils.py`, `version_utils.py`, `zarf_utils.py`. Add type hints and docstrings to all functions. Verify `pip install -e .` works, run mypy/black/pylint.
  **Owner**: Platform Engineer | **Dependencies**: Task 1.1
  **Acceptance**: Package installable, mypy passes with --strict, all modules have docstrings

- [x] **Task 1.3: Migrate Existing Python Code** (Day 3, 3 hours) - P0
  Move image parsing logic from `scripts/build/generate_zarf_images_block.py` to `src/opencenter_build/image_utils.py`. Move version validation to `version_utils.py`. Move zarf generation from `scripts/build/generate_zarf_yaml.py` to `zarf_utils.py`. Update scripts to use new package. Test all scripts work. Update unit tests to import from package.
  **Owner**: Platform Engineer | **Dependencies**: Task 1.2
  **Acceptance**: All Python scripts use `opencenter_build` package, tests pass

- [x] **Task 1.4: Configuration Schema Validation** (Days 4-5, 12 hours) - P0
  Create `config/schemas/` directory with README.md. Create JSON schemas: `versions.schema.json`, `nodes.schema.json`, `openstack-config.schema.json`, `zarf-variables.schema.json`. Create `src/opencenter_build/validation.py` with ConfigValidator class implementing `validate_versions_env()`, `validate_nodes_file()`, `validate_openstack_config()`. Add jsonschema dependency. Create `scripts/build/validate_config.py` and integrate into build pipeline. Create `tests/unit/test_validation.py` with test cases for valid/invalid configs and missing fields.
  **Owner**: Platform Engineer | **Dependencies**: Task 1.2
  **Acceptance**: Validation catches config errors, tests pass, clear error messages

---

## Week 2: Critical Infrastructure - State Management & Standards

- [x] **Task 2.1: Atomic State Management** (Days 1-3, 12 hours) - P0
  Implement `StateManager` class in `src/opencenter_build/state.py` with file locking (fcntl), atomic write (temp file + rename), backup before write, and recovery from backup. Add state validation (JSON parse check). Create `tests/unit/test_state.py` with tests for atomic writes, concurrent access (threading), recovery from corrupted state, and backup creation. Update `scripts/build/build.py` to use StateManager. Remove old state file operations. Run property-based tests for state operations.
  **Owner**: Platform Engineer | **Dependencies**: Task 1.2
  **Acceptance**: State operations atomic, concurrent access safe, recovery works

- [x] **Task 2.2: Language Boundary Documentation** (Days 3-4, 8 hours) - P0
  Create `docs/reference/coding-standards.md` documenting language decision matrix (Python vs Bash), when to use Python (data transformation, JSON/YAML, complex logic), when to use Bash (orchestration, file ops, tool invocation), error handling standards for both languages, logging standards, testing requirements, type checking (mypy), linting (pylint, shellcheck). Add examples of good patterns and anti-patterns. Create migration plan for mixed-responsibility scripts. Review with team. Update CONTRIBUTING.md to reference standards.
  **Owner**: Platform Engineer | **Dependencies**: None
  **Acceptance**: Standards documented, team reviewed, CONTRIBUTING.md updated

- [x] **Task 2.3: Secrets Management Implementation** (Day 5, 4 hours) - P1
  Create `src/opencenter_build/secrets.py` with SecretsManager class implementing permission checking (0600 enforcement), `get_secret()`, and `set_secret()` methods. Add `.secrets/` to `.gitignore`. Create `.secrets/README.md` with usage instructions. Update `scripts/build/collect_kubespray_offline.sh` to use file-based secrets. Remove GITHUB_TOKEN from environment variable usage. Create `tests/unit/test_secrets.py` with tests for permission validation, secret read/write, and error messages. Document secret rotation in `docs/reference/secrets-management.md`.
  **Owner**: Platform Engineer | **Dependencies**: Task 1.2
  **Acceptance**: Secrets file-based, permissions enforced, no tokens in env vars

---

## Week 3: Error Handling & Logging

- [x] **Task 3.1: Exception Hierarchy Implementation** (Days 1-2, 8 hours) - P1
  Expand `src/opencenter_build/exceptions.py` with full hierarchy: OpenCenterError base class, BuildError, AssetCollectionError, PackageError, ValidationError, StateError, SecretsError, DeploymentError, NetworkError, ConfigError. Add error context attributes (operation, details, timestamp) and error chaining support. Audit all Python scripts for bare `except:` blocks and replace with specific exception handling. Add error context to all raises. Create `tests/unit/test_exceptions.py` with tests for exception hierarchy, error chaining, and error context.
  **Owner**: Platform Engineer | **Dependencies**: Task 1.2
  **Acceptance**: No bare except blocks, all errors have context, tests pass

- [x] **Task 3.2: Centralized Logging** (Days 2-5, 12 hours) - P1
  Implement `setup_logging()` in `src/opencenter_build/logging.py` with console handler, file handler with rotation (10MB, 5 backups), `get_logger()` helper, and log level configuration. Update all Python scripts to use logging module. Remove all `print()` statements from production code (scripts/build/generate_opencenter_images.py, build_state.py, checksum_utils.py, workers/checksums.py, workers/validation.py). Add structured logging fields (timestamp, level, module). Extend `scripts/deploy/logging.sh` for build scripts. Create `scripts/lib/logging.sh` for shared Bash logging. Update all Bash scripts to use logging functions. Add log aggregation to single file per build. Configure log rotation. Create `tests/unit/test_logging.py` with tests for log file creation, rotation, levels, and console/file output. Document logging in `docs/reference/logging.md`.
  **Owner**: Platform Engineer | **Dependencies**: Task 3.1
  **Acceptance**: Centralized logging active, no print statements, logs rotated

---

## Week 4: Security & Recovery

- [x] **Task 4.1: Transaction and Rollback** (Days 1-3, 12 hours) - P1
  Create `src/opencenter_build/transaction.py` with Transaction class implementing `add_rollback()`, `commit()`, `rollback()`, and `transactional_operation()` context manager. Add rollback logging. Identify critical operations needing transactions. Add transaction support to zarf.yaml generation, asset organization, and state updates. Create `tests/unit/test_transaction.py` with tests for rollback on exception, commit clears rollback actions, multiple rollback actions, and rollback action failures. Document rollback patterns in `docs/reference/rollback.md`.
  **Owner**: Platform Engineer | **Dependencies**: Task 3.2
  **Acceptance**: Rollback works for critical operations, tests pass

- [x] **Task 4.2: Pre-commit Hooks** (Days 3-4, 8 hours) - P1
  Create `.pre-commit-config.yaml` with hooks: check-generated-files (zarf.yaml), detect-secrets, shellcheck, black, mypy, trailing-whitespace, end-of-file-fixer. Create `scripts/hooks/check-generated-files.sh`. Test hooks locally. Add pre-commit to dev dependencies. Update CONTRIBUTING.md with hook setup. Document hook bypass for emergencies.
  **Owner**: Platform Engineer | **Dependencies**: None
  **Acceptance**: Hooks installed, prevent invalid commits, documented

- [x] **Task 4.3: Recovery Procedures Documentation** (Day 5, 4 hours) - P2
  Create `docs/reference/recovery-procedures.md` documenting state corruption recovery, failed build recovery, rollback procedures, backup restoration, log analysis for troubleshooting. Add runbook for common failure scenarios and escalation paths. Review with ops team.
  **Owner**: Platform Engineer | **Dependencies**: Task 4.1
  **Acceptance**: Recovery procedures documented, ops team trained

---

## Week 5: Testing Infrastructure

- [x] **Task 5.1: Integration Test Suite** (Days 1-3, 12 hours) - P1
  Add pytest-timeout and pytest-podman to dev dependencies. Create `tests/integration/conftest.py` with fixtures. Create `tests/integration/test_full_pipeline.py` implementing test_build_package_end_to_end(), test_zarf_yaml_generation_idempotency(), test_asset_collection(), test_config_validation_integration(), test_state_persistence(). Add test fixtures for temporary directories and mock configs. Configure test timeouts (3600s for full build). Create test data in `tests/fixtures/`. Run integration tests locally. Document test execution in `tests/integration/README.md`.
  **Owner**: QA Engineer | **Dependencies**: Tasks 1.2, 1.4, 2.1
  **Acceptance**: Integration tests pass, cover build → package → verify

- [x] **Task 5.2: Property-Based Testing** (Days 3-4, 8 hours) - P2
  Add hypothesis to dev dependencies. Create property tests for state management, config validation, image parsing, and version validation. Test state operations under concurrent access. Test config validation with generated inputs. Test idempotency of operations. Run property tests with multiple iterations. Document property testing in `docs/reference/testing.md`.
  **Owner**: QA Engineer | **Dependencies**: Task 5.1
  **Acceptance**: Property tests pass, edge cases covered

- [x] **Task 5.3: Test Coverage Analysis** (Day 5, 4 hours) - P2
  Add pytest-cov to dev dependencies. Configure coverage in pyproject.toml. Run coverage: `pytest --cov=src --cov-report=html`. Identify uncovered code paths. Add tests for uncovered paths. Set coverage threshold to 80%. Add coverage badge to README.md. Document coverage requirements in CONTRIBUTING.md.
  **Owner**: QA Engineer | **Dependencies**: Tasks 5.1, 5.2
  **Acceptance**: Test coverage >80%, coverage enforced in CI

---

## Week 6: Observability & Metrics

- [x] **Task 6.1: Build Metrics Collection** (Days 1-2, 8 hours) - P1
  Implement BuildMetrics class in `src/opencenter_build/metrics.py` with fields: build_id, start_time, end_time, duration, steps_completed, steps_failed, success, package_size_bytes, image_count. Implement `complete()`, `to_json()`, `to_prometheus()`, and `save()` methods. Integrate metrics into `scripts/build/build.py`. Track metrics for each build step. Export metrics to `build/metrics.json` and `build/metrics.prom`. Create `tests/unit/test_metrics.py` with tests for metrics collection, JSON export, and Prometheus export.
  **Owner**: Platform Engineer | **Dependencies**: Task 1.2
  **Acceptance**: Metrics collected, exported in JSON and Prometheus formats

- [ ] **Task 6.2: Version Pinning to Commit SHAs** (Days 2-3, 8 hours) - P0
  Update `config/versions.env` to add commit SHA fields: KUBESPRAY_COMMIT_SHA, OPENCENTER_GITOPS_BASE_COMMIT_SHA. Change KUBESPRAY_VERSION from "master" to specific tag (e.g., v2.24.0). Change OPENCENTER_GITOPS_BASE_VERSION from "main" to specific tag or commit SHA. Create `scripts/build/verify_commit_shas.py` implementing git ls-remote verification. Integrate verification into build pipeline. Update `config/schemas/versions.schema.json` to require commit SHA fields. Test verification with correct and incorrect SHAs. Document version update procedure in `docs/reference/version-management.md`.
  **Owner**: Platform Engineer | **Dependencies**: Task 1.4
  **Acceptance**: All git deps pinned to SHAs, verification in build pipeline

- [ ] **Task 6.3: Skopeo/Podman Image Operations** (Days 3-4, 8 hours) - P0
  Implement ImageManager class in `src/opencenter_build/image_utils.py` with methods: `copy_image_to_dir()`, `sync_images()`, `save_image_to_tar()`, `load_image_from_tar()`, `list_local_images()`, `inspect_image()`. Use Skopeo for registry operations (copy, sync, inspect). Use Podman for tar operations (save, load). Add tool verification in `__init__()`. Update build scripts to use ImageManager instead of Docker commands. Create `tests/unit/test_image_manager.py` with tests for all operations. Document Skopeo/Podman installation in README.md.
  **Owner**: Platform Engineer | **Dependencies**: Task 1.2
  **Acceptance**: All image operations use Skopeo/Podman, no Docker dependencies

- [ ] **Task 6.4: Grafana Dashboard** (Days 4-5, 8 hours) - P2
  Create `assets/monitoring/grafana-dashboard.json` with panels: Build duration over time, Build success rate, Package size trend, Steps completed/failed, Image count. Add variables for build_id filtering. Add annotations for build events. Test dashboard with sample metrics. Document dashboard import in `docs/reference/monitoring.md`. Add health check endpoint documentation.
  **Owner**: SRE | **Dependencies**: Task 6.1
  **Acceptance**: Dashboard visualizes build metrics, documented

---

## Week 7: CI/CD & Developer Tooling

- [ ] **Task 7.1: GitHub Actions CI Pipeline** (Days 1-2, 8 hours) - P1
  Create `.github/workflows/ci.yml` with jobs: lint (black, mypy, pylint, shellcheck), test-unit (pytest unit tests), test-integration (pytest integration tests), validate-config (schema validation), check-coverage (pytest-cov with 80% threshold). Configure matrix for Python 3.10, 3.11, 3.12. Add caching for pip dependencies. Set timeout for jobs (15 min for lint/unit, 60 min for integration). Test CI pipeline in feature branch. Add status badges to README.md. Configure branch protection rules. Require CI pass before merge.
  **Owner**: Platform Engineer | **Dependencies**: Tasks 5.1, 5.3
  **Acceptance**: CI pipeline runs on every commit, branch protection enabled

- [ ] **Task 7.2: Makefile for Developer Commands** (Days 2-3, 8 hours) - P2
  Create `Makefile` in project root with targets: help (list all targets), install-dev (pip install -e ".[dev]"), lint (black, mypy, pylint, shellcheck), format (black --check=false), test (pytest all tests), test-unit (pytest unit only), test-integration (pytest integration only), coverage (pytest with coverage report), build (run build.py), clean (remove build artifacts), validate (validate configs). Test all targets locally. Update README.md with Makefile usage. Update CONTRIBUTING.md with make commands.
  **Owner**: Platform Engineer | **Dependencies**: Tasks 1.2, 5.1
  **Acceptance**: Makefile works, documented in README and CONTRIBUTING

- [ ] **Task 7.3: Developer Documentation** (Days 3-5, 8 hours) - P2
  Update `CONTRIBUTING.md` with complete setup instructions: Development environment setup, Running tests, Code style and linting, Pre-commit hooks, Submitting PRs, Debugging tips. Create `docs/reference/development-workflow.md` documenting feature branch workflow, testing requirements, code review process. Add troubleshooting section. Review with team.
  **Owner**: Platform Engineer | **Dependencies**: Tasks 7.1, 7.2
  **Acceptance**: Complete developer documentation, team trained

---

## Week 8: Security Validation

- [x] **Task 8.1: Asset Checksum Verification** (Days 1-2, 8 hours) - P1
  Create `scripts/build/generate_asset_checksums.py` implementing checksum generation for all assets. Generate manifest: `build/asset-checksums.json`. Create `scripts/build/verify_asset_checksums.py` implementing checksum verification. Integrate generation into asset collection. Integrate verification into package creation. Fail build on checksum mismatch. Create `tests/unit/test_checksums.py` with tests for checksum generation, verification, and mismatch detection. Document checksum update procedure in `docs/reference/asset-integrity.md`.
  **Owner**: Security Engineer | **Dependencies**: Task 1.2
  **Acceptance**: Checksums generated and verified, build fails on mismatch

- [x] **Task 8.2: Container Image Scanning** (Days 2-4, 12 hours) - P1
  Add Trivy to build prerequisites documentation. Create `scripts/build/scan_images.sh` implementing image scanning for all images in `config/all-images.txt`. Generate scan results: `build/image-scan-results.json`. Implement vulnerability threshold policy (fail on CRITICAL). Create summary report: `build/image-vulnerabilities.txt`. Integrate scanning into build pipeline. Add scan results to SBOM. Create `tests/integration/test_image_scanning.sh` with tests for scanning with known vulnerable image and threshold enforcement. Document vulnerability policy in `docs/reference/security-scanning.md`. Document remediation process.
  **Owner**: Security Engineer | **Dependencies**: None
  **Acceptance**: All images scanned, CRITICAL CVEs block build, documented

- [ ] **Task 8.3: Security Audit & Documentation** (Days 4-5, 8 hours) - P1
  Audit all scripts for hardcoded secrets. Verify no secrets in git history. Verify all dependencies pinned. Verify SBOM completeness. Create `docs/reference/security-controls.md` documenting secrets management controls, supply chain controls, vulnerability management, access controls, audit logging. Create security checklist for releases. Review with security team. Update SECURITY.md with controls.
  **Owner**: Security Engineer | **Dependencies**: Tasks 2.3, 6.2, 8.1, 8.2
  **Acceptance**: Security audit complete, controls documented

---

## Cross-Cutting Tasks

- [ ] **Documentation Updates** (Ongoing) - P1
  Update README.md with new structure. Update all docs/ files referencing old structure. Add migration guide for existing users. Update architecture diagrams. Update API documentation. Ensure all code has docstrings. Ensure all scripts have usage help.
  **Owner**: All Engineers
  **Acceptance**: Documentation current, no broken references

- [ ] **Testing** (Ongoing) - P0
  Write unit tests for all new code. Maintain >80% test coverage. Run tests before every commit. Fix failing tests immediately. Add integration tests for new features.
  **Owner**: All Engineers
  **Acceptance**: All tests pass, coverage >80%

---

## Success Criteria

### Week 1-2 (Critical)
- [x] Python package installable with `pip install -e .`
- [x] Config validation catches errors before build
- [x] State operations atomic with locking
- [x] Coding standards documented

### Week 3-4 (High Priority)
- [x] No bare except blocks in codebase
- [ ] Centralized logging active in all scripts
- [x] Secrets file-based with 0600 permissions
- [x] Rollback works for failed operations

### Week 5-6 (High Priority)
- [x] Integration tests pass in <30 minutes
- [ ] Metrics exported in JSON and Prometheus formats
- [ ] All git deps pinned to commit SHAs
- [ ] Skopeo/Podman image operations implemented
- [ ] Grafana dashboard deployed

### Week 7-8 (Medium Priority)
- [ ] CI pipeline green on all commits
- [x] Pre-commit hooks prevent invalid commits
- [x] Asset checksums verified before packaging
- [ ] Image vulnerabilities scanned, CRITICAL CVEs block build

---

## Risk Mitigation

### High Risk Items
1. **State Migration**: Backup existing state before migration (Task 2.1)
2. **Logging Changes**: Gradual rollout with monitoring (Task 3.2)
3. **CI Integration**: Test in feature branch first (Task 7.1)

### Rollback Plan
- Keep old code paths for 2 weeks after migration
- Feature flags for new functionality
- Documented rollback procedures (Task 4.3)

---

## Dependencies Graph

```
Week 1:
  1.1 (Quick Wins) → 1.2 (Python Package) → 1.3 (Migrate Code)
                   → 1.4 (Config Validation)

Week 2:
  1.2 → 2.1 (State Management)
  None → 2.2 (Language Standards)
  1.2 → 2.3 (Secrets)

Week 3:
  1.2 → 3.1 (Exceptions) → 3.2 (Logging)

Week 4:
  3.2 → 4.1 (Transactions)
  None → 4.2 (Pre-commit)
  4.1 → 4.3 (Recovery Docs)

Week 5:
  1.2, 1.4, 2.1 → 5.1 (Integration Tests) → 5.2 (Property Tests) → 5.3 (Coverage)

Week 6:
  1.2 → 6.1 (Metrics)
  1.4 → 6.2 (Version Pinning)
  6.1 → 6.3 (Grafana)

Week 7:
  5.1, 5.3 → 7.1 (CI Pipeline)
  1.2, 5.1 → 7.2 (Makefile)
  7.1, 7.2 → 7.3 (Dev Docs)

Week 8:
  1.2 → 8.1 (Checksums)
  None → 8.2 (Image Scanning)
  2.3, 6.2, 8.1, 8.2 → 8.3 (Security Audit)
```

---

## Tracking

**Project Board**: GitHub Projects
**Sprint Duration**: 1 week
**Standup**: Daily, 15 minutes
**Retrospective**: End of each week
**Demo**: End of Weeks 2, 4, 6, 8

**Metrics**:
- Tasks completed vs planned
- Test coverage percentage
- CI pipeline success rate
- Build duration trend
- Defect escape rate
