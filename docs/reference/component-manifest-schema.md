**doc_type: reference**

# Component Manifest Schema

JSON schema for `components.yaml` that defines what gets packaged.

## Schema Version

Current: `v1`

## Root Structure

```yaml
apiVersion: v1
metadata:
  name: string
  version: string
  description: string
components:
  - name: string
    type: image|chart|binary|file|repository
    enabled: boolean
    # type-specific fields
```

## Metadata Fields

`apiVersion` (required)
Schema version. Must be `v1`.

`metadata.name` (required)
Package name. Used in artifact filename.

`metadata.version` (required)
Package version. Semantic versioning (e.g., `1.2.3`).

`metadata.description` (optional)
Human-readable description.

## Component Fields

`name` (required)
Component identifier. Must be unique within manifest.

`type` (required)
Component type. One of: `image`, `chart`, `binary`, `file`, `repository`.

`enabled` (optional)
Include in build. Default: `true`.

## Component Types

### image

Container image to include in registry.

```yaml
- name: nginx
  type: image
  image: docker.io/library/nginx:1.25.0
  digest: sha256:4c0fdaa8b6341bfdeca5f18f7837462c80cff90527ee35ef185571e1c327beac
  platform: linux/amd64
```

**Fields**:

`image` (required)
Full image reference with tag.

`digest` (optional)
SHA256 digest. If provided, image is pulled by digest instead of tag.

`platform` (optional)
Target platform. Default: `linux/amd64`.

### chart

Helm chart to include.

```yaml
- name: ingress-nginx
  type: chart
  repository: https://kubernetes.github.io/ingress-nginx
  chart: ingress-nginx
  version: 4.7.0
  values:
    controller:
      service:
        type: NodePort
```

**Fields**:

`repository` (required)
Helm repository URL.

`chart` (required)
Chart name in repository.

`version` (required)
Chart version.

`values` (optional)
Default values to include. Merged with user-provided values at deploy time.

### binary

Executable binary to include.

```yaml
- name: kubectl
  type: binary
  url: https://dl.k8s.io/release/v1.34.3/bin/linux/amd64/kubectl
  checksum: sha256:a1b2c3d4...
  destination: /usr/local/bin/kubectl
  mode: "0755"
```

**Fields**:

`url` (required)
Download URL.

`checksum` (required)
SHA256 checksum. Format: `sha256:hexdigest`.

`destination` (required)
Install path on target nodes.

`mode` (optional)
File permissions. Default: `0755`.

### file

Arbitrary file to include.

```yaml
- name: custom-config
  type: file
  source: config/custom.yaml
  destination: /etc/kubernetes/custom.yaml
  mode: "0644"
```

**Fields**:

`source` (required)
Local file path (relative to manifest) or URL.

`destination` (required)
Install path on target nodes.

`mode` (optional)
File permissions. Default: `0644`.

### repository

Git repository to clone.

```yaml
- name: kubespray
  type: repository
  url: https://github.com/kubernetes-sigs/kubespray.git
  ref: v2.24.0
  destination: /opt/opencenter/kubespray
```

**Fields**:

`url` (required)
Git repository URL.

`ref` (required)
Git ref (tag, branch, or commit SHA).

`destination` (required)
Clone path on bastion.

## Validation Rules

**Component Names**:
- Must be lowercase alphanumeric with hyphens
- Must start with letter
- Max 63 characters
- Must be unique within manifest

**Image References**:
- Must include registry, repository, and tag
- Digest is optional but recommended
- Tag must not be `latest` in production

**Versions**:
- Must follow semantic versioning (major.minor.patch)
- Pre-release and build metadata allowed (e.g., `1.2.3-rc1+build.123`)

**URLs**:
- Must be HTTPS (HTTP allowed only for localhost)
- Must be reachable at build time

**Checksums**:
- Must be SHA256
- Format: `sha256:` followed by 64 hex characters

**File Modes**:
- Must be octal string (e.g., `"0755"`, not `755`)
- Executables: `0755`
- Configs: `0644`
- Secrets: `0600`

## Example Manifest

```yaml
apiVersion: v1
metadata:
  name: opencenter-airgap
  version: 1.0.0
  description: Air-gapped Kubernetes deployment package

components:
  # Container images
  - name: registry
    type: image
    image: docker.io/library/registry:2.8.3
    digest: sha256:a1b2c3d4e5f6...
    platform: linux/amd64

  - name: nginx
    type: image
    image: docker.io/library/nginx:1.29.2
    platform: linux/amd64

  # Helm charts
  - name: cert-manager
    type: chart
    repository: https://charts.jetstack.io
    chart: cert-manager
    version: v1.13.0
    values:
      installCRDs: true

  - name: ingress-nginx
    type: chart
    repository: https://kubernetes.github.io/ingress-nginx
    chart: ingress-nginx
    version: 4.7.0

  # Binaries
  - name: kubectl
    type: binary
    url: https://dl.k8s.io/release/v1.34.3/bin/linux/amd64/kubectl
    checksum: sha256:abc123...
    destination: /usr/local/bin/kubectl
    mode: "0755"

  - name: kubelet
    type: binary
    url: https://dl.k8s.io/release/v1.34.3/bin/linux/amd64/kubelet
    checksum: sha256:def456...
    destination: /usr/local/bin/kubelet
    mode: "0755"

  # Files
  - name: offline-repo-playbook
    type: file
    source: playbooks/offline-repo.yml
    destination: /opt/opencenter/playbook/offline-repo.yml
    mode: "0644"

  # Repositories
  - name: kubespray
    type: repository
    url: https://github.com/kubernetes-sigs/kubespray.git
    ref: v2.24.0
    destination: /opt/opencenter/kubespray

  - name: kubespray-offline
    type: repository
    url: https://github.com/kubespray-offline/kubespray-offline.git
    ref: main
    destination: /opt/opencenter/kubespray-offline
```

## Schema Validation

Validate manifest before build:

```bash
opencenter-build build --config components.yaml --validate-only
```

Or use JSON Schema validator:

```bash
jsonschema -i components.yaml config/schemas/components.schema.json
```

## Common Errors

**Error**: `Component name 'My-Component' is invalid`
**Fix**: Use lowercase: `my-component`

**Error**: `Image 'nginx:latest' uses mutable tag`
**Fix**: Pin version: `nginx:1.25.0` or use digest

**Error**: `Checksum format invalid: abc123`
**Fix**: Prefix with algorithm: `sha256:abc123...`

**Error**: `Duplicate component name: kubectl`
**Fix**: Component names must be unique. Use `kubectl-v1` and `kubectl-v2` if you need multiple versions.

**Error**: `URL must be HTTPS: http://example.com/file`
**Fix**: Use HTTPS or add to allowed HTTP hosts in config

## See Also

- [CLI Commands](cli-commands.md)
- [Build Steps](build-steps.md)
- [Component Independence](component-independence.md)
