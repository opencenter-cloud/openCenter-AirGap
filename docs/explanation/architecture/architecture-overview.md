---
doc_type: explanation
audience: Platform Engineers, Architects
scope: High-level system design, rationale, and architectural decisions
---

# Architecture Overview

This document explains the high-level architecture of openCenter AirGap, the rationale behind key design decisions, and how components interact to enable air-gapped Kubernetes deployments.

## Purpose

**Purpose**: For platform engineers and architects, explains the system design of openCenter AirGap, covering the three-zone model, component architecture, and design trade-offs.

## System Context

openCenter AirGap solves a specific problem: deploying production Kubernetes clusters in environments with no internet connectivity. This constraint drives the entire architecture.

**The Challenge**: A typical Kubernetes deployment pulls hundreds of container images, OS packages, Python libraries, and binaries from the internet. In air-gapped environments (military, financial, healthcare, edge computing), this is impossible.

**The Solution**: Collect all dependencies in a connected environment (Zone A), package them into a single artifact, physically transfer to the disconnected environment (Zone C), and deploy using local mirrors.

**Evidence**: `README.md:What This Is`, `README.md:Three-Zone Model`

## Three-Zone Architecture

The system operates across three distinct security zones:

```
┌─────────────────────────────────────────────────────────────┐
│ Zone A: Factory (Connected)                                 │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │ Build Host   │───▶│ openCenter   │───▶│ Zarf Package │   │
│  │ (internet)   │    │ Build System │    │ (.tar.zst)   │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│         │                     │                             │
│         ▼                     ▼                             │
│  Downloads from          Collects into                      │
│  public sources          single artifact                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ Physical Transfer (USB, DVD, Courier)
┌─────────────────────────────────────────────────────────────┐
│ Zone B: Airlock (Transfer)                                  │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │ Security     │───▶│ Verification │───▶│ Approved     │   │
│  │ Scan         │    │ (SBOM, sig)  │    │ Transfer     │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ Physical Transfer
┌─────────────────────────────────────────────────────────────┐
│ Zone C: Field (Disconnected)                                │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │ Bastion      │───▶│ Cluster      │───▶│ Workloads    │   │
│  │ (registry +  │    │ Nodes        │    │ (apps)       │   │
│  │  repos)      │    │ (K8s)        │    │              │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│         │                     │                             │
│         ▼                     ▼                             │
│  Serves local            Pulls from                         │
│  mirrors                 bastion only                       │
└─────────────────────────────────────────────────────────────┘
```

**Evidence**: `README.md:Architecture`, `README.md:Three-Zone Model`

### Zone A: Factory (Connected)

**Role**: Build and package all dependencies

**Components**:
- Build host with internet access
- openCenter build system (Python CLI)
- Dependency collectors (kubespray-offline, image scanners)
- Zarf packaging tool

**Inputs**:
- `config/versions.env` - Version specifications
- `config/components.yaml` - Component manifest (auto-generated)
- Public package sources (registries, repositories, GitHub)

**Outputs**:
- `dist/zarf-package-*.tar.zst` - Complete deployment package (~25 GB)
- `dist/zarf-package-*-sbom.json` - Software Bill of Materials
- `dist/zarf-package-*.sha256` - Checksum file

**Evidence**: `src/opencenter_build/cli.py:build()`, `src/opencenter_build/orchestrator.py`

### Zone B: Airlock (Transfer)

**Role**: Security verification and controlled transfer

**Components**:
- Security scanning tools (Trivy, Cosign)
- SBOM validation
- Approval workflow

**Process**:
1. Scan package for CVEs
2. Verify cryptographic signature
3. Validate SBOM against policy
4. Approve transfer to Zone C

**Evidence**: `src/opencenter_build/verifier.py`, `SECURITY.md`

### Zone C: Field (Disconnected)

**Role**: Deploy and operate Kubernetes cluster

**Components**:
- Bastion host (registry + file server)
- Cluster nodes (control plane + workers)
- Kubernetes workloads

