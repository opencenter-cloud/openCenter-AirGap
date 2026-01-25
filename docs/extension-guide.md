# openCenter AirGap Extension Guide

**doc_type**: how-to

**Purpose**: Instructions for extending the openCenter AirGap package with additional services and updating component versions.

**Audience**: Platform engineers maintaining and customizing the air-gap package.

## Adding New Services

### Overview

To add a new service to the deployment:
1. Add container images to the collection
2. Create Kubernetes manifests
3. Rebuild the package
4. Deploy and verify

### Step 1: Add Container Images

Edit `build/kubespray-offline/imagelists/additional_images.txt`:

```bash
cd opencenter-airgap
vim build/kubespray-offline/imagelists/additional_images.txt
```

Add your service images with pinned tags:

```
# Example: Adding PostgreSQL
docker.io/library/postgres:16.1-alpine

# Example: Adding Redis
docker.io/library/redis:7.2.3-alpine

# Example: Adding custom application
myregistry.io/myapp/backend:v2.1.0
myregistry.io/myapp/frontend:v2.1.0
```

**Important**:
- Always use specific version tags, never `latest`
- Include full registry path
- One image per line
- Group related images with comments

### Step 2: Create Kubernetes Manifests

Create manifest directory:

```bash
mkdir -p assets/manifests/myservice
```

Create deployment manifest `assets/manifests/myservice/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myservice
  namespace: myservice
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myservice
  template:
    metadata:
      labels:
        app: myservice
    spec:
      containers:
      - name: myservice
        image: myregistry.io/myapp/backend:v2.1.0
        ports:
        - containerPort: 8080
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: myservice-db
              key: url
```

Create service manifest `assets/manifests/myservice/service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: myservice
  namespace: myservice
spec:
  selector:
    app: myservice
  ports:
  - port: 80
    targetPort: 8080
  type: ClusterIP
```

Create namespace manifest `assets/manifests/myservice/namespace.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: myservice
```

Create kustomization `assets/manifests/myservice/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - deployment.yaml
  - service.yaml
```

### Step 3: Add to GitOps Repository

If using FluxCD, add to the Gitea repository structure:

Create `assets/gitea-repo/platform/myservice/kustomization.yaml`:

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: myservice
  namespace: flux-system
spec:
  interval: 10m
  sourceRef:
    kind: GitRepository
    name: cluster-config
  path: ./platform/myservice
  prune: true
  wait: true
```

### Step 4: Rebuild Package

Run the build process:

```bash
# Activate Python environment
source venv/bin/activate

# Run build script
./scripts/build/build.sh
```

This will:
- Download new images
- Include new manifests
- Generate updated SBOM
- Create new package

### Step 5: Verify New Package

Check package contents:

```bash
# List images
zarf package inspect dist/zarf-package-*.tar.zst --list-images | grep myservice

# Check SBOM
zarf package inspect dist/zarf-package-*.tar.zst --sbom | grep myservice
```

### Step 6: Deploy and Test

Deploy the updated package:

```bash
# Transfer to bastion
# Deploy package
zarf package deploy zarf-package-*.tar.zst --confirm

# Verify service deployed
kubectl get pods -n myservice
kubectl get svc -n myservice
```

## Updating Component Versions

### Updating Runtime Versions

Edit `build/kubespray-offline/target-scripts/config.sh`:

```bash
# Update versions
RUNC_VERSION=1.3.5          # Was 1.3.4
CONTAINERD_VERSION=2.1.6    # Was 2.1.5
NERDCTL_VERSION=2.1.7       # Was 2.1.6
CNI_VERSION=1.8.1           # Was 1.8.0
```

**Important**: Verify these versions are compatible with your Kubernetes version and exist in kubespray's checksums file.

### Updating Kubernetes Version

Edit `build/kubespray-offline/target-scripts/config.sh`:

```bash
# Update Kubespray version (uses master branch by default)
KUBESPRAY_VERSION=master

# Or pin to specific release
KUBESPRAY_VERSION=v2.24.0
```

The Kubernetes version is determined by Kubespray's defaults. To override:

Edit `build/kubespray-offline/kubespray/inventory/sample/group_vars/k8s_cluster/k8s-cluster.yml`:

```yaml
kube_version: v1.30.1  # Update from v1.30.0
```

### Updating Service Container Versions

Edit `build/kubespray-offline/imagelists/additional_images.txt`:

```bash
# Update FluxCD
ghcr.io/fluxcd/source-controller:v1.4.2        # Was v1.4.1
ghcr.io/fluxcd/kustomize-controller:v1.4.1     # Was v1.4.0

# Update Prometheus
quay.io/prometheus/prometheus:v2.49.0          # Was v2.48.0
```

### Updating System Packages

System packages are managed by kubespray-offline's DEB repository creation. To update:

1. Update package versions in kubespray configuration
2. Re-run `download-all.sh` to fetch new packages
3. Rebuild package

### Version Compatibility Matrix

Maintain a compatibility matrix in `config/versions.env`:

```bash
# Kubernetes and Runtime
KUBERNETES_VERSION=v1.30.0
CONTAINERD_VERSION=2.1.5
RUNC_VERSION=1.3.4
CNI_VERSION=1.8.0

# Core Services
FLUXCD_VERSION=v2.2.0
GITEA_VERSION=1.21.0
CERT_MANAGER_VERSION=v1.13.0
INGRESS_NGINX_VERSION=v1.9.0

