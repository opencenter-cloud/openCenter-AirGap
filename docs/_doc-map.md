---
id: doc-map
title: "Documentation Map"
sidebar_label: Doc Map
description: Complete inventory of openCenter AirGap documentation with evidence links and gap analysis.
doc_type: reference
audience: "contributors, platform engineers"
tags: [documentation, inventory, diataxis, maintenance]
---

# Documentation Map

This document provides a complete inventory of openCenter-AirGap documentation, organized by the Diátaxis framework.

## Audience Assumptions

**Platform Engineers**: Experienced with Kubernetes, Terraform, and CI/CD. Responsible for building and maintaining air-gap artifacts.

**Field Operators**: Familiar with Linux system administration and Ansible. Deploy clusters in disconnected environments.

**Security Officers**: Understand cryptographic signing, SBOM, and compliance requirements. Verify package integrity.

**Contributors**: Software developers familiar with Python, Bash, and Git workflows. Contribute code and documentation.

## Documentation Inventory

### Tutorials (Learning-Oriented)

| Document | Purpose | Prerequisites | Evidence |
|----------|---------|---------------|----------|
| [First Deployment](tutorials/01-first-deployment.md) | Build and deploy first air-gap cluster | Ubuntu 24.04, 100GB disk, Python 3.12+ | `src/opencenter_build/cli.py:build()`, `zarf.yaml` |
| [OpenStack Deployment](tutorials/02-openstack-deployment.md) | Deploy to OpenStack VMs with Terraform | First deployment completed, OpenStack credentials | `examples/openstack-config.yaml`, `config/versions.env:TERRAFORM_VERSION` |
| [Custom Component Addition](tutorials/03-custom-component.md) | Add custom Helm chart and images | First deployment completed | `src/opencenter_build/cli.py:add()`, `src/opencenter_build/component_manifest.py` |

### How-To Guides (Task-Oriented)

#### Build Tasks
| Document | Purpose | Evidence |
|----------|---------|----------|
| [Add Container Images](how-to/build/add-container-images.md) | Add custom images to package | `src/opencenter_build/cli.py:add()` |
| [Add Helm Charts](how-to/build/add-helm-charts.md) | Include additional Helm charts | `src/opencenter_build/scanner.py:HelmChartScanner` |
| [Customize Versions](how-to/build/customize-versions.md) | Pin specific component versions | `config/versions.env`, `src/opencenter_build/config.py` |
| [Resume Failed Build](how-to/build/resume-failed-build.md) | Recover from build failures | `src/opencenter_build/state.py:StateManager` |
| [Scan Repositories](how-to/build/scan-repositories.md) | Auto-discover images and charts | `src/opencenter_build/scanner.py:RepositoryScanner` |

#### Deploy Tasks
| Document | Purpose | Evidence |
|----------|---------|----------|
| [Configure Bastion Services](how-to/deploy/configure-bastion.md) | Set up registry and file server | `zarf.yaml:deploy-cluster`, `scripts/deploy/` |
| [Deploy Kubernetes Cluster](how-to/deploy/deploy-cluster.md) | Install K8s with Kubespray | `zarf.yaml:kubespray-core`, `config/versions.env:KUBESPRAY_VERSION` |
| [Set Up Offline Repositories](how-to/deploy/setup-offline-repos.md) | Configure apt and pip mirrors | `zarf.yaml:kubespray-core:repos` |
| [Verify Cluster Health](how-to/deploy/verify-cluster.md) | Check cluster status post-deployment | `kubectl` commands |

#### Verification Tasks
| Document | Purpose | Evidence |
|----------|---------|----------|
| [Verify Package Integrity](how-to/verify-package.md) | Check signatures and checksums | `src/opencenter_build/verifier.py:PackageVerifier` |
| [Validate SBOM](how-to/verify/validate-sbom.md) | Inspect bill of materials | `zarf package inspect --sbom` |
| [Inspect Zarf Package](how-to/verify/inspect-package.md) | Examine package contents | `zarf package inspect` |