**Process**:
1. Deploy Zarf package to bastion
2. Start local registry and file server
3. Configure cluster nodes to use bastion
4. Deploy Kubernetes with Kubespray
5. Deploy applications via FluxCD

**Evidence**: `zarf.yaml:components`, `src/opencenter_build/cli.py:serve()`

## Component Architecture

### Build System Components

```
┌─────────────────────────────────────────────────────────────┐
│ CLI Layer (Typer + Rich)                                    │
│  - User interface                                           │
│  - Command routing                                          │
│  - Progress display                                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Orchestration Layer                                         │
│  - BuildOrchestrator: Step execution                        │
│  - StateManager: Checkpoint/resume                          │
│  - TransactionManager: Rollback support                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Business Logic Layer                                        │
│  - ComponentManifest: Manifest management                   │
│  - RepositoryScanner: Image/chart discovery                 │
│  - ZarfGenerator: zarf.yaml generation                      │
│  - ManifestGenerator: Artifact manifest                     │
│  - PackageVerifier: Integrity checks                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Infrastructure Layer                                        │
│  - ConfigLoader: versions.env parsing                       │
│  - SecretsManager: File-based secrets                       │
│  - Logging: Structured logging                              │
│  - Metrics: Build telemetry                                 │
│  - Validation: Schema validation                            │
└─────────────────────────────────────────────────────────────┘
```

**Evidence**: `src/opencenter_build/` directory structure

### Deployment Components

```
┌─────────────────────────────────────────────────────────────┐
│ Zarf Package                                                │
│  - Component: bootstrap-tools (Python venv, scripts)        │
│  - Component: terraform-providers (OpenStack only)          │
│  - Component: kubespray-core (playbooks, binaries, repos)   │
│  - Component: k8s-images (container images)                 │
│  - Component: operator-tools (kubectl, helm, k9s)           │
│  - Component: deploy-cluster (orchestration)                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ zarf package deploy
┌─────────────────────────────────────────────────────────────┐
│ Bastion Services                                            │
│  - Container registry (port 5000)                           │
│  - Nginx file server (port 8080)                            │
│  - Gitea (port 3000, optional)                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ ansible-playbook
┌─────────────────────────────────────────────────────────────┐
│ Kubernetes Cluster                                          │
│  - Control plane (etcd, API server, scheduler, controller)  │
│  - Workers (kubelet, kube-proxy, containerd)                │
│  - CNI (Calico)                                             │
│  - FluxCD (GitOps)                                          │
└─────────────────────────────────────────────────────────────┘
```

**Evidence**: `zarf.yaml:components`, `README.md:Architecture`

## Key Design Decisions

### 1. Why Zarf for Packaging

**Decision**: Use Zarf as the packaging framework instead of custom tar archives or Docker images.

**Rationale**:
- **Declarative manifest**: `zarf.yaml` defines components, dependencies, and deployment actions
- **Built-in registry**: Zarf includes a container registry for air-gap deployments
- **SBOM generation**: Automatic software bill of materials
- **Cryptographic signing**: Cosign integration for package integrity
- **Component independence**: Deploy only what you need
- **Community support**: Active project with DoD backing

**Trade-offs**:
- **Dependency**: Requires Zarf CLI on bastion
- **Learning curve**: Zarf-specific concepts and syntax
- **Package size**: Zarf adds ~500 MB overhead

**Evidence**: `zarf.yaml`, `README.md:What This Is`, Zarf documentation

### 2. Python for Build System

**Decision**: Implement build system in Python instead of pure Bash.

**Rationale**:
- **Structured data**: JSON/YAML parsing with jsonschema validation
- **Error handling**: Exception hierarchy with context
- **State management**: Atomic file operations with rollback
- **Testing**: Property-based testing with hypothesis
- **Type safety**: mypy strict mode for correctness
- **Maintainability**: Clear module boundaries and interfaces

**Trade-offs**:
- **Runtime dependency**: Requires Python 3.12+
- **Startup time**: Slower than Bash for simple scripts
- **Deployment**: More complex than single Bash script

