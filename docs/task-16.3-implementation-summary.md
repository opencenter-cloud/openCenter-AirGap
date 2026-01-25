# Task 16.3 Implementation Summary

doc_type: reference

## Overview

Implemented Kubespray execution script following the kubespray-offline workflow for deploying Kubernetes clusters in air-gapped environments.

## Created Files

### scripts/deploy/deploy_kubespray.sh

Comprehensive deployment script that automates the complete Kubespray workflow:

**Features:**
- Extracts kubespray-*.tar.gz to kubespray-master/
- Activates Python venv (~/.venv/kubespray)
- Installs Ansible dependencies from requirements.txt
- Copies inventory structure from sample
- Generates hosts.yaml (bare-metal or OpenStack mode)
- Copies offline.yml with bastion IP substitution
- Runs offline-repo.yml playbook to configure nodes
- Executes cluster.yml playbook to deploy Kubernetes
- Exports kubeconfig to ~/.kube/config

**Command-line Options:**
- `--mode`: baremetal or openstack
- `--bastion-ip`: IP address of bastion host
- `--nodes`: Node list file (bare-metal mode)
- `--inventory-path`: Pre-generated inventory path (OpenStack mode)
- `--cluster-name`: Cluster name (default: mycluster)
- `--install-path`: Installation directory (default: /opt/opencenter)
- Skip flags: `--skip-extraction`, `--skip-venv-setup`, `--skip-inventory`, `--skip-offline-repo`, `--skip-cluster-deploy`

**Idempotency:**
- Safe to re-run after failures
- Skip flags allow resuming from specific steps
- Checks for existing resources before creating

## Modified Files

### scripts/deploy/deploy.sh

Updated Phase 4 to use the new deploy_kubespray.sh script:
- Delegates Kubespray deployment to specialized script
- Passes appropriate arguments based on deployment mode
- Maintains backward compatibility with existing workflow

### docs/deployment-guide.md

Updated manual deployment section:
- Added Option A: Using deploy_kubespray.sh (recommended)
- Kept Option B: Manual step-by-step for reference
- Updated kubeconfig export path to match kubespray-offline structure

### examples/deploy-workflow-baremetal.sh

Modernized example workflow:
- Primary example uses automated deploy.sh
- Manual step-by-step approach in commented section
- Demonstrates both deployment methods

## Workflow Integration

The script integrates seamlessly with the kubespray-offline workflow:

```
1. extract-kubespray.sh (from kubespray-offline)
   ↓
2. Activate ~/.venv/kubespray (created by setup-py.sh)
   ↓
3. pip install -r requirements.txt (Ansible + dependencies)
   ↓
4. Copy inventory/sample → inventory/mycluster
   ↓
5. Generate hosts.yaml (via generate_inventory_baremetal.py)
   ↓
6. Copy offline.yml with bastion IP substituted
   ↓
7. ansible-playbook offline-repo.yml (configure nodes)
   ↓
8. ansible-playbook cluster.yml (deploy K8s)
   ↓
9. Export kubeconfig to ~/.kube/config
```

## Requirements Validated

**Requirement 6.5**: Kubespray installs K8s binaries from local cache
- Script configures offline.yml to point to bastion http_server

**Requirement 6.6**: Kubespray pulls images from bastion registry
- Script configures offline.yml with registry_host pointing to bastion:35000

**Requirement 6.7**: Kubespray installs system packages from bastion apt
- offline-repo.yml playbook configures /etc/apt/sources.list.d/offline.list

**Requirement 6.8**: Kubespray installs Python packages from bastion PyPI
- offline-repo.yml playbook configures /etc/pip.conf

**Requirement 6.11**: Kubeconfig saved to known location
- Script exports admin.conf to ~/.kube/config with correct permissions

## Usage Examples

### Bare-metal Deployment

```bash
/opt/opencenter/scripts/deploy_kubespray.sh \
  --mode baremetal \
  --bastion-ip 192.168.1.5 \
  --nodes nodes.yaml
```

### OpenStack Deployment (Inventory Pre-generated)

```bash
/opt/opencenter/scripts/deploy_kubespray.sh \
  --mode openstack \
  --bastion-ip 10.0.0.5 \
  --inventory-path /opt/opencenter/kubespray/inventory/mycluster \
  --skip-inventory
```

### Resume After Failure

```bash
# If extraction and venv setup completed, skip those steps
/opt/opencenter/scripts/deploy_kubespray.sh \
  --mode baremetal \
  --bastion-ip 192.168.1.5 \
  --nodes nodes.yaml \
  --skip-extraction \
  --skip-venv-setup
```

### Deploy Only (Inventory Already Generated)

```bash
/opt/opencenter/scripts/deploy_kubespray.sh \
  --mode baremetal \
  --bastion-ip 192.168.1.5 \
  --skip-inventory \
  --skip-offline-repo
```

## Error Handling

The script includes comprehensive error handling:

- Validates all required parameters before execution
- Checks for prerequisite files and directories
- Verifies Python venv exists before activation
- Confirms Ansible installation succeeded
- Validates inventory files were created
- Checks kubeconfig was generated
- Provides clear error messages with context

## Testing

Syntax validation:
```bash
bash -n scripts/deploy/deploy_kubespray.sh  # ✓ Passed
bash -n scripts/deploy/deploy.sh            # ✓ Passed
bash -n examples/deploy-workflow-baremetal.sh  # ✓ Passed
```

Help output verification:
```bash
scripts/deploy/deploy_kubespray.sh --help  # ✓ Displays usage
```

## Next Steps

Task 16.4: Create cluster health verification script
- Check control plane component health
- Check node Ready status
- Report unhealthy components
