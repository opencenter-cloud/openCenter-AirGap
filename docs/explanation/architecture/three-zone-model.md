---
type: explanation
audience: platform-architect, platform-engineer
version: 1.0.0
last_updated: 2026-01-25
doc_type: explanation
---

# The Three-Zone Model

Why openCenter separates build, transport, and deployment into distinct zones.

## The Problem

Traditional deployment tools assume ubiquitous internet access. They fetch dependencies at runtime—images from registries, packages from repos, binaries from CDNs. This "pull" model fails in air-gapped environments where no outbound connectivity exists.

Manual workarounds (sneakernet, ad-hoc scripts) are fragile. Missing a single dependency causes field deployment failure with no recourse.

## The Three-Zone Approach

openCenter inverts the model: dependencies are "pushed" into a single artifact in a connected environment, then deployed without any network access.

### Zone A: The Factory

**Environment**: Connected build host with internet access.

**Purpose**: Discover and collect all dependencies.

**Activities**:
- Parse IaC and Ansible to identify dependency graph
- Download container images from registries
- Download OS packages (apt/yum)
- Download Python wheels
- Mirror Terraform providers
- Package everything into single Zarf artifact
- Generate SBOM and checksums

**Key Insight**: All network operations happen here. Zone C never touches the internet.

**Tools**: kubespray-offline for asset discovery, Zarf for packaging, Syft for SBOM generation.

### Zone B: The Airlock

**Environment**: Secure media transport (USB drive, data diode, courier).

**Purpose**: Move artifact across security boundary.

**Characteristics**:
- Single immutable file: `zarf-package-*.tar.zst`
- Cryptographically signed (Cosign)
- Checksum verified
- SBOM included for audit
- No network connectivity required

**Key Insight**: The artifact is the security boundary. Everything inside is trusted; everything outside is untrusted.

**Compliance**: Supports data diode workflows, manual inspection, and air-gap transfer protocols.

### Zone C: The Field

**Environment**: Disconnected deployment site with no internet.

**Purpose**: Deploy cluster using only local resources.

**Architecture**:
```
Bastion Host (Pseudo-Internet)
├── Registry (port 35000) → Serves container images
├── Nginx (port 80) → Serves binaries, packages, wheels
└── Ansible Control → Orchestrates node configuration

Cluster Nodes
├── Pull images from bastion:35000
├── Download binaries from bastion:80
└── Install packages from bastion:80
```

**Key Insight**: The bastion acts as a "pseudo-internet" for the cluster. Nodes think they're pulling from upstream sources, but everything is local.

**Tools**: Zarf for orchestration, Kubespray for cluster bootstrap, FluxCD for GitOps.

## Why This Works

**Determinism**: Same artifact produces identical cluster every time. No runtime dependency resolution means no surprises.

**Auditability**: SBOM lists every component. Security teams can review before Zone B transfer.

**Idempotency**: Re-running deployment is safe. Ansible checks current state before making changes.

**Offline-First**: Internet isolation is the baseline, not an exception. No code paths assume connectivity.

## Alternatives Considered

### Option 1: Lightweight Installer + Manual Asset Collection

**Approach**: Ship small installer, operator manually collects dependencies.

**Rejected**: Error-prone, inconsistent, no SBOM, high failure rate.

### Option 2: Multiple Tarballs

**Approach**: Separate tarballs for images, packages, binaries.

**Rejected**: Coordination overhead, version skew risk, no atomic delivery.

### Option 3: Network Mirror in Zone C

**Approach**: Deploy full mirror of upstream registries/repos in Zone C.

**Rejected**: Massive storage requirements, complex synchronization, unnecessary for single-cluster deployments.

## Tradeoffs

**Advantages**:
- Zero runtime network dependency
- Deterministic deployments
- Comprehensive SBOM
- Single artifact simplifies logistics

**Disadvantages**:
- Large artifact size (5-10GB)
- Build phase requires internet
- Updates require new artifact
- Storage requirements for artifact distribution

## Design Decisions

**Why single artifact?**

Atomic delivery. Either you have everything or nothing. No partial state, no version skew.

**Why Zarf?**

Purpose-built for air-gap. Handles image retagging, variable substitution, SBOM generation, and signing. Alternatives (Helm, Kustomize) assume network access.

**Why bastion-as-hub?**

Centralized control. Single point for registry, repos, and orchestration. Nodes are stateless consumers.

**Why not pre-install on nodes?**

Flexibility. Same artifact works for bare-metal, VMs, or cloud. Nodes can be ephemeral.

## Implications

**For Platform Engineers**:
- Build pipeline must be comprehensive
- Asset discovery must be complete
- Version pinning is mandatory

**For Field Operators**:
- Bastion is critical infrastructure
- Package integrity verification is required
- No internet fallback exists

**For Security Officers**:
- SBOM review happens in Zone A
- Artifact signing provides chain of custody
- Zone C is truly isolated

## Related Concepts

- [Architecture Overview](architecture-overview.md) - Complete system design
- [Air-Gap Constraints](air-gap-constraints.md) - Technical limitations
- [Bastion Architecture](bastion-architecture.md) - Bastion design details
- [Why Zarf](../design-decisions/why-zarf.md) - Tool selection rationale
