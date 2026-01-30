# Python Improvements Research: Bash Script Reduction via Zarf

This directory contains comprehensive research on reducing bash script dependencies by leveraging Zarf's native capabilities.

## Consolidated Document

**Start here**: [consolidated-python-improvements.md](./consolidated-python-improvements.md) - Single reference combining all research into actionable recommendations.

## Source Documents

### 1. [kubespray-offline-info.md](./kubespray-offline-info.md)
**Comprehensive analysis of kubespray-offline architecture**

- Two-phase model (build → deploy)
- Asset types: K8s binaries, images, OS packages, PyPI mirror
- 9-script build pipeline
- Deploy-phase services (nginx, registry)
- Integration patterns and constraints

**Key finding**: kubespray-offline downloads 4 asset types but has no SBOM/signing capabilities.

### 2. [zarf-info.md](./zarf-info.md)
**Deep dive into Zarf packaging framework**

- Component-based packaging model
- Native primitives: images, charts, repos, files, actions
- Registry bootstrapping via Rust injector
- Automatic SBOM generation and Cosign signing
- Comparison to bash orchestration

**Key finding**: Zarf provides native replacements for 60-70% of bash scripts.

### 3. [bash-script-reduction.md](./bash-script-reduction.md)
**Actionable plan for eliminating bash dependencies**

- Tool-by-tool elimination analysis
- Script-by-script replacement plan
- Hybrid architecture recommendation
- 6-week implementation roadmap
- Risk assessment and mitigation

**Key finding**: Can eliminate skopeo, podman, manual registry/git management while keeping bash for OS packages, PyPI, Terraform, Kubespray.

## Executive Summary

### Dependencies We Can Eliminate

| Tool | Replacement | Confidence |
|------|-------------|------------|
| skopeo | Zarf native image handling | High |
| podman (build) | Zarf `images:` component | High |
| docker save/load | Zarf automatic bundling | High |
| git clone/push | Zarf `repos:` component | High |
| helm install | Zarf `charts:` component | High |
| Manual registry | Zarf init package | Medium |
| Manual nginx | Zarf `files:` + actions | Medium |

### Dependencies We Must Keep

| Tool | Reason |
|------|--------|
| bash | Zarf actions execute shell commands |
| curl/wget | Binary downloads (kubespray-offline) |
| terraform | Infrastructure provisioning (stateful) |
| ansible | Kubespray execution (complex orchestration) |
| apt-get/yum | OS package repository creation |
| pip | PyPI mirror creation |

### Impact

**Quantitative**:
- Bash scripts: 25+ → 5-8 (70% reduction)
- Lines of bash: ~2,000 → ~500 (75% reduction)
- Build dependencies: 8 tools → 3 tools (62% reduction)

**Qualitative**:
- Idempotent operations
- Automatic error handling and rollback
- Declarative configuration
- Built-in SBOM and signing
- Better observability

## Recommended Architecture

### Zarf-Native (60-70% of functionality)

**Use Zarf declarative primitives for**:
- Container images (115 images)
- Helm charts (8-10 charts)
- Git repositories (2-3 repos)
- Kubernetes manifests
- Binary file distribution

### Python/Bash (30-40% of functionality)

**Keep scripting for**:
- OS package management (apt/yum repos)
- PyPI mirror creation
- Kubespray orchestration (Ansible)
- Terraform provisioning (OpenStack)
- Bastion service management (via Zarf actions)

## Implementation Roadmap

1. **Week 1-2**: Image lifecycle (eliminate skopeo/podman)
2. **Week 3**: Git & Helm (eliminate mirroring/install scripts)
3. **Week 4**: File distribution (declarative binary downloads)
4. **Week 5**: Orchestration (replace setup-all.sh with Zarf actions)
5. **Week 6-8**: Python refactor (OS packages, PyPI, orchestration)

### 4. [python-improvements.md](./python-improvements.md)
**Detailed Python implementation with code examples**

- Phase 1-4 implementation details
- Complete code samples for scanner, orchestrator, CLI
- Transaction semantics for each operation
- Testing strategy and benchmarks

### 5. [python-improvements-ux-reference.md](./python-improvements-ux-reference.md)
**Complete CLI command reference**

- 9 core commands with full syntax
- 7 workflow scenarios
- Environment variables and exit codes
- Troubleshooting guide

## Next Steps

1. Review [consolidated-python-improvements.md](./consolidated-python-improvements.md)
2. Validate Zarf capabilities with proof-of-concept
3. Create Zarf package definition (zarf.yaml) for openCenter AirGap
4. Begin Phase 1 implementation (Python performance)

## References

- [Zarf Documentation](https://docs.zarf.dev)
- [kubespray-offline GitHub](https://github.com/kubespray-offline/kubespray-offline)
- [Kubespray Offline Docs](https://github.com/kubernetes-sigs/kubespray/blob/master/docs/offline-environment.md)
