# Requirements Document: openCenter AirGap

## Introduction

openCenter AirGap is a comprehensive solution for deploying High Availability Kubernetes clusters in completely disconnected (air-gapped) environments. The system packages Terraform (optional, for OpenStack), Kubespray, and core Kubernetes services into a single cryptographically verifiable Zarf artifact. This artifact contains all dependencies required to provision infrastructure, bootstrap a cluster, and deploy core platform services without any internet connectivity during deployment.

The solution operates across three zones: Factory (connected build environment), Airlock (secure transport), and Field (disconnected deployment environment). A bastion host in the Field zone serves as the operational hub, providing local registry and repository services to cluster nodes.

## Glossary

- **Air-Gapped_Environment**: A network environment with zero connectivity to the public internet
- **Bastion_Host**: An administrative machine that executes deployment orchestration and serves as local registry/repository for cluster nodes
- **Zarf_Package**: A single compressed artifact (`.tar.zst`) containing all deployment dependencies with cryptographic integrity verification
- **SBOM**: Software Bill of Materials—a comprehensive inventory of all software components with version and provenance information
- **Factory_Zone**: The connected build environment where assets are discovered and downloaded
- **Airlock_Zone**: The secure transport layer for moving artifacts between connected and disconnected environments
- **Field_Zone**: The disconnected deployment environment where the cluster is provisioned
- **Kubespray**: An Ansible-based Kubernetes cluster installer
- **FluxCD**: A GitOps operator for continuous delivery in Kubernetes
- **Gitea**: A lightweight self-hosted Git server deployed in-cluster
- **Local_Registry**: A container registry running on the Bastion_Host serving images to cluster nodes
- **Filesystem_Mirror**: A local directory structure containing Terraform provider plugins for offline use
- **Deployment_Mode**: The target infrastructure type (bare-metal or OpenStack)

## Requirements

### Requirement 1: Asset Discovery and Collection

**User Story:** As a Platform Engineer, I want the build system to automatically discover and collect all required dependencies, so that no assets are missing during field deployment.

#### Acceptance Criteria

1. WHEN the build process starts, THE Asset_Discovery_System SHALL parse Kubespray configuration files to identify all required container images
2. WHEN the build process starts, THE Asset_Discovery_System SHALL parse Kubespray configuration files to identify all required Kubernetes binaries
3. WHEN the build process starts, THE Asset_Discovery_System SHALL parse Kubespray configuration files to identify all required Python packages
4. WHEN the build process starts, THE Asset_Discovery_System SHALL parse Kubespray configuration files to identify all required system packages
5. WHERE OpenStack deployment is enabled, THE Asset_Discovery_System SHALL identify all required Terraform provider plugins
6. WHEN Jinja2 templates are encountered, THE Asset_Discovery_System SHALL render templates with target version variables before parsing
7. WHEN all assets are identified, THE Asset_Discovery_System SHALL download each asset from upstream sources
8. WHEN downloading Terraform providers, THE Asset_Discovery_System SHALL generate cross-platform lock files for AMD64 architecture
9. WHEN downloading Python packages, THE Asset_Discovery_System SHALL download platform-specific wheels for manylinux2014_x86_64
10. WHEN all downloads complete, THE Asset_Discovery_System SHALL verify checksums for all downloaded assets

### Requirement 2: Zarf Package Creation

**User Story:** As a Platform Engineer, I want to bundle all collected assets into a single Zarf package, so that field deployment requires only one artifact.

#### Acceptance Criteria

1. WHEN package creation starts, THE Packaging_System SHALL create a Zarf package containing all discovered assets
2. WHEN packaging container images, THE Packaging_System SHALL compress image layers into the Zarf artifact
3. WHEN packaging files, THE Packaging_System SHALL organize assets by component (bootstrap-tools, terraform-providers, kubespray-core, k8s-images, deploy-cluster)
4. WHEN packaging completes, THE Packaging_System SHALL generate an SBOM using Syft for all package contents
5. WHEN SBOM generation completes, THE Packaging_System SHALL include the SBOM in the Zarf package
6. WHEN package creation completes, THE Packaging_System SHALL generate MD5 and SHA256 checksums for the package
7. WHERE cryptographic signing is enabled, THE Packaging_System SHALL sign the package using Cosign
8. WHEN the package is finalized, THE Packaging_System SHALL produce a single `.tar.zst` file
9. THE Packaging_System SHALL ensure the package size does not exceed 10GB
10. THE Packaging_System SHALL embed Zarf component metadata defining deployment sequence

