**doc_type: explanation**
**audience: Platform Engineers, Architects**

# Architecture Overview

This document explains the design of openCenter AirGap: why it's structured this way, what problems it solves, and what trade-offs were made.

## The Air-Gap Problem

Deploying Kubernetes in disconnected environments hits three constraints:

1. **No internet during deployment**: Target nodes can't pull from Docker Hub, apt repos, or PyPI
2. **Reproducibility**: Same artifact must produce identical clusters across sites
3. **Verification**: Security teams need to audit what's being deployed before it crosses the air-gap

Traditional deployment tools assume internet access. They download dependencies on-demand, which breaks in disconnected environments. Workarounds like "just mirror everything" create operational burden and version drift.

## Design Principles

**Single Artifact**: One file contains everything. No "step 1: download this, step 2: download that." The artifact is the deployment.

**Build Once, Deploy Many**: Build in a connected environment, deploy to N disconnected sites. The build process is expensive (downloads, scanning, packaging). Deployment is cheap (extract, serve, install).

**Cryptographic Verification**: SBOM and signatures travel with the artifact. Security officers verify before deployment, not after.

**Bastion as Local Mirror**: One node in the target environment serves as registry and package repository. Target nodes pull from bastion, not internet. This keeps the deployment model simple: nodes still use standard tools (apt, pip, containerd), just pointed at local sources.

## Three-Zone Architecture

### Zone A: Factory (Connected)

This is where the artifact is built. It has internet access and runs the build tooling.

**Components**:
- Build host (Ubuntu 24.04, 100GB+ disk)
- opencenter-build (Python CLI)
- kubespray-offline (asset discovery)
- Zarf (packaging framework)

**Process**:
1. Read component manifest (what to include)
2. Clone kubespray-offline
3. Run asset collection (downloads images, packages, binaries)
4. Collect Terraform providers (OpenStack only)
5. Create Zarf package (compress, SBOM, sign)

**Output**: `zarf-package-*.tar.zst` (~25GB compressed)

**Why this works**: All downloads happen once, in a controlled environment. Build failures are caught before the artifact crosses the air-gap. The build is deterministic: same inputs produce same outputs.

### Zone B: Airlock (Transfer)

Physical media transfer. USB drive, DVD, secure courier, or approved file transfer mechanism.

**Why this exists**: Regulated environments have formal processes for moving data across security boundaries. The artifact is self-contained and verifiable, so it fits into existing approval workflows.

### Zone C: Field (Disconnected)

This is the target environment. No internet access. The artifact is deployed here.

**Components**:
- Bastion host (Ubuntu 24.04, 100GB+ disk)
- Target nodes (3+ Ubuntu 24.04 nodes)
- Zarf CLI (pre-installed on bastion)

**Process**:
1. Copy artifact to bastion
2. Deploy Zarf package (extracts to `/opt/opencenter/`)
3. Start local services (registry on 5000, nginx on 8080)
4. Configure target nodes to use bastion repos
5. Run Kubespray to install Kubernetes
6. Deploy FluxCD and core services

**Why this works**: Bastion serves as a local mirror. Target nodes use standard tools (apt, containerd) but pull from bastion instead of internet. No custom agents or proprietary protocols. If a node needs a package, it's already on the bastion.

## Component Interaction

