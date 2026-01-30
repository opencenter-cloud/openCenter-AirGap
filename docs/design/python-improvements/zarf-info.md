---
doc_type: explanation
---

# Zarf Packaging Framework

**Purpose**: Understanding Zarf's architecture and capabilities for air-gap Kubernetes deployments to inform openCenter AirGap design decisions.

**Audience**: Platform engineers evaluating Zarf's native capabilities versus custom bash orchestration.

## What is Zarf

Zarf is a declarative packaging framework for deploying Kubernetes applications in disconnected environments. Written in Go with a single Rust binary for cluster bootstrapping, it bundles all deployment dependencies—container images, Helm charts, manifests, git repos, files—into a single zstd-compressed tarball.

**Core value proposition**: Eliminate bash orchestration scripts by providing native primitives for air-gap asset management, registry injection, and declarative deployment workflows.

## Architecture Model

### Three-Phase Lifecycle

1. **Package Creation** (`zarf package create`)
   - Executes on internet-connected system
   - Pulls all remote resources (images, repos, charts)
   - Bundles into single `.tar.zst` artifact
   - Generates SBOM automatically

2. **Package Transfer**
   - Single artifact transport across air-gap boundary
   - Cryptographic verification via Cosign signatures
   - Optional package splitting for media constraints (DVDs)

3. **Package Deployment** (`zarf package deploy`)
   - Executes on disconnected system
   - Extracts assets to filesystem or cluster
   - Mutates resource references to local registry/git
   - No internet connectivity required

### Component-Based Packaging

Packages consist of named components with explicit dependencies:

```yaml
kind: ZarfPackageConfig
metadata:
  name: my-package
  version: 1.0.0

components:
  - name: container-registry
    required: true
    images:
      - registry:2.8.3

  - name: application
    required: false
    charts:
      - name: app-chart
        url: https://charts.example.com
    images:
      - ghcr.io/org/app:v1.0.0
    repos:
      - https://github.com/org/repo.git@v1.0.0
```

**Component types**:
- `required: true` - Always deployed
- `required: false` - Interactive prompt or `--components` flag selection
- Deployed sequentially in definition order

## Container Image Handling

### Image Discovery

**Automatic**: `zarf dev find-images` scans Helm charts and manifests
**Manual**: Explicit `images:` list in component definition

### Image Collection (Create Phase)

1. Pulls images from source registries (Docker, GCR, Quay, etc.)
2. Stores in local cache (`~/.zarf-cache`)
3. Converts to OCI layout or tar archives
4. Bundles into package tarball

**Performance note**: Docker save is slow. Workaround: push to local registry first, then reference in package.

### Image Deployment (Deploy Phase)

1. Extracts images from package
2. Pushes to Zarf-managed registry (or external via `--registry-*` flags)
3. Mutating webhook (`zarf-agent`) rewrites pod specs:
   - `ghcr.io/org/app:v1.0.0` → `127.0.0.1:31999/org/app:v1.0.0-zarf-298505108`
   - CRC32 hash prevents collisions from different source registries
   - Injects ImagePullSecrets automatically

### Registry Injection (Init Package)

**Problem**: Cluster needs registry to pull images, but registry image requires a registry (chicken-egg).

**Solution**: Statically compiled Rust binary (`zarf-injector`) injected via ConfigMaps:

1. Split `registry:3` image into 512KB chunks (ConfigMap 1MB limit)
2. Inject chunks + `zarf-injector` binary as ConfigMaps
3. Ephemeral pod reassembles image, hosts temporary registry
4. Deploy permanent registry chart pulling from temporary registry
5. Destroy ephemeral resources

**Result**: Distro-agnostic cluster bootstrapping without pre-existing images.

## Component Primitives

### Images
```yaml
images:
  - ghcr.io/stefanprodan/podinfo:6.4.0
  - registry.k8s.io/pause:3.9
```
- OCI-compliant artifacts (containers, Helm charts, etc.)
- Automatic pull, cache, bundle, push workflow

### Image Archives
```yaml
imageArchives:
  - path: images.tar
    images:
      - custom/image:v1
```
- Pre-built OCI archives (docker save, podman save --format=oci-archive)
- Requires `io.containerd.image.name` or `org.opencontainers.image.ref.name` annotations

### Helm Charts
```yaml
charts:
  - name: podinfo
    version: 6.4.0
    namespace: podinfo
    url: https://github.com/stefanprodan/podinfo.git
    gitPath: charts/podinfo
```
- Local paths or remote URLs
- Automatic values templating with Zarf variables
- Deployed via Helm SDK

