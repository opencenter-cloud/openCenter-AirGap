---
id: docs-home
title: "openCenter AirGap Documentation"
sidebar_label: Documentation Home
description: Main documentation hub for openCenter AirGap, organized by the Diátaxis framework.
doc_type: reference
audience: "platform engineers, field operators, security officers, contributors"
tags: [documentation, index, getting-started]
---

# openCenter AirGap Documentation

Welcome to the openCenter AirGap documentation. This documentation follows the [Diátaxis framework](https://diataxis.fr/), organizing content by purpose: learning, task completion, reference lookup, and understanding.

## Quick Start

**New to openCenter AirGap?** Start with the [First Deployment Tutorial](tutorials/01-first-deployment.md) to build and deploy your first air-gap package in 60 minutes.

**Need to complete a specific task?** Browse the [How-to Guides](#how-to-guides) for step-by-step instructions.

**Looking for technical details?** Check the [Reference Documentation](#reference) for complete API, CLI, and configuration information.

**Want to understand the design?** Read the [Explanation Documentation](#explanation) for architecture, rationale, and trade-offs.

## Documentation Structure

### Tutorials (Learning-Oriented)

Hands-on guides that teach by doing. Each tutorial has a clear outcome and takes you from start to finish.

- **[First Deployment](tutorials/01-first-deployment.md)** - Build and deploy your first air-gap Kubernetes cluster (60 min)
- **[OpenStack Deployment](tutorials/02-openstack-deployment.md)** - Deploy to OpenStack VMs with Terraform (45 min)
- **[Custom Component Addition](tutorials/03-custom-component.md)** - Add custom Helm charts and images (30 min)

### How-to Guides (Task-Oriented)

Step-by-step recipes for completing specific tasks. Assumes you know what you want to do.

#### Build Tasks
- [Add Container Images](how-to/build/add-container-images.md)
- [Add Helm Charts](how-to/build/add-helm-charts.md)
- [Customize Versions](how-to/build/customize-versions.md)
- [Resume Failed Build](how-to/build/resume-failed-build.md)
- [Scan Repositories](how-to/build/scan-repositories.md)

#### Deploy Tasks
- [Configure Bastion Services](how-to/deploy/configure-bastion.md)
- [Deploy Kubernetes Cluster](how-to/deploy/deploy-cluster.md)
- [Set Up Offline Repositories](how-to/deploy/setup-offline-repos.md)
- [Verify Cluster Health](how-to/deploy/verify-cluster.md)

#### Verification Tasks
- [Verify Package Integrity](how-to/verify-package.md)
- [Validate SBOM](how-to/verify/validate-sbom.md)
- [Inspect Zarf Package](how-to/verify/inspect-package.md)

#### Extension Tasks
- [Package Custom Binaries](how-to/extend/package-binaries.md)
- [Add Third-Party Tools](how-to/extend/add-tools.md)

#### Operations Tasks
- [Monitor Build Progress](how-to/operate/monitor-build.md)
- [Update Component Versions](how-to/operate/update-versions.md)
- [Rotate Signing Keys](how-to/operate/rotate-keys.md)
- [Clean Build Artifacts](how-to/operate/clean-artifacts.md)

### Reference (Information-Oriented)

Technical specifications, API documentation, and lookup information. Organized for quick scanning.

#### CLI Reference
- **[CLI Commands](reference/cli-commands.md)** - Complete command reference
- [init](reference/cli/init.md) - Initialize project
- [build](reference/cli/build.md) - Build package
- [scan](reference/cli/scan.md) - Scan repositories
- [add](reference/cli/add.md) - Add components
- [verify](reference/cli/verify.md) - Verify package
- [status](reference/cli/status.md) - Show build status
- [clean](reference/cli/clean.md) - Clean artifacts
- [serve](reference/cli/serve.md) - Deploy and serve
- [keygen](reference/cli/keygen.md) - Generate signing keys
- [release](reference/cli/release.md) - Create release tag

#### Configuration Reference
- [versions.env Schema](reference/configuration/versions-env.md) - Version configuration format
- [components.yaml Schema](reference/component-manifest-schema.md) - Component manifest format
- [zarf.yaml Structure](reference/configuration/zarf-yaml.md) - Zarf package definition
- [Environment Variables](reference/configuration/environment-variables.md) - Runtime configuration

#### Build System Reference
- [Build Steps](reference/build-steps.md) - Build phase breakdown
- [State Management](reference/state-management.md) - Build state persistence
- [Metrics](reference/metrics.md) - Build metrics and telemetry
- [Logging](reference/logging.md) - Log formats and levels

#### Security Reference
- [Secrets Management](reference/secrets-management.md) - File-based secrets handling
- [Package Signing](reference/security/package-signing.md) - Cosign integration
- [SBOM Generation](reference/security/sbom.md) - Bill of materials

#### Architecture Reference
- [Component Independence](reference/architecture/component-independence.md) - Zarf component dependencies
- [Three-Zone Architecture](reference/architecture/three-zone.md) - Security model
- [Data Flow](reference/architecture/data-flow.md) - Build and deploy flow

#### Compatibility Reference
- [System Requirements](reference/system-requirements.md) - Hardware and software requirements
- [Kubernetes Versions](reference/compatibility/kubernetes-versions.md) - Supported K8s versions
- [OS Compatibility](reference/compatibility/os-compatibility.md) - Supported operating systems
- [Python Versions](reference/compatibility/python-versions.md) - Python version requirements

#### Standards Reference
- [Coding Standards](reference/coding-standards.md) - Python/Bash style guide
- [Version Management](reference/version-management.md) - Semantic versioning strategy
- [Error Handling](reference/error-handling.md) - Exception hierarchy

#### Troubleshooting Reference
- **[Troubleshooting](reference/troubleshooting.md)** - Common errors and solutions
- [Recovery Procedures](reference/recovery-procedures.md) - Disaster recovery steps

### Explanation (Understanding-Oriented)

Conceptual documentation that explains the "why" behind design decisions and architecture.

#### Architecture Explanations
- **[Architecture Overview](explanation/architecture/architecture-overview.md)** - High-level system design
- [Three-Zone Security Model](explanation/architecture/three-zone-security.md) - Air-gap security approach
- [Bastion Architecture](explanation/architecture/bastion-architecture.md) - Bastion service design

#### Design Decisions
- [Why Zarf](explanation/design-decisions/why-zarf.md) - Packaging framework choice
- [Python vs Bash](explanation/design-decisions/python-vs-bash.md) - Language selection criteria
- [State Management Approach](explanation/design-decisions/state-management.md) - Build state design
- [Manifest Taxonomy](explanation/design-decisions/manifest-taxonomy.md) - Three manifest types

#### Technical Explanations
- [Kubespray Integration](explanation/technical/kubespray-integration.md) - How Kubespray works
- [Zarf Package Structure](explanation/technical/zarf-package-structure.md) - Package internals
- [Offline Repository Mirroring](explanation/technical/offline-mirroring.md) - Repository mirror design
- [Terraform Provider Mirror](explanation/technical/terraform-mirror.md) - Provider filesystem mirror
- [Image Discovery](explanation/technical/image-discovery.md) - How scanning works

#### Requirements Explanations
- [Air-Gap Constraints](explanation/requirements/air-gap-constraints.md) - Disconnected deployment challenges
- [Security Requirements](explanation/requirements/security-requirements.md) - Regulated environment needs
- [Reproducibility Requirements](explanation/requirements/reproducibility.md) - Deterministic build needs
- [SBOM Requirements](explanation/requirements/sbom-requirements.md) - Bill of materials rationale

## Documentation by User Role

### Platform Engineers
Build and maintain air-gap artifacts for deployment.

**Start here**:
1. [First Deployment Tutorial](tutorials/01-first-deployment.md)
2. [CLI Commands Reference](reference/cli-commands.md)
3. [Build Steps Reference](reference/build-steps.md)
4. [Architecture Overview](explanation/architecture/architecture-overview.md)

**Common tasks**:
- [Customize Versions](how-to/build/customize-versions.md)
- [Add Container Images](how-to/build/add-container-images.md)
- [Scan Repositories](how-to/build/scan-repositories.md)
- [Resume Failed Build](how-to/build/resume-failed-build.md)

### Field Operators
Deploy clusters in disconnected environments.

**Start here**:
1. [First Deployment Tutorial](tutorials/01-first-deployment.md)
2. [Configure Bastion Services](how-to/deploy/configure-bastion.md)
3. [Deploy Kubernetes Cluster](how-to/deploy/deploy-cluster.md)
4. [Troubleshooting Reference](reference/troubleshooting.md)

**Common tasks**:
- [Set Up Offline Repositories](how-to/deploy/setup-offline-repos.md)
- [Verify Cluster Health](how-to/deploy/verify-cluster.md)
- [Recovery Procedures](reference/recovery-procedures.md)

### Security Officers
Verify package integrity and compliance.

**Start here**:
1. [Verify Package Integrity](how-to/verify-package.md)
2. [Package Signing Reference](reference/security/package-signing.md)
3. [SBOM Generation Reference](reference/security/sbom.md)
4. [Security Requirements](explanation/requirements/security-requirements.md)

**Common tasks**:
- [Validate SBOM](how-to/verify/validate-sbom.md)
- [Inspect Zarf Package](how-to/verify/inspect-package.md)
- [Rotate Signing Keys](how-to/operate/rotate-keys.md)

### Contributors
Contribute code and documentation.

**Start here**:
1. [CONTRIBUTING.md](../CONTRIBUTING.md)
2. [Coding Standards](reference/coding-standards.md)
3. [Python vs Bash](explanation/design-decisions/python-vs-bash.md)
4. [Error Handling Reference](reference/error-handling.md)

**Common tasks**:
- Set up development environment (see CONTRIBUTING.md)
- Run tests (see CONTRIBUTING.md)
- Submit pull requests (see CONTRIBUTING.md)

## Documentation Conventions

### Document Types

Each document clearly identifies its type in the front matter:

```markdown
---
doc_type: tutorial|how-to|reference|explanation
audience: Platform Engineers, Field Operators, Security Officers, Contributors
scope: Brief description of what the document covers
---
```

### Code Examples

All code examples are tested and include:
- Language identifier for syntax highlighting
- Comments explaining non-obvious steps
- Expected output when relevant
- Error handling examples

### File Paths

All file paths in examples are relative to the repository root:
- `config/versions.env` (not `./config/versions.env`)
- `src/opencenter_build/cli.py` (not `opencenter_build/cli.py`)

### Evidence Links

Reference documentation includes evidence links to source code:
- Format: `src/opencenter_build/cli.py:build()` (file:function)
- Format: `config/versions.env:KUBERNETES_VERSION` (file:variable)
- Format: `zarf.yaml:components` (file:section)

## Contributing to Documentation

Documentation contributions are welcome! Please follow these guidelines:

1. **Determine document type**: Is it a tutorial, how-to, reference, or explanation?
2. **Place in correct directory**: `tutorials/`, `how-to/`, `reference/`, or `explanation/`
3. **Add front matter**: Include `doc_type`, `audience`, and `scope`
4. **Update navigation**: Add link to this README and `_nav.md`
5. **Update doc map**: Add entry to `_doc-map.md`
6. **Follow style guide**: See [Documentation Spec](../.kiro/steering/Documentation.md)

See [CONTRIBUTING.md](../CONTRIBUTING.md) for complete contribution guidelines.

## Getting Help

- **Questions**: Open a discussion on GitHub
- **Issues**: Report bugs or request features via GitHub Issues
- **Security**: See [SECURITY.md](../SECURITY.md) for vulnerability reporting
- **Community**: Join our community channels (see main README)

## Additional Resources

- [Project README](../README.md) - Project overview and quick start
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Development guidelines
- [SECURITY.md](../SECURITY.md) - Security policy
- [Documentation Taxonomy](taxonomy.md) - Complete documentation index
- [Documentation Map](_doc-map.md) - Detailed documentation inventory

## Documentation Status

**Current Version**: 1.0.0-rc2
**Last Updated**: 2026-02-18
**Status**: Active development

### Completeness

- ✅ Tutorials: 1/3 complete (First Deployment)
- ⚠️ How-to Guides: 2/20 complete (most referenced but not created)
- ✅ Reference: 4/30 complete (CLI commands, component manifest, build steps, troubleshooting)
- ⚠️ Explanation: 0/15 complete (all referenced but not created)

### Known Gaps

See [Documentation Map](_doc-map.md) for complete list of gaps and planned documentation.

## License

Documentation is licensed under the same license as the project. See [LICENSE](../LICENSE) for details.
