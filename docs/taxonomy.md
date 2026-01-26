# Documentation Taxonomy (Diátaxis Framework)

## Framework Overview

Documentation organized by user need across two axes:
- **Practical/Theoretical**: Doing vs Understanding
- **Study/Work**: Learning vs Applying

```
                    PRACTICAL
                        │
         TUTORIALS      │      HOW-TO GUIDES
    (learning-oriented) │  (problem-oriented)
                        │
STUDY ──────────────────┼────────────────── WORK
                        │
      EXPLANATION       │      REFERENCE
  (understanding-       │   (information-
      oriented)         │      oriented)
                        │
                   THEORETICAL
```

## 1. TUTORIALS (Learning-Oriented)

**Purpose**: Take a newcomer from zero to working deployment through guided learning.

**Characteristics**:
- Step-by-step, no assumptions
- Reproducible outcomes
- Minimal explanation (defer to Explanation)
- Safe to experiment

### Current Mapping
- **NEW**: `tutorials/01-first-deployment.md`
  - Build first package in Zone A
  - Deploy to single-node cluster
  - Verify core services
  - ~30 minutes, bare-metal only

- **NEW**: `tutorials/02-openstack-deployment.md`
  - Terraform provisioning
  - Multi-node HA cluster
  - GitOps workflow
  - ~60 minutes

### To Create
```markdown
# Tutorial: Your First Air-Gap Deployment

## What You'll Build
Single-node Kubernetes cluster with core services in 30 minutes.

## Prerequisites
- Ubuntu 24.04 build host (8GB RAM, 100GB disk)
- Ubuntu 24.04 target node (8GB RAM, 100GB disk)
- SSH access between hosts

## Steps
1. Clone repository
2. Configure versions
3. Collect assets (15 min)
4. Build package (5 min)
5. Transfer to bastion
6. Deploy cluster (10 min)
7. Verify services

## What You Learned
- Three-zone architecture
- Zarf packaging workflow
- Bastion role
- Cluster validation
```

## 2. HOW-TO GUIDES (Problem-Oriented)

**Purpose**: Solve specific real-world problems. Assumes working knowledge.

**Characteristics**:
- Goal-oriented recipes
- Assumes prerequisites met
- Multiple paths acceptable
- Production-focused

### Current Mapping

#### Build Phase
- `docs/build-runbook.md` → `how-to/build-air-gap-package.md`
- **NEW**: `how-to/update-component-versions.md`
- **NEW**: `how-to/add-custom-images.md`
- **NEW**: `how-to/mirror-terraform-providers.md`

#### Deploy Phase
- `docs/deployment-runbook-baremetal.md` → `how-to/deploy-baremetal-cluster.md`
- `docs/deployment-runbook-openstack.md` → `how-to/deploy-openstack-cluster.md`
- `docs/bastion-setup-guide.md` → `how-to/configure-bastion-services.md`
- **NEW**: `how-to/deploy-multi-cluster.md`
- **NEW**: `how-to/deploy-behind-proxy.md`

#### Verify Phase
- `docs/cluster-health-verification-guide.md` → `how-to/verify-cluster-health.md`
- `docs/package-integrity-guide.md` → `how-to/verify-package-integrity.md`

#### Operate Phase
- `docs/troubleshooting-guide.md` → `how-to/troubleshoot-deployment.md`
- `docs/cleanup-guide.md` → `how-to/cleanup-cluster.md`
- **NEW**: `how-to/upgrade-kubernetes-version.md`
- **NEW**: `how-to/rotate-certificates.md`
- **NEW**: `how-to/backup-restore-cluster.md`

#### Extend Phase
- `docs/extension-guide.md` → `how-to/add-custom-services.md`
- `docs/zarf-package-creation-guide.md` → `how-to/create-zarf-components.md`
- **NEW**: `how-to/integrate-external-registry.md`
- **NEW**: `how-to/customize-kubespray-config.md`

### Structure Template
```markdown
# How To: [Achieve Specific Goal]

## Problem
[What user wants to accomplish]

## Prerequisites
- [Checklist]

## Solution
### Option 1: [Approach Name]
[Steps]

### Option 2: [Alternative Approach]
[Steps]

## Verification
[How to confirm success]

## Troubleshooting
[Common issues specific to this task]

## See Also
- [Related how-tos]
- [Reference docs]
```

## 3. REFERENCE (Information-Oriented)

**Purpose**: Provide accurate, complete technical specifications for lookup.

**Characteristics**:
- Comprehensive, authoritative
- Structured for scanning
- Minimal narrative
- Version-specific

### Current Mapping

#### Configuration Reference
- `docs/zarf-variables-reference.md` → `reference/zarf-variables.md`
- `docs/offline-repo-configuration.md` → `reference/offline-repositories.md`
- `config/versions.env` → `reference/component-versions.md`
- **NEW**: `reference/kubespray-variables.md`
- **NEW**: `reference/terraform-variables.md`
- **NEW**: `reference/ansible-inventory.md`