### Manifests
```yaml
manifests:
  - name: raw-manifests
    namespace: default
    files:
      - manifest.yaml
      - https://raw.githubusercontent.com/org/repo/main/deploy.yaml
    kustomizations:
      - path/to/kustomization
```
- Raw Kubernetes YAML
- Wrapped in auto-generated Helm chart for lifecycle management
- Supports local files, remote URLs, kustomizations

### Git Repositories
```yaml
repos:
  - https://github.com/zarf-dev/zarf.git@v0.15.0  # Tag-based (recommended)
  - https://github.com/zarf-dev/zarf.git@c74e2e9  # SHA-based
  - https://github.com/stefanprodan/podinfo.git   # Full clone (all branches/tags)
```
- Mirrored to in-cluster Gitea (via init package git-server component)
- Tag/SHA pushed to `zarf-ref-<tag>` branch
- CRC32 hash appended to repo name prevents collisions

### Files
```yaml
files:
  - source: local/file.txt
    target: /opt/app/config.txt
  - source: https://example.com/binary
    target: /usr/local/bin/tool
    executable: true
```
- Local or remote sources
- Placed on filesystem during deployment
- Supports executable permissions, symlinking

### Data Injections (Deprecated)
```yaml
dataInjections:
  - source: dataset/
    target:
      namespace: default
      selector: app=database
      container: db
      path: /data
```
- Inject files into running containers
- Requires `###ZARF_DATA_INJECTION_MARKER###` in pod spec
- Deprecated - use init containers or volumes instead

## Actions (Lifecycle Hooks)

Declarative command execution at package lifecycle stages:

```yaml
components:
  - name: example
    actions:
      onCreate:
        before:
          - cmd: ./scripts/pre-build.sh
        after:
          - cmd: echo "Package created"

      onDeploy:
        before:
          - cmd: kubectl create namespace app
        after:
          - wait:
              cluster:
                kind: deployment
                name: app
                namespace: app
                condition: available
        onSuccess:
          - cmd: ./scripts/post-deploy.sh
        onFailure:
          - cmd: ./scripts/rollback.sh

      onRemove:
        before:
          - cmd: ./scripts/cleanup.sh
```

**Action types**:
- `cmd`: Execute shell commands/scripts
- `wait`: Block until condition met (cluster resource, network endpoint)

**Action sets**:
- `onCreate`: Package creation lifecycle
- `onDeploy`: Package deployment lifecycle
- `onRemove`: Package removal lifecycle

**Conditional execution**:
- `onSuccess`: Runs if all previous actions + component stages succeed
- `onFailure`: Runs if any previous action or component stage fails

**Built-in transformations**:
- `./zarf` → Absolute path to Zarf binary
- `###ZARF_VAR_*###` → Variable substitution
- Cross-platform path handling

## Init Package

Special package (`zarf-init-<arch>-<version>.tar.zst`) that prepares cluster for air-gap operation.

**Required components**:
- `zarf-injector`: Rust binary for registry bootstrapping
- `zarf-seed-registry`: Temporary registry for init
- `zarf-registry`: Permanent in-cluster registry (NodePort 127.0.0.1:31999)
- `zarf-agent`: Mutating webhook for image/repo rewriting

**Optional components**:
- `k3s`: Lightweight Kubernetes cluster (requires root, systemd)
- `git-server`: Gitea for GitOps workflows

**Deployment**:
```bash
zarf init --confirm                           # Interactive
zarf init --components k3s,git-server         # Explicit components
zarf init --registry-url registry.corp.local  # External registry
```

**Registry HA configuration**:
```yaml
# zarf-config.yaml
package:
  deploy:
    set:
      REGISTRY_PVC_SIZE: 100Gi
      REGISTRY_PVC_ACCESS_MODE: ReadWriteMany
      REGISTRY_HPA_AUTO_SIZE: "true"
      REGISTRY_AFFINITY_CUSTOM: "soft"  # Override anti-affinity
```

## SBOM and Signing

### SBOM Generation

Automatic during `zarf package create`:
- Scans all images for dependencies
- Generates CycloneDX/SPDX format
- Embedded in package metadata

**Inspection**:
```bash
zarf package inspect package.tar.zst --sbom
zarf tools sbom packages:. -o json  # Scan local package directory
```

**Attestation** (Cosign integration):
```bash
zarf tools sbom attest --key cosign.key --output spdx-json image:tag
```

### Cryptographic Signing

**Package signing**:
```bash
zarf package create --signing-key private.key
zarf package publish oci://registry/repo --signing-key private.key
```

**Verification**:
```bash
zarf package deploy package.tar.zst --public-key public.key
```

Uses Cosign under the hood for OCI artifact signatures.

## CLI Command Reference

### Core Commands

