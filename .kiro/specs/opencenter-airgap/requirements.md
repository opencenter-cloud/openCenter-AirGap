# Requirements Document: openCenter AirGap

## Introduction

openCenter AirGap is a specialized solution for providing offline asset delivery in completely disconnected (air-gapped) environments. The system packages all container images and dependencies required by the openCenter platform into a single cryptographically verifiable Zarf artifact. This artifact enables the openCenter platform to deploy Kubernetes clusters and services without any internet connectivity.

**Primary Purpose:** Provide a bastion registry with all images required by openCenter for offline cluster deployment.

**Scope:** openCenter AirGap is responsible for:
1. Collecting all Kubernetes and openCenter service container images
2. Packaging images and dependencies into a single Zarf artifact
3. Setting up bastion services (container registry and package repository)
4. Making all images available for offline pull by openCenter

**Out of Scope:** openCenter AirGap does NOT handle:
- Infrastructure provisioning (handled by openCenter via Terraform)
- Kubernetes cluster bootstrap (handled by openCenter via Kubespray)
- Service deployment (handled by openCenter via Flux CD)
- Cluster health verification (handled by openCenter)

The solution operates across three zones: Factory (connected build environment), Airlock (secure transport), and Field (disconnected deployment environment). A bastion host in the Field zone serves as the image registry and package repository for the openCenter platform.

## Glossary

- **Air-Gapped_Environment**: A network environment with zero connectivity to the public internet
- **Bastion_Host**: A machine that serves as local container registry and package repository for openCenter platform
- **Zarf_Package**: A single compressed artifact (`.tar.zst`) containing all images and dependencies with cryptographic integrity verification
- **SBOM**: Software Bill of Materials—a comprehensive inventory of all software components with version and provenance information
- **Factory_Zone**: The connected build environment where assets are discovered and downloaded
- **Airlock_Zone**: The secure transport layer for moving artifacts between connected and disconnected environments
- **Field_Zone**: The disconnected deployment environment where openCenter deploys the cluster
- **Local_Registry**: A container registry running on the Bastion_Host serving images to openCenter and cluster nodes
- **openCenter_Platform**: The GitOps-based platform that handles infrastructure provisioning, cluster bootstrap, and service deployment
- **kubespray-offline**: Tool for collecting Kubernetes dependencies for offline deployment

## Requirements

### Requirement 1: Asset Discovery and Collection

**User Story:** As a Platform Engineer, I want the build system to automatically discover and collect all required container images and dependencies, so that openCenter can deploy clusters offline.

#### Acceptance Criteria

1. WHEN the build process starts, THE Asset_Discovery_System SHALL parse Kubespray configuration files to identify all required Kubernetes container images
2. WHEN the build process starts, THE Asset_Discovery_System SHALL parse openCenter service manifests to identify all required platform service images (20+ services)
3. WHEN the build process starts, THE Asset_Discovery_System SHALL identify all required Kubernetes binaries for bastion file serving
4. WHEN the build process starts, THE Asset_Discovery_System SHALL identify all required Python packages for bastion PyPI mirror
5. WHEN the build process starts, THE Asset_Discovery_System SHALL identify all required system packages for bastion apt repository
6. WHEN Jinja2 templates are encountered, THE Asset_Discovery_System SHALL render templates with target version variables before parsing
7. WHEN all assets are identified, THE Asset_Discovery_System SHALL download each asset from upstream sources
8. WHEN downloading Python packages, THE Asset_Discovery_System SHALL download platform-specific wheels for manylinux2014_x86_64
9. WHEN all downloads complete, THE Asset_Discovery_System SHALL verify checksums for all downloaded assets
10. THE Asset_Discovery_System SHALL document all collected images in the asset manifest

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

### Requirement 4: Bastion Registry and Repository Setup

**User Story:** As a Field Operator, I want the bastion host to automatically configure local registry and repository services, so that openCenter can deploy clusters without internet access.

#### Acceptance Criteria

1. WHEN Zarf package deployment starts, THE Bastion_Setup_System SHALL extract all assets to the configured installation path
2. WHEN bastion-setup component deploys, THE Bastion_Setup_System SHALL install containerd runtime on the bastion host
3. WHEN bastion-setup component deploys, THE Bastion_Setup_System SHALL start a container registry on port 35000
4. IF a registry container already exists, THEN THE Bastion_Setup_System SHALL reuse the existing container
5. WHEN the registry is running, THE Bastion_Setup_System SHALL load all container images from the package
6. WHEN images are loaded, THE Bastion_Setup_System SHALL push all Kubernetes images to the local registry
7. WHEN images are loaded, THE Bastion_Setup_System SHALL push all openCenter service images (20+ services) to the local registry
8. WHEN bastion-setup component deploys, THE Bastion_Setup_System SHALL start an nginx container on port 80 serving files, apt packages, and PyPI mirror
9. WHEN all services are running, THE Bastion_Setup_System SHALL verify connectivity to registry (port 35000) and nginx (port 80)
10. WHEN setup completes, THE Bastion_Setup_System SHALL verify all images are pullable from the registry
11. THE Bastion_Setup_System SHALL configure the registry to accept insecure connections (HTTP) for air-gap environments
12. THE Bastion_Setup_System SHALL log all setup operations for troubleshooting

