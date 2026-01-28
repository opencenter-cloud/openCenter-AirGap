# Zarf Package Improvements

**doc_type**: explanation
**audience**: Platform engineers maintaining the build system
**scope**: Recommendations for dynamic image management and operator tooling

## Current State

The zarf.yaml defines a manual image loading approach in component `k8s-images`:

```yaml
- name: k8s-images
  description: Container images for Kubernetes and core services (optional until collected)
  required: false
  actions:
    onDeploy:
      before:
      - cmd: |
          if [ -d "###ZARF_VAR_INSTALL_PATH###/images" ] && [ "$(ls -A ###ZARF_VAR_INSTALL_PATH###/images 2>/dev/null)" ]; then
            podman run -d -p ###ZARF_VAR_REGISTRY_PORT###:5000 ...
            ###ZARF_VAR_INSTALL_PATH###/target-scripts/load-push-all-images.sh
          fi
```

This bypasses Zarf's native image handling. Images are collected via kubespray-offline, stored as tarballs, and manually loaded into a podman registry.

**Trade-offs**:
- Control: Full visibility into image loading process
- Flexibility: Works with kubespray-offline's existing workflow
- Complexity: Manual registry management, no SBOM integration for images
- Determinism: Image list changes require manual zarf.yaml updates

## Problem: Dynamic Image Lists

Kubernetes deployments vary by:
- CNI plugin (Calico, Cilium, Flannel)
- CSI drivers (Ceph, Longhorn, vSphere)
- Kubespray version (different K8s component versions)
- openCenter platform services (optional components)

Hardcoding 137+ images in zarf.yaml creates maintenance burden and version drift.

## Recommendation 1: Generate images Block Dynamically

### Approach

Create `scripts/build/generate_zarf_images_block.py` that reads `config/all-images.txt` and outputs a YAML fragment:

```python
#!/usr/bin/env python3
"""Generate Zarf images block from config/all-images.txt"""

import sys
from pathlib import Path

def parse_image_list(image_file: Path) -> list[str]:
    """Extract non-comment, non-empty lines from image list."""
    images = []
    with open(image_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                images.append(line)
    return images

def generate_yaml_block(images: list[str]) -> str:
    """Generate YAML images block for zarf.yaml."""
    lines = ["  images:"]
    for img in images:
        lines.append(f"    - {img}")
    return "\n".join(lines)

def main():
    project_root = Path(__file__).parent.parent.parent
    image_file = project_root / "config" / "all-images.txt"

    if not image_file.exists():
        print(f"Error: {image_file} not found", file=sys.stderr)
        sys.exit(1)

    images = parse_image_list(image_file)
    print(generate_yaml_block(images))
    print(f"\n# Total images: {len(images)}", file=sys.stderr)

if __name__ == "__main__":
    main()
```

### Integration

Modify `scripts/build/build_steps.py` to inject the generated block:

```python
def generate_zarf_yaml_with_images(state: BuildState) -> StepResult:
    """Generate zarf.yaml with dynamic images block."""

    # Generate images block
    result = subprocess.run(
        ["python3", "scripts/build/generate_zarf_images_block.py"],
        capture_output=True,
        text=True,
        check=True
    )
    images_block = result.stdout

    # Read template zarf.yaml
    with open("zarf.yaml.template") as f:
        template = f.read()

    # Replace placeholder
    final_yaml = template.replace("###IMAGES_BLOCK###", images_block)

    # Write final zarf.yaml
    with open("zarf.yaml", "w") as f:
        f.write(final_yaml)

    return StepResult(success=True, message=f"Generated zarf.yaml with {len(images_block.splitlines())} images")
```

### Template Structure

Rename `zarf.yaml` to `zarf.yaml.template` and add placeholder:

```yaml
- name: k8s-images
  description: Container images for Kubernetes and core services
  required: true
###IMAGES_BLOCK###
```