**Package creation**:
```bash
zarf package create [directory]
  --confirm                    # Skip prompts
  --output-dir ./dist          # Output location
  --signing-key key.pem        # Sign package
  --max-package-size 1000      # Split into chunks (MB)
  --registry-override reg.local # Override image sources
```

**Package deployment**:
```bash
zarf package deploy package.tar.zst
  --confirm                    # Skip prompts
  --components comp1,comp2     # Select components
  --set VAR=value              # Set variables
  --registry-url registry.local # External registry
  --registry-push-username user
  --registry-push-password pass
```

**Package inspection**:
```bash
zarf package inspect package.tar.zst
  --sbom                       # Show SBOM
  --list-images                # List all images
zarf package inspect definition package.tar.zst  # Show zarf.yaml
```

**OCI operations**:
```bash
zarf package publish package.tar.zst oci://registry/repo:tag
zarf package pull oci://registry/repo:tag
zarf package deploy oci://registry/repo:tag
```

### Development Commands

```bash
zarf dev deploy [directory]    # Create + deploy in one step (YOLO mode)
zarf dev find-images [directory] # Scan for images in charts/manifests
zarf dev inspect definition [directory] # Preview zarf.yaml
```

### Tools Commands

```bash
zarf tools registry push image.tar registry:5000/image:tag
zarf tools registry pull registry:5000/image:tag
zarf tools sbom packages:. -o spdx-json
zarf tools cache-clear         # Clear ~/.zarf-cache
```

## Component Composition

Import components from other packages for reusability:

### Local Import
```yaml
components:
  - name: imported-component
    import:
      path: ../common-components
```

### OCI Import (Skeleton Packages)
```yaml
components:
  - name: imported-component
    import:
      url: oci://registry/skeleton-package:v1.0.0
```

**Skeleton packages**: Published package definitions without remote resources (images/repos not fetched). Created via:
```bash
zarf package publish ./package-dir oci://registry/skeleton:v1.0.0
```

### Merge Behavior

