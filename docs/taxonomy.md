---
id: documentation-taxonomy
title: "Documentation Taxonomy"
sidebar_label: Taxonomy
description: Diátaxis-based organization and navigation index for openCenter AirGap documentation.
doc_type: reference
audience: "platform engineers, field operators, contributors"
tags: [documentation, diataxis, navigation, taxonomy]
---

# Documentation Taxonomy

Diátaxis-based organization of openCenter AirGap documentation. Each document serves one purpose: learning (tutorials), task completion (how-to), lookup (reference), or understanding (explanation).

## Quick Navigation

| I want to... | Document Type | Start Here |
|--------------|---------------|------------|
| Learn by building something | Tutorial | [First Deployment](tutorials/01-first-deployment.md) |
| Complete a specific task | How-to | [How-to Index](#how-to-guides) |
| Look up technical details | Reference | [Reference Index](#reference) |
| Understand concepts | Explanation | [Explanation Index](#explanation) |

## Tutorials (Learning-Oriented)

Goal: Build confidence through hands-on practice with a clear outcome.

### Available Tutorials

- **[First Deployment](tutorials/01-first-deployment.md)** - Build and deploy your first air-gap package from scratch (bare-metal, 60 minutes)

### Planned Tutorials

- **OpenStack Deployment** - Deploy to OpenStack VMs with Terraform provisioning
- **Custom Component Addition** - Add a custom Helm chart and container images
- **Multi-Site Deployment** - Deploy identical packages to multiple edge sites

## How-to Guides (Task-Oriented)

Goal: Solve a specific problem with minimal context.

### Build Tasks

- **[Component Manifest Management](how-to/component-manifest.md)** - Add/remove components from build manifest
- **[Migrate from Bash](how-to/migrate-from-bash.md)** - Convert bash scripts to Python modules

### Deploy Tasks

Located in `how-to/deploy/`:
- Configure bastion services
- Set up offline repositories
- Deploy Kubernetes cluster
- Verify cluster health

### Verification Tasks

Located in `how-to/verify/`:
- **[Package Verification](how-to/verify-package.md)** - Verify package integrity and signatures
- Validate SBOM contents
- Check artifact checksums
- Inspect Zarf package

### Extension Tasks

Located in `how-to/extend/`:
- Add custom container images
- Include additional Helm charts
- Package custom binaries
- Integrate third-party tools

### Operations Tasks

Located in `how-to/operate/`:
- Monitor build progress
- Resume failed builds
- Update component versions
- Rotate signing keys

## Reference (Information-Oriented)

Goal: Provide exact facts for lookup.

### CLI Reference

- **[CLI Commands](reference/cli-commands.md)** - Complete command reference with all flags and options

Located in `reference/cli/`:
- `init` command
- `build` command
- `verify` command
- `deploy` command
- `status` command
- `add` command

### Configuration Reference

Located in `reference/configuration/`:
- `versions.env` schema
- `components.yaml` schema
- `nodes.json` schema
- `openstack-config.yaml` schema
- Zarf variables

### Component Reference

- **[Component Manifest Schema](reference/component-manifest-schema.md)** - JSON schema for component definitions
- **[Component Independence](reference/component-independence.md)** - Component dependency matrix
- **[Image Lists](reference/image-lists.md)** - Complete list of packaged container images

### Build System Reference

- **[Build Steps](reference/build-steps.md)** - Detailed build phase breakdown
- **[Build Determinism](reference/build-determinism-summary.md)** - Reproducible build guarantees
- **[Binary Packaging](reference/binary-packaging.md)** - PyInstaller binary creation

### Security Reference

- **[Secrets Management](reference/secrets-management.md)** - File-based secrets handling
- **[Security Scanning](reference/security-scanning.md)** - Trivy integration and CVE policies
- **[Firewall Whitelist](reference/firewall-whitelist.md)** - Required network endpoints for build phase

### Operations Reference

- **[Logging](reference/logging.md)** - Log levels, formats, and locations
- **[Metrics Integration](reference/metrics-integration.md)** - Prometheus metrics export
- **[State Management](reference/state-management-integration.md)** - Build state persistence
- **[Troubleshooting](reference/troubleshooting.md)** - Common errors and solutions
- **[Recovery Procedures](reference/recovery-procedures.md)** - Disaster recovery steps
- **[Rollback](reference/rollback.md)** - Rollback procedures for failed deployments

### Architecture Reference

Located in `reference/architecture/`:
- Three-zone architecture diagram
- Component interaction diagrams
- Data flow diagrams
- Network topology

### Standards Reference

- **[Coding Standards](reference/coding-standards.md)** - Python/Bash style guide and decision matrix
- **[Code Review Findings](reference/code-review-findings.md)** - Placeholder implementations and unused code
- **[Version Management](reference/version-management.md)** - Semantic versioning and pinning strategy

### Compatibility Reference

Located in `reference/compatibility/`:
- Kubernetes version matrix
- OS compatibility table
- Terraform provider versions
- Python version requirements

## Explanation (Understanding-Oriented)

Goal: Clarify concepts, trade-offs, and design decisions.

### Architecture Explanations

Located in `explanation/architecture/`:
- **[Architecture Review](../architecture-review.md)** - High-level system design and rationale
- Three-zone security model
- Air-gap constraints and solutions
- Bastion service architecture

### Design Decisions

Located in `explanation/design-decisions/`:
- Why Zarf over custom packaging
- Python vs Bash decision criteria
- State management approach
- Manifest taxonomy rationale

### Technical Explanations

Located in `explanation/technical/`:
- How kubespray-offline integration works
- Zarf package structure internals
- Offline repository mirroring
- Terraform provider filesystem mirror

### Requirements Explanations

Located in `explanation/requirements/`:
- Air-gap deployment constraints
- Security requirements for regulated environments
- Reproducibility requirements
- SBOM and signing requirements

### Manifest Taxonomy

- **[Manifest Taxonomy](explanation/manifest-taxonomy.md)** - Three manifest types (component, Zarf, artifact) and their lifecycle roles

### Design Documentation

Located in `design/python-improvements/`:
- Consolidated Python improvements design
- Performance optimization rationale
- CLI/UX design decisions
- State management design

## Cross-References

### By User Role

**Platform Engineers** (build and maintain artifacts):
- Tutorial: [First Deployment](tutorials/01-first-deployment.md)
- How-to: [Component Manifest](how-to/component-manifest.md)
- Reference: [CLI Commands](reference/cli-commands.md), [Build Steps](reference/build-steps.md)
- Explanation: [Architecture Review](architecture-review.md)

**Field Operators** (deploy in air-gap):
- Tutorial: [First Deployment](tutorials/01-first-deployment.md)
- How-to: Deploy guides in `how-to/deploy/`
- Reference: [Troubleshooting](reference/troubleshooting.md), [Recovery](reference/recovery-procedures.md)
- Explanation: Three-zone architecture

**Security Officers** (verify integrity):
- How-to: [Package Verification](how-to/verify-package.md)
- Reference: [Security Scanning](reference/security-scanning.md), [Secrets Management](reference/secrets-management.md)
- Explanation: Security model in architecture docs
- Policy: [SECURITY.md](../SECURITY.md)

**Developers** (contribute code):
- How-to: [Migrate from Bash](how-to/migrate-from-bash.md)
- Reference: [Coding Standards](reference/coding-standards.md)
- Explanation: Design decisions
- Policy: [CONTRIBUTING.md](../CONTRIBUTING.md)

### By Workflow

**Initial Setup**:
1. Tutorial: [First Deployment](tutorials/01-first-deployment.md)
2. Reference: [CLI Commands](reference/cli-commands.md)
3. Explanation: [Architecture Review](architecture-review.md)

**Build Workflow**:
1. How-to: [Component Manifest](how-to/component-manifest.md)
2. Reference: [Build Steps](reference/build-steps.md)
3. How-to: Build guides in `how-to/build/`
4. Reference: [Troubleshooting](reference/troubleshooting.md)

**Verification Workflow**:
1. How-to: [Package Verification](how-to/verify-package.md)
2. Reference: [Security Scanning](reference/security-scanning.md)
3. Explanation: SBOM and signing requirements

**Deployment Workflow**:
1. How-to: Deploy guides in `how-to/deploy/`
2. Reference: [Recovery Procedures](reference/recovery-procedures.md)
3. Reference: [Rollback](reference/rollback.md)

**Troubleshooting Workflow**:
1. Reference: [Troubleshooting](reference/troubleshooting.md)
2. Reference: [Logging](reference/logging.md)
3. How-to: Operations guides in `how-to/operate/`

## Document Metadata

All documents include front matter:

```markdown
doc_type: tutorial|how-to|reference|explanation
audience: Platform Engineers, Field Operators, Security Officers, Developers
scope: Brief description of what the document covers
```

### Metadata Fields

- **doc_type**: Diátaxis category (required)
- **audience**: Target user roles (optional)
- **scope**: One-sentence summary (optional)
- **prerequisites**: Required knowledge or setup (tutorials/how-to only)
- **duration**: Estimated time (tutorials only)

## Writing Guidelines

### Tutorials

- Start with clear learning outcome
- Provide complete working example
- Include "Check your work" sections
- End with "Next steps" suggestions
- Assume beginner knowledge
- Be encouraging and patient

### How-to Guides

- Start with task summary
- List prerequisites up front
- Provide ordered steps
- Include troubleshooting section
- Assume intermediate knowledge
- Be direct and practical

### Reference

- Start with one-paragraph overview
- Organize by logical grouping
- Use tables for structured data
- Include examples for clarity
- Assume expert knowledge
- Be precise and complete

### Explanation

- Start with concept summary
- Explain "why" not "how"
- Discuss trade-offs and alternatives
- Address common misconceptions
- Assume intermediate knowledge
- Be thoughtful and grounded

## Contributing Documentation

When adding new documentation:

1. Determine Diátaxis category (tutorial/how-to/reference/explanation)
2. Place in appropriate directory
3. Add front matter with `doc_type`
4. Update this taxonomy with link
5. Cross-reference related documents
6. Follow writing guidelines for category

See [CONTRIBUTING.md](../CONTRIBUTING.md) for code contribution guidelines.

## Documentation Standards

- **Format**: Markdown with front matter
- **Line length**: 100 characters (soft limit)
- **Code blocks**: Include language identifier
- **Links**: Use relative paths
- **Images**: Store in `docs/assets/`
- **Examples**: Use realistic data (no "foo/bar")

## Maintenance

This taxonomy is updated when:
- New documents are added
- Documents are reorganized
- User feedback indicates navigation issues
- Quarterly documentation review

Last updated: 2026-01-30
