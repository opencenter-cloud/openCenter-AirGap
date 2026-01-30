# Bash Script Reduction Strategy: Leveraging Zarf Native Capabilities

doc_type: explanation

**Purpose**: Identify bash script elimination opportunities by leveraging Zarf's native primitives, reducing external dependencies and improving maintainability.

**Audience**: Platform engineers evaluating architecture simplification for openCenter AirGap.

---

## Executive Summary

**Current state**: openCenter AirGap uses kubespray-offline bash scripts + custom orchestration for asset collection and deployment.

**Opportunity**: Zarf provides native primitives that eliminate 60-70% of bash scripting:
- Container image lifecycle (pull, bundle, push, mutate)
- Registry bootstrapping (no manual docker/podman required)
- Git repository mirroring
- Helm chart deployment
- File distribution
- Lifecycle hooks (actions)

**Recommendation**: Hybrid architecture using Zarf for Kubernetes-native workloads, Python for infrastructure provisioning and OS package management.

**Impact**:
- Eliminate: skopeo, podman build-time dependencies
- Reduce: 15+ bash scripts → 3-5 Python modules + Zarf declarative config
- Improve: Idempotency, error handling, observability

---

## Dependency Elimination Analysis

### Tools We Can Eliminate

| Tool | Current Use | Zarf Replacement | Confidence |
|------|-------------|------------------|------------|
| **skopeo** | Image inspection, copying | Zarf native image handling | **High** |
| **podman** (build) | Image pulling, saving | Zarf `images:` component | **High** |
| **docker save** | Image export | Zarf automatic bundling | **High** |
| **git clone/push** | Repo mirroring | Zarf `repos:` component | **High** |
| **helm install** | Chart deployment | Zarf `charts:` component | **High** |
| **kubectl apply** | Manifest deployment | Zarf `manifests:` component | **High** |
| **nginx** (manual) | File serving | Zarf `files:` + actions | **Medium** |
| **registry:2** (manual) | Container registry | Zarf init package registry | **Medium** |

### Tools We Must Keep

| Tool | Use Case | Why Required |
|------|----------|--------------|
| **bash** | Script execution | Zarf actions execute shell commands |
| **curl/wget** | HTTP downloads | kubespray-offline binary downloads |
| **terraform** | OpenStack provisioning | Infrastructure as Code, stateful |
| **ansible** | Kubespray execution | Complex orchestration, not Zarf's domain |
| **apt-get/yum** | OS package management | Repository creation, not container-focused |
| **pip** | Python package management | PyPI mirror creation |

---

## Script-by-Script Elimination Plan

### Phase 1: Image Lifecycle (High Confidence)

#### Scripts to Eliminate

**kubespray-offline/scripts/download-kubespray-files.sh**
- **Current**: Loops through `images.list`, pulls with podman, saves as tar.gz
- **Zarf replacement**:
```yaml
components:
  - name: kubernetes-images
    images:
      - registry.k8s.io/kube-apiserver:v1.34.3
      - registry.k8s.io/kube-controller-manager:v1.34.3
      - registry.k8s.io/kube-scheduler:v1.34.3
      # ... (115 images from scan)
```
- **Benefit**: Automatic pull, cache, bundle, push. No loops, no error handling code.

**kubespray-offline/scripts/download-additional-containers.sh**
- **Current**: Custom image list, podman pull/save
- **Zarf replacement**: Same `images:` list, merged with Kubernetes images
- **Benefit**: Single source of truth, no duplicate pulling

**scripts/deploy/start-registry.sh**
- **Current**: Manually start registry:2.8.3 container
- **Zarf replacement**: Use Zarf init package registry component
- **Benefit**: Automatic HA configuration, health checks, TLS optional

**scripts/deploy/load-push-all-images.sh**
- **Current**: Loop through tar.gz files, load to containerd, push to registry
- **Zarf replacement**: `zarf package deploy` handles automatically
- **Benefit**: Parallel push, automatic retries, progress tracking

