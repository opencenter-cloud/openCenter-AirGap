# Product Requirements Document (PRD)
# openCenter AirGap

| Field | Value |
|:---|:---|
| **Product Name** | openCenter-airgap |
| **Version** | 1.0 |
| **Status** | Draft |
| **Date** | January 24, 2026 |

---

## 1. Executive Summary

openCenter AirGap is a turnkey solution for deploying High Availability (HA) Kubernetes clusters in strictly air-gapped (disconnected) environments. The solution encapsulates infrastructure provisioning (Terraform), cluster bootstrapping (Kubespray), and core platform services into a single, cryptographically verifiable **Zarf** artifact.

The core innovation is the "Disconnected-First" design philosophy: internet isolation is treated as the baseline constraint, not an exception. A single artifact—delivered via secure media to a bastion host—contains everything needed to provision hardware, hydrate a local registry, and bootstrap a production-grade cluster without any outbound network traffic.

---

## 2. Problem Statement

Deploying cloud-native infrastructure in denied environments (defense, finance, critical infrastructure) is excessively complex:

- **Dependency Hell:** Standard tooling (Terraform, Kubespray, Helm) assumes ubiquitous internet connectivity for fetching dependencies at runtime.
- **High Failure Rates:** Missing dependencies (images, packages, binaries) cause deployment failures in the field with no recourse.
- **Security Risks:** Difficulty verifying integrity and provenance (SBOM) of manually collected artifacts.
- **Configuration Drift:** Inconsistent environments due to lack of version locking and deterministic builds.
- **Manual Fragility:** Traditional "sneakernet" operations rely on ad-hoc file transfers and fragmented scripts.

---

## 3. Goals & Objectives

| ID | Objective |
|:---|:---|
| **G-01** | **Single-Artifact Delivery:** Encapsulate the entire supply chain (Terraform providers, OS packages, container images, Python wheels, Helm charts) into one `.tar.zst` Zarf package. |
| **G-02** | **Zero-Trust Connectivity:** Deployment succeeds with **zero** internet access on the target bastion and cluster nodes. |
| **G-03** | **Deterministic & Idempotent:** The same package produces the exact same cluster state every time; safe to re-run on failure. |
| **G-04** | **GitOps-Native:** Bootstrap the cluster with an internal GitOps engine (FluxCD + Gitea) to manage day-2 configuration. |
| **G-05** | **Security & Compliance:** Provide comprehensive SBOM (SPDX/CycloneDX) and cryptographic integrity checks for all components. |

---

## 4. Target Audience

| Persona | Description |
|:---|:---|
| **Platform Engineer** | Builds the air-gap artifact, maintains version pinning, and defines the core services stack. |
| **Field Operator / Deployment Engineer** | Deploys the artifact in disconnected environments; executes runbooks on bastion hosts. |
| **Security / Compliance Officer** | Validates SBOM, checksums, and artifact integrity; audits software introduced to the air-gapped network. |
| **Platform Architect** | Designs the standard operating environment for disconnected edge sites. |

---

## 5. Scope

### 5.1 In-Scope

| Category | Details |
|:---|:---|
| **Infrastructure Provisioning** | **Primary Target:** Bare-metal or pre-provisioned hardware (VMs/physical servers) with Ubuntu installed. **Secondary Target:** Automated VM creation on **OpenStack** via Terraform with embedded provider plugins. vSphere support deferred to future releases. |
| **Cluster Bootstrapping** | Offline HA Kubernetes installation (control plane + workers) using **Kubespray** with all dependencies (apt, pip, images) served locally. |
| **Core Platform Services** | Pre-integrated services deployed via GitOps: |
| | • **GitOps:** FluxCD v2 + internal Gitea server |
| | • **Ingress/Certs:** Ingress-NGINX, Cert-Manager (self-signed/internal CA) |
| | • **Observability:** Kube-Prometheus-Stack (Prometheus, Grafana, Alertmanager) |
| | • **Identity:** Keycloak (OIDC/SSO) |
| **Tooling** | Bundled CLI tools (Zarf, Terraform, kubectl, helm) required for operation. |
| **Compliance** | SBOM generation (SPDX/CycloneDX), checksum manifests, optional Cosign signing. |