### Requirement 5: openCenter Service Image Collection

**User Story:** As a Platform Engineer, I want all openCenter platform service container images included in the air-gap package, so that openCenter can deploy its 20+ services offline.

#### Acceptance Criteria

1. WHEN asset collection starts, THE Asset_Discovery_System SHALL identify all container images required by openCenter platform services
2. WHEN asset collection starts, THE Asset_Discovery_System SHALL identify FluxCD controller images (source-controller, kustomize-controller, helm-controller, notification-controller)
3. WHEN asset collection starts, THE Asset_Discovery_System SHALL identify Gitea images
4. WHEN asset collection starts, THE Asset_Discovery_System SHALL identify cert-manager images (controller, webhook, cainjector)
5. WHEN asset collection starts, THE Asset_Discovery_System SHALL identify ingress-nginx images (controller, webhook-certgen)
6. WHEN asset collection starts, THE Asset_Discovery_System SHALL identify Gateway API images
7. WHEN asset collection starts, THE Asset_Discovery_System SHALL identify Keycloak images
8. WHEN asset collection starts, THE Asset_Discovery_System SHALL identify observability stack images (Prometheus, Grafana, Alertmanager, Loki, Tempo, OpenTelemetry, Mimir)
9. WHEN asset collection starts, THE Asset_Discovery_System SHALL identify storage images (Longhorn, vSphere CSI, OpenStack CSI, External Snapshotter)
10. WHEN asset collection starts, THE Asset_Discovery_System SHALL identify policy and governance images (Kyverno, OLM, RBAC Manager)
11. WHEN asset collection starts, THE Asset_Discovery_System SHALL identify backup and DR images (Velero)
12. WHEN asset collection starts, THE Asset_Discovery_System SHALL identify additional platform images (Harbor, Headlamp, Weave GitOps, MetalLB, Sealed Secrets, Postgres Operator, Strimzi Kafka)
13. WHEN packaging completes, THE Packaging_System SHALL include all openCenter service images in the Zarf package
14. WHEN bastion setup completes, THE Bastion_Setup_System SHALL push all openCenter service images to the local registry
15. WHEN setup is complete, THE openCenter_Platform SHALL be able to pull all service images from the bastion registry
16. THE Asset_Discovery_System SHALL document which images are for openCenter services in the SBOM
17. THE Asset_Discovery_System SHALL use the openCenter-specified versions for all service images

**Note:** openCenter AirGap is responsible for collecting and making available the container images. The actual deployment of all services (Gitea, FluxCD, cert-manager, ingress-nginx, Keycloak, observability stack, storage, policy engines, backup, and all other platform services) is handled by the openCenter platform itself via Flux CD GitOps.
4. WHEN asset collection starts, THE Asset_Discovery_System SHALL identify cert-manager images
5. WHEN asset collection starts, THE Asset_Discovery_System SHALL identify ingress-nginx images
6. WHEN asset collection starts, THE Asset_Discovery_System SHALL identify Keycloak images
7. WHEN asset collection starts, THE Asset_Discovery_System SHALL identify kube-prometheus-stack images (Prometheus, Grafana, Alertmanager)
8. WHEN packaging completes, THE Packaging_System SHALL include all openCenter core service images in the Zarf package
9. WHEN bastion setup completes, THE Bastion_Setup_System SHALL push all openCenter core service images to the local registry
10. WHEN cluster is ready, THE openCenter_Platform SHALL be able to pull all core service images from the bastion registry
11. THE Asset_Discovery_System SHALL document which images are for openCenter core services in the SBOM
12. THE Asset_Discovery_System SHALL use the openCenter-specified versions for all core service images

**Note:** openCenter AirGap is responsible for collecting and making available the container images. The actual deployment of FluxCD, Gitea, cert-manager, ingress-nginx, Keycloak, and kube-prometheus-stack is handled by the openCenter platform itself after cluster bootstrap.

### Requirement 6: Idempotency and Recovery

**User Story:** As a Field Operator, I want to re-run failed bastion setup steps safely, so that I can recover from transient failures without starting over.

#### Acceptance Criteria

