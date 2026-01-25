# Implementation Plan: openCenter AirGap

## Overview

This implementation plan integrates **kubespray-offline@main** as the foundation for K8s asset collection and runtime setup, packaged and orchestrated by **Zarf**.

**Integration Model:**
- **Build Phase (Zone A)**: Execute kubespray-offline `download-all.sh` to populate `outputs/` directory
- **Package Phase (Zone A→B)**: Zarf bundles kubespray-offline outputs + target scripts into single artifact
- **Deploy Phase (Zone C)**: Zarf extracts and executes kubespray-offline `setup-all.sh` on bastion
- **Bootstrap Phase (Zone C)**: Zarf runs Kubespray with `offline.yml` pointing to bastion services (nginx:80, registry:35000)
- **GitOps Phase (Zone C)**: Zarf deploys FluxCD + Gitea + core services post-cluster

**kubespray-offline Workflow:**
1. **Download**: `download-all.sh` → `outputs/{files,images,debs,pypi,playbook,kubespray-*.tar.gz,target-scripts}`
2. **Setup**: `setup-all.sh` → `setup-container.sh`, `start-nginx.sh`, `start-registry.sh`, `load-push-all-images.sh`
3. **Deploy**: `extract-kubespray.sh` + `ansible-playbook cluster.yml` with `offline.yml`

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
  - Create `build/kubespray-offline/imagelists/additional_images.txt` with FluxCD, cert-manager, ingress-nginx, Keycloak, kube-prometheus-stack images
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.7_

- [-] 2. Run kubespray-offline asset collection
  - [ ] 2.1 Execute kubespray-offline download workflow
    - Run `download-all.sh` (orchestrates prepare-py, get-kubespray, pypi-mirror, download-kubespray-files, download-additional-containers, create-repo, copy-target-scripts)
    - Verify `outputs/` directory structure: files/, images/, debs/, pypi/, playbook/
    - Verify target-scripts copied: setup-all.sh, start-nginx.sh, start-registry.sh, load-push-all-images.sh, extract-kubespray.sh
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.7_
  
  - [ ] 2.2 Validate kubespray-offline outputs
    - Verify K8s binaries present in outputs/files/kubernetes/, outputs/files/runc/, outputs/files/containerd-*.tar.gz, outputs/files/nerdctl-*.tar.gz, outputs/files/helm-*.tar.gz
    - Verify container images in outputs/images/ as tar.gz files (registry_2.8.3.tar.gz, nginx_1.29.2.tar.gz, kube-apiserver_*.tar.gz, etc.)
    - Verify DEB repository in outputs/debs/local/ (Packages.gz, Release files)
    - Verify PyPI mirror in outputs/pypi/simple/ directory structure
    - Verify offline-repo.yml playbook in outputs/playbook/
    - Verify kubespray-*.tar.gz tarball in outputs/
    - Verify target-scripts/ directory with setup-all.sh, start-nginx.sh, start-registry.sh, load-push-all-images.sh, extract-kubespray.sh, offline.yml template, config.sh
    - _Requirements: 1.7, 2.3_

- [ ] 3. Implement Terraform provider collection
  - [ ] 3.1 Create Terraform requirements file
    - Define required providers (local, null, tls, openstack)
    - Pin provider versions
    - _Requirements: 1.5_
  
  - [ ] 3.2 Implement provider mirror download script
    - Execute `terraform providers mirror` for AMD64
    - Generate cross-platform lock file with `-platform=linux_amd64`
    - Verify lock file contains AMD64 hashes
    - _Requirements: 1.8_
  
  - [ ]* 3.3 Write property test for Terraform lock files
    - **Property 3: Terraform Lock File Cross-Platform Integrity**
    - **Validates: Requirements 1.8**

- [ ] 4. Implement checksum utilities
  - [ ] 4.1 Create checksum calculation utilities (Python 3.12+)
    - Create `scripts/build/checksum_utils.py` in project venv
    - Implement MD5 checksum calculation
    - Implement SHA256 checksum calculation
    - Implement file download utility with retry logic
    - _Requirements: 1.10, 2.6_
  
  - [ ]* 4.2 Write property test for checksum utilities
    - **Property 4: Checksum Verification Round-Trip**
    - Use pytest with hypothesis in project venv
    - **Validates: Requirements 1.10, 3.1, 3.2**