```
┌─────────────────────────────────────────────────────────────┐
│ Build Phase (Zone A)                                        │
│                                                              │
│  Component Manifest                                         │
│         │                                                    │
│         ▼                                                    │
│  opencenter-build ──▶ kubespray-offline ──▶ Asset Cache    │
│         │                                                    │
│         ▼                                                    │
│  Zarf Package Creator ──▶ SBOM Generator ──▶ Signer        │
│         │                                                    │
│         ▼                                                    │
│  zarf-package-*.tar.zst                                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ Physical Transfer
┌─────────────────────────────────────────────────────────────┐
│ Deploy Phase (Zone C)                                       │
│                                                              │
│  Bastion Host                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Zarf Extract ──▶ /opt/opencenter/                     │ │
│  │                                                        │ │
│  │ Registry (5000) ◀── images/                           │ │
│  │ Nginx (8080)    ◀── debs/, pypi/, files/              │ │
│  └────────────────────────────────────────────────────────┘ │
│         │                                                    │
│         ▼ SSH + Ansible                                     │
│  Target Nodes                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ apt ──▶ bastion:8080/debs/                            │ │
│  │ pip ──▶ bastion:8080/pypi/                            │ │
│  │ containerd ──▶ bastion:5000/                          │ │
│  │                                                        │ │
│  │ Kubernetes Cluster                                     │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### Why Zarf?

Zarf provides:
- Declarative packaging (zarf.yaml manifest)
- SBOM generation (tracks every component)
- Cryptographic signing (Cosign integration)
- Compression (tar.zst, ~40% smaller than tar.gz)
- Component-based structure (easy to add/remove pieces)

Alternative considered: Custom tar + manifest. Rejected because we'd be reimplementing SBOM, signing, and compression. Zarf is maintained by the CNCF and used in production by DoD projects.

### Why Kubespray?

Kubespray is Ansible-based, which means:
- Readable playbooks (no compiled binaries)
- Idempotent (safe to re-run)
- Extensible (add custom tasks)
- Well-tested (used by CNCF, large enterprises)

Alternative considered: kubeadm directly. Rejected because Kubespray handles OS-level setup (kernel params, firewall, swap), HA control plane, and CNI installation. Doing this manually is error-prone.

### Why kubespray-offline?

kubespray-offline discovers dependencies by parsing Kubespray playbooks and Helm charts. It generates lists of:
- Container images (from Helm values, Kubespray defaults)
- OS packages (from Kubespray package lists)
- Python wheels (from Kubespray requirements.txt)
- Kubernetes binaries (from Kubespray version matrix)

Alternative considered: Manual lists. Rejected because they drift when Kubespray updates. kubespray-offline stays in sync automatically.

### Why Bastion Model?

The bastion serves as a local mirror. This keeps the deployment model simple:
- Nodes use standard tools (apt, pip, containerd)
- No custom agents or proprietary protocols
- Easy to troubleshoot (curl, apt-cache policy, etc.)
- Works with existing automation (Ansible, Terraform)

Alternative considered: Pre-load every node with all packages. Rejected because:
- Wastes disk space (each node has 25GB of packages it won't use)
- Complicates updates (have to touch every node)
- Breaks standard tooling (apt expects a repository, not a local directory)

### Why Python CLI?

The original build system was bash scripts. We're migrating to Python for:
- Better error handling (exceptions vs exit codes)
- Testability (unit tests, property-based tests)
- Maintainability (type hints, structured logging)
- Extensibility (plugins, hooks)

Bash is still used for simple glue scripts (start-nginx.sh, setup-all.sh) because it's transparent and easy to audit.

## Data Flow

### Build Phase

1. **Input**: Component manifest (components.yaml) + version pins (versions.env)
2. **Asset Collection**: kubespray-offline downloads from internet
3. **Staging**: Assets copied to `assets/` directory
4. **Packaging**: Zarf reads zarf.yaml, compresses assets, generates SBOM
5. **Signing**: Cosign signs the package with a private key
6. **Output**: Artifact + SBOM + signature

### Deploy Phase

1. **Input**: Artifact on bastion
2. **Extraction**: Zarf unpacks to `/opt/opencenter/`
3. **Service Start**: Registry and nginx start, serving local content
4. **Node Configuration**: Ansible configures nodes to use bastion repos
5. **Cluster Install**: Kubespray installs Kubernetes, pulling from bastion
6. **GitOps Bootstrap**: FluxCD deploys core services from Gitea

## Security Model

**Threat Model**: Attacker controls the network between build host and internet. Attacker cannot modify the artifact after it's signed.

**Mitigations**:
- All downloads verified with checksums (kubespray-offline)
- Container images pulled by digest, not tag
- Artifact signed with Cosign (private key offline)
- SBOM includes every component (auditable before deployment)
- Trivy scans for CVEs (fail build on HIGH/CRITICAL)

**Trust Boundary**: The artifact. Everything inside is trusted (verified at build time). Everything outside is untrusted (network, external repos).

**Secrets**: Never in git. Injected at build time from `.secrets/` directory. See [Secrets Management](../../reference/secrets-management.md).

## Scalability

**Build**: Single-threaded. Takes 30-45 minutes. Parallelizing downloads would help, but adds complexity. Current bottleneck is network (downloading 25GB).

**Deploy**: Bastion serves 100+ nodes without issue. Registry and nginx are lightweight. Bottleneck is Ansible (serial SSH connections). Kubespray supports batching (10 nodes at a time).

**Storage**: Bastion needs 100GB. Each additional component adds ~1-5GB. If you hit limits, split into multiple packages (base + addons).

## Failure Modes

**Build fails mid-download**: Resume from last checkpoint. State manager tracks completed steps.

**Deploy fails mid-install**: Kubespray is idempotent. Re-run the playbook.

**Bastion loses power**: Registry and nginx restart automatically (systemd units). Cluster keeps running (nodes cache images).

**Node loses connectivity to bastion**: Cluster keeps running. New pods can't start (ImagePullBackOff). Fix network, pods recover automatically.

## Trade-offs

**Artifact Size**: 25GB compressed. Large, but unavoidable. We need every dependency. Splitting into multiple artifacts adds operational complexity.

**Build Time**: 30-45 minutes. Slow, but acceptable. Build once, deploy many times. If this becomes a bottleneck, parallelize downloads.

**Bastion as SPOF**: If bastion fails, new pods can't start. Mitigation: HA bastion (two nodes, load balanced). Not implemented yet because it adds complexity.

**Version Coupling**: All components pinned to tested versions. Updating one component requires rebuilding the entire artifact. This is intentional: we want tested combinations, not arbitrary mixes.

## Future Directions

**Incremental Updates**: Delta packages (only changed components). Reduces transfer size for updates.

**HA Bastion**: Two bastion nodes, load balanced. Eliminates SPOF.

**Multi-Arch**: ARM64 support. Requires separate builds (different binaries, different images).

**Modular Packages**: Base + addons. Deploy base first, add components later. Reduces initial artifact size.

See [Roadmap](../../roadmap.md) for details.