1. WHEN a Zarf component is re-deployed, THE Deployment_System SHALL detect existing resources before creating new ones
2. WHEN a registry container already exists, THE Deployment_System SHALL reuse it instead of failing
3. WHEN a repository service already exists, THE Deployment_System SHALL reuse it instead of failing
4. WHEN bastion setup fails, THE Deployment_System SHALL preserve all logs for troubleshooting
5. WHEN bastion setup fails, THE Deployment_System SHALL provide clear error messages indicating the failure point
6. THE Deployment_System SHALL allow individual bastion components to be re-deployed independently
7. THE Deployment_System SHALL ensure re-running a successful bastion setup does not change state

### Requirement 7: Offline Operation Validation

**User Story:** As a Security Officer, I want to verify that no component attempts external network access during bastion setup, so that I can ensure air-gap compliance.

#### Acceptance Criteria

1. WHEN bastion setup executes, THE Deployment_System SHALL complete without any outbound internet connections
2. WHEN images are pushed to registry, THE Bastion_Setup_System SHALL only use locally extracted images
3. WHEN packages are served, THE Bastion_Setup_System SHALL only use locally extracted packages
4. THE Deployment_System SHALL log all network connections for audit purposes
5. IF any component attempts external network access, THEN THE Deployment_System SHALL fail with a clear error message

**Note:** Validation of openCenter platform operations (cluster bootstrap, service deployment) is the responsibility of openCenter, not openCenter AirGap.

### Requirement 8: Version Pinning and Determinism

**User Story:** As a Platform Engineer, I want all component versions strictly pinned, so that the same package produces identical image sets every time.

#### Acceptance Criteria

1. THE Build_System SHALL pin the Kubernetes version in all configuration files
2. THE Build_System SHALL pin all container image tags without using "latest"
3. THE Build_System SHALL pin all openCenter service image versions
4. THE Build_System SHALL pin all Python package versions in requirements files
5. THE Build_System SHALL pin all system package versions in apt manifests
6. THE Build_System SHALL pin the kubespray-offline version used for asset collection
7. WHEN the same package is built twice, THE Build_System SHALL produce identical image lists
8. THE Build_System SHALL record all pinned versions in the SBOM
9. THE Build_System SHALL fail if any dependency cannot be resolved to a specific version

### Requirement 9: Logging and Observability

**User Story:** As a Field Operator, I want comprehensive logs of all bastion setup operations, so that I can troubleshoot failures and verify successful setup.

#### Acceptance Criteria

1. WHEN any bastion setup operation executes, THE Logging_System SHALL write logs to a persistent location on bastion
2. WHEN Zarf actions execute, THE Logging_System SHALL capture all command output
3. WHEN images are pushed to registry, THE Logging_System SHALL log all push operations
4. WHEN errors occur, THE Logging_System SHALL log stack traces and error context
5. WHEN bastion setup completes, THE Logging_System SHALL generate a summary report with timestamps
6. THE Logging_System SHALL include log rotation to prevent disk exhaustion
7. THE Logging_System SHALL preserve logs across setup re-runs
8. WHEN bastion is operational, THE Deployment_System SHALL verify registry and nginx services are accessible

**Note:** Logging and observability for openCenter platform operations (cluster bootstrap, service deployment) is the responsibility of openCenter, not openCenter AirGap.

### Requirement 10: Documentation and Runbooks

**User Story:** As a Field Operator, I want clear documentation for build and bastion setup procedures, so that I can execute operations without expert assistance.

#### Acceptance Criteria

1. THE Documentation_System SHALL provide a build runbook with step-by-step instructions
2. THE Documentation_System SHALL provide a bastion setup runbook
3. THE Documentation_System SHALL document all Zarf variables and their default values
4. THE Documentation_System SHALL document all prerequisites for bastion host
5. THE Documentation_System SHALL provide troubleshooting guides for common bastion setup failure modes
6. THE Documentation_System SHALL document the recovery procedure for each bastion component
7. THE Documentation_System SHALL document the verification steps for successful bastion setup
8. THE Documentation_System SHALL document how to extend the package with new service images
9. THE Documentation_System SHALL document the handoff contract with openCenter platform

**Note:** Documentation for openCenter platform operations (infrastructure provisioning, cluster bootstrap, service deployment) is the responsibility of openCenter, not openCenter AirGap.
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
9. WHEN cluster is operational, THE Deployment_System SHALL verify cluster health and node readiness
10. WHEN cluster is operational, THE Deployment_System SHALL verify bastion services remain accessible

**Note:** Verification of openCenter core services (kube-prometheus-stack, Grafana, FluxCD, Gitea, etc.) is the responsibility of the openCenter platform, not openCenter AirGap.

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