### Requirement 3: Package Integrity Verification

**User Story:** As a Security Officer, I want to verify package integrity before deployment, so that I can ensure no tampering has occurred during transport.

#### Acceptance Criteria

1. WHEN a package is received, THE Verification_System SHALL validate MD5 checksum against the provided manifest
2. WHEN a package is received, THE Verification_System SHALL validate SHA256 checksum against the provided manifest
3. WHERE the package is signed, THE Verification_System SHALL verify the Cosign signature before extraction
4. IF checksum validation fails, THEN THE Verification_System SHALL halt deployment and report the mismatch
5. IF signature verification fails, THEN THE Verification_System SHALL halt deployment and report the failure
6. WHEN verification succeeds, THE Verification_System SHALL log successful validation with timestamp

### Requirement 4: Bastion Host Setup

**User Story:** As a Field Operator, I want the bastion host to automatically configure local services, so that cluster nodes can pull dependencies without internet access.

#### Acceptance Criteria

1. WHEN Zarf package deployment starts, THE Bastion_Setup_System SHALL extract all assets to the configured installation path
2. WHEN bootstrap-tools component deploys, THE Bastion_Setup_System SHALL create a Python virtual environment
3. WHEN bootstrap-tools component deploys, THE Bastion_Setup_System SHALL install all Python wheels into the virtual environment
4. WHERE Terraform is included, THE Bastion_Setup_System SHALL copy the Terraform binary to `/usr/local/bin`
5. WHERE Terraform providers are included, THE Bastion_Setup_System SHALL extract the filesystem mirror to the configured path
6. WHERE Terraform providers are included, THE Bastion_Setup_System SHALL create `.terraformrc` configuration file pointing to the filesystem mirror
7. WHEN k8s-images component deploys, THE Bastion_Setup_System SHALL load all container images into the local container runtime
8. WHEN k8s-images component deploys, THE Bastion_Setup_System SHALL start a Docker Registry container on port 5000
9. IF a registry container already exists, THEN THE Bastion_Setup_System SHALL reuse the existing container
10. WHEN the registry is running, THE Bastion_Setup_System SHALL push all Kubernetes images to the local registry
11. WHEN kubespray-core component deploys, THE Bastion_Setup_System SHALL start an Nginx container on port 8080 serving apt and PyPI repositories
12. WHEN all services are running, THE Bastion_Setup_System SHALL verify connectivity to registry and repository services

### Requirement 5: Infrastructure Provisioning (OpenStack)

**User Story:** As a Field Operator deploying on OpenStack, I want Terraform to provision VMs automatically, so that I don't need to manually create infrastructure.

#### Acceptance Criteria

1. WHERE deployment mode is OpenStack, THE Infrastructure_Provisioner SHALL execute Terraform initialization using the filesystem mirror
2. WHERE deployment mode is OpenStack, THE Infrastructure_Provisioner SHALL validate Terraform configuration before applying
3. WHERE deployment mode is OpenStack, THE Infrastructure_Provisioner SHALL provision control plane VMs according to the configuration
4. WHERE deployment mode is OpenStack, THE Infrastructure_Provisioner SHALL provision worker VMs according to the configuration
5. WHERE deployment mode is OpenStack, THE Infrastructure_Provisioner SHALL configure network resources for cluster communication
6. WHERE deployment mode is OpenStack, THE Infrastructure_Provisioner SHALL generate an Ansible inventory from Terraform outputs
7. WHERE deployment mode is OpenStack, THE Infrastructure_Provisioner SHALL wait for all VMs to reach running state before proceeding
8. IF Terraform apply fails, THEN THE Infrastructure_Provisioner SHALL preserve state files for recovery
9. WHERE deployment mode is bare-metal, THE Infrastructure_Provisioner SHALL skip all Terraform operations
10. WHERE deployment mode is bare-metal, THE Infrastructure_Provisioner SHALL use the operator-provided inventory file