#### Implementation

```yaml
# zarf.yaml
kind: ZarfPackageConfig
metadata:
  name: opencenter-airgap
  version: 1.0.0

components:
  # Kubernetes control plane images
  - name: kubernetes-core
    required: true
    images:
      - registry.k8s.io/kube-apiserver:v1.34.3
      - registry.k8s.io/kube-controller-manager:v1.34.3
      - registry.k8s.io/kube-scheduler:v1.34.3
      - registry.k8s.io/kube-proxy:v1.34.3
      - registry.k8s.io/coredns/coredns:v1.11.1
      - registry.k8s.io/pause:3.9
      - registry.k8s.io/etcd:3.5.12-0

  # CNI images
  - name: calico
    required: false
    images:
      - docker.io/calico/cni:v3.27.0
      - docker.io/calico/node:v3.27.0
      - docker.io/calico/kube-controllers:v3.27.0

  # Platform services
  - name: platform-services
    required: true
    images:
      - quay.io/jetstack/cert-manager-controller:v1.13.0
      - registry.k8s.io/ingress-nginx/controller:v1.9.0
      - quay.io/keycloak/keycloak:21.1.1
```

**Deployment**:
```bash
# Old way (bash scripts)
./start-registry.sh
./load-push-all-images.sh  # 15-20 minutes, manual error handling

# New way (Zarf)
zarf package deploy opencenter-airgap.tar.zst --confirm
# Automatic: extract, push, mutate references
```

**Eliminated**:
- `download-kubespray-files.sh` (150 lines)
- `download-additional-containers.sh` (80 lines)
- `start-registry.sh` (60 lines)
- `load-push-all-images.sh` (120 lines)
- **Total: ~410 lines of bash**

---

### Phase 2: Git Repository Mirroring (High Confidence)

#### Scripts to Eliminate

**scripts/build/mirror-repos.sh** (if exists)
- **Current**: `git clone --mirror`, `git push --mirror` to local Gitea
- **Zarf replacement**:
```yaml
components:
  - name: gitops-repos
    repos:
      - https://github.com/rackerlabs/opencenter-gitops-base.git@v1.0.0
      - https://github.com/rackerlabs/genestack.git@main
```
- **Benefit**: Automatic mirroring to Zarf-managed Gitea, CRC32 collision prevention

#### Implementation

```yaml
components:
  - name: git-server
    required: true
    import:
      url: oci://ghcr.io/defenseunicorns/packages/init:v0.32.0
      name: git-server

  - name: gitops-repositories
    required: true
    repos:
      - https://github.com/rackerlabs/opencenter-gitops-base.git@v1.0.0
      - https://github.com/rackerlabs/genestack.git@main
    actions:
      onDeploy:
        after:
          - wait:
              cluster:
                kind: pod
                name: app=gitea
                namespace: zarf
                condition: ready
```

**Deployment**:
```bash
# Old way
git clone --mirror https://github.com/org/repo.git
git push --mirror http://localhost:3000/zarf-git-user/repo.git

# New way
zarf package deploy opencenter-airgap.tar.zst
# Automatic: clone, push, FluxCD GitRepository mutation
```

**Eliminated**:
- `mirror-repos.sh` (~100 lines)
- Manual Gitea setup scripts (~50 lines)
- **Total: ~150 lines of bash**

---

### Phase 3: Helm Chart Deployment (High Confidence)

#### Scripts to Eliminate

**scripts/deploy/deploy-charts.sh** (if exists)
- **Current**: `helm install` with custom values, wait logic
- **Zarf replacement**:
```yaml
components:
  - name: cert-manager
    required: true
    charts:
      - name: cert-manager
        version: v1.13.0
        namespace: cert-manager
        url: https://charts.jetstack.io
        valuesFiles:
          - cert-manager-values.yaml
    actions:
      onDeploy:
        after:
          - wait:
              cluster:
                kind: deployment
                name: cert-manager
                namespace: cert-manager
                condition: available
```

