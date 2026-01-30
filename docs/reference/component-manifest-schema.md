# Component Manifest Schema

**doc_type: reference**

Complete schema reference for `config/components.yaml`.

## Root Structure

```yaml
kubernetes: KubernetesSpec
tools: list[ToolSpec]
repositories: list[RepositorySpec]
images: ImageSpec
charts: list[ChartSpec]
os_packages: OSPackageSpec
python_packages: PythonPackageSpec
terraform_providers: list[TerraformProviderSpec]
```

## KubernetesSpec

```yaml
kubernetes:
  version: string  # Kubernetes version (e.g., "1.34.3")
  binaries: list[BinarySpec]
```

### BinarySpec

```yaml
- name: string      # Binary name (e.g., "kubectl")
  url: string       # Download URL (supports {{version}} template)
```

**Example**:
```yaml
kubernetes:
  version: "1.34.3"
  binaries:
    - name: kubectl
      url: "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubectl"
    - name: kubelet
      url: "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubelet"
```

## ToolSpec

```yaml
- name: string           # Tool name
  version: string        # Tool version
  url: string            # Download URL (supports {{version}} template)
  extract: bool          # Extract archive (default: false)
  binary: string         # Path to binary in archive (if extract: true)
  checksum_url: string   # Optional checksum URL
```

**Example**:
```yaml
tools:
  - name: helm
    version: "3.14.0"
    url: "https://get.helm.sh/helm-v{{version}}-linux-amd64.tar.gz"
    extract: true
    binary: linux-amd64/helm

  - name: k9s
    version: "0.32.4"
    url: "https://github.com/derailed/k9s/releases/download/v{{version}}/k9s_Linux_amd64.tar.gz"
    extract: true
    binary: k9s
```

## RepositorySpec

```yaml
- name: string    # Repository name
  url: string     # Git URL
  ref: string     # Git ref (branch, tag, or commit SHA)
  type: string    # Repository type (default: "git")
```

**Example**:
```yaml
repositories:
  - name: kubespray
    url: "https://github.com/kubernetes-sigs/kubespray.git"
    ref: "master"

  - name: opencenter-gitops-base
    url: "https://github.com/rackerlabs/opencenter-gitops-base.git"
    ref: "v1.0.0"
```

## ImageSpec

```yaml
images:
  auto_discover: list[ImageDiscoverySpec]
  additional: list[string]
```

### ImageDiscoverySpec

```yaml
- source: string         # Repository reference (e.g., "repositories.kubespray")
  patterns: list[string] # File patterns to scan
```

**Example**:
```yaml
images:
  auto_discover:
    - source: repositories.kubespray
      patterns:
        - "roles/*/defaults/main.yml"
        - "inventory/*/group_vars/*.yml"

    - source: repositories.opencenter-gitops-base
      patterns:
        - "**/*.yaml"

  additional:
    - "docker.io/grafana/grafana:10.2.0"
    - "quay.io/prometheus/prometheus:v2.48.0"
    - "registry.k8s.io/kube-apiserver:v1.34.3"
```

## ChartSpec

```yaml
- name: string      # Chart name
  repo: string      # Helm repository URL
  version: string   # Chart version
```

**Example**:
```yaml
charts:
  - name: cert-manager
    repo: "https://charts.jetstack.io"
    version: "v1.13.0"

  - name: ingress-nginx
    repo: "https://kubernetes.github.io/ingress-nginx"
    version: "4.8.3"
```

## OSPackageSpec

```yaml
os_packages:
  ubuntu_24_04: bool  # Collect Ubuntu 24.04 packages (default: true)
```

**Example**:
```yaml
os_packages:
  ubuntu_24_04: true
```

**Note**: OS packages are collected by kubespray-offline. This setting enables/disables collection.

## PythonPackageSpec

```yaml
python_packages:
  requirements_file: string  # Path to requirements.txt
```

**Example**:
```yaml
python_packages:
  requirements_file: "requirements.txt"
```

**Note**: Python packages are collected by kubespray-offline from specified requirements file.

## TerraformProviderSpec

```yaml
- name: string       # Provider name
  version: string    # Provider version
  platform: string   # Platform (e.g., "linux_amd64")
```

**Example**:
```yaml
terraform_providers:
  - name: openstack
    version: "1.54.1"
    platform: "linux_amd64"

  - name: local
    version: "2.4.0"
    platform: "linux_amd64"
```

## Template Variables

Use `{{variable}}` syntax for version interpolation:

```yaml
tools:
  - name: kubectl
    version: "1.34.3"
    url: "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubectl"
```

Resolves to: `https://dl.k8s.io/v1.34.3/bin/linux/amd64/kubectl`

**Supported Variables**:
- `{{version}}`: Component version field

## Validation Rules

### Required Fields

**ToolSpec**:
- `name` (string, non-empty)
- `version` (string, non-empty)
- `url` (string, valid URL)

**RepositorySpec**:
- `name` (string, non-empty)
- `url` (string, valid Git URL)
- `ref` (string, non-empty)

**ChartSpec**:
- `name` (string, non-empty)
- `repo` (string, valid URL)
- `version` (string, non-empty)

### Format Rules

**Version Strings**:
- Semantic versioning recommended (e.g., "1.2.3")
- Prefix "v" optional (e.g., "v1.2.3" or "1.2.3")

**URLs**:
- Must start with `http://` or `https://`
- Git URLs may use `git://` or `ssh://`

**Git Refs**:
- Branch names (e.g., "master", "main")
- Tags (e.g., "v1.0.0")
- Commit SHAs (e.g., "a1b2c3d4...")

**Image References**:
- Format: `[registry/]repository:tag`
- Registry optional (defaults to docker.io)
- Tag required

## Complete Example

```yaml
kubernetes:
  version: "1.34.3"
  binaries:
    - name: kubectl
      url: "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubectl"
    - name: kubelet
      url: "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubelet"
    - name: kubeadm
      url: "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubeadm"

tools:
  - name: helm
    version: "3.14.0"
    url: "https://get.helm.sh/helm-v{{version}}-linux-amd64.tar.gz"
    extract: true
    binary: linux-amd64/helm

  - name: k9s
    version: "0.32.4"
    url: "https://github.com/derailed/k9s/releases/download/v{{version}}/k9s_Linux_amd64.tar.gz"
    extract: true
    binary: k9s

repositories:
  - name: kubespray
    url: "https://github.com/kubernetes-sigs/kubespray.git"
    ref: "master"

  - name: opencenter-gitops-base
    url: "https://github.com/rackerlabs/opencenter-gitops-base.git"
    ref: "v1.0.0"

images:
  auto_discover:
    - source: repositories.kubespray
      patterns:
        - "roles/*/defaults/main.yml"
        - "inventory/*/group_vars/*.yml"

  additional:
    - "docker.io/grafana/grafana:10.2.0"
    - "quay.io/prometheus/prometheus:v2.48.0"

charts:
  - name: cert-manager
    repo: "https://charts.jetstack.io"
    version: "v1.13.0"

  - name: ingress-nginx
    repo: "https://kubernetes.github.io/ingress-nginx"
    version: "4.8.3"

os_packages:
  ubuntu_24_04: true

python_packages:
  requirements_file: "requirements.txt"

terraform_providers:
  - name: openstack
    version: "1.54.1"
    platform: "linux_amd64"
```
