# Terraform Idempotency

doc_type: reference

This document describes the idempotency behavior of Terraform scripts used in openCenter AirGap OpenStack deployments.

## Purpose

Terraform is inherently designed to be idempotent through its state management system. This document describes how openCenter AirGap leverages Terraform's idempotency features and adds additional checks for safe re-runs.

## Terraform State Management

### State File Location

Terraform state is stored at:
```
/opt/opencenter/terraform/terraform.tfstate
```

This file tracks all resources created by Terraform and is critical for idempotent operations.

### State Preservation

**On Success**: State file is updated with current infrastructure state.

**On Failure**: State file is preserved at the point of failure, allowing recovery:
- Partial infrastructure may exist
- Re-running terraform apply will continue from the failure point
- Terraform will not recreate already-existing resources

## terraform_openstack.sh Idempotency

### Idempotency Checks

The `terraform_openstack.sh` script includes the following idempotency checks:

#### 1. Existing State Detection

```bash
# Check for existing Terraform state
if [ -f "terraform.tfstate" ]; then
    log_info "Existing Terraform state found"
    
    # Check if state has resources
    RESOURCE_COUNT=$(terraform show -json | jq '.values.root_module.resources | length')
    
    if [ "${RESOURCE_COUNT}" -gt 0 ]; then
        log_info "State contains ${RESOURCE_COUNT} existing resources"
        log_info "Terraform will use existing state for planning"
    fi
fi
```

**Behavior**:
- Detects existing state file
- Counts resources in state
- Logs information about existing infrastructure
- Proceeds with planning using existing state

#### 2. Plan Analysis

```bash
# Check if plan has changes
if grep -q "No changes" "${PLAN_OUTPUT}"; then
    log_info "Infrastructure already exists and matches desired state"
    log_info "No changes needed - skipping apply"
    SKIP_APPLY=true
fi
```

**Behavior**:
- Analyzes terraform plan output
- If no changes detected: Skips apply, uses existing infrastructure
- If changes detected: Proceeds with apply

#### 3. Conditional Apply

```bash
if [ "${SKIP_APPLY:-false}" = "false" ]; then
    # Apply infrastructure changes
    terraform apply tfplan
else
    log_info "Infrastructure already exists - using existing resources"
fi
```

**Behavior**:
- Only applies changes if needed
- Skips apply if infrastructure matches desired state
- Extracts outputs from existing state

## Re-run Scenarios

### Scenario 1: Fresh Deployment

**State**: No terraform.tfstate file exists

**Behavior**:
1. terraform init: Initializes backend and providers
2. terraform plan: Plans all resources to be created
3. terraform apply: Creates all infrastructure
4. State file created with all resources

**Result**: Infrastructure created successfully

### Scenario 2: Re-run After Success

**State**: terraform.tfstate exists with all resources

**Behavior**:
1. terraform init: Uses existing state
2. terraform plan: Detects no changes needed
3. terraform apply: **SKIPPED** (infrastructure already exists)
4. Outputs extracted from existing state

**Result**: No changes made, existing infrastructure used

### Scenario 3: Re-run After Partial Failure

**State**: terraform.tfstate exists with some resources

**Example**: 2 of 3 control plane VMs created, then network error

**Behavior**:
1. terraform init: Uses existing state
2. terraform plan: Plans to create missing resources only
3. terraform apply: Creates only the missing control plane VM
4. State updated with all resources

**Result**: Infrastructure completed without recreating existing resources

### Scenario 4: Configuration Change

**State**: terraform.tfstate exists, but configuration changed

**Example**: Increase worker_count from 2 to 3

**Behavior**:
1. terraform init: Uses existing state
2. terraform plan: Plans to add 1 worker VM
3. terraform apply: Creates only the new worker VM
4. State updated with new resource

**Result**: Infrastructure updated incrementally

### Scenario 5: Resource Drift

**State**: terraform.tfstate exists, but actual infrastructure differs

**Example**: VM manually deleted from OpenStack console

**Behavior**:
1. terraform init: Uses existing state
2. terraform plan: Detects missing resource, plans to recreate
3. terraform apply: Recreates the missing VM
4. State updated to match actual infrastructure

**Result**: Infrastructure restored to desired state

## Terraform Commands

### Check Current State

```bash
cd /opt/opencenter/terraform

# Show all resources in state
terraform show

# Show specific resource
terraform state show openstack_compute_instance_v2.control_plane[0]

# List all resources
terraform state list
```

### Refresh State

```bash
# Update state to match actual infrastructure
terraform refresh \
    -var="cluster_name=mycluster" \
    -var="control_plane_count=3" \
    -var="worker_count=2" \
    # ... other vars
```

### Plan Without Apply

```bash
# See what changes would be made
terraform plan \
    -var="cluster_name=mycluster" \
    -var="control_plane_count=3" \
    -var="worker_count=2" \
    # ... other vars
```

### Force Resource Recreation