#### API/CLI Reference
- **NEW**: `reference/zarf-commands.md`
- **NEW**: `reference/deployment-scripts.md`
- **NEW**: `reference/environment-variables.md`

#### Architecture Reference
- **NEW**: `reference/network-ports.md`
- **NEW**: `reference/disk-requirements.md`
- **NEW**: `reference/service-endpoints.md`

#### Compatibility Reference
- **NEW**: `reference/version-compatibility-matrix.md`
- **NEW**: `reference/supported-platforms.md`
- **NEW**: `reference/tested-configurations.md`

### Structure Template
```markdown
# Reference: [Component/API Name]

## Overview
[One paragraph: what this is]

## [Section 1]
### Parameter Name
- **Type**: string
- **Required**: yes
- **Default**: `value`
- **Description**: [What it does]
- **Example**: `VARIABLE=value`

[Repeat for all parameters]

## Examples
[Minimal, complete examples]

## Version History
- v1.2.0: Added `new_param`
- v1.1.0: Deprecated `old_param`
```

## 4. EXPLANATION (Understanding-Oriented)

**Purpose**: Illuminate concepts, design decisions, and context.

**Characteristics**:
- Conceptual, not procedural
- Explains "why" not "how"
- Connects ideas
- Opinionated where appropriate

### Current Mapping

#### Architecture
- `docs/design-document.md` → `explanation/architecture-overview.md`
- `docs/build-flow-diagram.md` → `explanation/build-process.md`
- **NEW**: `explanation/three-zone-model.md`
- **NEW**: `explanation/air-gap-constraints.md`
- **NEW**: `explanation/bastion-architecture.md`

#### Design Decisions
- **NEW**: `explanation/why-kubespray.md`
- **NEW**: `explanation/why-zarf.md`
- **NEW**: `explanation/offline-first-design.md`
- **NEW**: `explanation/security-model.md`

#### Technical Deep-Dives
- `docs/kubespray-idempotency.md` → `explanation/kubespray-idempotency.md`
- `docs/kubespray-offline-idempotency.md` → `explanation/offline-mode-idempotency.md`
- `docs/terraform-idempotency.md` → `explanation/terraform-idempotency.md`
- `docs/fluxcd-idempotency.md` → `explanation/fluxcd-idempotency.md`
- **NEW**: `explanation/package-integrity-model.md`
- **NEW**: `explanation/gitops-in-airgap.md`

#### Requirements Context
- `docs/product-requirements.md` → `explanation/requirements-rationale.md`
- **NEW**: `explanation/compliance-considerations.md`
- **NEW**: `explanation/edge-deployment-patterns.md`

### Structure Template
```markdown
# Explanation: [Concept/Decision]

## Context
[What problem space this addresses]

## The Challenge
[What makes this difficult/interesting]

## Our Approach
[How we solve it, design decisions]

## Alternatives Considered
[What we didn't choose and why]

## Tradeoffs
[What we gain/lose with this approach]

## Implications
[How this affects users/operations]

## Related Concepts
[Links to other explanations]
```

## 5. Proposed Directory Structure

```
docs/
├── README.md                          # Navigation hub
│
├── tutorials/                         # LEARNING
│   ├── 01-first-deployment.md
│   ├── 02-openstack-deployment.md
│   └── 03-custom-services.md
│
├── how-to/                            # PROBLEM-SOLVING
│   ├── build/
│   │   ├── build-air-gap-package.md
│   │   ├── update-component-versions.md
│   │   ├── add-custom-images.md
│   │   └── mirror-terraform-providers.md
│   ├── deploy/
│   │   ├── deploy-baremetal-cluster.md
│   │   ├── deploy-openstack-cluster.md
│   │   ├── configure-bastion-services.md
│   │   └── deploy-multi-cluster.md
│   ├── verify/
│   │   ├── verify-cluster-health.md
│   │   └── verify-package-integrity.md
│   ├── operate/
│   │   ├── troubleshoot-deployment.md
│   │   ├── cleanup-cluster.md
│   │   ├── upgrade-kubernetes-version.md
│   │   └── backup-restore-cluster.md
│   └── extend/
│       ├── add-custom-services.md
│       ├── create-zarf-components.md
│       └── customize-kubespray-config.md
│
├── reference/                         # INFORMATION
│   ├── configuration/
│   │   ├── zarf-variables.md
│   │   ├── kubespray-variables.md
│   │   ├── terraform-variables.md
│   │   └── environment-variables.md
│   ├── architecture/
│   │   ├── network-ports.md
│   │   ├── disk-requirements.md
│   │   └── service-endpoints.md
│   ├── compatibility/
│   │   ├── component-versions.md
│   │   ├── version-compatibility-matrix.md
│   │   └── supported-platforms.md
│   └── cli/
│       ├── zarf-commands.md
│       └── deployment-scripts.md
│
└── explanation/                       # UNDERSTANDING
    ├── architecture/
    │   ├── architecture-overview.md
    │   ├── three-zone-model.md
    │   ├── air-gap-constraints.md
    │   ├── bastion-architecture.md
    │   └── build-process.md
    ├── design-decisions/
    │   ├── why-kubespray.md
    │   ├── why-zarf.md
    │   ├── offline-first-design.md
    │   └── security-model.md
    ├── technical/
    │   ├── kubespray-idempotency.md
    │   ├── offline-mode-idempotency.md
    │   ├── terraform-idempotency.md
    │   ├── fluxcd-idempotency.md
    │   ├── package-integrity-model.md
    │   └── gitops-in-airgap.md
    └── requirements/
        ├── requirements-rationale.md
        ├── compliance-considerations.md
        └── edge-deployment-patterns.md
```

