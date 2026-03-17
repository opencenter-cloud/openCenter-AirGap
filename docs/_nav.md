---
id: docs-navigation
title: "Documentation Navigation"
sidebar_label: Navigation
description: Quick navigation guide for openCenter AirGap documentation organized by type, role, and workflow.
doc_type: reference
audience: "platform engineers, field operators, security officers, contributors"
tags: [navigation, index, documentation]
---

# Documentation Navigation

Quick navigation for openCenter AirGap documentation.

## By Document Type

### 📚 Tutorials (Learning)
1. [First Deployment](tutorials/01-first-deployment.md) ⭐ Start here
2. [OpenStack Deployment](tutorials/02-openstack-deployment.md)
3. [Custom Component Addition](tutorials/03-custom-component.md)

### 🔧 How-to Guides (Tasks)

**Build**
- [Add Container Images](how-to/build/add-container-images.md)
- [Add Helm Charts](how-to/build/add-helm-charts.md)
- [Customize Versions](how-to/build/customize-versions.md)
- [Resume Failed Build](how-to/build/resume-failed-build.md)
- [Scan Repositories](how-to/build/scan-repositories.md)

**Deploy**
- [Configure Bastion Services](how-to/deploy/configure-bastion.md)
- [Deploy Kubernetes Cluster](how-to/deploy/deploy-cluster.md)
- [Set Up Offline Repositories](how-to/deploy/setup-offline-repos.md)
- [Verify Cluster Health](how-to/deploy/verify-cluster.md)

**Verify**
- [Verify Package Integrity](how-to/verify-package.md) ⭐
- [Validate SBOM](how-to/verify/validate-sbom.md)
- [Inspect Zarf Package](how-to/verify/inspect-package.md)

**Extend**
- [Package Custom Binaries](how-to/extend/package-binaries.md)
- [Add Third-Party Tools](how-to/extend/add-tools.md)

**Operate**
- [Monitor Build Progress](how-to/operate/monitor-build.md)
- [Update Component Versions](how-to/operate/update-versions.md)
- [Rotate Signing Keys](how-to/operate/rotate-keys.md)
- [Clean Build Artifacts](how-to/operate/clean-artifacts.md)

### 📖 Reference (Lookup)

**CLI**
- [CLI Commands](reference/cli-commands.md) ⭐ Complete reference
- [init](reference/cli/init.md)
- [build](reference/cli/build.md)
- [scan](reference/cli/scan.md)
- [add](reference/cli/add.md)
- [verify](reference/cli/verify.md)
- [status](reference/cli/status.md)
- [clean](reference/cli/clean.md)
- [serve](reference/cli/serve.md)
- [keygen](reference/cli/keygen.md)
- [release](reference/cli/release.md)

**Configuration**
- [versions.env Schema](reference/configuration/versions-env.md)
- [components.yaml Schema](reference/component-manifest-schema.md) ⭐
- [zarf.yaml Structure](reference/configuration/zarf-yaml.md)
- [Environment Variables](reference/configuration/environment-variables.md)

**Build System**
- [Build Steps](reference/build-steps.md) ⭐
- [State Management](reference/state-management.md)
- [Metrics](reference/metrics.md)
- [Logging](reference/logging.md)

**Security**
- [Secrets Management](reference/secrets-management.md)
- [Package Signing](reference/security/package-signing.md)
- [SBOM Generation](reference/security/sbom.md)

**Architecture**
- [Component Independence](reference/architecture/component-independence.md)
- [Three-Zone Architecture](reference/architecture/three-zone.md)
- [Data Flow](reference/architecture/data-flow.md)

**Compatibility**
- [System Requirements](reference/system-requirements.md) ⭐
- [Kubernetes Versions](reference/compatibility/kubernetes-versions.md)
- [OS Compatibility](reference/compatibility/os-compatibility.md)
- [Python Versions](reference/compatibility/python-versions.md)

**Standards**
- [Coding Standards](reference/coding-standards.md)
- [Version Management](reference/version-management.md)
- [Error Handling](reference/error-handling.md)

**Troubleshooting**
- [Troubleshooting](reference/troubleshooting.md) ⭐ Common errors
- [Recovery Procedures](reference/recovery-procedures.md)

### 💡 Explanation (Understanding)

**Architecture**
- [Architecture Overview](explanation/architecture/architecture-overview.md) ⭐
- [Three-Zone Security Model](explanation/architecture/three-zone-security.md)
- [Bastion Architecture](explanation/architecture/bastion-architecture.md)