### Build Workflow

```bash
# 1. Collect kubespray-offline assets (generates image lists)
python3 scripts/build/build.py --from-step clone_kubespray_offline

# 2. Extract openCenter images from gitops-base
python3 scripts/build/build.py --from-step collect_opencenter_assets

# 3. Merge into config/all-images.txt
python3 scripts/build/build.py --from-step generate_image_lists

# 4. Generate zarf.yaml with images block
python3 scripts/build/build.py --from-step generate_zarf_yaml

# 5. Create package (Zarf pulls images during this step)
zarf package create --confirm
```

### Benefits

- **Single source of truth**: `config/all-images.txt` drives both kubespray-offline and Zarf
- **Version tracking**: Git diff shows exactly which images changed
- **SBOM integration**: Zarf automatically includes images in SBOM
- **Determinism**: Same input files produce identical packages

### Migration Path

Keep manual approach as fallback:

```yaml
- name: k8s-images-manual
  description: Manual image loading (fallback if Zarf native fails)
  required: false
  actions:
    onDeploy:
      before:
      - cmd: |
          # Existing manual loading script
```

Test native Zarf approach first. If issues arise, enable manual component.

## Recommendation 2: Operator Tooling Component

### Problem

Field operators need diagnostic tools not included in base Kubernetes:
- `k9s`: Terminal UI for cluster management
- `helm`: Chart deployment
- `kubectl` plugins: `kubectl-tree`, `kubectl-neat`
- `stern`: Multi-pod log tailing
- `kubectx`/`kubens`: Context switching

These tools improve operator efficiency but aren't deployment dependencies.

### Approach

Add optional `operator-tools` component:

```yaml
- name: operator-tools
  description: Optional CLI tools for cluster operators
  required: false
  files:
  - source: assets/operator-tools/k9s
    target: /usr/local/bin/k9s
    executable: true
  - source: assets/operator-tools/helm
    target: /usr/local/bin/helm
    executable: true
  - source: assets/operator-tools/stern
    target: /usr/local/bin/stern
    executable: true
  - source: assets/operator-tools/kubectx
    target: /usr/local/bin/kubectx
    executable: true
  - source: assets/operator-tools/kubens
    target: /usr/local/bin/kubens
    executable: true
  actions:
    onDeploy:
      after:
      - cmd: |
          echo "Operator tools installed:"
          k9s version
          helm version
          stern --version
```

### Collection Script

Create `scripts/build/collect_operator_tools.sh`:

```bash
#!/bin/bash
set -euo pipefail

# Collect operator tools for air-gap deployment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TOOLS_DIR="${PROJECT_ROOT}/assets/operator-tools"

# Source versions
source "${PROJECT_ROOT}/config/versions.env"

# Tool versions (add to versions.env)
K9S_VERSION="${K9S_VERSION:-v0.32.5}"
HELM_VERSION="${HELM_VERSION:-v3.14.0}"
STERN_VERSION="${STERN_VERSION:-v1.28.0}"
KUBECTX_VERSION="${KUBECTX_VERSION:-v0.9.5}"

ARCH="amd64"

mkdir -p "${TOOLS_DIR}"

download_k9s() {
    local url="https://github.com/derailed/k9s/releases/download/${K9S_VERSION}/k9s_Linux_${ARCH}.tar.gz"
    curl -L "${url}" | tar xz -C "${TOOLS_DIR}" k9s
    chmod +x "${TOOLS_DIR}/k9s"
}

download_helm() {
    local url="https://get.helm.sh/helm-${HELM_VERSION}-linux-${ARCH}.tar.gz"
    curl -L "${url}" | tar xz -C "${TOOLS_DIR}" --strip-components=1 linux-${ARCH}/helm
    chmod +x "${TOOLS_DIR}/helm"
}

download_stern() {
    local url="https://github.com/stern/stern/releases/download/${STERN_VERSION}/stern_${STERN_VERSION#v}_linux_${ARCH}.tar.gz"
    curl -L "${url}" | tar xz -C "${TOOLS_DIR}" stern
    chmod +x "${TOOLS_DIR}/stern"
}

download_kubectx() {
    local base_url="https://github.com/ahmetb/kubectx/releases/download/${KUBECTX_VERSION}"
    curl -L "${base_url}/kubectx" -o "${TOOLS_DIR}/kubectx"
    curl -L "${base_url}/kubens" -o "${TOOLS_DIR}/kubens"
    chmod +x "${TOOLS_DIR}/kubectx" "${TOOLS_DIR}/kubens"
}

echo "Downloading operator tools..."
download_k9s
download_helm
download_stern
download_kubectx

echo "Operator tools collected:"
ls -lh "${TOOLS_DIR}"
```