## 6. Migration Strategy

### Phase 1: Establish Structure
1. Create directory structure
2. Write `docs/README.md` navigation hub
3. Create templates for each quadrant

### Phase 2: Migrate Existing Docs
1. **Tutorials**: Create new (none exist)
2. **How-To**: Refactor runbooks/guides
3. **Reference**: Extract from guides, add missing
4. **Explanation**: Reorganize design docs, add context

### Phase 3: Fill Gaps
Priority order:
1. Tutorial: First deployment (critical for onboarding)
2. Reference: Version compatibility matrix
3. How-To: Upgrade procedures
4. Explanation: Why Kubespray/Zarf

### Phase 4: Deprecate Old Structure
1. Add redirects in old docs
2. Update all internal links
3. Archive old structure after 1 release cycle

## 7. Documentation Standards

### Diátaxis-Specific Rules

#### Tutorials
- **Must** be reproducible start-to-finish
- **Must** state learning objectives upfront
- **Must not** explain concepts (link to Explanation)
- **Must** provide exact commands/values

#### How-To Guides
- **Must** state the problem/goal first
- **Must** list prerequisites
- **Must not** teach concepts (link to Explanation)
- **May** offer multiple approaches

#### Reference
- **Must** be comprehensive for the scope
- **Must** use consistent structure
- **Must not** include procedures (link to How-To)
- **Must** specify version applicability

#### Explanation
- **Must** explain "why" not "how"
- **Must** provide context and background
- **Must not** include step-by-step procedures
- **May** be opinionated

### Cross-Linking Rules
- Tutorials → Explanation (for concepts)
- How-To → Reference (for parameters)
- How-To → Explanation (for context)
- Reference → How-To (for usage examples)
- Explanation → Reference (for specifications)

### Metadata Template
```markdown
---
type: [tutorial|how-to|reference|explanation]
audience: [build-engineer|field-operator|security-auditor|platform-architect]
difficulty: [beginner|intermediate|advanced]
time: [estimated minutes]
version: [applicable version range]
last_updated: YYYY-MM-DD
---
```

## 8. Quality Checklist

### For Each Document
- [ ] Correct quadrant (Tutorial/How-To/Reference/Explanation)
- [ ] Metadata complete
- [ ] Links to related docs in other quadrants
- [ ] Code blocks have language specified
- [ ] Commands show expected output
- [ ] Prerequisites clearly stated
- [ ] Version-specific information marked

### For Tutorials
- [ ] Tested end-to-end on clean system
- [ ] Takes stated time ±20%
- [ ] Learning objectives achieved
- [ ] No unexplained concepts

### For How-To Guides
- [ ] Problem clearly stated
- [ ] Solution works in production
- [ ] Verification steps included
- [ ] Troubleshooting section present

### For Reference
- [ ] All parameters documented
- [ ] Examples are minimal and complete
- [ ] Version history included
- [ ] Alphabetically or logically ordered

### For Explanation
- [ ] Explains "why" not "how"
- [ ] Design decisions justified
- [ ] Tradeoffs acknowledged
- [ ] Related concepts linked

## 9. Maintenance

### Update Triggers
- **Code change** → Update How-To + Reference
- **Architecture change** → Update Explanation + Reference
- **New feature** → Add Tutorial + How-To + Reference + Explanation
- **Version bump** → Update Reference + How-To
- **Bug fix** → Update How-To (troubleshooting)

### Review Cadence
- **Tutorials**: Test quarterly
- **How-To**: Review on each release
- **Reference**: Update with code changes
- **Explanation**: Review annually or on major changes

### Ownership
- Build Engineer: Build how-tos, build reference
- Field Operator: Deploy how-tos, troubleshooting
- Platform Architect: Explanation docs, architecture reference
- All: Tutorials (collaborative)