### 5.2 Out-of-Scope

- Physical hardware setup (racking, stacking, network cabling)
- Day-2 operations tooling beyond core services (Velero backup, centralized logging)
- Live OS patching (requires new package or separate OS repo mirror)
- Multi-cluster federation
- Automated cluster upgrades (delivered as new packages)
- Hardware-specific drivers or proprietary integrations
- External Git provider integration (focus on in-cluster Git)

### 5.3 Technical Constraints

| Constraint | Specification |
|:---|:---|
| **Target OS** | Ubuntu Linux 24.04 LTS |
| **Architecture** | AMD64 (x86_64) only for initial release |
| **Bastion Host** | Dedicated admin VM/host with SSH access to target nodes, container runtime (Docker/Podman) |
| **Package Size** | Multi-gigabyte (2-5GB+); distribution media must support this size |
| **Scripting** | Bash or Python only (no compiled code aside from provided tools) for transparency and auditing |
| **Versions** | kubespray@master, kubespray-offline@main (latest development branches) |

---

## 6. Architecture Overview

### 6.1 The Three-Zone Model

The architecture separates concerns into three logical zones:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ZONE A: THE FACTORY                                  │
│                    (Connected Build Environment)                            │
│  • Asset Discovery: Parse IaC/Ansible to identify dependency graph          │
│  • Pull Operations: Download images, packages, providers, wheels            │
│  • Package Creation: Bundle everything into Zarf artifact                   │
│  • SBOM Generation: Syft scans all content                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ZONE B: THE AIRLOCK                                  │
│                        (Transport Layer)                                    │
│  • Single Artifact: openCenter-airgap-<version>.tar.zst                     │
│  • Cryptographic Signing: Cosign/Sigstore verification                      │
│  • Checksum Manifest: MD5/SHA256 integrity verification                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ZONE C: THE FIELD                                    │
│                   (Disconnected Run Environment)                            │
│  • Bastion Host: Executes Zarf, runs Terraform/Ansible                      │
│  • Local Registry: Serves container images to cluster nodes                 │
│  • Local Repo: Serves apt/pip packages via Nginx                            │
│  • Cluster Nodes: Pull all dependencies from bastion                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Toolchain Convergence

| Tool | Role |
|:---|:---|
| **Zarf** | The Envelope—packaging schema, runtime delivery, SBOM generation, integrity verification |
| **Terraform** | The Provisioner (Optional)—immutable infrastructure for OpenStack using filesystem mirror for providers. Not required for bare-metal deployments. |
| **Kubespray** | The Bootstrapper—industry-standard Ansible playbook for Kubernetes, configured for offline sources |
| **kubespray-offline** | The Map—asset discovery logic (not runtime scripts); identifies required dependencies |

### 6.3 Bastion-as-Hub Topology

The bastion host serves as the operational center of gravity:

1. **Zarf** extracts and orchestrates deployment
2. **Terraform** (optional, OpenStack only) creates VMs if infrastructure not pre-provisioned
3. **Kubespray** (executed by Zarf) configures nodes, pulling from:
   - **Docker Registry** container (port 5000) seeded with images
   - **Nginx** container (port 8080) serving Ubuntu apt repos and Python wheels
4. **FluxCD** takes over day-2, syncing from in-cluster **Gitea**

**Deployment Modes:**
- **Bare-metal/Pre-provisioned:** Operator provides inventory of existing nodes; Terraform step skipped
- **OpenStack:** Terraform provisions VMs, generates inventory automatically

---

## 7. Artifact Model

### 7.1 Package Structure

The `openCenter-airgap` artifact is a single Zarf package containing:

| Component | Contents |
|:---|:---|
| **infra** | (Optional) Terraform modules for OpenStack, provider plugins (filesystem mirror), `.terraformrc` config. Skipped for bare-metal deployments. |
| **cluster** | Kubespray playbooks, offline dependencies (apt mirror, container images, PyPI wheels), setup scripts, inventory templates |
| **core** | FluxCD manifests/images, Gitea Helm chart/image, core services (cert-manager, ingress-nginx, Keycloak, kube-prometheus-stack) |
| **sbom** | Auto-generated SBOM (SPDX/CycloneDX) for all components |
| **checksums** | MD5/SHA256 manifest for integrity verification |