# Monitoring
PROMETHEUS_VERSION=v2.48.0
GRAFANA_VERSION=10.2.0
```

## Rebuilding Package

### Full Rebuild

Complete rebuild from scratch:

```bash
# Clean previous build
rm -rf build/kubespray-offline/outputs/
rm -rf assets/
rm -rf dist/

# Run build
source venv/bin/activate
./scripts/build/build.sh
```

### Incremental Rebuild

If only manifests changed (no new images):

```bash
# Skip asset collection
# Manually organize assets
./scripts/build/organize_assets_for_zarf.sh

# Create package
./scripts/build/generate_zarf_yaml.py
zarf package create --confirm

# Generate checksums
./scripts/build/checksum_utils.py dist/zarf-package-*.tar.zst
```

### Verify Rebuild

After rebuilding:

```bash
# Check package size
du -h dist/zarf-package-*.tar.zst

# Verify SBOM completeness
python scripts/build/verify_sbom.py dist/zarf-package-*.tar.zst

# Verify checksums
sha256sum -c dist/zarf-package-*.tar.zst.sha256

# List all images
zarf package inspect dist/zarf-package-*.tar.zst --list-images
```

## Advanced Customization

### Custom Kubespray Configuration

Override Kubespray defaults by editing files in `build/kubespray-offline/kubespray/`:

```bash
# Example: Change CNI to Cilium
vim build/kubespray-offline/kubespray/inventory/sample/group_vars/k8s_cluster/k8s-cluster.yml

# Change:
kube_network_plugin: calico
# To:
kube_network_plugin: cilium
```

Remember to add Cilium images to `additional_images.txt`.

### Custom Terraform Modules

For OpenStack deployments, customize Terraform:

```bash
# Edit Terraform configuration
vim assets/terraform/main.tf

# Add custom resources
# Example: Additional security groups, networks, etc.
```

### Custom Ansible Playbooks

Add custom playbooks to run during deployment:

```bash
# Create custom playbook
vim assets/playbooks/custom-setup.yml

# Add to Zarf actions in zarf.yaml
```

### Custom Registry Configuration

Change registry port or configuration:

Edit `build/kubespray-offline/target-scripts/config.sh`:

```bash
# Change registry port
REGISTRY_PORT=5000  # Default is 35000

# Add custom registry configuration
REGISTRY_HTTP_SECRET="my-secret-key"
```

## Testing Extensions

### Test in Isolated Environment

Before deploying to production:

1. Build package with extensions
2. Deploy to test environment
3. Verify all services start correctly
4. Test service functionality
5. Verify offline operation (no external connections)

### Validation Checklist

- [ ] All new images present in registry
- [ ] All new manifests applied successfully
- [ ] All pods reach Running state
- [ ] Services accessible via ingress
- [ ] No external network connections
- [ ] SBOM includes all new components
- [ ] Package size within limits (<10GB)
- [ ] Deployment idempotent (can re-run)

## Removing Services

To remove a service:

1. Remove images from `additional_images.txt`
2. Remove manifests from `assets/manifests/`
3. Remove from GitOps repository structure
4. Rebuild package

The service will not be deployed in new installations. For existing deployments:

```bash
# Remove from cluster
kubectl delete namespace <service-namespace>

# Remove from FluxCD
kubectl delete kustomization <service-name> -n flux-system
```

## Version Control

Track customizations in version control:

```bash
# Initialize git (if not already)
git init

# Track configuration files
git add build/kubespray-offline/imagelists/additional_images.txt
git add build/kubespray-offline/target-scripts/config.sh
git add assets/manifests/
git add config/versions.env

# Commit changes
git commit -m "Add myservice v2.1.0"

# Tag release
git tag -a v1.1.0 -m "Release 1.1.0 with myservice"
```

## Documentation

Document your extensions:

Create `docs/extensions/myservice.md`:

```markdown
# MyService Extension

## Overview
Brief description of the service.

## Version
- Image: myregistry.io/myapp/backend:v2.1.0
- Added in: openCenter AirGap v1.1.0

## Configuration
Environment variables, secrets, etc.

## Verification
How to verify the service is working.

## Troubleshooting
Common issues and solutions.
```

## Best Practices

1. **Pin All Versions**: Never use `latest` or floating tags
2. **Test Thoroughly**: Test extensions in isolated environment first
3. **Document Changes**: Maintain changelog of customizations
4. **Version Control**: Track all configuration changes
5. **SBOM Review**: Always verify SBOM after rebuild
6. **Size Monitoring**: Keep package size under 10GB
7. **Compatibility**: Verify version compatibility before updating
8. **Backup**: Keep previous working package versions
9. **Incremental**: Add one service at a time
10. **Validate**: Run validation scripts after each change

## Example: Adding Vault

Complete example of adding HashiCorp Vault:

### 1. Add Images

Edit `additional_images.txt`:
```
# HashiCorp Vault
docker.io/hashicorp/vault:1.15.4
```

### 2. Create Manifests

```bash
mkdir -p assets/manifests/vault
```

Create `assets/manifests/vault/statefulset.yaml`, `service.yaml`, `configmap.yaml`, etc.

### 3. Add to GitOps

Create `assets/gitea-repo/platform/vault/kustomization.yaml`

### 4. Rebuild

```bash
./scripts/build/build.sh
```

### 5. Deploy and Verify

```bash
# Deploy package
zarf package deploy zarf-package-*.tar.zst --confirm

# Verify
kubectl get pods -n vault
kubectl exec -n vault vault-0 -- vault status
```

## Support

For questions about extensions:
- Review existing service implementations in `assets/manifests/`
- Check Kubespray documentation for configuration options
- Consult Zarf documentation for packaging features
- Review troubleshooting guide for common issues