- [ ] 5. Checkpoint - Verify asset collection
  - Run complete asset collection on kubespray@master with kubespray-offline@main
  - Verify all expected images, binaries, packages are present
  - Verify kubespray-offline outputs are complete
  - Ensure all tests pass, ask the user if questions arise

- [ ] 7. Implement asset organization for Zarf
  - [ ] 7.1 Create asset organization script
    - Create `scripts/build/organize_assets_for_zarf.sh` (uses project venv for Python scripts)
    - Copy kubespray-offline outputs/files/* to assets/k8s-binaries/
    - Copy kubespray-offline outputs/pypi/* to assets/python-wheels/
    - Copy kubespray-offline outputs/debs/* to assets/repos/apt/
    - Load container images from outputs/images/*.tar.gz into podman (gunzip | podman load)
    - Extract kubespray-*.tar.gz to assets/kubespray/
    - Copy target-scripts/* to assets/target-scripts/
    - Copy playbook/ to assets/playbook/
    - _Requirements: 2.3_
  
  - [ ] 7.2 Validate asset organization (Python 3.12+)
    - Create `scripts/build/validate_assets.py` in project venv
    - Verify all directories created under assets/
    - Verify all images loaded into podman
    - Verify kubespray extracted correctly
    - _Requirements: 2.3_

- [ ] 8. Implement version pinning validation
  - [ ] 8.1 Create version specification parser (Python 3.12+)
    - Create `scripts/build/version_validator.py` in project venv
    - Detect "latest", "stable", wildcard versions in configs
    - Parse semantic version strings
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_
  
  - [ ] 8.2 Implement version pinning validator (Python 3.12+)
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

- [ ] 9. Implement Zarf package creation
  - [ ] 9.1 Create zarf.yaml generator (Python 3.12+)
    - Create `scripts/build/generate_zarf_yaml.py` in project venv
    - Generate package metadata (name, version, architecture)
    - Define components (bootstrap-tools, terraform-providers, kubespray-core, k8s-images, deploy-cluster)
    - Configure component files, images, and actions
    - _Requirements: 2.1, 2.3, 2.10_
  
  - [ ] 9.2 Implement asset organization script
    - Organize downloaded assets into component directories
    - Create filesystem mirror structure for Terraform providers
    - Copy Kubespray repository and binaries
    - _Requirements: 2.3_
  
  - [ ] 9.3 Create package build script
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

- [ ] 10. Implement SBOM generation and verification
  - [ ] 10.1 Integrate Syft SBOM generation
    - Configure Zarf to generate SBOM during package creation
    - Verify SBOM is embedded in package
    - _Requirements: 2.4, 2.5_
  
  - [ ] 10.2 Implement SBOM completeness checker (Python 3.12+)
    - Create `scripts/build/verify_sbom.py` in project venv
    - Extract SBOM from package
    - Verify all images, binaries, packages are listed
    - Check version information is present
    - _Requirements: 2.4, 10.9_
  
  - [ ]* 10.3 Write property test for SBOM completeness
    - **Property 6: SBOM Completeness**
    - Use pytest with hypothesis in project venv
    - **Validates: Requirements 2.4, 2.5, 10.9**

- [ ] 11. Implement package integrity features
  - [ ] 11.1 Create checksum manifest generator
    - Generate MD5 and SHA256 for package file
    - Write checksums to manifest file
    - _Requirements: 2.6_
  
  - [ ] 11.2 Implement package signing script (optional)
    - Sign package with Cosign if key provided
    - Generate signature file
    - _Requirements: 2.7_
  
  - [ ] 11.3 Create package verification script
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

- [ ] 12. Checkpoint - Verify package creation
  - Build complete package with all assets
  - Verify SBOM contains all components
  - Verify checksums and signature (if enabled)
  - Ensure all tests pass, ask the user if questions arise

- [ ] 13. Implement bastion setup scripts (integrate kubespray-offline)
  - [ ] 13.1 Create Zarf component for kubespray-offline setup
    - Package kubespray-offline outputs/ directory in Zarf component "bastion-setup"
    - Package target-scripts/ in Zarf component
    - Create Zarf action to execute `target-scripts/setup-all.sh` on deploy
    - _Requirements: 4.2, 4.3, 4.8, 4.9, 4.11_
  
  - [ ] 13.2 Validate setup-all.sh execution
    - Verify `setup-container.sh` installs containerd and loads nginx:1.29.2 and registry:2.8.3 images
    - Verify `start-nginx.sh` launches nginx on port 80 serving files/, debs/, pypi/ from outputs/
    - Verify `setup-offline.sh` configures apt sources.list and pip.conf to use bastion
    - Verify `setup-py.sh` installs Python 3.11 from local DEB repo and creates ~/.venv/kubespray
    - Verify `start-registry.sh` launches registry:2 on port 35000 with data in /var/lib/registry
    - Verify `load-push-all-images.sh` loads images from outputs/images/*.tar.gz and pushes to localhost:35000 with registry prefix stripping
    - _Requirements: 4.2, 4.3, 4.7, 4.8, 4.9, 4.10, 4.11_
  
  - [ ] 13.3 Create bastion service verification script
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

- [ ] 14. Implement Terraform configuration
  - [ ] 14.1 Create .terraformrc generator
    - Generate config pointing to filesystem mirror
    - Set plugin_cache_dir and disable_checkpoint
    - _Requirements: 4.5, 4.6_
  
  - [ ] 14.2 Create Terraform init wrapper script
    - Execute `terraform init` with filesystem mirror
    - Verify initialization succeeds without network
    - _Requirements: 5.1_
  
  - [ ]* 14.3 Write property test for Terraform offline init
    - **Property 14: Terraform Filesystem Mirror Resolution**
    - **Validates: Requirements 5.1**

- [ ] 15. Implement Kubespray inventory generation (use kubespray-offline templates)
  - [ ] 15.1 Create offline.yml generator from kubespray-offline template
    - Copy kubespray-offline target-scripts/offline.yml template
    - Replace YOUR_HOST placeholder with bastion IP variable
    - Configure registry_host: `{{ bastion_ip }}:35000`
    - Configure http_server: `http://{{ bastion_ip }}`
    - Configure containerd_registries_mirrors with insecure registry support
    - Configure download URLs: files_repo, ubuntu_repo, kubeadm_download_url, kubectl_download_url, kubelet_download_url, etc.
    - Configure image repos: kube_image_repo, gcr_image_repo, podman_image_repo, quay_image_repo, github_image_repo
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  
  - [ ] 15.2 Create inventory generator for bare-metal mode
    - Accept node list from user input (JSON or YAML)
    - Generate Ansible inventory file (inventory/mycluster/hosts.yaml) with control_plane, etcd, kube_node groups
    - Copy offline.yml to inventory/mycluster/group_vars/all/offline.yml with bastion IP substituted
    - _Requirements: 5.10, 6.1_
  
  - [ ] 15.3 Create inventory generator for OpenStack mode
    - Parse Terraform outputs (control_plane_ips, worker_ips)
    - Generate Ansible inventory from provisioned VMs
    - Copy offline.yml to inventory/mycluster/group_vars/all/offline.yml with bastion IP substituted
    - _Requirements: 5.6, 6.1_
  
  - [ ] 15.4 Create Zarf action to run offline-repo.yml playbook
    - Execute `ansible-playbook -i inventory/mycluster/hosts.yaml playbook/offline-repo.yml`
    - Verify playbook configures /etc/apt/sources.list.d/offline.list on all nodes
    - Verify playbook configures /etc/pip.conf on all nodes
    - _Requirements: 6.1, 6.7, 6.8_
  
  - [ ]* 15.5 Write property test for Kubespray offline config
    - **Property 16: Kubespray Offline Configuration Completeness**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

- [ ] 16. Implement deployment orchestration scripts (integrate kubespray-offline workflow)
  - [ ] 16.1 Create main deployment script
    - Accept deployment mode (baremetal/openstack)
    - Accept bastion IP and SSH user
    - Orchestrate deployment phases
    - _Requirements: 5.9, 5.10_
  
  - [ ] 16.2 Create Terraform execution script (OpenStack mode)
    - Execute terraform init, plan, apply
    - Generate inventory from outputs
    - Preserve state on failure
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_
  
  - [ ] 16.3 Create Kubespray execution script (use kubespray-offline workflow)
    - Execute `target-scripts/extract-kubespray.sh` to extract kubespray-*.tar.gz to kubespray-master/
    - Activate Python venv: `source ~/.venv/kubespray/bin/activate`
    - Install Ansible: `cd kubespray-master && pip install -r requirements.txt`
    - Copy inventory: `cp -r inventory/sample inventory/mycluster`
    - Generate hosts.yaml (bare-metal: from user input, OpenStack: from Terraform outputs)
    - Copy offline.yml to inventory/mycluster/group_vars/all/offline.yml with bastion IP substituted
    - Run offline-repo.yml playbook: `ansible-playbook -i inventory/mycluster/hosts.yaml ../playbook/offline-repo.yml`
    - Execute cluster.yml: `ansible-playbook -i inventory/mycluster/hosts.yaml --become cluster.yml`
    - Export kubeconfig: `cp inventory/mycluster/artifacts/admin.conf ~/.kube/config`
    - _Requirements: 6.5, 6.6, 6.7, 6.8, 6.11_
  
  - [ ] 16.4 Create cluster health verification script
    - Check control plane component health
    - Check node Ready status
    - Report unhealthy components
    - _Requirements: 6.9, 6.10_
  
  - [ ]* 16.5 Write property test for cluster health verification
    - **Property 17: Cluster Health Verification**
    - **Validates: Requirements 6.9, 6.10**

- [ ] 17. Checkpoint - Verify deployment orchestration
  - Test deployment in bare-metal mode (simulated with VMs)
  - Verify all bastion services start correctly
  - Verify Kubespray executes without errors
  - Ensure all tests pass, ask the user if questions arise

- [ ] 18. Implement core services deployment
  - [ ] 18.1 Create Gitea deployment manifests
    - Define Deployment, Service, PVC for Gitea
    - Configure admin credentials
    - _Requirements: 7.1_
  
  - [ ] 18.2 Create repository seeding script
    - Initialize Git repository in Gitea
    - Push FluxCD manifests
    - Push core service manifests (cert-manager, ingress-nginx, Keycloak, kube-prometheus-stack)
    - _Requirements: 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_
  
  - [ ] 18.3 Create FluxCD installation script
    - Install FluxCD controllers
    - Create GitRepository resource pointing to Gitea
    - Create Kustomization resources for core services
    - _Requirements: 7.8, 7.9, 7.10_
  
  - [ ] 18.4 Create service readiness verification script
    - Check pod status for all core services
    - Check Ingress resources exist
    - Verify endpoints are valid
    - _Requirements: 7.11, 7.12_
  
  - [ ]* 18.5 Write property test for service readiness
    - **Property 18: Core Services Readiness**
    - **Validates: Requirements 7.11, 7.12**

- [ ] 19. Implement idempotency and recovery features (kubespray-offline scripts are idempotent)
  - [ ] 19.1 Verify kubespray-offline script idempotency
    - Test `setup-all.sh` re-run: should detect existing containerd installation, skip if present
    - Test `start-nginx.sh` re-run: should detect nginx container running on port 80, skip if present
    - Test `start-registry.sh` re-run: should detect registry container running on port 35000, skip if present
    - Test `load-push-all-images.sh` re-run: should check registry catalog, skip images already pushed
    - Document idempotency behavior in runbook
    - _Requirements: 8.1, 8.2, 8.3_
  
  - [ ] 19.2 Add idempotency checks to Terraform scripts
    - Use existing state if present
    - Skip apply if resources already exist
    - _Requirements: 8.4_
  
  - [ ] 19.3 Verify Kubespray idempotency
    - Test cluster.yml re-run on healthy cluster (should report "ok" for all tasks, no "changed")
    - Verify no changes made to cluster state
    - Document expected behavior in runbook
    - _Requirements: 8.5_
  
  - [ ] 19.4 Add idempotency checks to FluxCD installation
    - Check if FluxCD already installed: `kubectl get ns flux-system`
    - If exists, update resources using `flux install` (idempotent)
    - If not exists, install FluxCD
    - Document behavior in runbook
    - _Requirements: 8.6_
  
  - [ ]* 19.5 Write property test for deployment idempotency
    - **Property 19: Deployment Idempotency**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.10**

- [ ] 20. Implement logging infrastructure
  - [ ] 20.1 Create logging utility module
    - Implement structured logging with timestamps
    - Write logs to persistent location on bastion
    - Support log levels (INFO, WARN, ERROR)
    - _Requirements: 11.1_
  
  - [ ] 20.2 Integrate logging into all scripts
    - Log Terraform output
    - Log Ansible output
    - Log Zarf action output
    - Capture stderr and stdout
    - _Requirements: 11.2, 11.3, 11.4_
  
  - [ ] 20.3 Implement error logging with context
    - Log stack traces on errors
    - Log error context (component, operation, inputs)
    - _Requirements: 11.5, 6.12, 8.8_
  
  - [ ] 20.4 Create deployment summary generator
    - Generate summary report with timestamps
    - List completed phases and durations
    - List any errors or warnings
    - _Requirements: 11.6_
  
  - [ ] 20.5 Implement log rotation
    - Rotate logs when size exceeds threshold
    - Preserve logs across re-runs with timestamps
    - _Requirements: 11.7, 11.8_
  
  - [ ]* 20.6 Write property test for logging completeness
    - **Property 28: Operation Logging Completeness**
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5, 11.6**
  
  - [ ]* 20.7 Write property test for log persistence
    - **Property 29: Log Persistence Across Re-runs**
    - **Validates: Requirements 11.8**

- [ ] 21. Implement offline operation validation
  - [ ] 21.1 Create network connection monitor
    - Log all network connections (source, dest, port)
    - Detect connections to external IPs
    - _Requirements: 9.7_
  
  - [ ] 21.2 Integrate network monitoring into deployment
    - Start monitoring before deployment
    - Stop monitoring after deployment
    - Analyze logs for external connections
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_
  
  - [ ] 21.3 Implement external access detection
    - Fail deployment if external connection detected
    - Log clear error with component and target address
    - _Requirements: 9.8_
  
  - [ ]* 21.4 Write property test for offline compliance
    - **Property 22: Offline Operation Compliance**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6**
  
  - [ ]* 21.5 Write property test for connection logging
    - **Property 23: Network Connection Logging**
    - **Validates: Requirements 9.7**
  
  - [ ]* 21.6 Write property test for external access detection
    - **Property 24: External Access Detection**
    - **Validates: Requirements 9.8**

- [ ] 22. Implement component independence
  - [ ] 22.1 Add component dependency checking
    - Verify dependencies are deployed before component
    - Allow independent component deployment
    - _Requirements: 8.9_
  
  - [ ]* 22.2 Write property test for component independence
    - **Property 21: Component Independence**
    - **Validates: Requirements 8.9**

- [ ] 23. Implement determinism validation
  - [ ] 23.1 Create cluster state snapshot utility
    - Capture resource counts, versions, configurations
    - Export to comparable format (JSON)
    - _Requirements: 10.8_
  
  - [ ] 23.2 Create state comparison utility
    - Compare two cluster state snapshots
    - Report differences
    - _Requirements: 10.8_
  
  - [ ]* 23.3 Write property test for deployment determinism
    - **Property 26: Deployment Determinism**
    - **Validates: Requirements 10.8**

- [ ] 24. Checkpoint - Verify complete system
  - Build package from scratch
  - Deploy to test environment (bare-metal mode)
  - Verify all services running
  - Verify offline operation (no external connections)
  - Verify idempotency (re-run deployment)
  - Ensure all tests pass, ask the user if questions arise

- [ ] 25. Create build automation script
  - [ ] 25.1 Create master build script
    - Create `scripts/build/build.sh` that orchestrates the complete build process
    - Step 0: Verify Python 3.12+ available and activate project venv
    - Step 1: Run kubespray-offline `download-all.sh` (asset discovery and download)
    - Step 2: Execute `organize_assets_for_zarf.sh` (organize outputs for Zarf)
    - Step 3: Execute Terraform provider collection (if OpenStack mode enabled)
    - Step 4: Execute version validation using `version_validator.py` (check for unpinned versions)
    - Step 5: Execute Zarf package creation using `generate_zarf_yaml.py` then `zarf package create`
    - Step 6: Execute SBOM generation (via Zarf)
    - Step 7: Execute checksum generation using `checksum_utils.py` (MD5 and SHA256)
    - Step 8: Execute signing (if enabled, via Cosign)
    - _Requirements: All build phase requirements_
  
  - [ ] 25.2 Add build validation
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

- [ ] 26. Create deployment automation script
  - [ ] 26.1 Create master deployment script
    - Create `scripts/deploy/deploy.sh` that orchestrates the complete deployment
    - Accept parameters: deployment_mode (baremetal/openstack), bastion_ip, ssh_user, inventory_file (baremetal) or openstack_config (openstack)
    - Step 1: Execute package verification (checksums, signature)
    - Step 2: Execute Zarf package deploy (extracts to bastion, runs setup-all.sh)
    - Step 3: Execute infrastructure provisioning (if OpenStack mode: terraform init/plan/apply)
    - Step 4: Execute inventory generation (baremetal: from file, openstack: from terraform outputs)
    - Step 5: Execute cluster bootstrap (extract-kubespray.sh, ansible-playbook cluster.yml)
    - Step 6: Execute cluster health verification
    - Step 7: Execute core services deployment (Gitea, FluxCD, cert-manager, etc.)
    - Step 8: Execute service readiness verification
    - _Requirements: All deployment phase requirements_
  
  - [ ] 26.2 Add deployment validation
    - Verify package integrity before extraction
    - Verify bastion services running (nginx:80, registry:35000)
    - Verify cluster healthy (control plane components, node Ready status)
    - Verify core services running (pod status, ingress endpoints)
    - Generate deployment summary report
    - _Requirements: All deployment phase requirements_

- [ ] 27. Create documentation
  - [ ] 27.1 Write build runbook
    - Prerequisites: Python 3.12+, podman, git, internet connectivity, 50GB disk space
    - Environment setup: `python3.12 -m venv venv && source venv/bin/activate && pip install pyyaml jinja2 requests`
    - Configuration: Edit config.sh (KUBESPRAY_VERSION, runtime versions, registry port)
    - Configuration: Edit additional_images.txt (add core services images)
    - Step-by-step build instructions: Run build.sh, verify outputs
    - Troubleshooting: Python version mismatch, kubespray-offline download failures, podman image load failures, package size exceeded
    - _Requirements: 12.1_
  
  - [ ] 27.2 Write deployment runbook for bare-metal
    - Prerequisites: Bastion host (Ubuntu 24.04, 100GB disk, podman), target nodes (Ubuntu 24.04, SSH access)
    - Inventory preparation: Create hosts.yaml with control_plane, etcd, kube_node groups
    - Step-by-step deployment: Transfer package, run deploy.sh --mode baremetal --inventory hosts.yaml
    - Verification: Check bastion services (curl localhost:80, curl localhost:35000/v2/_catalog), check cluster (kubectl get nodes), check services (kubectl get pods -A)
    - _Requirements: 12.2, 12.5, 12.6, 12.9_
  
  - [ ] 27.3 Write deployment runbook for OpenStack
    - Prerequisites: Bastion host (Ubuntu 24.04, 100GB disk, podman, Terraform), OpenStack credentials
    - Cloud credentials setup: Create openstack_config.yaml with auth_url, project, credentials
    - Step-by-step deployment: Transfer package, run deploy.sh --mode openstack --config openstack_config.yaml
    - Verification: Check Terraform state, check bastion services, check cluster, check services
    - _Requirements: 12.3, 12.5, 12.6, 12.9_
  
  - [ ] 27.4 Write troubleshooting guide
    - Common failure modes: Registry startup failure (port conflict), image push failure (disk space), Kubespray failure (node unreachable), FluxCD reconciliation failure
    - Recovery procedures: Re-run setup-all.sh (bastion), terraform apply (infrastructure), ansible-playbook cluster.yml (cluster), flux reconcile (services)
    - Log locations: /opt/opencenter/logs/, kubespray-master/inventory/mycluster/artifacts/, /var/log/containers/
    - Log analysis: Search for ERROR, check Ansible task failures, check pod events
    - _Requirements: 12.7, 12.8_
  
  - [ ] 27.5 Write extension guide
    - How to add new services: Add image to additional_images.txt, add manifest to assets/manifests/, rebuild package
    - How to update versions: Edit config.sh (runtime versions), edit additional_images.txt (image tags), rebuild package
    - How to rebuild package: Run build.sh, verify new package
    - _Requirements: 12.10_
  
  - [ ] 27.6 Document Zarf variables
    - DEPLOYMENT_MODE: baremetal or openstack (default: baremetal)
    - BASTION_IP: IP address of bastion host (required)
    - SSH_USER: SSH user for node access (default: deployer)
    - INSTALL_PATH: Installation directory on bastion (default: /opt/opencenter)
    - REGISTRY_PORT: Registry port (default: 35000, from kubespray-offline)
    - NGINX_PORT: Nginx port (default: 80, from kubespray-offline)
    - _Requirements: 12.4_

- [ ] 28. Final integration testing
  - [ ] 28.1 Test complete build-deploy cycle (bare-metal)
    - Build: Run build.sh on connected system, verify package created
    - Transfer: Copy openCenter-airgap-*.tar.zst to air-gapped bastion
    - Deploy: Run deploy.sh --mode baremetal --bastion-ip <ip> --inventory hosts.yaml
    - Verify bastion: curl localhost:80/files/, curl localhost:35000/v2/_catalog
    - Verify cluster: kubectl get nodes (all Ready), kubectl get pods -A (all Running)
    - Verify services: Check Gitea, FluxCD, cert-manager, ingress-nginx, Keycloak, kube-prometheus-stack
    - Verify offline: No external network connections during deployment
  
  - [ ] 28.2 Test complete build-deploy cycle (OpenStack)
    - Build: Run build.sh on connected system, verify package created
    - Transfer: Copy openCenter-airgap-*.tar.zst to air-gapped bastion
    - Deploy: Run deploy.sh --mode openstack --bastion-ip <ip> --config openstack_config.yaml
    - Verify infrastructure: terraform show (VMs created)
    - Verify bastion: curl localhost:80/files/, curl localhost:35000/v2/_catalog
    - Verify cluster: kubectl get nodes (all Ready), kubectl get pods -A (all Running)
    - Verify services: Check Gitea, FluxCD, cert-manager, ingress-nginx, Keycloak, kube-prometheus-stack
    - Verify offline: No external network connections during deployment
  
  - [ ] 28.3 Test failure recovery scenarios
    - Simulate node failure during Kubespray: Kill SSH connection mid-deployment
    - Verify recovery: Re-run ansible-playbook cluster.yml, verify cluster healthy
    - Simulate Terraform failure: Inject invalid OpenStack credentials
    - Verify state preservation: Check terraform.tfstate exists, fix credentials, re-run terraform apply
    - Simulate registry failure: Stop registry container mid-deployment
    - Verify recovery: Re-run start-registry.sh, re-run deployment
  
  - [ ] 28.4 Test idempotency
    - Deploy package: Run deploy.sh, verify successful deployment
    - Re-deploy same package: Run deploy.sh again with same parameters
    - Verify no changes: Check cluster state snapshot before/after, verify identical
    - Verify logs: Check deployment logs show "skipped" or "ok" for all operations
  
  - [ ] 28.5 Test package corruption detection
    - Modify package bytes: Use dd to flip bits in package file
    - Verify deployment halts: Run deploy.sh, expect checksum error before extraction
    - Verify error message: Check logs show expected vs actual checksum

- [ ] 29. Final checkpoint - Production readiness
  - All unit tests passing
  - All property tests passing (100+ iterations each)
  - All integration tests passing
  - Documentation complete
  - Build and deployment runbooks validated
  - System ready for production use

## Notes

- Tasks marked with `*` are optional property-based tests that can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation throughout implementation
- Property tests validate universal correctness properties with 100+ iterations
- Unit tests validate specific examples, edge cases, and error conditions
- **Python 3.12+ Environment**: All Python scripts run in project root venv (`PROJECT_ROOT/venv`)
- **Bastion Python Environment**: Separate venv (`~/.venv/kubespray`) created by kubespray-offline on bastion for Ansible/Kubespray
- Mixed language approach: Python 3.12+ for complex logic, Bash for orchestration
- All scripts must be idempotent and handle re-runs gracefully
- All operations must complete without internet access during deployment