### 7.2 Zarf Package Schema

```yaml
kind: ZarfPackageConfig
metadata:
  name: openCenter-airgap
  description: "Air-gapped Kubernetes Deployment Artifact"
  version: "1.0.0"
  architecture: amd64

variables:
  - name: DEPLOYMENT_MODE
    description: "Deployment mode (baremetal or openstack)"
    default: "baremetal"
  - name: PLATFORM
    description: "Target platform (openstack only if DEPLOYMENT_MODE=openstack)"
  - name: BASTION_IP
    description: "IP address of bastion host for registry/repo access"
  - name: SSH_USER
    description: "SSH user for Ansible"
    default: "deployer"

components:
  - name: infra
    required: false  # Only for OpenStack deployments
    # Terraform code, providers, execution actions

  - name: cluster
    required: true
    # Kubespray, offline assets, registry/nginx setup, inventory templates

  - name: core
    required: true
    # FluxCD, Gitea, core services images/charts
```

---

## 8. Functional Requirements

### 8.1 Artifact Generation (Build Phase - Zone A)

| ID | Requirement | Description |
|:---|:---|:---|
| **FR-01** | Asset Discovery | Build pipeline must automatically identify and download all dependencies based on pinned versions using kubespray-offline logic and custom scripts. |
| **FR-02** | Version Locking | All components (K8s version, chart versions, image tags) must be strictly pinned; no "latest" tags. |
| **FR-03** | SBOM Generation | Complete SBOM (SPDX/CycloneDX) must be generated for the final artifact via Zarf/Syft. |
| **FR-04** | Checksum Manifest | MD5/SHA256 checksums for all major files must be recorded for integrity verification. |
| **FR-05** | Single Package | All assets must be bundled into a single Zarf package executable on a standard Linux bastion. |
| **FR-06** | Terraform Provider Mirror | Providers must be mirrored with `terraform providers lock -platform=linux_amd64` for cross-platform integrity. |

### 8.2 Deployment Execution (Run Phase - Zone C)

| ID | Requirement | Description |
|:---|:---|:---|
| **FR-07** | Integrity Verification | Installer must verify cryptographic checksum of the package before extraction. |
| **FR-08** | Local Registry | System must spin up ephemeral Docker Registry (port 5000) on bastion to serve images. |
| **FR-09** | Local Repository | System must spin up Nginx (port 8080) to serve apt/pip packages to nodes. |
| **FR-10** | Infrastructure Automation | **Bare-metal:** Operator provides static inventory. **OpenStack:** Terraform provisions VMs using embedded provider plugins (no internet download). |
| **FR-11** | Node Configuration | Target nodes must be automatically configured to use bastion's local repositories. |
| **FR-12** | Cluster Installation | Kubespray must run non-interactively to provision a healthy K8s cluster using local assets. |
| **FR-13** | Inventory Generation | **Bare-metal:** Operator creates inventory manually or from template. **OpenStack:** Ansible inventory auto-generated from Terraform outputs. |

### 8.3 Core Services & GitOps

| ID | Requirement | Description |
|:---|:---|:---|
| **FR-14** | Internal Git Server | Gitea must be deployed in-cluster as the GitOps "Source of Truth." |
| **FR-15** | GitOps Seeding | Solution must automatically push initial cluster configuration to internal Gitea. |
| **FR-16** | Flux Bootstrap | FluxCD must be installed and configured to sync from internal Gitea immediately. |
| **FR-17** | Service Availability | Core services must be accessible via Ingress/NodePort without external dependencies. |
| **FR-18** | Image Mirroring | Containerd on nodes must be configured to use bastion registry as mirror for all upstream registries. |

### 8.4 Idempotency and Recovery

| ID | Requirement | Description |
|:---|:---|:---|
| **FR-19** | Idempotent Actions | All deployment actions must be idempotent; re-running must not break a healthy deployment. |
| **FR-20** | Component Re-run | Individual components (infra, cluster, core) must be re-runnable independently after failure. |
| **FR-21** | Graceful Failure | Scripts must handle "already running" states gracefully (e.g., registry container exists). |

---