### Requirement 6: Cluster Bootstrapping

**User Story:** As a Field Operator, I want Kubespray to bootstrap the Kubernetes cluster using only local resources, so that cluster installation succeeds without internet access.

#### Acceptance Criteria

1. WHEN cluster deployment starts, THE Cluster_Bootstrapper SHALL configure Kubespray inventory with bastion registry URL
2. WHEN cluster deployment starts, THE Cluster_Bootstrapper SHALL configure Kubespray to use local binary cache
3. WHEN cluster deployment starts, THE Cluster_Bootstrapper SHALL configure Kubespray to download files only once to bastion
4. WHEN cluster deployment starts, THE Cluster_Bootstrapper SHALL configure containerd on nodes to use bastion as registry mirror
5. WHEN Kubespray executes, THE Cluster_Bootstrapper SHALL install Kubernetes binaries from local cache
6. WHEN Kubespray executes, THE Cluster_Bootstrapper SHALL pull all container images from bastion registry
7. WHEN Kubespray executes, THE Cluster_Bootstrapper SHALL install system packages from bastion apt repository
8. WHEN Kubespray executes, THE Cluster_Bootstrapper SHALL install Python packages from bastion PyPI repository
9. WHEN cluster initialization completes, THE Cluster_Bootstrapper SHALL verify all control plane components are healthy
10. WHEN cluster initialization completes, THE Cluster_Bootstrapper SHALL verify all worker nodes are in Ready state
11. WHEN cluster initialization completes, THE Cluster_Bootstrapper SHALL save kubeconfig to a known location on bastion
12. IF any node fails to join, THEN THE Cluster_Bootstrapper SHALL log detailed error information for troubleshooting

### Requirement 7: Core Services Deployment

**User Story:** As a Platform Engineer, I want core platform services deployed automatically via GitOps, so that the cluster is production-ready immediately after bootstrap.

#### Acceptance Criteria

1. WHEN cluster is healthy, THE Core_Services_Deployer SHALL deploy Gitea using manifests from the package
2. WHEN Gitea is running, THE Core_Services_Deployer SHALL initialize an empty Git repository for cluster configuration
3. WHEN Gitea repository is ready, THE Core_Services_Deployer SHALL push FluxCD installation manifests to the repository
4. WHEN Gitea repository is ready, THE Core_Services_Deployer SHALL push cert-manager manifests to the repository
5. WHEN Gitea repository is ready, THE Core_Services_Deployer SHALL push ingress-nginx manifests to the repository
6. WHEN Gitea repository is ready, THE Core_Services_Deployer SHALL push Keycloak manifests to the repository
7. WHEN Gitea repository is ready, THE Core_Services_Deployer SHALL push kube-prometheus-stack manifests to the repository
8. WHEN all manifests are pushed, THE Core_Services_Deployer SHALL install FluxCD controllers in the cluster
9. WHEN FluxCD is installed, THE Core_Services_Deployer SHALL create GitRepository resource pointing to internal Gitea
10. WHEN FluxCD is installed, THE Core_Services_Deployer SHALL create Kustomization resources for each core service
11. WHEN FluxCD reconciles, THE Core_Services_Deployer SHALL verify all core services reach Running state
12. WHEN all services are running, THE Core_Services_Deployer SHALL verify Ingress resources are created with valid endpoints

### Requirement 8: Idempotency and Recovery

**User Story:** As a Field Operator, I want to re-run failed deployment steps safely, so that I can recover from transient failures without starting over.

#### Acceptance Criteria

1. WHEN a Zarf component is re-deployed, THE Deployment_System SHALL detect existing resources before creating new ones
2. WHEN a registry container already exists, THE Deployment_System SHALL reuse it instead of failing
3. WHEN a repository service already exists, THE Deployment_System SHALL reuse it instead of failing
4. WHEN Terraform state exists, THE Deployment_System SHALL use existing state for plan operations
5. WHEN Kubespray is re-run on a healthy cluster, THE Deployment_System SHALL complete without errors
6. WHEN FluxCD is already installed, THE Deployment_System SHALL update configurations instead of failing
7. WHEN a deployment step fails, THE Deployment_System SHALL preserve all logs for troubleshooting
8. WHEN a deployment step fails, THE Deployment_System SHALL provide clear error messages indicating the failure point
9. THE Deployment_System SHALL allow individual components to be re-deployed independently
10. THE Deployment_System SHALL ensure re-running a successful deployment does not change cluster state