**Evidence**: `src/opencenter_build/`, `pyproject.toml`, `CONTRIBUTING.md:Language Selection`

### 3. Auto-Generated Component Manifest

**Decision**: Auto-generate `components.yaml` from `versions.env` instead of manual editing.

**Rationale**:
- **Single source of truth**: `versions.env` is the only file users edit
- **Consistency**: Prevents version mismatches between manifest and config
- **Discoverability**: `scan --repos` auto-discovers images and charts
- **Flexibility**: Manual additions preserved during regeneration
- **Simplicity**: Users don't need to understand manifest schema

**Trade-offs**:
- **Magic**: Auto-generation can be surprising
- **Debugging**: Harder to troubleshoot manifest issues
- **Customization**: Advanced users may want full control

**Evidence**: `src/opencenter_build/cli.py:build()`, `src/opencenter_build/component_manifest.py:create_default_manifest()`

### 4. Checkpoint/Resume Build System

**Decision**: Implement stateful build with checkpoint/resume capability.

**Rationale**:
- **Network failures**: Internet downloads can fail mid-build
- **Time savings**: Resume from last successful step (not restart)
- **Debugging**: Inspect state after failure
- **Reproducibility**: State file documents what was built

**Trade-offs**:
- **Complexity**: State management adds code complexity
- **State corruption**: File corruption can break resume
- **Disk usage**: State files consume disk space

**Evidence**: `src/opencenter_build/state.py:StateManager`, `src/opencenter_build/orchestrator.py:BuildOrchestrator`

### 5. Bastion Architecture

**Decision**: Use dedicated bastion host instead of distributing packages to each node.

**Rationale**:
- **Centralized control**: Single point for package management
- **Bandwidth efficiency**: Nodes pull from local network (not USB)
- **Security**: Bastion is the only host with package access
- **Scalability**: Add nodes without re-distributing packages
- **Observability**: Monitor all package pulls from one location

**Trade-offs**:
- **Single point of failure**: Bastion down = cluster can't pull images
- **Network dependency**: Requires reliable bastion-to-node connectivity
- **Resource overhead**: Bastion needs 100+ GB disk, 8+ GB RAM

**Evidence**: `zarf.yaml:deploy-cluster`, `README.md:Three-Zone Model`

## Data Flow

### Build Flow

```
versions.env
    │
    ▼ parse_versions_env()
BuildConfig
    │
    ▼ create_default_manifest()
components.yaml (auto-generated)
    │
    ▼ scan_repositories()
components.yaml (with discoveries)
    │
    ▼ BuildOrchestrator.execute()
Build Steps:
  1. scan_repositories()      → config/all-images.txt
  2. collect_helm_charts()    → config/helm-charts.txt
  3. generate_kubespray_lists() → config/kubespray-files.txt
  4. mirror_terraform_providers() → assets/terraform-mirror/
  5. organize_assets()        → assets/
  6. create_zarf_package()    → dist/zarf-package-*.tar.zst
  7. generate_manifest()      → dist/artifact-manifest.json
    │
    ▼
Zarf Package + SBOM + Checksum
```

**Evidence**: `src/opencenter_build/orchestrator.py:BuildOrchestrator`, `src/opencenter_build/cli.py:build()`

### Deployment Flow

```
Zarf Package
    │
    ▼ zarf package deploy
Bastion Services:
  - Extract to /opt/opencenter/
  - Start registry (port 5000)
  - Start nginx (port 8080)
  - Load images into registry
    │
    ▼ ansible-playbook offline-repo.yml
Cluster Nodes:
  - Configure apt sources → bastion:8080/debs
  - Configure pip index → bastion:8080/pypi
    │
    ▼ ansible-playbook cluster.yml
Kubernetes Cluster:
  - Install containerd (from bastion)
  - Install kubelet (from bastion)
  - Pull images (from bastion:5000)
  - Bootstrap control plane
  - Join worker nodes
    │
    ▼ FluxCD reconciliation
Applications:
  - Deploy platform services
  - Deploy customer workloads
```

