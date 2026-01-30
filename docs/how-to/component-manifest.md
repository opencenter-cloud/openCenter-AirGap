# Component Manifest Guide

**doc_type: how-to**

For platform engineers who need to declare components for air-gap collection.

## Task Summary

Create and maintain `config/components.yaml` to specify tools, repositories, images, charts, and packages for collection.

## Prerequisites

- openCenter AirGap tool installed
- Write access to `config/` directory

## Steps

### 1. Initialize Manifest

```bash
opencenter-airgap init --create-manifest --template baremetal
```

Creates `config/components.yaml` with baremetal defaults.

### 2. Add CLI Tools

```bash
opencenter-airgap add tool helm 3.14.0 \
  https://get.helm.sh/helm-v3.14.0-linux-amd64.tar.gz
```

For tools requiring extraction:

```yaml
tools:
  - name: k9s
    version: "0.32.4"
    url: "https://github.com/derailed/k9s/releases/download/v{{version}}/k9s_Linux_amd64.tar.gz"
    extract: true
    binary: k9s
```

### 3. Add Git Repositories

```bash
opencenter-airgap add repo kubespray \
  --url https://github.com/kubernetes-sigs/kubespray.git \
  --ref master
```

### 4. Configure Image Discovery

Edit `config/components.yaml`:

```yaml
images:
  auto_discover:
    - source: repositories.kubespray
      patterns:
        - "roles/*/defaults/main.yml"
        - "inventory/*/group_vars/*.yml"
```

Scans specified files for image references.

### 5. Add Explicit Images

```bash
opencenter-airgap add image docker.io/grafana/grafana:10.2.0
```

Or edit manifest:

```yaml
images:
  additional:
    - "docker.io/grafana/grafana:10.2.0"
    - "quay.io/prometheus/prometheus:v2.48.0"
```

### 6. Add Helm Charts

```bash
opencenter-airgap add chart cert-manager \
  --version v1.13.0 \
  --repo https://charts.jetstack.io
```

### 7. Validate Manifest

```bash
opencenter-airgap validate --strict
```

Checks:
- YAML syntax
- Required fields
- Version format
- URL format

### 8. Test Discovery

```bash
opencenter-airgap scan --discover-images
```

Outputs discovered images to `config/all-images.txt`.

## Troubleshooting

### "Invalid YAML syntax"

Check indentation. YAML requires consistent spacing (2 spaces recommended).

### "URL not reachable"

```bash
# Validate with upstream check
opencenter-airgap validate --check-upstream
```

Verifies URLs return HTTP 200.

### "No images discovered"

Check patterns match actual file paths:

```bash
# List files in repository
find build/kubespray -name "*.yml" | grep -E "(defaults|group_vars)"
```

Adjust patterns in manifest to match actual paths.

### "Version template not resolved"

Ensure version field exists:

```yaml
tools:
  - name: kubectl
    version: "1.34.3"  # Required for {{version}} template
    url: "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubectl"
```
