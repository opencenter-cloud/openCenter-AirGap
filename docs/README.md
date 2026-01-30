# openCenter AirGap Documentation

Air-gapped Kubernetes deployment for disconnected environments.

## Getting Started

New to openCenter? Start here:
- [First Deployment Tutorial](tutorials/01-first-deployment.md) - Deploy your first cluster in 30 minutes

## Documentation by Purpose

### Learning (Tutorials)
Step-by-step guided learning for building confidence.

- [First Deployment](tutorials/01-first-deployment.md) - Single-node cluster from scratch
- [OpenStack Deployment](tutorials/02-openstack-deployment.md) - Multi-node HA cluster on OpenStack

### Problem-Solving (How-To Guides)
Task-focused recipes for getting work done.

**Build**
- [Component Manifest Guide](how-to/component-manifest.md) - Create and maintain component manifests
- [Migrate from Bash Scripts](how-to/migrate-from-bash.md) - Migrate to Python build tool
- [Build Air-Gap Package](how-to/build/build-air-gap-package.md)
- [Update Component Versions](how-to/build/update-component-versions.md)
- [Add Custom Images](how-to/build/add-custom-images.md)

**Deploy**
- [Deploy Bare-Metal Cluster](how-to/deploy/deploy-baremetal-cluster.md)
- [Deploy OpenStack Cluster](how-to/deploy/deploy-openstack-cluster.md)
- [Configure Bastion Services](how-to/deploy/configure-bastion-services.md)

**Verify**
- [Verify Package Integrity](how-to/verify/verify-package-integrity.md)
- [Verify Cluster Health](how-to/verify/verify-cluster-health.md)

**Operate**
- [Troubleshoot Deployment](how-to/operate/troubleshoot-deployment.md)
- [Cleanup Cluster](how-to/operate/cleanup-cluster.md)

**Extend**
- [Add Custom Services](how-to/extend/add-custom-services.md)
- [Create Zarf Components](how-to/extend/create-zarf-components.md)

### Reference (Information Lookup)
Precise technical specifications and parameters.

**CLI**
- [CLI Command Reference](reference/cli-commands.md) - Complete command reference
- [Component Manifest Schema](reference/component-manifest-schema.md) - Schema specification
- [Troubleshooting Guide](reference/troubleshooting.md) - Common issues and solutions

**Configuration**
- [Zarf Variables](reference/configuration/zarf-variables.md)
- [Kubespray Variables](reference/configuration/kubespray-variables.md)
- [Environment Variables](reference/configuration/environment-variables.md)

**Architecture**
- [Network Ports](reference/architecture/network-ports.md)
- [Service Endpoints](reference/architecture/service-endpoints.md)

**Compatibility**
- [Component Versions](reference/compatibility/component-versions.md)
- [Version Compatibility Matrix](reference/compatibility/version-compatibility-matrix.md)

### Understanding (Explanations)
Concepts, design decisions, and context.

**Manifests**
- [Manifest Taxonomy](explanation/manifest-taxonomy.md) - Understanding the three manifest types

**Architecture**
- [Architecture Overview](explanation/architecture/architecture-overview.md)
- [Three-Zone Model](explanation/architecture/three-zone-model.md)
- [Air-Gap Constraints](explanation/architecture/air-gap-constraints.md)
- [Bastion Architecture](explanation/architecture/bastion-architecture.md)

**Design Decisions**
- [Why Kubespray](explanation/design-decisions/why-kubespray.md)
- [Why Zarf](explanation/design-decisions/why-zarf.md)
- [Offline-First Design](explanation/design-decisions/offline-first-design.md)

**Technical**
- [Kubespray Idempotency](explanation/technical/kubespray-idempotency.md)
- [Offline Mode Idempotency](explanation/technical/offline-mode-idempotency.md)
- [Package Integrity Model](explanation/technical/package-integrity-model.md)

**Requirements**
- [Requirements Rationale](explanation/requirements/requirements-rationale.md)

## Quick Links

- [Taxonomy](taxonomy.md) - Documentation organization framework
- [Troubleshooting](how-to/operate/troubleshoot-deployment.md) - Common issues and solutions
- [GitHub Repository](#) - Source code and issues

## Support

- File issues on GitHub
- Check troubleshooting guide first
- Include logs and error messages