**Evidence**: `zarf.yaml:components`, `README.md:Complete Cluster Lifecycle`

## Security Architecture

### Threat Model

**Threats mitigated**:
- **Supply chain attacks**: SBOM + signature verification
- **Package tampering**: Cryptographic signing with Cosign
- **Credential exposure**: File-based secrets (never in git)
- **Unauthorized access**: SSH key-based authentication
- **Network eavesdropping**: TLS for all external connections

**Threats NOT mitigated**:
- **Insider threats**: Assumes trusted build environment
- **Physical security**: Assumes secure Zone B transfer
- **Runtime vulnerabilities**: Requires separate runtime security (Kyverno, PSS)

**Evidence**: `SECURITY.md`, `src/opencenter_build/secrets.py`, `src/opencenter_build/verifier.py`

### Defense in Depth

**Layer 1: Build-time**
- Dependency pinning (`config/versions.env`)
- Schema validation (`src/opencenter_build/validation.py`)
- Secrets isolation (`.secrets/` directory)

**Layer 2: Package-time**
- SBOM generation (Zarf)
- Cryptographic signing (Cosign)
- Checksum generation (SHA256)

**Layer 3: Transfer-time**
- Signature verification
- SBOM validation
- CVE scanning (Trivy)

**Layer 4: Deploy-time**
- Package integrity check
- SSH key authentication
- Bastion network isolation

**Layer 5: Runtime**
- Pod Security Admission (Kubespray)
- Kyverno policies (openCenter-gitops-base)
- NetworkPolicies (openCenter-gitops-base)

**Evidence**: `SECURITY.md`, `src/opencenter_build/verifier.py`, ecosystem.md (in parent workspace)

## Scalability Considerations

### Build Scalability

**Horizontal scaling**: Not supported (single build host)

**Vertical scaling**:
- CPU: Parallel downloads (`--parallel N`)
- RAM: Caching (more RAM = faster builds)
- Disk: SSD vs HDD (3-5x faster)
- Network: Bandwidth (major bottleneck)

**Typical limits**:
- Components: 500+ (tested)
- Images: 1000+ (tested)
- Package size: 50 GB (practical limit)

**Evidence**: `src/opencenter_build/cli.py:build()`, `src/opencenter_build/scanner.py:RepositoryScanner`

### Deployment Scalability

**Cluster size**:
- Control plane: 5 nodes (etcd limit)
- Workers: 100 nodes (Kubernetes default)
- Pods: 11,000 (Kubernetes default)

**Bastion limits**:
- Concurrent pulls: 100+ (registry limit)
- Bandwidth: 10 Gbps (network limit)
- Storage: 200 GB (practical limit)

**Evidence**: Kubernetes scalability documentation, observed deployments

## Performance Characteristics

### Build Performance

**Bottlenecks**:
1. **Network bandwidth** (major) - Downloading 15+ GB of images
2. **Disk I/O** (moderate) - Writing 50+ GB of artifacts
3. **CPU** (minor) - Parallel downloads and compression

**Optimization strategies**:
- Use SSD for build directory
- Increase parallel workers (`--parallel 8`)
- Use fast internet connection (100+ Mbps)
- Cache builds (resume from checkpoint)

**Evidence**: Observed from build logs, `src/opencenter_build/orchestrator.py`

### Deployment Performance

**Bottlenecks**:
1. **Bastion-to-node bandwidth** (major) - Pulling images
2. **Disk I/O on nodes** (moderate) - Extracting images
3. **Ansible serial execution** (minor) - Node provisioning

**Optimization strategies**:
- Use 10 Gbps network between bastion and nodes
- Use SSD on cluster nodes
- Increase Ansible parallelism (Kubespray config)

**Evidence**: Observed from deployment logs, Kubespray documentation

## Extensibility Points

### Adding New Components

**Extension point**: `opencenter-build add` command

**Process**:
1. Add component to `components.yaml` (manual or via CLI)
2. Rebuild package
3. Deploy updated package

