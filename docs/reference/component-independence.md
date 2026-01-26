# Component Independence Reference

**doc_type:** reference

This document provides reference information about Zarf component independence in the openCenter AirGap package.

## Component Dependency Matrix

| Component | Required | Dependencies | Can Deploy Independently |
|:----------|:---------|:-------------|:------------------------|
| bootstrap-tools | Yes | None | Yes |
| terraform-providers | No | None | Yes |
| kubespray-core | Yes | bootstrap-tools (logical) | Yes (files only) |
| k8s-images | No | None | Yes |
| deploy-cluster | Yes | bootstrap-tools, kubespray-core | No |

## Component Definitions

### bootstrap-tools

**Purpose:** Python environment and deployment scripts

**Provides:**
- Python virtual environment at `###ZARF_VAR_INSTALL_PATH###/venv`
- Python dependencies (ansible, jinja2, netaddr)
- Target scripts for bastion setup

**Dependencies:** None

**Independence:** Fully independent. Can deploy alone.

**Deploy Command:**
```bash
zarf package deploy <package> --components=bootstrap-tools --confirm
```

### terraform-providers

**Purpose:** Terraform provider filesystem mirror for OpenStack deployments

**Provides:**
- Terraform provider mirror at `###ZARF_VAR_INSTALL_PATH###/terraform-mirror`
- Terraform configuration at `/root/.terraformrc`

**Dependencies:** None

**Independence:** Fully independent. Can deploy alone or skip entirely for bare-metal deployments.

**Deploy Command:**
```bash
zarf package deploy <package> --components=terraform-providers --confirm
```

### kubespray-core

**Purpose:** Kubespray playbooks, K8s binaries, and package repositories

**Provides:**
- Kubespray playbooks at `###ZARF_VAR_INSTALL_PATH###/kubespray`
- K8s binaries at `###ZARF_VAR_INSTALL_PATH###/k8s-binaries`
- Package repositories at `###ZARF_VAR_INSTALL_PATH###/repos`
- Offline playbook at `###ZARF_VAR_INSTALL_PATH###/playbook`

**Dependencies:** 
- Logical dependency on bootstrap-tools (Python venv used later by Kubespray)
- No runtime dependency during deployment (only copies files)

**Independence:** Can deploy independently. Files are copied without executing Python.

**Deploy Command:**
```bash
zarf package deploy <package> --components=kubespray-core --confirm
```

### k8s-images

**Purpose:** Container images for Kubernetes and core services

**Provides:**
- Local registry container on port 35000
- All K8s and openCenter service images pushed to registry

**Dependencies:** None (checks for images directory, skips if not present)

**Independence:** Fully independent. Can deploy alone if images are available.

**Deploy Command:**
```bash
zarf package deploy <package> --components=k8s-images --confirm
```

**Note:** This component is optional until images are collected. It gracefully skips if no images directory exists.

### deploy-cluster

**Purpose:** Cluster deployment orchestration

**Provides:**
- Bastion setup (nginx, registry, Python venv)
- Service verification

**Dependencies:**
- Requires bootstrap-tools (needs target-scripts)
- Requires kubespray-core (needs kubespray playbooks)

**Independence:** Cannot deploy independently. Must deploy after bootstrap-tools and kubespray-core.

**Deploy Command:**
```bash
# Must deploy prerequisites first
zarf package deploy <package> --components=bootstrap-tools,kubespray-core,deploy-cluster --confirm
```

## Deployment Scenarios

### Scenario 1: Bare-Metal Deployment

Skip terraform-providers (not needed for bare-metal):

```bash
zarf package deploy <package> --confirm
```

Zarf will prompt to skip optional components or deploy all required components automatically.

### Scenario 2: OpenStack Deployment

Include terraform-providers:

```bash
zarf package deploy <package> --confirm
```

Select terraform-providers when prompted, or deploy all components.

### Scenario 3: Minimal Deployment

Deploy only core components, skip images:

```bash
zarf package deploy <package> --components=bootstrap-tools,kubespray-core,deploy-cluster --confirm
```

Images must be provided separately or already present on bastion.

### Scenario 4: Independent Component Testing

Deploy individual components for testing:

```bash
# Test bootstrap-tools
zarf package deploy <package> --components=bootstrap-tools --confirm

# Test terraform-providers
zarf package deploy <package> --components=terraform-providers --confirm

# Test k8s-images
zarf package deploy <package> --components=k8s-images --confirm
```

## Dependency Management

### Explicit Dependencies

Zarf uses the `required` field to declare mandatory components:

```yaml
components:
  - name: bootstrap-tools
    required: true    # Must deploy

  - name: terraform-providers
    required: false   # Optional, can skip
```

### Implicit Dependencies

Logical dependencies are managed through deployment order:

1. bootstrap-tools (provides scripts and Python venv)
2. terraform-providers (optional, independent)
3. kubespray-core (uses Python venv later, but not during deployment)
4. k8s-images (optional, independent)
5. deploy-cluster (uses scripts from bootstrap-tools and playbooks from kubespray-core)

### Zarf Behavior

- Components deploy in the order defined in zarf.yaml
- Required components must deploy (cannot skip)
- Optional components can be skipped via `--components` flag
- Zarf does not enforce runtime dependencies (relies on deployment order)

## Verification

### Verify Component Definitions

```bash
./scripts/deploy/verify_component_dependencies.sh
```

Output shows:
- Component dependency analysis
- Logical dependency chain
- Independence verification
- Deployment recommendations

### Test Component Independence

```bash
./scripts/deploy/test_component_independence.sh
```

Output shows:
- Component definition validation
- Deployment scenario testing
- Component isolation verification
- Independent deployment commands

### Test with Actual Package

```bash
./scripts/deploy/test_component_independence.sh --package dist/zarf-package-*.tar.zst
```

## Best Practices

### When to Deploy Components Independently

1. **Testing:** Deploy individual components to test functionality
2. **Debugging:** Deploy specific components to isolate issues
3. **Partial Updates:** Deploy only changed components (if package supports it)
4. **Custom Scenarios:** Skip optional components for specific deployment needs

### When to Deploy All Components

1. **Production:** Deploy all required components for complete setup
2. **First Deployment:** Deploy everything to ensure complete environment
3. **Simplicity:** Let Zarf manage deployment order automatically

### Component Design Guidelines

1. **Minimize Dependencies:** Keep components as independent as possible
2. **Use `required` Field:** Clearly mark mandatory vs optional components
3. **Document Dependencies:** Use comments in zarf.yaml to explain logical dependencies
4. **Test Independence:** Verify components can deploy independently when appropriate
5. **Handle Missing Resources:** Optional components should gracefully handle missing dependencies

## Troubleshooting

### Component Deployment Fails

**Symptom:** Component fails to deploy with missing resource error

**Cause:** Component has undeclared dependency on another component

**Solution:** Deploy prerequisite components first, or deploy all required components together

### Optional Component Skipped Unexpectedly

**Symptom:** Optional component not deployed even when specified

**Cause:** Component may have `required: false` and Zarf skipped it

**Solution:** Explicitly specify component with `--components` flag

### Deployment Order Issues

**Symptom:** Later component fails because earlier component not deployed

**Cause:** Logical dependency not satisfied due to deployment order

**Solution:** Deploy components in correct order (bootstrap-tools → kubespray-core → deploy-cluster)

## Related Documentation

- [Zarf Package Configuration](../reference/zarf-variables.md)
- [Deployment Runbook](../how-to/deploy/deploy-baremetal-cluster.md)
- [Troubleshooting Guide](../how-to/troubleshooting.md)