#### Extension Tasks
| Document | Purpose | Evidence |
|----------|---------|----------|
| [Package Custom Binaries](how-to/extend/package-binaries.md) | Include additional CLI tools | `src/opencenter_build/cli.py:add()` |
| [Add Third-Party Tools](how-to/extend/add-tools.md) | Integrate external utilities | `config/versions.env:*_VERSION` |

#### Operations Tasks
| Document | Purpose | Evidence |
|----------|---------|----------|
| [Monitor Build Progress](how-to/operate/monitor-build.md) | Track build status | `src/opencenter_build/cli.py:status()` |
| [Update Component Versions](how-to/operate/update-versions.md) | Upgrade components | `config/versions.env` |
| [Rotate Signing Keys](how-to/operate/rotate-keys.md) | Generate new Cosign keys | `src/opencenter_build/cli.py:keygen()` |
| [Clean Build Artifacts](how-to/operate/clean-artifacts.md) | Remove build files | `src/opencenter_build/cli.py:clean()` |

### Reference (Information-Oriented)

#### CLI Reference
| Document | Purpose | Evidence |
|----------|---------|----------|
| [CLI Commands](reference/cli-commands.md) | Complete command reference | `src/opencenter_build/cli.py` |
| [init Command](reference/cli/init.md) | Initialize project | `src/opencenter_build/cli.py:init()` |
| [build Command](reference/cli/build.md) | Build package | `src/opencenter_build/cli.py:build()` |
| [scan Command](reference/cli/scan.md) | Scan repositories | `src/opencenter_build/cli.py:scan()` |
| [add Command](reference/cli/add.md) | Add components | `src/opencenter_build/cli.py:add()` |
| [verify Command](reference/cli/verify.md) | Verify package | `src/opencenter_build/cli.py:verify()` |
| [status Command](reference/cli/status.md) | Show build status | `src/opencenter_build/cli.py:status()` |
| [clean Command](reference/cli/clean.md) | Clean artifacts | `src/opencenter_build/cli.py:clean()` |
| [serve Command](reference/cli/serve.md) | Deploy and serve | `src/opencenter_build/cli.py:serve()` |
| [keygen Command](reference/cli/keygen.md) | Generate signing keys | `src/opencenter_build/cli.py:keygen()` |
| [release Command](reference/cli/release.md) | Create release tag | `src/opencenter_build/cli.py:release()` |

#### Configuration Reference
| Document | Purpose | Evidence |
|----------|---------|----------|
| [versions.env Schema](reference/configuration/versions-env.md) | Version configuration format | `config/versions.env`, `src/opencenter_build/config.py:BuildConfig` |
| [components.yaml Schema](reference/component-manifest-schema.md) | Component manifest format | `src/opencenter_build/component_manifest.py:ComponentManifest` |
| [zarf.yaml Structure](reference/configuration/zarf-yaml.md) | Zarf package definition | `zarf.yaml`, `zarf.yaml.template` |
| [Environment Variables](reference/configuration/environment-variables.md) | Runtime configuration | `src/opencenter_build/cli.py`, `src/opencenter_build/config.py` |

#### Build System Reference
| Document | Purpose | Evidence |
|----------|---------|----------|
| [Build Steps](reference/build-steps.md) | Build phase breakdown | `src/opencenter_build/orchestrator.py:BuildOrchestrator` |
| [State Management](reference/state-management.md) | Build state persistence | `src/opencenter_build/state.py:StateManager` |
| [Metrics](reference/metrics.md) | Build metrics and telemetry | `src/opencenter_build/metrics.py` |
| [Logging](reference/logging.md) | Log formats and levels | `src/opencenter_build/logging.py` |

#### Security Reference
| Document | Purpose | Evidence |
|----------|---------|----------|
| [Secrets Management](reference/secrets-management.md) | File-based secrets handling | `src/opencenter_build/secrets.py:SecretsManager` |
| [Package Signing](reference/security/package-signing.md) | Cosign integration | `src/opencenter_build/cli.py:keygen()` |
| [SBOM Generation](reference/security/sbom.md) | Bill of materials | `zarf package inspect --sbom` |