### Version Pinning

Add to `config/versions.env`:

```bash
# Operator Tools
K9S_VERSION="v0.32.5"
HELM_VERSION="v3.14.0"
STERN_VERSION="v1.28.0"
KUBECTX_VERSION="v0.9.5"
```

### Build Integration

Add step to `scripts/build/build_steps.py`:

```python
BuildStep(
    name="collect_operator_tools",
    description="Download operator CLI tools",
    function=run_bash_worker,
    args={"script": "scripts/build/collect_operator_tools.sh"},
    dependencies=["validate_versions"],
    checkpoint=True
)
```

### Deployment

Operators choose whether to install:

```bash
# Deploy with operator tools
zarf package deploy zarf-package-*.tar.zst \
  --components=bootstrap-tools,kubespray-core,k8s-images,operator-tools,deploy-cluster

# Deploy without (minimal footprint)
zarf package deploy zarf-package-*.tar.zst \
  --components=bootstrap-tools,kubespray-core,k8s-images,deploy-cluster
```

## Recommendation 3: Additional Terraform Binaries

### Problem

OpenStack deployments may need additional Terraform providers:
- `terraform-provider-local`: Local file management
- `terraform-provider-null`: Provisioner execution
- `terraform-provider-random`: Random resource generation
- `terraform-provider-tls`: Certificate generation

These aren't always in the base mirror.

### Approach

Extend `scripts/build/mirror_terraform_providers.sh`:

```bash
#!/bin/bash
set -euo pipefail

# Mirror Terraform providers for offline use

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
MIRROR_DIR="${PROJECT_ROOT}/assets/terraform-mirror"

# Source versions
source "${PROJECT_ROOT}/config/versions.env"

# Provider versions (add to versions.env)
OPENSTACK_PROVIDER_VERSION="${OPENSTACK_PROVIDER_VERSION:-1.54.1}"
LOCAL_PROVIDER_VERSION="${LOCAL_PROVIDER_VERSION:-2.4.1}"
NULL_PROVIDER_VERSION="${NULL_PROVIDER_VERSION:-3.2.2}"
RANDOM_PROVIDER_VERSION="${RANDOM_PROVIDER_VERSION:-3.6.0}"
TLS_PROVIDER_VERSION="${TLS_PROVIDER_VERSION:-4.0.5}"

# Create temporary Terraform config
cat > /tmp/terraform-mirror.tf <<EOF
terraform {
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "${OPENSTACK_PROVIDER_VERSION}"
    }
    local = {
      source  = "hashicorp/local"
      version = "${LOCAL_PROVIDER_VERSION}"
    }
    null = {
      source  = "hashicorp/null"
      version = "${NULL_PROVIDER_VERSION}"
    }
    random = {
      source  = "hashicorp/random"
      version = "${RANDOM_PROVIDER_VERSION}"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "${TLS_PROVIDER_VERSION}"
    }
  }
}
EOF

# Mirror providers
terraform -chdir=/tmp providers mirror \
  -platform=linux_amd64 \
  "${MIRROR_DIR}"

# Generate lock file
terraform -chdir=/tmp providers lock \
  -platform=linux_amd64

# Copy lock file to assets
cp /tmp/.terraform.lock.hcl "${PROJECT_ROOT}/assets/terraform/.terraform.lock.hcl"

echo "Terraform providers mirrored to: ${MIRROR_DIR}"
ls -lh "${MIRROR_DIR}"
```