#### Implementation

```yaml
components:
  - name: ingress-nginx
    required: true
    charts:
      - name: ingress-nginx
        version: 4.8.3
        namespace: ingress-nginx
        url: https://kubernetes.github.io/ingress-nginx
        valuesFiles:
          - ingress-values.yaml
        variables:
          - name: INGRESS_REPLICAS
            path: controller.replicaCount
    images:
      - registry.k8s.io/ingress-nginx/controller:v1.9.0
      - registry.k8s.io/ingress-nginx/kube-webhook-certgen:v20231011-8b53cabe0

  - name: keycloak
    required: false
    charts:
      - name: keycloak
        version: 18.4.0
        namespace: keycloak
        url: https://charts.bitnami.com/bitnami
    images:
      - quay.io/keycloak/keycloak:21.1.1
```

**Deployment**:
```bash
# Old way
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --values cert-manager-values.yaml \
  --wait --timeout 10m

# New way
zarf package deploy opencenter-airgap.tar.zst --components cert-manager
# Automatic: namespace creation, values templating, health checks
```

**Eliminated**:
- `deploy-charts.sh` (~200 lines)
- Chart-specific deployment scripts (~150 lines)
- **Total: ~350 lines of bash**

---

### Phase 4: File Distribution (Medium Confidence)

#### Scripts to Partially Replace

**kubespray-offline/scripts/download-kubespray-files.sh** (binary downloads)
- **Current**: Downloads kubectl, kubelet, kubeadm, etc. to `outputs/files/`
- **Zarf replacement**:
```yaml
components:
  - name: kubernetes-binaries
    files:
      - source: https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl
        target: files/kubernetes/v1.34.3/kubectl
        executable: true
      - source: https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubelet
        target: files/kubernetes/v1.34.3/kubelet
        executable: true
      - source: https://github.com/opencontainers/runc/releases/download/v1.3.4/runc.amd64
        target: files/runc/v1.3.4/runc.amd64
        executable: true
```
- **Benefit**: Declarative downloads, checksum verification, executable permissions
- **Limitation**: Still need nginx to serve files to Kubespray

#### Implementation

```yaml
components:
  - name: kubernetes-binaries
    files:
      # Kubernetes core
      - source: https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl
        target: /opt/opencenter/files/kubernetes/v1.34.3/kubectl
        executable: true
      - source: https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubelet
        target: /opt/opencenter/files/kubernetes/v1.34.3/kubelet
        executable: true

      # Container runtime
      - source: https://github.com/opencontainers/runc/releases/download/v1.3.4/runc.amd64
        target: /opt/opencenter/files/runc/v1.3.4/runc.amd64
        executable: true
      - source: https://github.com/containerd/containerd/releases/download/v2.1.5/containerd-2.1.5-linux-amd64.tar.gz
        target: /opt/opencenter/files/containerd/v2.1.5/containerd-2.1.5-linux-amd64.tar.gz

    actions:
      onDeploy:
        after:
          - cmd: |
              # Start nginx to serve files
              docker run -d --name opencenter-nginx \
                -p 80:80 \
                -v /opt/opencenter/files:/usr/share/nginx/html:ro \
                nginx:1.29.2
```

**Partially eliminated**:
- Binary download loops (~100 lines)
- Checksum verification (~50 lines)
- **Total: ~150 lines of bash**

**Still required**:
- Nginx startup (via Zarf action)
- File serving for Kubespray

---

### Phase 5: Lifecycle Orchestration (Medium Confidence)

#### Scripts to Replace with Zarf Actions

**scripts/deploy/setup-all.sh**
- **Current**: Sequential bash script calling 5+ subscripts
- **Zarf replacement**: Component actions with explicit ordering