#### Architecture Reference
| Document | Purpose | Evidence |
|----------|---------|----------|
| [Component Independence](reference/architecture/component-independence.md) | Zarf component dependencies | `zarf.yaml:components` |
| [Three-Zone Architecture](reference/architecture/three-zone.md) | Security model | `README.md:Three-Zone Model` |
| [Data Flow](reference/architecture/data-flow.md) | Build and deploy flow | `src/opencenter_build/orchestrator.py` |

#### Compatibility Reference
| Document | Purpose | Evidence |
|----------|---------|----------|
| [System Requirements](reference/system-requirements.md) | Hardware and software requirements | `README.md:Requirements` |
| [Kubernetes Versions](reference/compatibility/kubernetes-versions.md) | Supported K8s versions | `config/versions.env:KUBERNETES_VERSION` |
| [OS Compatibility](reference/compatibility/os-compatibility.md) | Supported operating systems | `config/versions.env:UBUNTU_VERSION` |
| [Python Versions](reference/compatibility/python-versions.md) | Python version requirements | `pyproject.toml:requires-python` |

#### Standards Reference
| Document | Purpose | Evidence |
|----------|---------|----------|
| [Coding Standards](reference/coding-standards.md) | Python/Bash style guide | `CONTRIBUTING.md`, `pyproject.toml:[tool.black]` |
| [Version Management](reference/version-management.md) | Semantic versioning strategy | `pyproject.toml:version` |
| [Error Handling](reference/error-handling.md) | Exception hierarchy | `src/opencenter_build/exceptions.py` |

#### Troubleshooting Reference
| Document | Purpose | Evidence |
|----------|---------|----------|
| [Troubleshooting](reference/troubleshooting.md) | Common errors and solutions | Aggregated from code and issues |
| [Recovery Procedures](reference/recovery-procedures.md) | Disaster recovery steps | `src/opencenter_build/state.py`, `src/opencenter_build/transaction.py` |

### Explanation (Understanding-Oriented)

#### Architecture Explanations
| Document | Purpose | Evidence |
|----------|---------|----------|
| [Architecture Overview](explanation/architecture/architecture-overview.md) | High-level system design | `README.md:Architecture`, `zarf.yaml` |
| [Three-Zone Security Model](explanation/architecture/three-zone-security.md) | Air-gap security approach | `README.md:Three-Zone Model` |
| [Bastion Architecture](explanation/architecture/bastion-architecture.md) | Bastion service design | `zarf.yaml:deploy-cluster` |

#### Design Decisions
| Document | Purpose | Evidence |
|----------|---------|----------|
| [Why Zarf](explanation/design-decisions/why-zarf.md) | Packaging framework choice | `zarf.yaml`, `README.md` |
| [Python vs Bash](explanation/design-decisions/python-vs-bash.md) | Language selection criteria | `CONTRIBUTING.md`, `src/opencenter_build/` |
| [State Management Approach](explanation/design-decisions/state-management.md) | Build state design | `src/opencenter_build/state.py` |
| [Manifest Taxonomy](explanation/design-decisions/manifest-taxonomy.md) | Three manifest types | `src/opencenter_build/component_manifest.py`, `src/opencenter_build/zarf_generator.py`, `src/opencenter_build/manifest.py` |

#### Technical Explanations
| Document | Purpose | Evidence |
|----------|---------|----------|
| [Kubespray Integration](explanation/technical/kubespray-integration.md) | How Kubespray works | `config/versions.env:KUBESPRAY_*`, `zarf.yaml:kubespray-core` |
| [Zarf Package Structure](explanation/technical/zarf-package-structure.md) | Package internals | `zarf.yaml`, `src/opencenter_build/zarf_generator.py` |
| [Offline Repository Mirroring](explanation/technical/offline-mirroring.md) | Repository mirror design | `zarf.yaml:kubespray-core:repos` |
| [Terraform Provider Mirror](explanation/technical/terraform-mirror.md) | Provider filesystem mirror | `zarf.yaml:terraform-providers` |
| [Image Discovery](explanation/technical/image-discovery.md) | How scanning works | `src/opencenter_build/scanner.py` |