### Version Pinning

Add to `config/versions.env`:

```bash
# Terraform Providers
TERRAFORM_VERSION="1.6.6"
OPENSTACK_PROVIDER_VERSION="1.54.1"
LOCAL_PROVIDER_VERSION="2.4.1"
NULL_PROVIDER_VERSION="3.2.2"
RANDOM_PROVIDER_VERSION="3.6.0"
TLS_PROVIDER_VERSION="4.0.5"
```

### Verification

Add validation step:

```python
def verify_terraform_mirror(state: BuildState) -> StepResult:
    """Verify all required Terraform providers are mirrored."""

    mirror_dir = Path("assets/terraform-mirror")
    required_providers = [
        "terraform-provider-openstack/openstack",
        "hashicorp/local",
        "hashicorp/null",
        "hashicorp/random",
        "hashicorp/tls"
    ]

    missing = []
    for provider in required_providers:
        provider_path = mirror_dir / provider
        if not provider_path.exists():
            missing.append(provider)

    if missing:
        return StepResult(
            success=False,
            message=f"Missing providers: {', '.join(missing)}"
        )

    return StepResult(
        success=True,
        message=f"Verified {len(required_providers)} Terraform providers"
    )
```

## Implementation Priority

1. **Dynamic images block** (high impact, low risk)
   - Reduces maintenance burden immediately
   - Improves SBOM accuracy
   - Enables version tracking via git diff

2. **Operator tools component** (medium impact, low risk)
   - Optional component, no deployment risk
   - Improves operator experience
   - Small package size increase (~50MB)

3. **Extended Terraform providers** (low impact, medium risk)
   - Only affects OpenStack deployments
   - Increases package size (~100MB)
   - Test thoroughly with Terraform init offline

## Testing Strategy

### Dynamic Images

```bash
# 1. Generate image list
python3 scripts/build/generate_complete_image_lists.sh

# 2. Generate zarf.yaml
python3 scripts/build/generate_zarf_yaml.py

# 3. Validate YAML syntax
yq eval . zarf.yaml > /dev/null

# 4. Create package
zarf package create --confirm

# 5. Inspect SBOM
zarf package inspect dist/zarf-package-*.tar.zst --sbom | grep "Total images"

# 6. Deploy and verify
zarf package deploy dist/zarf-package-*.tar.zst --confirm
kubectl get pods -A  # All images should pull successfully
```

### Operator Tools

```bash
# 1. Deploy with tools
zarf package deploy --components=operator-tools

# 2. Verify installation
k9s version
helm version
stern --version

# 3. Test functionality
k9s  # Should launch TUI
helm list -A  # Should work without internet
```

### Terraform Providers

```bash
# 1. Deploy package
zarf package deploy dist/zarf-package-*.tar.zst

# 2. Test offline init
cd /opt/opencenter/terraform
terraform init  # Should use filesystem mirror

# 3. Verify providers
terraform providers
# Should show all 5 providers with correct versions
```

## Migration Checklist

- [ ] Backup current zarf.yaml
- [ ] Create zarf.yaml.template with placeholder
- [ ] Implement generate_zarf_images_block.py
- [ ] Update build_steps.py with generation step
- [ ] Test image block generation
- [ ] Verify package creation succeeds
- [ ] Deploy test package and verify image pulls
- [ ] Update documentation
- [ ] Add operator-tools component (optional)
- [ ] Extend Terraform provider mirror (optional)
- [ ] Update versions.env with new tool versions
- [ ] Run full integration test