**Design Decisions**
- [Why Zarf](explanation/design-decisions/why-zarf.md)
- [Python vs Bash](explanation/design-decisions/python-vs-bash.md)
- [State Management Approach](explanation/design-decisions/state-management.md)
- [Manifest Taxonomy](explanation/design-decisions/manifest-taxonomy.md)

**Technical**
- [Kubespray Integration](explanation/technical/kubespray-integration.md)
- [Zarf Package Structure](explanation/technical/zarf-package-structure.md)
- [Offline Repository Mirroring](explanation/technical/offline-mirroring.md)
- [Terraform Provider Mirror](explanation/technical/terraform-mirror.md)
- [Image Discovery](explanation/technical/image-discovery.md)

**Requirements**
- [Air-Gap Constraints](explanation/requirements/air-gap-constraints.md)
- [Security Requirements](explanation/requirements/security-requirements.md)
- [Reproducibility Requirements](explanation/requirements/reproducibility.md)
- [SBOM Requirements](explanation/requirements/sbom-requirements.md)

## By User Role

### Platform Engineers
1. [First Deployment Tutorial](tutorials/01-first-deployment.md)
2. [CLI Commands](reference/cli-commands.md)
3. [Build Steps](reference/build-steps.md)
4. [Customize Versions](how-to/build/customize-versions.md)
5. [Architecture Overview](explanation/architecture/architecture-overview.md)

### Field Operators
1. [First Deployment Tutorial](tutorials/01-first-deployment.md)
2. [Configure Bastion](how-to/deploy/configure-bastion.md)
3. [Deploy Cluster](how-to/deploy/deploy-cluster.md)
4. [Troubleshooting](reference/troubleshooting.md)
5. [Recovery Procedures](reference/recovery-procedures.md)

### Security Officers
1. [Verify Package](how-to/verify-package.md)
2. [Package Signing](reference/security/package-signing.md)
3. [SBOM Generation](reference/security/sbom.md)
4. [Security Requirements](explanation/requirements/security-requirements.md)

### Contributors
1. [CONTRIBUTING.md](../CONTRIBUTING.md)
2. [Coding Standards](reference/coding-standards.md)
3. [Python vs Bash](explanation/design-decisions/python-vs-bash.md)
4. [Error Handling](reference/error-handling.md)

## By Workflow

### Initial Setup
1. [First Deployment Tutorial](tutorials/01-first-deployment.md)
2. [System Requirements](reference/system-requirements.md)
3. [CLI Commands](reference/cli-commands.md)

### Building Package
1. [Customize Versions](how-to/build/customize-versions.md)
2. [Scan Repositories](how-to/build/scan-repositories.md)
3. [Add Container Images](how-to/build/add-container-images.md)
4. [Build Steps](reference/build-steps.md)
5. [Resume Failed Build](how-to/build/resume-failed-build.md)

### Verifying Package
1. [Verify Package Integrity](how-to/verify-package.md)
2. [Validate SBOM](how-to/verify/validate-sbom.md)
3. [Inspect Package](how-to/verify/inspect-package.md)
4. [Package Signing](reference/security/package-signing.md)

### Deploying Cluster
1. [Configure Bastion](how-to/deploy/configure-bastion.md)
2. [Set Up Offline Repos](how-to/deploy/setup-offline-repos.md)
3. [Deploy Cluster](how-to/deploy/deploy-cluster.md)
4. [Verify Cluster Health](how-to/deploy/verify-cluster.md)

### Troubleshooting
1. [Troubleshooting Reference](reference/troubleshooting.md)
2. [Logging Reference](reference/logging.md)
3. [Recovery Procedures](reference/recovery-procedures.md)
4. [Monitor Build Progress](how-to/operate/monitor-build.md)

## Quick Links

- [Documentation Home](README.md)
- [Documentation Taxonomy](taxonomy.md)
- [Documentation Map](_doc-map.md)
- [Project README](../README.md)
- [CONTRIBUTING](../CONTRIBUTING.md)
- [SECURITY](../SECURITY.md)

## Legend

- ⭐ = Recommended starting point
- 📚 = Tutorial (learning-oriented)
- 🔧 = How-to (task-oriented)
- 📖 = Reference (information-oriented)
- 💡 = Explanation (understanding-oriented)
