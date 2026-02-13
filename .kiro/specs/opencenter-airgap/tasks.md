# Implementation Plan: openCenter AirGap

## Implementation Status

**Core Build & Package System**: ✅ Complete
- Asset collection (kubespray-offline integration)
- Asset organization for Zarf
- Terraform provider mirroring
- Version validation
- Zarf package creation
- SBOM generation and verification
- Checksum generation
- Package signing (optional)
- Master build script (`scripts/build/build.sh`)

**Core Deployment System**: ✅ Complete
- Bastion setup (kubespray-offline scripts)
- Service verification (nginx, registry, Python venv)
- Terraform execution (OpenStack mode)
- Inventory generation (bare-metal and OpenStack)
- Kubespray execution
- Cluster health verification
- Logging infrastructure
- Network monitoring for offline compliance
- Master deployment script (`scripts/deploy/deploy.sh`)

**Documentation**: ✅ Complete
- Build runbook
- Deployment runbooks (bare-metal and OpenStack)
- Troubleshooting guide
- Extension guide
- Zarf variables reference

**Testing**: 🔄 Partial
- ✅ Offline compliance property tests (3 properties)
- ⏳ Remaining property tests (23 properties)
- ⏳ Integration tests

**Remaining Work**:
- [-] openCenter platform service image collection (20+ services)
- [ ] Property-based tests (optional, 23 remaining properties)
- [ ] Integration testing (optional, end-to-end validation)
- [ ] Component independence testing
- [ ] Build determinism validation

**Ready for**: MVP deployment testing with openCenter platform handling infrastructure provisioning, cluster bootstrap, and service deployment

## Overview

This implementation plan integrates **kubespray-offline@main** as the foundation for K8s asset collection and runtime setup, packaged and orchestrated by **Zarf**.

**Integration Model:**
- **Build Phase (Zone A)**: Execute kubespray-offline `download-all.sh` to populate `outputs/` directory
- **Package Phase (Zone A→B)**: Zarf bundles kubespray-offline outputs + target scripts into single artifact
- **Deploy Phase (Zone C)**: Zarf extracts and executes kubespray-offline `setup-all.sh` on bastion
- **Handoff Phase (Zone C)**: openCenter AirGap completes, openCenter platform takes over

**Scope Clarification:**
- **openCenter AirGap**: Collects assets, sets up bastion registry, provides all images
- **openCenter Platform (gitops-base)**: Provisions infrastructure, bootstraps cluster, deploys 20+ services via Flux CD

**kubespray-offline Workflow:**
1. **Download**: `download-all.sh` → `outputs/{files,images,debs,pypi,playbook,kubespray-*.tar.gz,target-scripts}`
2. **Setup**: `setup-all.sh` → `setup-container.sh`, `start-nginx.sh`, `start-registry.sh`, `load-push-all-images.sh`
3. **Handoff**: Bastion registry and nginx ready for openCenter platform to consume

**Key Configuration:**
- **Registry**: Port 35000 (kubespray-offline default, not 5000)
- **Nginx**: Port 80 (kubespray-offline default, not 8080)
- **Branches**: kubespray@master, kubespray-offline@main
- **Runtime Versions**: RUNC_VERSION=1.3.4, CONTAINERD_VERSION=2.1.5, NERDCTL_VERSION=2.1.6, CNI_VERSION=1.8.0
- **Container Versions**: NGINX_VERSION=1.29.2, REGISTRY_VERSION=2.8.3
- **Python Environments**:
  - **Build (Zone A)**: Python 3.12+ venv at `PROJECT_ROOT/venv` for build scripts
  - **Deploy (Zone C)**: Python 3.11+ venv at `~/.venv/kubespray` on bastion for Ansible/Kubespray

**Implementation Languages:**
- **Python 3.12+**: Asset validation, manifest generation, version checking (venv at PROJECT_ROOT/venv)
- **Bash**: Build orchestration, kubespray-offline integration, Zarf actions