**Evidence**: `src/opencenter_build/cli.py:add()`, `src/opencenter_build/component_manifest.py`

### Adding New Build Steps

**Extension point**: `BuildOrchestrator.register_step_handler()`

**Process**:
1. Implement step handler function
2. Register with orchestrator
3. Add to build sequence

**Evidence**: `src/opencenter_build/orchestrator.py:BuildOrchestrator`, `src/opencenter_build/cli.py:build()`

### Adding New Zarf Components

**Extension point**: `zarf.yaml:components`

**Process**:
1. Define component in `zarf.yaml`
2. Add files/images to component
3. Define deployment actions

**Evidence**: `zarf.yaml`, Zarf documentation

## Operational Characteristics

### Observability

**Logging**:
- Structured logs (`src/opencenter_build/logging.py`)
- Multiple levels (DEBUG, INFO, WARNING, ERROR)
- File and console output

**Metrics**:
- Build duration
- Component counts
- Artifact sizes
- Step timings

**State**:
- Build state file (`build/state.json`)
- Checkpoint/resume capability
- Progress tracking

**Evidence**: `src/opencenter_build/logging.py`, `src/opencenter_build/metrics.py`, `src/opencenter_build/state.py`

### Maintainability

**Code organization**:
- Clear module boundaries
- Single responsibility principle
- Dependency injection

**Testing**:
- Unit tests (96.8% coverage)
- Property-based tests (hypothesis)
- Integration tests

**Documentation**:
- Diátaxis framework
- Code comments
- Type hints

**Evidence**: `src/opencenter_build/`, `tests/`, `docs/`, `pyproject.toml:[tool.coverage]`

## Trade-offs and Limitations

### Current Limitations

1. **kubespray-offline integration**: In progress, not fully automated
2. **Zarf package creation**: Requires Zarf CLI (not pure Python)
3. **Terraform provider mirroring**: OpenStack only
4. **Multi-architecture**: amd64 only (arm64 planned)
5. **Windows nodes**: Separate process (opencenter-windows)

**Evidence**: `README.md:Project Status`, `zarf.yaml:metadata:architecture`

### Architectural Trade-offs

**Simplicity vs Flexibility**:
- Chose simplicity: Auto-generated manifest, opinionated structure
- Trade-off: Less flexibility for advanced users

**Performance vs Reliability**:
- Chose reliability: Checkpoint/resume, state management
- Trade-off: More complex code, slower builds

**Portability vs Integration**:
- Chose integration: Zarf, Kubespray, FluxCD
- Trade-off: More dependencies, less portable

**Evidence**: Design decision sections above

## Future Architecture Evolution

### Planned Improvements

1. **Binary distribution**: PyInstaller for single-file executable
2. **Multi-architecture**: arm64 support
3. **Enhanced SBOM**: Vulnerability scanning integration
4. **Build determinism**: Reproducible builds with fixed timestamps
5. **Distributed builds**: Multi-host parallel builds

**Evidence**: `README.md:Planned`

### Architectural Principles

**Guiding principles** for future changes:

1. **Simplicity first**: Prefer simple solutions over clever ones
2. **Evidence-based**: All claims backed by code or tests
3. **Fail-safe**: Errors should be obvious and recoverable
4. **Composability**: Components should work independently
5. **Observability**: All operations should be traceable

**Evidence**: `CONTRIBUTING.md`, `.kiro/steering/Engineering.md`

## See Also

- [Three-Zone Security Model](three-zone-security.md) - Detailed security architecture
- [Bastion Architecture](bastion-architecture.md) - Bastion service design
- [Why Zarf](../design-decisions/why-zarf.md) - Packaging framework rationale
- [Python vs Bash](../design-decisions/python-vs-bash.md) - Language selection
- [State Management Approach](../design-decisions/state-management.md) - Build state design
- [System Requirements](../../reference/system-requirements.md) - Hardware and software requirements
- [Build Steps Reference](../../reference/build-steps.md) - Detailed build phase breakdown