## 9. Non-Functional Requirements

| ID | Requirement | Description |
|:---|:---|:---|
| **NFR-01** | Offline-Only | Zero outbound network dependency at deploy time. |
| **NFR-02** | Deterministic Builds | Pinned versions for all dependencies; bit-for-bit reproducible packages. |
| **NFR-03** | Integrity Verification | Checksums and optional package signing (Cosign). |
| **NFR-04** | Compliance Readiness | SBOMs and auditable artifact contents for security review. |
| **NFR-05** | Usability | Single high-level command (`zarf package deploy`) with interactive prompts for environment-specific variables. |
| **NFR-06** | Performance | Infrastructure and cluster provisioning should complete within 45 minutes on standard hardware. |
| **NFR-07** | Observability | Deployment logs (Terraform, Ansible) must be captured and persisted on bastion. |
| **NFR-08** | Documentation | Clear runbooks for build and deploy flows. |

---

## 10. Kubespray-Offline Integration Strategy

kubespray-offline provides proven asset discovery and runtime setup for Kubespray air-gap deployments. OpenCenter integrates it as the foundation:

| Aspect | kubespray-offline | Zarf | Integration |
|:---|:---|:---|:---|
| **Asset Discovery** | `download-all.sh` orchestrates downloads | N/A | Execute in build phase |
| **Packaging** | `outputs/` directory (files, images, debs, pypi) | Single `.tar.zst` artifact | Zarf packages outputs/ |
| **Integrity** | File checksums | SBOM (Syft), Cosign signing | Zarf adds compliance |
| **Registry Setup** | `start-registry.sh` (port 35000) | Component actions | Zarf executes script |
| **Web Server** | `start-nginx.sh` (port 80) | Component actions | Zarf executes script |
| **Image Loading** | `load-push-all-images.sh` | Component actions | Zarf executes script |
| **Node Config** | `offline-repo.yml` playbook | Component actions | Zarf runs playbook |
| **Kubespray Execution** | `extract-kubespray.sh` + manual ansible-playbook | Component actions | Zarf orchestrates |
| **GitOps** | Not addressed | FluxCD + Gitea deployment | Zarf adds post-cluster |

**Workflow:**
1. **Build (Zone A)**: Run kubespray-offline `download-all.sh` → populate `outputs/`
2. **Package (Zone A→B)**: Zarf bundles `outputs/` + scripts + Terraform + core services
3. **Deploy (Zone C)**: Zarf extracts and executes `setup-all.sh` on bastion
4. **Bootstrap (Zone C)**: Zarf runs Kubespray with `offline.yml` pointing to bastion services
5. **GitOps (Zone C)**: Zarf deploys FluxCD + Gitea + core services

**Value Add:**
- **kubespray-offline**: Battle-tested asset lists, setup scripts, offline.yml template
- **Zarf**: Atomic delivery, SBOM/signing, orchestration, Terraform integration, GitOps bootstrap

---

## 11. Failure Modes & Recovery

| Failure | Symptom | Resolution |
|:---|:---|:---|
| **Package Corruption** | MD5 mismatch | Halt deployment; re-transfer package |
| **Terraform Failure** | Bad credentials, quota exceeded | Correct variables; re-run `infra` component |
| **Kubespray Failure** | Node unreachable, timeout | Fix SSH/network; re-run `cluster` component |
| **Checksum Mismatch** | Ansible fails at download_file | Set `ignore_assert_errors: true` or fix asset versions |
| **Provider Lock Error** | terraform init fails (missing hashes) | Rebuild package with correct `providers lock` |
| **Image Pull BackOff** | Pods fail to start | Check bastion firewall (port 5000), insecure registry config |
| **Gitea Failure** | Storage issue | Fix PV; re-run `core` component |

---

## 12. Success Metrics

| ID | Metric | Target |
|:---|:---|:---|
| **SM-01** | Dependency Completeness | 100% of required dependencies present; no internet access needed at deploy time |
| **SM-02** | Deployment Time | Complete within 45 minutes on standard hardware |
| **SM-03** | Integrity Verification | SBOM and checksum verification pass in the field |
| **SM-04** | Idempotency | Re-running components causes no failures or drift |
| **SM-05** | GitOps Sync | FluxCD syncs from Gitea within 2 minutes of deployment |