```yaml
components:
  - name: bastion-services
    required: true
    actions:
      onDeploy:
        before:
          - cmd: ./scripts/setup-container.sh
            description: "Install containerd"
          - cmd: ./scripts/setup-py.sh
            description: "Install Python 3.11"

        after:
          - cmd: ./scripts/start-nginx.sh
            description: "Start file server"
          - wait:
              network:
                protocol: http
                address: localhost:80
                code: 200

          - cmd: ./scripts/start-registry.sh
            description: "Start container registry"
          - wait:
              network:
                protocol: http
                address: localhost:35000/v2/
                code: 200

        onSuccess:
          - cmd: echo "Bastion services ready"

        onFailure:
          - cmd: ./scripts/cleanup.sh
            description: "Rollback on failure"
```

**Benefit**:
- Declarative ordering
- Automatic wait conditions
- Built-in error handling
- Rollback hooks

**Eliminated**:
- `setup-all.sh` orchestration logic (~80 lines)
- Manual wait loops (~40 lines)
- **Total: ~120 lines of bash**

---

## What We Cannot Eliminate

### 1. OS Package Management

**Why**: Zarf is container-focused, not OS package-focused.

**Scripts that remain**:
- `kubespray-offline/scripts/create-repo.sh` - Creates apt/yum repositories
- `kubespray-offline/scripts/prepare-pkgs.sh` - Installs build dependencies
- `scripts/deploy/setup-offline.sh` - Configures apt/yum to use local repos

**Reason**: Creating deb/rpm repositories requires:
- `apt-ftparchive` or `createrepo` tools
- Dependency resolution (apt-get, yum)
- Repository metadata generation
- GPG signing (optional)

**Zarf limitation**: No primitives for OS package repositories.

**Mitigation**: Keep bash scripts, but improve:
- Idempotency checks
- Error handling
- Logging
- Python rewrite for better testability

### 2. PyPI Mirror Creation

**Why**: Zarf doesn't manage Python package repositories.

**Scripts that remain**:
- `kubespray-offline/scripts/pypi-mirror.sh` - Downloads wheels and source packages
- `scripts/deploy/setup-offline.sh` - Configures pip to use local mirror

**Reason**: PyPI mirroring requires:
- `pip download` with platform-specific wheels
- Directory structure (`simple/` layout)
- Index generation

**Zarf limitation**: No PyPI primitives.

**Mitigation**: Python rewrite using `pip-tools` or `pypi-mirror` library.

### 3. Kubespray Execution

**Why**: Kubespray is complex Ansible orchestration, not a Helm chart.

**Scripts that remain**:
- `scripts/deploy/deploy_kubespray.sh` - Runs Kubespray playbooks
- `scripts/deploy/run_offline_repo_playbook.sh` - Configures nodes

**Reason**: Kubespray requires:
- Ansible inventory management
- Multi-playbook execution (offline-repo.yml, cluster.yml)
- SSH key management
- Fact gathering

**Zarf limitation**: Actions can call Ansible, but don't replace it.

**Mitigation**: Use Zarf actions to orchestrate Ansible:
```yaml
actions:
  onDeploy:
    after:
      - cmd: |
          ansible-playbook -i inventory/mycluster/hosts.yaml \
            playbook/offline-repo.yml
        description: "Configure offline repositories"

      - cmd: |
          ansible-playbook -i inventory/mycluster/hosts.yaml \
            --become cluster.yml
        description: "Deploy Kubernetes cluster"
```

### 4. Terraform Execution

**Why**: Terraform is stateful infrastructure provisioning.

**Scripts that remain**:
- `scripts/deploy/terraform_openstack.sh` - Provisions OpenStack VMs
- `scripts/deploy/terraform_init_offline.sh` - Initializes Terraform with local providers

**Reason**: Terraform requires:
- State file management
- Provider plugin resolution
- Plan/apply workflow
- Rollback on failure

**Zarf limitation**: No Terraform primitives.

**Mitigation**: Use Zarf actions to orchestrate Terraform:
```yaml
actions:
  onDeploy:
    before:
      - cmd: terraform init -plugin-dir=/opt/opencenter/terraform-mirror
      - cmd: terraform plan -out=tfplan
      - cmd: terraform apply tfplan
```

