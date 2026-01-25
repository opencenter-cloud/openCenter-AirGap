# FluxCD Idempotency

doc_type: reference

This document describes the idempotency behavior of FluxCD installation and operations in openCenter AirGap.

## Purpose

FluxCD is designed to be declarative and idempotent. This document describes how FluxCD maintains idempotency and how the openCenter AirGap installation script leverages this behavior.

## FluxCD Idempotency Principles

### Declarative Configuration

FluxCD uses Kubernetes custom resources to declare desired state:
- **GitRepository**: Declares Git repository source
- **Kustomization**: Declares how to apply manifests
- **HelmRelease**: Declares Helm chart deployments

### Reconciliation Loop

FluxCD controllers continuously reconcile actual state with desired state:
1. **Read desired state** from Git repository
2. **Compare with actual state** in cluster
3. **Apply changes** if state differs
4. **Report status** via resource conditions
5. **Repeat** at configured interval

### Idempotent Operations

All FluxCD operations are idempotent:
- **flux install**: Can be run multiple times, updates existing installation
- **kubectl apply**: Kubernetes resources are declarative and idempotent
- **Reconciliation**: Controllers only make changes when needed

## install_fluxcd.sh Idempotency

The `install_fluxcd.sh` script includes comprehensive idempotency checks:

### 1. Existing Installation Detection

```bash
# Check if FluxCD namespace exists
if kubectl get namespace "${FLUX_NAMESPACE}" &> /dev/null; then
    FLUX_INSTALLED=true
    
    # Check if controllers are running
    CONTROLLER_COUNT=$(kubectl get deployments -n "${FLUX_NAMESPACE}" | wc -l)
    
    if [ "$CONTROLLER_COUNT" -gt 0 ]; then
        log_info "FluxCD controllers found: ${CONTROLLER_COUNT}"
    fi
fi
```

**Behavior**:
- Checks for flux-system namespace
- Counts existing controllers
- Determines if installation or update is needed

### 2. Conditional Installation vs Update

```bash
if [ "$FLUX_INSTALLED" = "true" ]; then
    log_info "Updating existing FluxCD installation"
    flux install --namespace="${FLUX_NAMESPACE}"
else
    log_info "Installing FluxCD"
    flux install --namespace="${FLUX_NAMESPACE}"
fi
```

**Behavior**:
- If installed: Updates to ensure desired state
- If not installed: Performs fresh installation
- `flux install` is idempotent in both cases

### 3. Controller Health Check

```bash
# Check controller health
NOT_READY=$(kubectl get deployments -n "${FLUX_NAMESPACE}" | \
    awk '$2 !~ /^[0-9]+\/\1$/ {print $1}' | wc -l)

if [ "$NOT_READY" -eq 0 ]; then
    log_info "✓ All controllers are ready"
fi
```

**Behavior**:
- Verifies all controllers are ready
- Reports unhealthy controllers
- Waits for controllers to become ready

### 4. Gitea Integration Idempotency

```bash
# Check if secret already exists
if kubectl get secret -n "${FLUX_NAMESPACE}" gitea-credentials &> /dev/null; then
    log_info "Gitea credentials secret already exists - updating..."
    kubectl delete secret -n "${FLUX_NAMESPACE}" gitea-credentials
fi

kubectl create secret generic gitea-credentials ...
```

**Behavior**:
- Checks for existing secret
- Deletes and recreates if exists (to update credentials)
- Creates new secret if not exists

```bash
# Create GitRepository resource (idempotent)
cat <<EOF | kubectl apply -f -
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
...
EOF
```

**Behavior**:
- Uses `kubectl apply` (idempotent)
- Creates resource if not exists
- Updates resource if exists

## Re-run Scenarios

### Scenario 1: Fresh Installation

**State**: FluxCD not installed

**Behavior**:
1. Detects no existing installation
2. Runs `flux install`
3. Creates flux-system namespace
4. Deploys all controllers
5. Waits for controllers to be ready

**Result**: FluxCD installed successfully

### Scenario 2: Re-run After Success