#### Requirements Explanations
| Document | Purpose | Evidence |
|----------|---------|----------|
| [Air-Gap Constraints](explanation/requirements/air-gap-constraints.md) | Disconnected deployment challenges | `README.md:What This Is` |
| [Security Requirements](explanation/requirements/security-requirements.md) | Regulated environment needs | `SECURITY.md`, `src/opencenter_build/secrets.py` |
| [Reproducibility Requirements](explanation/requirements/reproducibility.md) | Deterministic build needs | `config/versions.env`, `src/opencenter_build/config.py:hash()` |
| [SBOM Requirements](explanation/requirements/sbom-requirements.md) | Bill of materials rationale | `zarf package inspect --sbom` |

## Gaps and Unknowns

### Known Gaps
1. **kubespray-offline integration**: In progress, not fully documented
2. **Zarf package creation automation**: Requires Zarf CLI, not fully automated
3. **Terraform provider mirroring**: Implementation details incomplete
4. **Multi-architecture support**: Planned but not implemented

### Documentation Needs
1. **Tutorial**: OpenStack deployment (referenced but not created)
2. **Tutorial**: Custom component addition (referenced but not created)
3. **How-to**: Many task guides referenced in taxonomy but not created
4. **Reference**: Detailed CLI command pages (only summary exists)
5. **Explanation**: Several design decision docs referenced but not created

### Evidence Gaps
1. **Binary packaging**: PyInstaller mentioned in README but no implementation found
2. **Metrics integration**: Prometheus export mentioned but implementation unclear
3. **Security scanning**: Trivy integration mentioned but not found in code
4. **Build determinism**: Mentioned but validation mechanism unclear

## Cross-References

### By User Journey

**First-Time User**:
1. [First Deployment Tutorial](tutorials/01-first-deployment.md)
2. [CLI Commands Reference](reference/cli-commands.md)
3. [Architecture Overview](explanation/architecture/architecture-overview.md)
4. [Troubleshooting](reference/troubleshooting.md)

**Building Custom Package**:
1. [Customize Versions](how-to/build/customize-versions.md)
2. [Add Container Images](how-to/build/add-container-images.md)
3. [Scan Repositories](how-to/build/scan-repositories.md)
4. [versions.env Schema](reference/configuration/versions-env.md)
5. [Component Manifest Schema](reference/component-manifest-schema.md)

**Deploying to Production**:
1. [Configure Bastion Services](how-to/deploy/configure-bastion.md)
2. [Deploy Kubernetes Cluster](how-to/deploy/deploy-cluster.md)
3. [Verify Cluster Health](how-to/deploy/verify-cluster.md)
4. [Recovery Procedures](reference/recovery-procedures.md)

**Security Verification**:
1. [Verify Package Integrity](how-to/verify-package.md)
2. [Validate SBOM](how-to/verify/validate-sbom.md)
3. [Package Signing](reference/security/package-signing.md)
4. [Security Requirements](explanation/requirements/security-requirements.md)

**Contributing Code**:
1. [CONTRIBUTING.md](../CONTRIBUTING.md)
2. [Coding Standards](reference/coding-standards.md)
3. [Python vs Bash](explanation/design-decisions/python-vs-bash.md)
4. [Error Handling](reference/error-handling.md)

## Maintenance Plan

### Review Schedule
- **Weekly**: Update troubleshooting with new issues
- **Monthly**: Review and update CLI reference for new commands
- **Quarterly**: Full documentation audit for accuracy
- **Per Release**: Update version compatibility matrices

### Update Triggers
- New CLI command added → Update CLI reference
- New component type supported → Update component manifest schema
- Build process changes → Update build steps reference
- Architecture changes → Update architecture explanations
- Security changes → Update security reference

### Quality Checks
- [ ] All code references point to existing files
- [ ] All examples are tested and work
- [ ] All cross-references are valid
- [ ] All prerequisites are accurate
- [ ] All evidence is verifiable

Last updated: 2026-02-18