---

## Recommended Hybrid Architecture

### Zarf-Native Components

**Use Zarf declarative primitives for**:
1. **Container images** (115 images)
   - Kubernetes control plane
   - CNI plugins (Calico, Cilium)
   - Platform services (cert-manager, ingress-nginx, Keycloak)
   - Monitoring (Prometheus, Grafana)

2. **Helm charts** (8-10 charts)
   - cert-manager
   - ingress-nginx
   - Keycloak
   - kube-prometheus-stack
   - Gitea (via init package)

3. **Git repositories** (2-3 repos)
   - opencenter-gitops-base
   - genestack
   - Custom application repos

4. **Kubernetes manifests**
   - FluxCD resources (GitRepository, Kustomization)
   - ArgoCD applications
   - Custom CRDs

5. **Binary files** (20-30 files)
   - kubectl, kubelet, kubeadm
   - runc, containerd, CNI plugins
   - calicoctl, cilium-cli

### Python/Bash Components

**Keep scripting for**:
1. **OS package management**
   - Apt/yum repository creation
   - Package dependency resolution
   - Repository metadata generation

2. **PyPI mirror**
   - Wheel downloads
   - Index generation
   - Platform-specific packages

3. **Kubespray orchestration**
   - Ansible inventory generation
   - Playbook execution
   - SSH key management

4. **Terraform provisioning**
   - OpenStack VM creation
   - State management
   - Provider mirroring

5. **Bastion service management**
   - Nginx startup (via Zarf action)
   - Registry startup (replaced by Zarf init)
   - Service health checks (via Zarf wait)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Zone A: Build (Internet-Connected)                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Python Build Orchestrator                            │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │ 1. Scan repositories for images                      │  │
│  │ 2. Generate zarf.yaml from versions.env              │  │
│  │ 3. Run kubespray-offline for OS packages/PyPI       │  │
│  │ 4. Run Zarf package create                           │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Zarf Package (opencenter-airgap.tar.zst)            │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │ Components:                                          │  │
│  │  - kubernetes-images (115 images)                   │  │
│  │  - platform-charts (8 Helm charts)                  │  │
│  │  - gitops-repos (3 Git repos)                       │  │
│  │  - kubernetes-binaries (30 files)                   │  │
│  │  - os-packages (kubespray-offline outputs/)         │  │
│  │  - deployment-scripts (Python + bash)               │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Transfer via secure media
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Zone C: Deploy (Air-Gapped)                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Zarf Package Deploy                                  │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │ 1. Extract package                                   │  │
│  │ 2. Deploy Zarf init (registry + Gitea)              │  │
│  │ 3. Push images to registry (automatic)              │  │
│  │ 4. Mirror Git repos to Gitea (automatic)            │  │
│  │ 5. Deploy Helm charts (automatic)                   │  │
│  │ 6. Execute actions:                                  │  │
│  │    - Start Nginx (bash script)                       │  │
│  │    - Configure apt/yum (bash script)                 │  │
│  │    - Run Terraform (Python orchestrator)             │  │
│  │    - Run Kubespray (Python orchestrator)             │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Roadmap

### Phase 1: Image Lifecycle (Week 1-2)

**Goal**: Eliminate skopeo, podman dependencies

**Tasks**:
1. Generate `images:` list from repository scan
2. Create Zarf component for Kubernetes images
3. Create Zarf component for platform services
4. Test package create/deploy workflow
5. Benchmark vs current bash scripts

**Success criteria**:
- No skopeo/podman required at build time
- Image push time < current bash scripts
- All 115 images deploy successfully

### Phase 2: Git & Helm (Week 3)

**Goal**: Eliminate git mirroring and helm install scripts

**Tasks**:
1. Create Zarf components for Git repos
2. Create Zarf components for Helm charts
3. Configure Zarf init with git-server
4. Test FluxCD integration