**State**: FluxCD already installed and healthy

**Behavior**:
1. Detects existing installation
2. Runs `flux install` (idempotent update)
3. Controllers already at desired state
4. No changes made
5. Verification passes

**Result**: No changes, existing installation verified

### Scenario 3: Update to New Version

**State**: FluxCD v2.2.0 installed, script specifies v2.3.0

**Behavior**:
1. Detects existing installation
2. Runs `flux install --version=v2.3.0`
3. Updates controller images to v2.3.0
4. Controllers restart with new version
5. Waits for controllers to be ready

**Result**: FluxCD updated to v2.3.0

### Scenario 4: Recover from Partial Failure

**State**: FluxCD partially installed (some controllers missing)

**Behavior**:
1. Detects existing namespace
2. Detects missing controllers
3. Runs `flux install`
4. Creates missing controllers
5. Existing controllers unchanged

**Result**: FluxCD installation completed

### Scenario 5: Gitea Integration Re-run

**State**: FluxCD installed, Gitea integration already configured

**Behavior**:
1. Detects existing gitea-credentials secret
2. Deletes and recreates secret (to update password)
3. Applies GitRepository resource (idempotent)
4. GitRepository controller reconciles
5. No changes if configuration unchanged

**Result**: Gitea integration verified and updated

## flux CLI Idempotency

The `flux` CLI provides idempotent commands:

### flux install

```bash
# First run - installs FluxCD
flux install

# Second run - updates to ensure desired state
flux install

# With version - updates to specific version
flux install --version=v2.3.0
```

**Behavior**:
- Creates namespace if not exists
- Creates/updates CRDs
- Creates/updates controllers
- Idempotent - safe to run multiple times

### flux check

```bash
# Verify FluxCD installation
flux check
```

**Behavior**:
- Checks prerequisites (kubectl, cluster access)
- Checks FluxCD installation
- Checks controller health
- Idempotent - read-only operation

### flux reconcile

```bash
# Force reconciliation of GitRepository
flux reconcile source git cluster-config

# Force reconciliation of Kustomization
flux reconcile kustomization infrastructure
```

**Behavior**:
- Triggers immediate reconciliation
- Idempotent - can be run multiple times
- Useful for forcing updates without waiting for interval

## FluxCD Resource Idempotency

### GitRepository

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: cluster-config
  namespace: flux-system
spec:
  interval: 1m
  url: http://gitea.gitea.svc.cluster.local:3000/gitea/cluster-config
  ref:
    branch: main
```

**Idempotency**:
- `kubectl apply` is idempotent
- Re-applying same resource: No changes
- Changing spec: Controller reconciles to new state
- Deleting and recreating: Controller re-clones repository

### Kustomization

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: infrastructure
  namespace: flux-system
spec:
  interval: 10m
  sourceRef:
    kind: GitRepository
    name: cluster-config
  path: ./infrastructure
  prune: true
```

**Idempotency**:
- `kubectl apply` is idempotent
- Re-applying same resource: No changes
- Controller reconciles at interval
- Prune: Removes resources not in Git (declarative)

### HelmRelease

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: cert-manager
  namespace: flux-system
spec:
  interval: 10m
  chart:
    spec:
      chart: cert-manager
      version: v1.13.0
      sourceRef:
        kind: HelmRepository
        name: jetstack
```

**Idempotency**:
- `kubectl apply` is idempotent
- Re-applying same resource: No changes
- Controller reconciles Helm release
- Helm upgrades are idempotent

## Testing Idempotency

### Test 1: Re-run Installation Script

```bash
# First run
./scripts/deploy/install_fluxcd.sh

# Second run (should update, not fail)
./scripts/deploy/install_fluxcd.sh

# Expected output:
# "FluxCD is already installed - will update to ensure desired state"
# "✓ FluxCD updated successfully"
```

### Test 2: Verify No Changes

```bash
# Capture state before
kubectl get deployments -n flux-system -o yaml > before.yaml

# Re-run installation
./scripts/deploy/install_fluxcd.sh