### Requirement 9: Offline Operation Validation

**User Story:** As a Security Officer, I want to verify that no component attempts external network access, so that I can ensure air-gap compliance.

#### Acceptance Criteria

1. WHEN deployment executes, THE Deployment_System SHALL complete without any outbound internet connections
2. WHEN cluster nodes pull images, THE Cluster_Nodes SHALL only connect to bastion registry
3. WHEN cluster nodes install packages, THE Cluster_Nodes SHALL only connect to bastion repositories
4. WHEN Terraform initializes, THE Terraform_CLI SHALL only access the local filesystem mirror
5. WHEN Kubespray executes, THE Ansible_Playbooks SHALL only download from bastion services
6. WHEN FluxCD reconciles, THE FluxCD_Controllers SHALL only connect to internal Gitea
7. THE Deployment_System SHALL log all network connections for audit purposes
8. IF any component attempts external network access, THEN THE Deployment_System SHALL fail with a clear error message

### Requirement 10: Version Pinning and Determinism

**User Story:** As a Platform Engineer, I want all component versions strictly pinned, so that the same package produces identical deployments every time.

#### Acceptance Criteria

1. THE Build_System SHALL pin the Kubernetes version in all configuration files
2. THE Build_System SHALL pin all container image tags without using "latest"
3. THE Build_System SHALL pin all Terraform provider versions in lock files
4. THE Build_System SHALL pin all Python package versions in requirements files
5. THE Build_System SHALL pin all system package versions in apt manifests
6. THE Build_System SHALL pin the Kubespray version used for cluster bootstrap
7. THE Build_System SHALL pin all Helm chart versions for core services
8. WHEN the same package is deployed twice, THE Deployment_System SHALL produce identical cluster states
9. THE Build_System SHALL record all pinned versions in the SBOM
10. THE Build_System SHALL fail if any dependency cannot be resolved to a specific version

### Requirement 11: Logging and Observability

**User Story:** As a Field Operator, I want comprehensive logs of all deployment operations, so that I can troubleshoot failures and verify successful deployment.

#### Acceptance Criteria

1. WHEN any deployment operation executes, THE Logging_System SHALL write logs to a persistent location on bastion
2. WHEN Terraform executes, THE Logging_System SHALL capture all Terraform output
3. WHEN Kubespray executes, THE Logging_System SHALL capture all Ansible output
4. WHEN Zarf actions execute, THE Logging_System SHALL capture all command output
5. WHEN errors occur, THE Logging_System SHALL log stack traces and error context
6. WHEN deployment completes, THE Logging_System SHALL generate a summary report with timestamps
7. THE Logging_System SHALL include log rotation to prevent disk exhaustion
8. THE Logging_System SHALL preserve logs across deployment re-runs
9. WHEN cluster is operational, THE Logging_System SHALL verify kube-prometheus-stack is collecting metrics
10. WHEN cluster is operational, THE Logging_System SHALL verify Grafana dashboards are accessible

### Requirement 12: Documentation and Runbooks

**User Story:** As a Field Operator, I want clear documentation for build and deployment procedures, so that I can execute operations without expert assistance.

#### Acceptance Criteria

1. THE Documentation_System SHALL provide a build runbook with step-by-step instructions
2. THE Documentation_System SHALL provide a deployment runbook for bare-metal mode
3. THE Documentation_System SHALL provide a deployment runbook for OpenStack mode
4. THE Documentation_System SHALL document all Zarf variables and their default values
5. THE Documentation_System SHALL document all prerequisites for bastion host
6. THE Documentation_System SHALL document all prerequisites for target nodes
7. THE Documentation_System SHALL provide troubleshooting guides for common failure modes
8. THE Documentation_System SHALL document the recovery procedure for each component
9. THE Documentation_System SHALL document the verification steps for successful deployment
10. THE Documentation_System SHALL document the procedure for extending the package with new services