---

## 13. Assumptions

- **Primary deployment target:** Bare-metal or pre-provisioned VMs with Ubuntu 24.04 LTS already installed
- **Secondary deployment target:** OpenStack with base Ubuntu image/template available
- Target nodes and bastion host run Ubuntu 24.04 LTS
- Bastion host has SSH access to all target nodes
- Bastion host has container runtime (Docker or containerd/nerdctl)
- Cluster is HA (3 control-plane nodes, multiple workers)
- Bastion is on same network as cluster nodes (or has routing)
- **Bare-metal:** Operator provides node inventory (IPs, hostnames) before deployment
- **OpenStack:** Operator has cloud credentials at deploy time

---

## 14. Risks & Mitigations

| Risk | Impact | Mitigation |
|:---|:---|:---|
| Missing dependencies during build | Field deployment failure | Automated discovery (kubespray-offline logic), pinned versions, build-time validation |
| Terraform provider lock mismatch | terraform init fails offline | Use `providers lock -platform=linux_amd64` during build |
| Package size growth | Distribution challenges | Limit apt mirror to required packages; prune unnecessary artifacts |
| Kubernetes image list drift | Missing images for new Kubespray versions | Robust discovery automation (Python parser for Jinja2 templates) |
| Checksum mismatches | Ansible failures | Download exact versions specified in Kubespray defaults |

---

## 15. Open Questions

1. ~~What Kubernetes version and core service versions are required for the first release?~~ **Resolved**: Use kubespray@master (latest K8s versions)
2. Which CNI plugin is standard (Calico vs. Cilium)?
3. Should package signing (Cosign) be mandatory for all builds?
4. What are the minimum hardware specs for bastion and cluster nodes?
5. Should vSphere support be added in a future release, or is OpenStack sufficient for cloud-based deployments?

---

## 16. Milestones

| Milestone | Description |
|:---|:---|
| **M1** | Define version matrix and dependency sources |
| **M2** | Build pipeline produces Zarf artifact with Terraform + Kubespray offline assets |
| **M3** | Deploy in lab air-gapped environment (OpenStack or vSphere) |
| **M4** | Add core services and GitOps bootstrap flow |
| **M5** | Document runbooks and validation steps (SBOM, checksums) |
| **M6** | Security review and compliance validation |

---

## 17. Acceptance Criteria

- [ ] Single Zarf package provisions infrastructure, installs Kubernetes, and deploys core services
- [ ] Deployment succeeds without any external network access
- [ ] SBOM and checksum verification are available and documented
- [ ] All steps are repeatable and idempotent
- [ ] FluxCD syncs from in-cluster Gitea and manages core services
- [ ] Core services (Grafana, Keycloak, Ingress) are accessible post-deployment
- [ ] Runbooks cover build, deploy, and troubleshooting procedures

---

## Appendix A: User Stories

| ID | Story |
|:---|:---|
| **US-01** | As a Platform Engineer, I can build a single offline artifact that includes Terraform, Kubespray assets, and core service images so that field deployment is deterministic. |
| **US-02** | As a Field Operator, I can deploy a cluster without internet by running a single package on a bastion host. |
| **US-03** | As a Security Officer, I can review SBOM and checksums to confirm packaged contents and integrity. |
| **US-04** | As a Platform Engineer, I can extend the package with new Helm charts/images by adding to imagelists and rebuilding. |
| **US-05** | As a Field Operator, I can re-run a failed component without affecting already-deployed resources. |

---

## Appendix B: Glossary

| Term | Definition |
|:---|:---|
| **Air-gapped** | Network environment with no connectivity to the public internet |
| **Bastion Host** | Admin machine that executes deployment; serves as local registry/repo |
| **SBOM** | Software Bill of Materials—inventory of all software components |
| **Zarf** | Air-gap packaging tool for Kubernetes deployments |
| **Kubespray** | Ansible-based Kubernetes installer |
| **kubespray-offline** | Scripts for preparing Kubespray offline dependencies |
| **FluxCD** | GitOps operator for Kubernetes |
| **Gitea** | Lightweight Git server deployed in-cluster |