# Capture state after
kubectl get deployments -n flux-system -o yaml > after.yaml

# Compare (should be identical except timestamps)
diff <(yq eval 'del(.items[].metadata.managedFields, .items[].metadata.resourceVersion, .items[].metadata.generation)' before.yaml) \
     <(yq eval 'del(.items[].metadata.managedFields, .items[].metadata.resourceVersion, .items[].metadata.generation)' after.yaml)

# Expected: No differences
```

### Test 3: Update Version

```bash
# Install v2.2.0
./scripts/deploy/install_fluxcd.sh --flux-version v2.2.0

# Verify version
flux version

# Update to v2.3.0
./scripts/deploy/install_fluxcd.sh --flux-version v2.3.0

# Verify version updated
flux version

# Expected: Version changed from v2.2.0 to v2.3.0
```

### Test 4: Gitea Integration Re-run

```bash
# First run with Gitea
./scripts/deploy/install_fluxcd.sh \
    --gitea-url http://gitea.gitea.svc.cluster.local:3000 \
    --gitea-username gitea \
    --gitea-password password1

# Second run with same credentials
./scripts/deploy/install_fluxcd.sh \
    --gitea-url http://gitea.gitea.svc.cluster.local:3000 \
    --gitea-username gitea \
    --gitea-password password1

# Expected: Secret recreated, GitRepository unchanged

# Third run with new password
./scripts/deploy/install_fluxcd.sh \
    --gitea-url http://gitea.gitea.svc.cluster.local:3000 \
    --gitea-username gitea \
    --gitea-password password2

# Expected: Secret updated with new password
```

## Best Practices

### 1. Use flux install for Updates

```bash
# Always use flux install, not manual kubectl apply
flux install --version=v2.3.0

# Not recommended:
# kubectl apply -f https://github.com/fluxcd/flux2/releases/download/v2.3.0/install.yaml
```

**Reason**: `flux install` handles version compatibility and migration

### 2. Verify After Installation

```bash
# Always verify after installation or update
flux check

# Check controller status
kubectl get deployments -n flux-system

# Check controller logs if issues
kubectl logs -n flux-system deployment/source-controller
```

### 3. Use Declarative Resources

```bash
# Use kubectl apply (idempotent)
kubectl apply -f gitrepository.yaml

# Not kubectl create (fails if exists)
# kubectl create -f gitrepository.yaml
```

### 4. Monitor Reconciliation

```bash
# Watch reconciliation status
flux get all

# Force reconciliation if needed
flux reconcile source git cluster-config
```

### 5. Handle Secrets Carefully

```bash
# Secrets are not idempotent by default
# Always check and delete before recreating

if kubectl get secret gitea-credentials -n flux-system; then
    kubectl delete secret gitea-credentials -n flux-system
fi

kubectl create secret generic gitea-credentials ...
```

## Comparison with Other Components

| Component | Idempotency | Re-run Safety | Notes |
|:----------|:------------|:--------------|:------|
| FluxCD | ✓ Built-in | ✓ Always safe | flux install is idempotent |
| Kubespray | ✓ Built-in | ✓ Always safe | Ansible idempotency |
| Terraform | ✓ Built-in | ✓ Always safe | State-based idempotency |
| kubespray-offline | ⚠️ Partial | ⚠️ Some scripts fail | Registry script not idempotent |

## Related Requirements

- **Requirement 8.6**: FluxCD installation is idempotent (update if exists, install if not)

## Summary

FluxCD provides robust idempotency through:

1. **Declarative resources**: All configuration is declarative
2. **Reconciliation loops**: Controllers continuously ensure desired state
3. **flux install idempotency**: Can be run multiple times safely
4. **kubectl apply idempotency**: Kubernetes resources are idempotent
5. **Status reporting**: Clear status conditions for all resources

The `install_fluxcd.sh` script enhances this with:
- Existing installation detection
- Conditional install vs update
- Controller health verification
- Gitea integration idempotency
- Comprehensive error handling

This ensures FluxCD can be safely installed, updated, or verified at any time without causing errors or unwanted changes.
