# Kubespray Idempotency

doc_type: reference

This document describes the idempotency behavior of Kubespray cluster deployment used in openCenter AirGap.

## Purpose

Kubespray (Ansible-based Kubernetes installer) is designed to be idempotent by default. This means the `cluster.yml` playbook can be safely re-run on an existing cluster without causing errors or unwanted changes.

## Ansible Idempotency Principles

Ansible modules are designed to be idempotent:
- **Check before change**: Modules check current state before making changes
- **Skip if correct**: If resource is already in desired state, module reports "ok" and skips
- **Change if needed**: If resource differs from desired state, module makes changes and reports "changed"
- **Fail on error**: If operation fails, module reports "failed" and stops

## Kubespray cluster.yml Idempotency

### Expected Behavior on Re-run

When `cluster.yml` is re-run on a healthy cluster:

**Expected Results**:
- All tasks report "ok" (green)
- No tasks report "changed" (yellow)
- No tasks report "failed" (red)
- Cluster state unchanged

**Example Output**:
```
PLAY RECAP *********************************************************************
control-01                 : ok=234  changed=0    unreachable=0    failed=0    skipped=156  rescued=0    ignored=0
control-02                 : ok=234  changed=0    unreachable=0    failed=0    skipped=156  rescued=0    ignored=0
control-03                 : ok=234  changed=0    unreachable=0    failed=0    skipped=156  rescued=0    ignored=0
worker-01                  : ok=189  changed=0    unreachable=0    failed=0    skipped=134  rescued=0    ignored=0
worker-02                  : ok=189  changed=0    unreachable=0    failed=0    skipped=134  rescued=0    ignored=0
```

### What Gets Checked

Kubespray verifies and maintains:

1. **System packages**: Ensures required packages installed
2. **Kernel modules**: Ensures required modules loaded
3. **Sysctl settings**: Ensures kernel parameters set correctly
4. **Container runtime**: Ensures containerd configured and running
5. **Kubernetes binaries**: Ensures kubelet, kubectl, kubeadm present
6. **Certificates**: Ensures PKI certificates valid and not expired
7. **Static pods**: Ensures control plane components running
8. **Kubelet service**: Ensures kubelet systemd service enabled and running
9. **CNI plugin**: Ensures Calico/Cilium deployed and configured
10. **CoreDNS**: Ensures DNS service running
11. **Kube-proxy**: Ensures proxy service running

### Tasks That May Show "changed"

Some tasks may legitimately show "changed" on re-run:

**Temporary files**:
- Tasks that create temp files may show changed
- Example: "Create temporary directory for kubeconfig"
- Impact: None (temp files cleaned up)

**Time-based checks**:
- Tasks that check certificate expiration
- Example: "Check certificate validity"
- Impact: None (informational only)

**Dynamic configuration**:
- Tasks that regenerate dynamic configs
- Example: "Generate kubeadm config"
- Impact: Minimal (config regenerated but identical)

**These are normal and do not indicate problems.**

## Testing Kubespray Idempotency

### Test Procedure

```bash
# Deploy cluster initially
cd /opt/opencenter/outputs/kubespray-master
source ~/.venv/kubespray/bin/activate

ansible-playbook -i inventory/mycluster/hosts.yaml \
    --become \
    --become-user=root \
    cluster.yml

# Verify cluster is healthy
kubectl get nodes
kubectl get pods -A

# Re-run cluster.yml on healthy cluster
ansible-playbook -i inventory/mycluster/hosts.yaml \
    --become \
    --become-user=root \
    cluster.yml

# Check for changes in output
# Expected: changed=0 for all hosts
```

### Verification Steps

After re-running cluster.yml:

1. **Check play recap**: Verify `changed=0` for all hosts
2. **Check node status**: Verify all nodes still Ready
3. **Check pod status**: Verify all pods still Running
4. **Check cluster version**: Verify version unchanged
5. **Check certificates**: Verify certificates not regenerated

```bash
# 1. Play recap already shown in Ansible output

# 2. Check nodes
kubectl get nodes
# All should be Ready

# 3. Check pods
kubectl get pods -A
# All should be Running

# 4. Check version
kubectl version --short
# Should match original version

# 5. Check certificate dates
sudo kubeadm certs check-expiration
# Dates should be unchanged
```

## Cluster State Snapshot

To verify idempotency, capture cluster state before and after re-run:

### Capture State Script

```bash
#!/bin/bash
# capture_cluster_state.sh

OUTPUT_FILE="${1:-cluster-state.json}"

kubectl get nodes -o json > /tmp/nodes.json
kubectl get pods -A -o json > /tmp/pods.json
kubectl get services -A -o json > /tmp/services.json
kubectl get deployments -A -o json > /tmp/deployments.json
kubectl get daemonsets -A -o json > /tmp/daemonsets.json
kubectl get statefulsets -A -o json > /tmp/statefulsets.json

# Combine into single JSON
jq -n \
    --slurpfile nodes /tmp/nodes.json \
    --slurpfile pods /tmp/pods.json \
    --slurpfile services /tmp/services.json \
    --slurpfile deployments /tmp/deployments.json \
    --slurpfile daemonsets /tmp/daemonsets.json \
    --slurpfile statefulsets /tmp/statefulsets.json \
    '{
        nodes: $nodes[0],
        pods: $pods[0],
        services: $services[0],
        deployments: $deployments[0],
        daemonsets: $daemonsets[0],
        statefulsets: $statefulsets[0]
    }' > "${OUTPUT_FILE}"

echo "Cluster state saved to: ${OUTPUT_FILE}"
```

### Compare States

```bash
# Capture state before re-run
./capture_cluster_state.sh state-before.json

# Re-run cluster.yml
ansible-playbook -i inventory/mycluster/hosts.yaml \
    --become \
    --become-user=root \
    cluster.yml

# Capture state after re-run
./capture_cluster_state.sh state-after.json

# Compare states (should be identical)
diff <(jq -S . state-before.json) <(jq -S . state-after.json)

# Expected: No differences (or only timestamp differences)
```

## Recovery Scenarios

### Scenario 1: Node Failure During Deployment

**Situation**: SSH connection lost to node during cluster.yml execution

**Recovery**:
```bash
# Re-run cluster.yml
ansible-playbook -i inventory/mycluster/hosts.yaml \
    --become \
    --become-user=root \
    cluster.yml

# Kubespray will:
# 1. Skip tasks already completed on other nodes
# 2. Complete tasks on failed node
# 3. Verify cluster health
```

**Expected Result**: Cluster deployment completes successfully

### Scenario 2: Partial Configuration

**Situation**: cluster.yml stopped mid-execution (Ctrl+C, system reboot, etc.)

**Recovery**:
```bash
# Re-run cluster.yml
ansible-playbook -i inventory/mycluster/hosts.yaml \
    --become \
    --become-user=root \
    cluster.yml

# Kubespray will:
# 1. Check state of each component
# 2. Skip components already configured
# 3. Complete remaining configuration
```

**Expected Result**: Cluster configuration completes

### Scenario 3: Configuration Drift

**Situation**: Manual changes made to cluster (e.g., kubelet config edited)

**Recovery**:
```bash
# Re-run cluster.yml to restore desired state
ansible-playbook -i inventory/mycluster/hosts.yaml \
    --become \
    --become-user=root \
    cluster.yml

# Kubespray will:
# 1. Detect configuration differences
# 2. Restore configurations to desired state
# 3. Restart affected services
```

**Expected Result**: Cluster restored to desired state

### Scenario 4: Component Failure

**Situation**: Control plane component crashed (e.g., kube-apiserver pod deleted)

**Recovery**:
```bash
# Re-run cluster.yml
ansible-playbook -i inventory/mycluster/hosts.yaml \
    --become \
    --become-user=root \
    cluster.yml

# Kubespray will:
# 1. Verify static pod manifests exist
# 2. Kubelet will restart missing pods
# 3. Verify all components healthy
```

**Expected Result**: Failed components restarted

## Limitations

### Not Idempotent for Version Changes

Kubespray is idempotent for the **same version**, but not for version upgrades:

**Same version re-run**: ✓ Idempotent
```bash
# Both runs with k8s v1.28.6
ansible-playbook cluster.yml  # First run
ansible-playbook cluster.yml  # Second run - idempotent
```

**Version upgrade**: ✗ Not idempotent (use upgrade-cluster.yml)
```bash
# First run with v1.28.6, second with v1.29.0
ansible-playbook cluster.yml  # First run
# Edit inventory: kube_version: v1.29.0
ansible-playbook cluster.yml  # Second run - NOT SAFE

# Use upgrade playbook instead:
ansible-playbook upgrade-cluster.yml
```