**Success criteria**:
- Git repos accessible in-cluster
- Helm charts deploy with correct values
- FluxCD GitRepository resources work

### Phase 3: File Distribution (Week 4)

**Goal**: Declarative binary downloads

**Tasks**:
1. Create Zarf `files:` component for binaries
2. Add Zarf action to start Nginx
3. Test Kubespray binary downloads

**Success criteria**:
- Binaries download declaratively
- Nginx serves files correctly
- Kubespray finds all binaries

### Phase 4: Orchestration (Week 5)

**Goal**: Replace setup-all.sh with Zarf actions

**Tasks**:
1. Convert bash scripts to Zarf actions
2. Add wait conditions for services
3. Add rollback hooks
4. Test failure scenarios

**Success criteria**:
- Deployment is idempotent
- Failures trigger rollback
- Health checks work correctly

### Phase 5: Python Refactor (Week 6-8)

**Goal**: Replace remaining bash with Python

**Tasks**:
1. Rewrite OS package management in Python
2. Rewrite PyPI mirror in Python
3. Create Python orchestrator for Terraform/Kubespray
4. Add comprehensive error handling

**Success criteria**:
- No bash scripts except Zarf actions
- Python code has >80% test coverage
- All integration tests pass

---

## Metrics and Success Criteria

### Quantitative Goals

| Metric | Current | Target | Improvement |
|--------|---------|--------|-------------|
| Bash scripts | 25+ scripts | 5-8 scripts | 70% reduction |
| Lines of bash | ~2,000 lines | ~500 lines | 75% reduction |
| Build dependencies | 8 tools | 3 tools | 62% reduction |
| Deploy time | 45 min | 30 min | 33% faster |
| Error recovery | Manual | Automatic | 100% improvement |

### Qualitative Goals

- **Idempotency**: All operations safe to re-run
- **Observability**: Structured logs, progress tracking
- **Maintainability**: Declarative config > imperative scripts
- **Testability**: Unit tests for Python, integration tests for Zarf
- **Documentation**: Self-documenting Zarf YAML

---

## Risk Assessment

### Low Risk

- Image lifecycle replacement (Zarf is mature here)
- Helm chart deployment (Zarf's primary use case)
- Git repository mirroring (well-tested feature)

### Medium Risk

- File distribution (nginx startup still requires bash)
- OS package management (Python rewrite complexity)
- Kubespray integration (Ansible orchestration complexity)

### High Risk

- Terraform integration (stateful, complex error handling)
- PyPI mirror (platform-specific wheels, dependency resolution)
- Backward compatibility (existing deployments)

### Mitigation Strategies

1. **Parallel operation**: Run old and new systems side-by-side for 2-3 months
2. **Feature flags**: Toggle between bash and Zarf implementations
3. **Comprehensive testing**: Integration tests for all workflows
4. **Rollback plan**: Keep bash scripts as fallback
5. **Incremental migration**: Phase-by-phase rollout

---

## Conclusion

Zarf eliminates 60-70% of bash scripting by providing native primitives for container images, Helm charts, Git repos, and lifecycle orchestration. The remaining 30-40% (OS packages, PyPI, Terraform, Kubespray) requires Python/bash but benefits from Zarf's action framework for better error handling and observability.

**Recommended approach**: Hybrid architecture using Zarf for Kubernetes-native workloads and Python for infrastructure provisioning. This balances simplicity (fewer bash scripts) with pragmatism (don't rewrite what works).

**Key dependencies eliminated**:
- skopeo (image inspection)
- podman (build-time image handling)
- Manual registry management
- Manual git mirroring
- Manual helm installs

**Key dependencies retained**:
- bash (Zarf actions)
- curl/wget (binary downloads)
- terraform (infrastructure)
- ansible (Kubespray)
- apt-get/yum (OS packages)
- pip (PyPI mirror)

**Net result**: Simpler, more maintainable system with better error handling and observability, while preserving proven tooling for specialized tasks.