**Key Dependencies:**
- Python 3.12+ (build environment)
- kubespray-offline@main (asset discovery + runtime setup)
- kubespray@master (cluster bootstrap)
- Zarf CLI (packaging + orchestration)
- Terraform (optional, OpenStack only)
- containerd (runtime on bastion + nodes)

## Tasks

- [x] 1. Setup project structure and integrate kubespray-offline
  - Create directory structure: `build/`, `scripts/build/`, `scripts/deploy/`, `tests/`, `assets/`, `config/`
  - Create Python 3.12+ virtual environment at project root: `python3.12 -m venv venv`
  - Install build dependencies: `pip install pyyaml jinja2 requests hypothesis pytest`
  - Clone kubespray-offline@main into `build/kubespray-offline/`
  - Configure `build/kubespray-offline/target-scripts/config.sh`: KUBESPRAY_VERSION=master, RUNC_VERSION=1.3.4, CONTAINERD_VERSION=2.1.5, NERDCTL_VERSION=2.1.6, CNI_VERSION=1.8.0, NGINX_VERSION=1.29.2, REGISTRY_VERSION=2.8.3, REGISTRY_PORT=35000
  - Create `build/kubespray-offline/imagelists/additional_images.txt` with openCenter platform service images (20+ services: FluxCD, Gitea, cert-manager, ingress-nginx, Gateway API, Keycloak, Prometheus, Grafana, Loki, Tempo, OpenTelemetry, Mimir, Longhorn, vSphere CSI, OpenStack CSI, Kyverno, OLM, RBAC Manager, Velero, Harbor, Headlamp, Weave GitOps, MetalLB, Sealed Secrets, Postgres Operator, Strimzi Kafka)
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.7, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

- [x] 2. Run kubespray-offline asset collection
  - [x] 2.1 Execute kubespray-offline download workflow
    - Run `download-all.sh` (orchestrates prepare-py, get-kubespray, pypi-mirror, download-kubespray-files, download-additional-containers, create-repo, copy-target-scripts)
    - Verify `outputs/` directory structure: files/, images/, debs/, pypi/, playbook/
    - Verify target-scripts copied: setup-all.sh, start-nginx.sh, start-registry.sh, load-push-all-images.sh, extract-kubespray.sh
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.7_

  - [x] 2.2 Validate kubespray-offline outputs
    - Verify K8s binaries present in outputs/files/kubernetes/, outputs/files/runc/, outputs/files/containerd-*.tar.gz, outputs/files/nerdctl-*.tar.gz, outputs/files/helm-*.tar.gz
    - Verify container images in outputs/images/ as tar.gz files (registry_2.8.3.tar.gz, nginx_1.29.2.tar.gz, kube-apiserver_*.tar.gz, etc.)
    - Verify DEB repository in outputs/debs/local/ (Packages.gz, Release files)
    - Verify PyPI mirror in outputs/pypi/simple/ directory structure
    - Verify offline-repo.yml playbook in outputs/playbook/
    - Verify kubespray-*.tar.gz tarball in outputs/
    - Verify target-scripts/ directory with setup-all.sh, start-nginx.sh, start-registry.sh, load-push-all-images.sh, extract-kubespray.sh, offline.yml template, config.sh
    - _Requirements: 1.7, 2.3_

- [x] 3. Implement Terraform provider collection
  - [x] 3.1 Create Terraform requirements file
    - Define required providers (local, null, tls, openstack)
    - Pin provider versions
    - _Requirements: 1.5_

  - [x] 3.2 Implement provider mirror download script
    - Execute `terraform providers mirror` for AMD64
    - Generate cross-platform lock file with `-platform=linux_amd64`
    - Verify lock file contains AMD64 hashes
    - _Requirements: 1.8_

  - [ ]* 3.3 Write property test for Terraform lock files
    - **Property 3: Terraform Lock File Cross-Platform Integrity**
    - **Validates: Requirements 1.8**