| Primitive Type | Merge Strategy |
|----------------|----------------|
| `name`, `required`, `default` | Override (use importing component's value) |
| `description` | Override if non-empty |
| Un-named arrays (`images`, `repos`, `files`) | Append |
| Named arrays (`charts`, `manifests`) | Merge by name, append if new |

## Integration Points

### Kubernetes
- Helm SDK for all workload installs
- Mutating webhook for runtime image rewriting
- NodePort registry (127.0.0.1:31999) avoids TLS issues
- Health checks via kstatus library

### Container Registries
- Docker Registry v2 API
- OCI Distribution Spec compliance
- Supports Docker, containerd, Podman runtimes
- Registry mirror configuration via `--registry-override`

### GitOps
- Gitea for in-cluster Git server
- FluxCD resource mutation (GitRepository, OCIRepository, HelmRepository)
- ArgoCD resource mutation (Application, ApplicationSet, Repository)

### CI/CD
- Package publishing to OCI registries
- SBOM integration for supply chain security
- Cosign signing for artifact verification
- Declarative package definitions (GitOps-friendly)

## Variables and Templating

**Variable definition**:
```yaml
variables:
  - name: DOMAIN
    description: "Application domain"
    default: "example.com"
    prompt: true

  - name: REPLICAS
    default: "3"
    pattern: "^[0-9]+$"
```

**Variable usage**:
```yaml
charts:
  - name: app
    valuesFiles:
      - values.yaml
    variables:
      - name: DOMAIN
        path: ingress.host
```

**Built-in variables**:
- `###ZARF_REGISTRY###` - Zarf registry address
- `###ZARF_SEED_REGISTRY###` - Temporary seed registry
- `###ZARF_VAR_*###` - User-defined variables
- `###ZARF_TEMP###` - Temporary directory

**Setting variables**:
```bash
zarf package deploy --set DOMAIN=app.local --set REPLICAS=5
```

## Package Flavors

Conditional component inclusion based on deployment target:

```yaml
components:
  - name: aws-storage
    only:
      flavor: aws

  - name: azure-storage
    only:
      flavor: azure
```

**Usage**:
```bash
zarf package create --flavor aws
```

## YOLO Mode

Skip `zarf init` requirement for testing or externally-managed infrastructure:

```yaml
metadata:
  name: test-package
  yolo: true
```

**Use cases**:
- Testing in development clusters
- Environments with pre-existing registries/git servers
- Gradual Zarf adoption without full migration

## Comparison to Bash Orchestration

| Capability | Bash Scripts | Zarf Native |
|------------|--------------|-------------|
| Image collection | `docker pull && docker save` loops | Declarative `images:` list, automatic pull |
| Image deployment | `docker load && docker push` loops | Single `zarf package deploy`, automatic push |
| Registry bootstrapping | Manual registry deployment, chicken-egg | Automatic injector system |
| Image reference rewriting | Manual manifest editing or admission controller | Built-in mutating webhook |
| Git repo mirroring | `git clone && git push --mirror` | Declarative `repos:` list |
| Helm chart deployment | `helm install` with custom logic | Helm SDK with lifecycle management |
| Dependency ordering | Bash script sequencing | Component ordering + health checks |
| Error handling | Manual `set -e`, trap handlers | Automatic rollback, onFailure hooks |
| Idempotency | Manual state checking | Helm-based state management |
| SBOM generation | External tooling (Syft, Trivy) | Automatic during package creation |
| Package verification | Manual checksum scripts | Built-in Cosign integration |
| Variable substitution | Bash parameter expansion, envsubst | Declarative variables with validation |
| Cross-platform | Bash + coreutils dependencies | Single static binary (Go + Rust) |

## Limitations and Considerations

### Performance
- Docker save is slow for large images (use local registry workaround)
- Package creation time scales with asset count
- Cache directory grows unbounded (manual `zarf tools cache-clear`)

### Operational
- Init package required for most deployments (unless YOLO mode)
- Registry not HA by default (requires RWX storage or S3 backend)
- NodePort registry binding (127.0.0.1:31999) may conflict
- Mutating webhook requires cluster admin permissions

### Design Constraints
- Component ordering is sequential (no parallel deployment)
- Image tag mutation with CRC32 hash (observability impact)
- ConfigMap size limit (1MB) constrains injector design
- Helm SDK dependency (all workloads wrapped in Helm charts)

### Compatibility
- K3s component requires root + systemd (not sudo)
- Docker engine >= 25.0.0 for OCI-compliant save
- Kubernetes 1.19+ for admission webhook features

## Applicability to openCenter AirGap

### Direct Replacement Opportunities

**High confidence**:
- Image collection and bundling (replace `download-images.sh`)
- Registry deployment and seeding (replace `start-registry.sh`)
- Git repository mirroring (replace `mirror-repos.sh`)
- Helm chart deployment (replace `deploy-charts.sh`)
- SBOM generation (replace external Syft/Trivy calls)

**Medium confidence**:
- Kubespray integration (via `files:` component + actions)
- Terraform provider mirroring (via `files:` component)
- Apt/PyPI repository setup (via `files:` + actions)

**Low confidence**:
- OpenStack provisioning (Terraform execution via actions)
- Multi-stage build orchestration (Zarf is single-package focused)

### Integration Challenges

1. **Kubespray offline assets**: Zarf expects OCI images, not kubespray-offline directory structure
   - **Mitigation**: Use `files:` component to bundle kubespray-offline outputs, deploy via actions

2. **Bastion-based architecture**: Zarf assumes in-cluster registry, openCenter uses bastion host
   - **Mitigation**: Use `--registry-url` to point to bastion registry, skip zarf-registry component

3. **Nginx file server**: Zarf doesn't manage apt/pypi repositories
   - **Mitigation**: Bundle repos as `files:`, use actions to start Nginx

4. **Version pinning**: Zarf uses package-level versions, openCenter uses `versions.env`
   - **Mitigation**: Generate zarf.yaml from versions.env via templating

5. **Multi-package workflow**: openCenter is single artifact, Zarf encourages component modularity
   - **Mitigation**: Single mega-package or UDS bundle (multi-package orchestration)

### Recommended Hybrid Approach

**Use Zarf for**:
- Container image lifecycle (pull, bundle, push, mutate)
- Helm chart deployment (cert-manager, ingress-nginx, Keycloak, etc.)
- Git repository mirroring (FluxCD sources)
- SBOM generation and package signing
- Declarative component definitions

**Keep bash/Python for**:
- Kubespray execution (complex Ansible orchestration)
- Terraform OpenStack provisioning (stateful infrastructure)
- Apt/PyPI repository generation (deb/wheel specific tooling)
- Bastion service management (Nginx, registry startup)
- Build-time asset collection (kubespray-offline integration)

**Rationale**: Zarf excels at Kubernetes-native workloads but doesn't replace infrastructure provisioning or OS-level package management. Hybrid approach leverages Zarf's strengths while preserving existing tooling for specialized tasks.

## References

- [Zarf Documentation](https://docs.zarf.dev) - Official docs
- [Zarf GitHub](https://github.com/defenseunicorns/zarf) - Source code
- [UDS (Unicorn Delivery Service)](https://uds.defenseunicorns.com) - Multi-package orchestration
- [Zarf Injector](https://github.com/zarf-dev/zarf-injector) - Registry bootstrapping binary
- [Defense Unicorns Blog](https://medium.com/defense-unicorns) - Use cases and tutorials

---

**Content rephrased for compliance with licensing restrictions. Original sources linked inline.**