```bash
# Taint a resource to force recreation
terraform taint openstack_compute_instance_v2.control_plane[0]

# Then apply
terraform apply
```

## Recovery Procedures

### Recover from Failed Apply

```bash
# Re-run the terraform script
./scripts/deploy/terraform_openstack.sh \
    --config openstack.yaml \
    --bastion-ip 10.0.0.5 \
    --auto-approve

# Terraform will:
# 1. Use existing state
# 2. Plan only missing resources
# 3. Complete the deployment
```

### Recover from State Corruption

```bash
# Backup corrupted state
cp terraform.tfstate terraform.tfstate.backup

# Import existing resources manually
terraform import openstack_compute_instance_v2.control_plane[0] <instance-id>

# Or restore from backup if available
cp terraform.tfstate.backup.1 terraform.tfstate
```

### Recover from Manual Changes

```bash
# Refresh state to detect drift
terraform refresh -var-file=terraform.tfvars

# Plan to see what needs to be fixed
terraform plan -var-file=terraform.tfvars

# Apply to restore desired state
terraform apply -var-file=terraform.tfvars
```

## Best Practices

### 1. Never Delete State File

The state file is critical for idempotent operations. Deleting it will cause Terraform to attempt to recreate all resources, which will fail if they already exist.

**If state is lost**:
- Resources must be imported manually
- Or resources must be destroyed and recreated

### 2. Use Version Control for State (Production)

For production deployments, use remote state backend:
```hcl
terraform {
  backend "s3" {
    bucket = "terraform-state"
    key    = "opencenter/terraform.tfstate"
    region = "us-east-1"
  }
}
```

### 3. Always Review Plan Before Apply

```bash
# Review plan output carefully
terraform plan -out=tfplan

# Review the plan file
terraform show tfplan

# Only apply if plan looks correct
terraform apply tfplan
```

### 4. Use Auto-Approve Carefully

The `--auto-approve` flag skips interactive confirmation:
- Safe for CI/CD pipelines
- Safe for re-runs after reviewing plan
- **Not safe** for first-time deployments without review

### 5. Preserve State on Failure

The terraform_openstack.sh script automatically preserves state on failure:
```bash
log_error "Terraform apply failed"
log_error "State file preserved at: ${TERRAFORM_DIR}/terraform.tfstate"
log_error "You can retry by re-running this script"
```

## Testing Idempotency

### Test 1: Re-run After Success

```bash
# First run
./scripts/deploy/terraform_openstack.sh \
    --config openstack.yaml \
    --bastion-ip 10.0.0.5

# Second run (should skip apply)
./scripts/deploy/terraform_openstack.sh \
    --config openstack.yaml \
    --bastion-ip 10.0.0.5

# Expected output:
# "Infrastructure already exists and matches desired state"
# "No changes needed - skipping apply"
```

### Test 2: Recover from Failure

```bash
# Simulate failure by killing terraform during apply
./scripts/deploy/terraform_openstack.sh \
    --config openstack.yaml \
    --bastion-ip 10.0.0.5 &
PID=$!

# Wait a bit, then kill
sleep 30
kill $PID

# Re-run to complete
./scripts/deploy/terraform_openstack.sh \
    --config openstack.yaml \
    --bastion-ip 10.0.0.5

# Expected: Completes without recreating existing resources
```

### Test 3: Configuration Change

```bash
# Initial deployment with 2 workers
# Edit openstack.yaml: worker_count: 2
./scripts/deploy/terraform_openstack.sh \
    --config openstack.yaml \
    --bastion-ip 10.0.0.5

# Increase to 3 workers
# Edit openstack.yaml: worker_count: 3
./scripts/deploy/terraform_openstack.sh \
    --config openstack.yaml \
    --bastion-ip 10.0.0.5

# Expected: Creates 1 new worker, keeps existing 2
```

## Comparison with kubespray-offline

| Aspect | Terraform | kubespray-offline |
|:-------|:----------|:------------------|
| State Management | Explicit state file | Implicit (container existence) |
| Idempotency | Built-in via state | Partial (some scripts) |
| Re-run Safety | ✓ Always safe | ⚠️ Some scripts fail |
| Resource Detection | Automatic via state | Manual checks |
| Partial Failure Recovery | ✓ Automatic | ⚠️ Manual cleanup needed |
| Configuration Drift | ✓ Detected and fixed | ✗ Not detected |

## Related Requirements

- **Requirement 8.4**: Use existing state if present, skip apply if resources already exist

## Summary

Terraform provides robust idempotency through its state management system. The `terraform_openstack.sh` script enhances this with:

1. **State detection**: Checks for existing state before operations
2. **Plan analysis**: Skips apply if no changes needed
3. **Conditional apply**: Only applies when changes detected
4. **State preservation**: Keeps state on failure for recovery
5. **Output extraction**: Works with existing or new infrastructure

This ensures that OpenStack infrastructure provisioning can be safely re-run at any time without causing errors or duplicate resources.