- [-] 4. Implement checksum utilities
  - [x] 4.1 Create checksum calculation utilities (Python 3.12+)
    - Create `scripts/build/checksum_utils.py` in project venv
    - Implement MD5 checksum calculation
    - Implement SHA256 checksum calculation
    - Implement file download utility with retry logic
    - _Requirements: 1.10, 2.6_

  - [ ]* 4.2 Write property test for checksum utilities
    - **Property 4: Checksum Verification Round-Trip**
    - Use pytest with hypothesis in project venv
    - **Validates: Requirements 1.10, 3.1, 3.2**

- [x] 5. Checkpoint - Verify asset collection
  - Run complete asset collection on kubespray@master with kubespray-offline@main
  - Verify all expected images, binaries, packages are present
  - Verify kubespray-offline outputs are complete
  - Ensure all tests pass, ask the user if questions arise

- [x] 7. Implement asset organization for Zarf
  - [x] 7.1 Create asset organization script
    - Create `scripts/build/organize_assets_for_zarf.sh` (uses project venv for Python scripts)
    - Copy kubespray-offline outputs/files/* to assets/k8s-binaries/
    - Copy kubespray-offline outputs/pypi/* to assets/python-wheels/
    - Copy kubespray-offline outputs/debs/* to assets/repos/apt/
    - Load container images from outputs/images/*.tar.gz into podman (gunzip | podman load)
    - Extract kubespray-*.tar.gz to assets/kubespray/
    - Copy target-scripts/* to assets/target-scripts/
    - Copy playbook/ to assets/playbook/
    - _Requirements: 2.3_

  - [x] 7.2 Validate asset organization (Python 3.12+)
    - Create `scripts/build/validate_assets.py` in project venv
    - Verify all directories created under assets/
    - Verify all images loaded into podman
    - Verify kubespray extracted correctly
    - _Requirements: 2.3_

- [x] 8. Implement version pinning validation
  - [x] 8.1 Create version specification parser (Python 3.12+)
    - Create `scripts/build/version_validator.py` in project venv
    - Detect "latest", "stable", wildcard versions in configs
    - Parse semantic version strings
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

  - [x] 8.2 Implement version pinning validator (Python 3.12+)
    - Scan all configuration files for version specifications
    - Fail if any unpinned versions found
    - Report all violations with file locations
    - _Requirements: 10.10_

  - [ ]* 8.3 Write property test for version pinning
    - **Property 25: Version Pinning Completeness**
    - Use pytest with hypothesis in project venv
    - **Validates: Requirements 10.1-10.7**

  - [ ]* 8.4 Write property test for version resolution
    - **Property 27: Version Resolution Strictness**
    - Use pytest with hypothesis in project venv
    - **Validates: Requirements 10.10**

- [x] 9. Implement Zarf package creation
  - [x] 9.1 Create zarf.yaml generator (Python 3.12+)
    - Create `scripts/build/generate_zarf_yaml.py` in project venv
    - Generate package metadata (name, version, architecture)
    - Define components (bootstrap-tools, terraform-providers, kubespray-core, k8s-images, deploy-cluster)
    - Configure component files, images, and actions
    - _Requirements: 2.1, 2.3, 2.10_

  - [x] 9.2 Implement asset organization script
    - Organize downloaded assets into component directories
    - Create filesystem mirror structure for Terraform providers
    - Copy Kubespray repository and binaries
    - _Requirements: 2.3_

  - [x] 9.3 Create package build script
    - Execute `zarf package create`
    - Verify package creation succeeds
    - Check package size < 10GB
    - _Requirements: 2.1, 2.8, 2.9_

  - [ ]* 9.4 Write property test for package creation
    - **Property 5: Package Asset Completeness**
    - Use pytest with hypothesis in project venv
    - **Validates: Requirements 2.1, 2.2, 2.3**

  - [ ]* 9.5 Write property test for package format
    - **Property 8: Package Format Consistency**
    - Use pytest with hypothesis in project venv
    - **Validates: Requirements 2.8, 2.9**

- [x] 10. Implement SBOM generation and verification
  - [x] 10.1 Integrate Syft SBOM generation
    - Configure Zarf to generate SBOM during package creation
    - Verify SBOM is embedded in package
    - _Requirements: 2.4, 2.5_

  - [x] 10.2 Implement SBOM completeness checker (Python 3.12+)
    - Create `scripts/build/verify_sbom.py` in project venv
    - Extract SBOM from package
    - Verify all images, binaries, packages are listed
    - Check version information is present
    - _Requirements: 2.4, 10.9_

  - [ ]* 10.3 Write property test for SBOM completeness
    - **Property 6: SBOM Completeness**
    - Use pytest with hypothesis in project venv
    - **Validates: Requirements 2.4, 2.5, 10.9**

- [x] 11. Implement package integrity features
  - [x] 11.1 Create checksum manifest generator
    - Generate MD5 and SHA256 for package file
    - Write checksums to manifest file
    - _Requirements: 2.6_

  - [x] 11.2 Implement package signing script (optional)
    - Sign package with Cosign if key provided
    - Generate signature file
    - _Requirements: 2.7_

  - [x] 11.3 Create package verification script
    - Verify checksums against manifest
    - Verify Cosign signature if present
    - Halt on verification failure
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 11.4 Write property test for integrity verification
    - **Property 7: Package Integrity Round-Trip**
    - **Validates: Requirements 2.6, 2.7, 3.3**

  - [ ]* 11.5 Write property test for corruption detection
    - **Property 9: Integrity Verification Error Detection**
    - **Validates: Requirements 3.4, 3.5**

- [ ]* 12. Checkpoint - Verify package creation
  - Build complete package with all assets
  - Verify SBOM contains all components
  - Verify checksums and signature (if enabled)
  - Ensure all tests pass, ask the user if questions arise

- [x] 13. Implement bastion setup scripts (integrate kubespray-offline)
  - [x] 13.1 Create Zarf component for kubespray-offline setup
    - Package kubespray-offline outputs/ directory in Zarf component "bastion-setup"
    - Package target-scripts/ in Zarf component
    - Create Zarf action to execute `target-scripts/setup-all.sh` on deploy
    - _Requirements: 4.2, 4.3, 4.8, 4.9, 4.11_

  - [x] 13.2 Validate setup-all.sh execution
    - Verify `setup-container.sh` installs containerd and loads nginx:1.29.2 and registry:2.8.3 images
    - Verify `start-nginx.sh` launches nginx on port 80 serving files/, debs/, pypi/ from outputs/
    - Verify `setup-offline.sh` configures apt sources.list and pip.conf to use bastion
    - Verify `setup-py.sh` installs Python 3.11 from local DEB repo and creates ~/.venv/kubespray
    - Verify `start-registry.sh` launches registry:2 on port 35000 with data in /var/lib/registry
    - Verify `load-push-all-images.sh` loads images from outputs/images/*.tar.gz and pushes to localhost:35000 with registry prefix stripping
    - _Requirements: 4.2, 4.3, 4.7, 4.8, 4.9, 4.10, 4.11_

  - [x] 13.3 Create bastion service verification script
    - Check nginx accessible: `curl http://localhost/files/`
    - Check registry accessible: `curl http://localhost:35000/v2/_catalog`
    - Check Python venv created: `test -d ~/.venv/kubespray`
    - Verify images in registry: `curl http://localhost:35000/v2/_catalog | jq .repositories`
    - _Requirements: 4.8, 4.9, 4.11, 4.12_

  - [ ]* 13.4 Write property test for Python wheel installation
    - **Property 11: Python Wheel Installation Completeness**
    - **Validates: Requirements 4.3**

  - [ ]* 13.5 Write property test for image registry round-trip
    - **Property 12: Container Image Registry Round-Trip**
    - **Validates: Requirements 4.7, 4.10**

- [x] 14. Collect openCenter platform service images (20+ services)
  - [x] 14.1 Create comprehensive openCenter platform image list
    - Extract image references from `assets/gitops-base/applications/` directory
    - Document FluxCD controller images (source-controller, kustomize-controller, helm-controller, notification-controller)
    - Document Gitea images
    - Document cert-manager images (controller, webhook, cainjector)
    - Document ingress-nginx and Gateway API images (controller, webhook-certgen, admission-server)
    - Document Keycloak images
    - Document observability stack images (Prometheus, Grafana, Loki, Tempo, OpenTelemetry, Mimir, Alertmanager, prometheus-operator, kube-state-metrics)
    - Document storage images (Longhorn, vSphere CSI, OpenStack CSI, External Snapshotter)
    - Document policy and security images (Kyverno, OLM, RBAC Manager, Sealed Secrets)
    - Document backup images (Velero with plugins)
    - Document additional service images (Harbor, Headlamp, Weave GitOps, MetalLB, Postgres Operator, Strimzi Kafka)
    - Create `config/opencenter-images.txt` with all image references
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.11, 5.12_

  - [x] 14.2 Integrate openCenter images with kubespray-offline
    - Copy `config/opencenter-images.txt` to `build/kubespray-offline/imagelists/additional_images.txt`
    - Modify `scripts/build/build.sh` to merge openCenter images before running kubespray-offline
    - Verify images are downloaded during asset collection (check `build/kubespray-offline/outputs/images/`)
    - Verify images are loaded into podman/docker during asset organization
    - _Requirements: 5.13_

  - [x] 14.3 Create openCenter image verification script
    - Create `scripts/deploy/verify_opencenter_images.sh`
    - Query bastion registry catalog: `curl http://localhost:35000/v2/_catalog`
    - For each openCenter image, verify it exists in registry
    - Check image tags: `curl http://localhost:35000/v2/<image>/tags/list`
    - Generate verification report with missing images (if any)
    - _Requirements: 5.14, 5.15_

  - [x] 14.4 Update SBOM to document openCenter images
    - Modify `scripts/build/verify_sbom.py` to check for openCenter images
    - Ensure SBOM includes all 20+ openCenter service images
    - Tag openCenter images in SBOM metadata
    - _Requirements: 5.16_

  - [x]* 14.5 Write property test for openCenter image availability
    - **Property 15: openCenter Platform Service Images Available**
    - Create `tests/property/test_opencenter_images.py`
    - Test that all openCenter images are pullable from bastion registry
    - **Validates: Requirements 5.13, 5.14, 5.15**

**Note:** Task 14 focuses on collecting and making available openCenter platform service images (20+ services). The actual deployment of these services (Gitea, FluxCD, cert-manager, ingress-nginx, Gateway API, Keycloak, observability stack, storage, policy, backup, and additional services) is handled by the openCenter platform (gitops-base) after bastion setup.

- [x] 15. Implement idempotency and recovery features (bastion operations)
- [x] 15. Implement idempotency and recovery features (bastion operations)
  - [x] 15.1 Verify kubespray-offline script idempotency
    - Test `setup-all.sh` re-run: should detect existing containerd installation, skip if present
    - Test `start-nginx.sh` re-run: should detect nginx container running on port 80, skip if present
    - Test `start-registry.sh` re-run: should detect registry container running on port 35000, skip if present
    - Test `load-push-all-images.sh` re-run: should check registry catalog, skip images already pushed
    - Document idempotency behavior in runbook
    - _Requirements: 6.1, 6.2, 6.3_

  - [ ]* 15.2 Write property test for deployment idempotency (bastion)
    - **Property 16: Deployment Idempotency (Bastion)**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.10**

- [x] 16. Implement logging infrastructure
- [x] 16. Implement logging infrastructure
  - [x] 16.1 Create logging utility module
    - Implement structured logging with timestamps
    - Write logs to persistent location on bastion
    - Support log levels (INFO, WARN, ERROR)
    - _Requirements: 9.1_

  - [x] 16.2 Integrate logging into all scripts
    - Log bastion setup output
    - Log image push output
    - Log Zarf action output
    - Capture stderr and stdout
    - _Requirements: 9.2, 9.3, 9.4_

  - [x] 16.3 Implement error logging with context
    - Log stack traces on errors
    - Log error context (component, operation, inputs)
    - _Requirements: 9.5, 6.12, 6.8_

  - [x] 16.4 Create deployment summary generator
    - Generate summary report with timestamps
    - List completed phases and durations
    - List any errors or warnings
    - _Requirements: 9.6_

  - [x] 16.5 Implement log rotation
    - Rotate logs when size exceeds threshold
    - Preserve logs across re-runs with timestamps
    - _Requirements: 9.7, 9.8_

  - [ ]* 16.6 Write property test for logging completeness
    - **Property 25: Operation Logging Completeness**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6**

  - [ ]* 16.7 Write property test for log persistence
    - **Property 26: Log Persistence Across Re-runs**
    - **Validates: Requirements 9.8**

- [x] 17. Implement offline operation validation
- [x] 17. Implement offline operation validation
  - [x] 17.1 Create network connection monitor
    - Log all network connections (source, dest, port)
    - Detect connections to external IPs
    - _Requirements: 7.7_

  - [x] 17.2 Integrate network monitoring into deployment
    - Start monitoring before deployment
    - Stop monitoring after deployment
    - Analyze logs for external connections
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 17.3 Implement external access detection
    - Fail deployment if external connection detected
    - Log clear error with component and target address
    - _Requirements: 7.8_

  - [x]* 17.4 Write property test for offline compliance
    - **Property 19: Offline Operation Compliance**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6**

  - [x]* 17.5 Write property test for connection logging
    - **Property 20: Network Connection Logging**
    - **Validates: Requirements 7.7**

  - [x]* 17.6 Write property test for external access detection
    - **Property 21: External Access Detection**
    - **Validates: Requirements 7.8**

- [x] 18. Implement component independence
  - [x] 18.1 Verify Zarf component dependencies
    - Review `zarf.yaml` component definitions
    - Ensure components declare explicit dependencies via `required` field
    - Test deploying individual components: `zarf package deploy --components=<component>`
    - Verify components can be deployed independently when dependencies are met
    - _Requirements: 6.9_

  - [ ]* 18.2 Write property test for component independence
    - **Property 18: Component Independence**
    - Create `tests/property/test_component_independence.py`
    - Test that components with satisfied dependencies can deploy independently
    - **Validates: Requirements 6.9**

- [x] 19. Implement build determinism validation
  - [x] 19.1 Create image list snapshot utility
    - Create `scripts/build/snapshot_image_list.py`
    - Extract image names, tags, and digests from Zarf package
    - Export to JSON format for comparison
    - _Requirements: 8.8_

  - [x] 19.2 Create image list comparison utility
    - Create `scripts/build/compare_image_lists.py`
    - Compare two image list snapshots (JSON files)
    - Report differences in images, tags, or digests
    - Exit with error if differences found
    - _Requirements: 8.8_

  - [x] 19.3 Create build determinism test script
    - Create `tests/integration/test_build_determinism.sh`
    - Build package twice with same configuration
    - Generate snapshots for both builds
    - Compare snapshots and verify identical
    - _Requirements: 8.8_

  - [ ]* 19.4 Write property test for build determinism
    - **Property 23: Build Determinism**
    - Create `tests/property/test_build_determinism.py`
    - Test that identical configurations produce identical image lists
    - **Validates: Requirements 8.8**

- [ ]* 20. Checkpoint - Verify complete system
  - Build package from scratch: `./scripts/build/build.sh`
  - Deploy to test bastion: `./scripts/deploy/deploy.sh --mode baremetal --bastion-ip <ip> --nodes nodes.yaml`
  - Verify all services running: `./scripts/deploy/verify_bastion_services.sh`
  - Verify offline operation: Check network monitor logs for zero external connections
  - Verify idempotency: Re-run deployment, verify no state changes
  - Verify all K8s images available in registry
  - Verify all openCenter images available in registry (20+ services)
  - Run property tests: `pytest tests/property/ -v`
  - Run integration tests: `./tests/integration/test_airgap_deployment.py`
  - Ensure all tests pass, ask the user if questions arise

- [-] 21. Create build automation script
- [ ] 21. Create build automation script
  - [ ] 21.1 Create master build script
    - Create `scripts/build/build.sh` that orchestrates the complete build process
    - Step 0: Verify Python 3.12+ available and activate project venv
    - Step 1: Run kubespray-offline `download-all.sh` (asset discovery and download)
    - Step 2: Execute `organize_assets_for_zarf.sh` (organize outputs for Zarf)
    - Step 3: Execute version validation using `version_validator.py` (check for unpinned versions)
    - Step 4: Execute Zarf package creation using `generate_zarf_yaml.py` then `zarf package create`
    - Step 5: Execute SBOM generation (via Zarf)
    - Step 6: Execute checksum generation using `checksum_utils.py` (MD5 and SHA256)
    - Step 7: Execute signing (if enabled, via Cosign)
    - _Requirements: All build phase requirements_

  - [ ] 21.2 Add build validation
    - Verify Python version >= 3.12: `python --version`
    - Verify project venv exists and activated: `which python` should show PROJECT_ROOT/venv/bin/python
    - Verify kubespray-offline outputs/ directory populated
    - Verify all assets organized under assets/
    - Verify all images loaded into podman
    - Verify package created successfully (*.tar.zst exists)
    - Verify SBOM embedded in package using `verify_sbom.py`
    - Verify checksums correct (recompute and compare)
    - Verify package size < 10GB
    - _Requirements: All build phase requirements_

- [x] 22. Create deployment automation script
  - [x] 22.1 Create master deployment script
    - Create `scripts/deploy/deploy.sh` that orchestrates bastion setup
    - Accept parameters: bastion_ip
    - Step 1: Execute package verification (checksums, signature)
    - Step 2: Execute Zarf package deploy (extracts to bastion, runs setup-all.sh)
    - Step 3: Execute bastion service verification (registry, nginx)
    - Step 4: Execute image availability verification
    - _Requirements: All deployment phase requirements_

  - [x] 22.2 Add deployment validation
    - Verify package integrity before extraction
    - Verify bastion services running (nginx:80, registry:35000)
    - Verify all images available in registry
    - Generate deployment summary report
    - _Requirements: All deployment phase requirements_

- [x] 23. Create documentation
  - [x] 23.1 Write build runbook
    - Prerequisites: Python 3.12+, podman, git, internet connectivity, 50GB disk space
    - Environment setup: `python3.12 -m venv venv && source venv/bin/activate && pip install pyyaml jinja2 requests`
    - Configuration: Edit config.sh (KUBESPRAY_VERSION, runtime versions, registry port)
    - Configuration: Edit additional_images.txt (add platform service images - 20+ services)
    - Step-by-step build instructions: Run build.sh, verify outputs
    - Troubleshooting: Python version mismatch, kubespray-offline download failures, podman image load failures, package size exceeded
    - _Requirements: 10.1_

  - [x] 23.2 Write bastion setup runbook
    - Prerequisites: Bastion host (Ubuntu 24.04, 100GB disk, podman)
    - Step-by-step deployment: Transfer package, run deploy.sh --bastion-ip <ip>
    - Verification: Check bastion services (curl localhost:80, curl localhost:35000/v2/_catalog)
    - Handoff contract: Document what openCenter platform receives (registry with all images, nginx with binaries/packages)
    - _Requirements: 10.2, 10.5, 10.6, 10.9_

  - [x] 23.3 Write troubleshooting guide
    - Common failure modes: Registry startup failure (port conflict), image push failure (disk space), nginx startup failure
    - Recovery procedures: Re-run setup-all.sh (bastion), stop/remove containers, check disk space
    - Log locations: /opt/opencenter/logs/, /var/lib/registry/
    - Log analysis: Search for ERROR, check container logs
    - _Requirements: 10.7, 10.8_

  - [x] 23.4 Write extension guide
    - How to add new services: Add image to additional_images.txt, rebuild package
    - How to update versions: Edit config.sh (runtime versions), edit additional_images.txt (image tags), rebuild package
    - How to rebuild package: Run build.sh, verify new package
    - _Requirements: 10.10_

  - [x] 23.5 Document Zarf variables
    - BASTION_IP: IP address of bastion host (required)
    - INSTALL_PATH: Installation directory on bastion (default: /opt/opencenter)
    - REGISTRY_PORT: Registry port (default: 35000, from kubespray-offline)
    - NGINX_PORT: Nginx port (default: 80, from kubespray-offline)
    - _Requirements: 10.4_

- [ ]* 24. Final integration testing
  - [ ] 24.1 Test complete build-deploy cycle
    - Build: Run `./scripts/build/build.sh` on connected system
    - Verify package created in `dist/` directory
    - Verify SBOM generated and complete
    - Transfer: Copy `dist/zarf-package-*.tar.zst` to air-gapped bastion
    - Deploy: Run `./scripts/deploy/deploy.sh --mode baremetal --bastion-ip <ip> --nodes nodes.yaml`
    - Verify bastion: `curl localhost:80/files/`, `curl localhost:35000/v2/_catalog`
    - Verify K8s images: Check all Kubernetes images available in registry
    - Verify openCenter images: Check all 20+ platform service images available
    - Verify offline: Review network monitor logs, confirm zero external connections

  - [ ] 24.2 Test failure recovery scenarios
    - Simulate registry failure: Stop registry container mid-deployment
    - Verify recovery: Re-run `scripts/deploy/verify_bastion_services.sh`, re-run deployment
    - Simulate nginx failure: Stop nginx container mid-deployment
    - Verify recovery: Re-run bastion setup, verify services restored
    - Simulate image push failure: Fill disk to trigger push error
    - Verify recovery: Free disk space, re-run image push

  - [ ] 24.3 Test idempotency
    - Deploy package: Run `./scripts/deploy/deploy.sh` with full parameters
    - Verify successful deployment: Check all services running
    - Re-deploy same package: Run `./scripts/deploy/deploy.sh` again with identical parameters
    - Verify no changes: Compare bastion state before/after (container list, registry catalog)
    - Verify logs: Check deployment logs show "skipped" or "ok" for all operations
    - Verify performance: Second deployment should complete faster (no downloads/pushes)

  - [ ] 24.4 Test package corruption detection
    - Create test package: Build or copy existing package
    - Modify package bytes: Use `dd if=/dev/urandom of=<package> bs=1 count=100 seek=1000 conv=notrunc`
    - Verify deployment halts: Run `./scripts/deploy/verify_package.sh <package>`
    - Verify error message: Check logs show checksum mismatch with expected vs actual values
    - Verify no extraction: Confirm package was not extracted to bastion

- [ ]* 25. Final checkpoint - Production readiness
  - All core functionality implemented and tested
  - Property tests implemented for offline compliance (3 properties complete, 23 optional remaining)
  - Integration tests passing for core deployment scenarios
  - Documentation complete (build, deployment, troubleshooting)
  - Build and bastion setup runbooks validated
  - openCenter platform service images collected and available (20+ services)
  - System ready for handoff to openCenter platform for infrastructure provisioning, cluster bootstrap, and service deployment

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Property-based tests (marked with `*`) provide formal verification but are not required for basic functionality
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation throughout implementation
- **Core functionality is complete**: Build system, deployment system, logging, network monitoring, and documentation are all implemented
- **Remaining work focuses on**:
  1. openCenter platform service image collection (Task 14) - Required for platform deployment
  2. Optional property-based tests (23 properties) - For formal verification
  3. Optional integration tests - For end-to-end validation
  4. Optional component independence testing - For advanced deployment scenarios
  5. Optional build determinism validation - For reproducibility verification
- **Python 3.12+ Environment**: All Python scripts run in project root venv (`PROJECT_ROOT/venv`)
- **Bastion Python Environment**: Separate venv (`~/.venv/kubespray`) created by kubespray-offline on bastion for Ansible/Kubespray
- Mixed language approach: Python 3.12+ for complex logic, Bash for orchestration
- All scripts must be idempotent and handle re-runs gracefully
- All operations must complete without internet access during deployment