### Not Idempotent for Node Changes

Adding/removing nodes requires different playbooks:

**Add nodes**: Use `scale.yml`
```bash
# Add new nodes to inventory
ansible-playbook scale.yml
```

**Remove nodes**: Use `remove-node.yml`
```bash
ansible-playbook remove-node.yml --extra-vars "node=worker-03"
```

## Best Practices

### 1. Always Use Same Inventory

```bash
# Use the same inventory file for all operations
INVENTORY="inventory/mycluster/hosts.yaml"

ansible-playbook -i ${INVENTORY} cluster.yml
ansible-playbook -i ${INVENTORY} cluster.yml  # Re-run
```

### 2. Verify Cluster Health Before Re-run

```bash
# Check cluster is healthy
kubectl get nodes
kubectl get pods -A

# If cluster is unhealthy, investigate before re-running
```

### 3. Use --check Mode for Dry Run

```bash
# See what would change without making changes
ansible-playbook -i inventory/mycluster/hosts.yaml \
    --become \
    --check \
    cluster.yml

# Review output, then run without --check
```

### 4. Use --diff to See Changes

```bash
# Show file differences for changed files
ansible-playbook -i inventory/mycluster/hosts.yaml \
    --become \
    --diff \
    cluster.yml
```

### 5. Limit to Specific Hosts

```bash
# Re-run only on specific node
ansible-playbook -i inventory/mycluster/hosts.yaml \
    --become \
    --limit worker-01 \
    cluster.yml
```

### 6. Use Tags for Specific Components

```bash
# Re-run only specific components
ansible-playbook -i inventory/mycluster/hosts.yaml \
    --become \
    --tags kubelet \
    cluster.yml
```

## Monitoring Re-runs

### Log Analysis

```bash
# Save Ansible output to log
ansible-playbook -i inventory/mycluster/hosts.yaml \
    --become \
    cluster.yml 2>&1 | tee cluster-rerun.log

# Check for changes
grep "changed=" cluster-rerun.log

# Check for failures
grep "failed=" cluster-rerun.log

# Check for specific tasks that changed
grep "changed: \[" cluster-rerun.log
```

### Metrics to Track

After re-running cluster.yml, verify:

1. **Task counts**: changed=0, failed=0
2. **Node count**: Same number of nodes
3. **Pod count**: Same number of pods
4. **Service count**: Same number of services
5. **Certificate expiry**: Dates unchanged
6. **Kubelet version**: Version unchanged
7. **API server uptime**: Not restarted

## Integration with openCenter AirGap

The `deploy_kubespray.sh` script supports idempotent re-runs:

```bash
# Initial deployment
./scripts/deploy/deploy_kubespray.sh \
    --mode baremetal \
    --bastion-ip 192.168.1.5 \
    --nodes nodes.yaml

# Re-run (all steps)
./scripts/deploy/deploy_kubespray.sh \
    --mode baremetal \
    --bastion-ip 192.168.1.5 \
    --nodes nodes.yaml

# Re-run (skip extraction and venv setup)
./scripts/deploy/deploy_kubespray.sh \
    --mode baremetal \
    --bastion-ip 192.168.1.5 \
    --nodes nodes.yaml \
    --skip-extraction \
    --skip-venv-setup

# Re-run (only cluster deployment)
./scripts/deploy/deploy_kubespray.sh \
    --mode baremetal \
    --bastion-ip 192.168.1.5 \
    --nodes nodes.yaml \
    --skip-extraction \
    --skip-venv-setup \
    --skip-inventory \
    --skip-offline-repo
```

## Related Requirements

- **Requirement 8.5**: Kubespray re-run on healthy cluster completes without errors

## Summary

Kubespray provides robust idempotency through Ansible's built-in mechanisms:

1. **Check-before-change**: All tasks verify current state
2. **Skip-if-correct**: Tasks skip if already in desired state
3. **Change-if-needed**: Tasks only make necessary changes
4. **Fail-on-error**: Tasks fail clearly with error messages

This ensures that `cluster.yml` can be safely re-run on a healthy cluster without causing changes or errors, making it ideal for recovery scenarios and configuration drift correction.

**Key Takeaway**: Re-running `cluster.yml` on a healthy cluster should result in `changed=0` for all hosts, indicating perfect idempotency.
