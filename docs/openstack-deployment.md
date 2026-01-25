# OpenStack Deployment Guide

doc_type: how-to

## Purpose

Deploy Kubernetes infrastructure on OpenStack using Terraform in an air-gapped environment. This guide covers automated VM provisioning and cluster deployment.

## Prerequisites

### Bastion Host
- Ubuntu 24.04 LTS
- 100GB+ free disk space
- Zarf package deployed with terraform-providers component
- Terraform binary available
- Bastion services running (nginx:80, registry:35000)

### OpenStack Environment
- OpenStack cloud with API access
- Project/tenant with sufficient quota:
  - VMs: control_plane_count + worker_count
  - vCPUs: (control_plane_count + worker_count) × 4
  - RAM: (control_plane_count + worker_count) × 8GB
  - Storage: (control_plane_count + worker_count) × 50GB
- Ubuntu 24.04 LTS image available
- Network with DHCP enabled
- SSH key pair created
- Security groups allowing cluster communication

### OpenStack Credentials
- Auth URL (Keystone endpoint)
- Project name
- Username and password
- Region name
- Domain name (usually "Default")

## Configuration

### Create OpenStack Config File

```yaml
# openstack-config.yaml
auth_url: https://openstack.example.com:5000/v3
project_name: kubernetes-project
username: my-user
password: secure-password
region: RegionOne
domain_name: Default

# VM Configuration
control_plane_count: 3
worker_count: 2
flavor: m1.large
image: ubuntu-24.04
network: private-network
floating_ip_pool: public  # Optional
key_pair: my-keypair
```

**Security Note**: Store passwords securely. Consider using environment variables or a secrets manager.

### Verify OpenStack Access

Test connectivity before deployment:

```bash
# Export credentials
export OS_AUTH_URL=https://openstack.example.com:5000/v3
export OS_PROJECT_NAME=kubernetes-project
export OS_USERNAME=my-user
export OS_PASSWORD=secure-password
export OS_REGION_NAME=RegionOne
export OS_USER_DOMAIN_NAME=Default
export OS_PROJECT_DOMAIN_NAME=Default

# Test OpenStack CLI (if available)
openstack server list
openstack network list
openstack image list | grep ubuntu-24.04
```

## Deployment Methods

### Automated (Recommended)

Use the main deployment script with OpenStack mode:

```bash
/opt/opencenter/scripts/deploy.sh \
  --mode openstack \
  --bastion-ip 10.0.0.5 \
  --openstack-config openstack-config.yaml \
  --cluster-name production
```

This executes all phases:
1. Validate prerequisites
2. Provision infrastructure with Terraform
3. Generate inventory from Terraform outputs
4. Configure nodes for offline operation
5. Deploy Kubernetes cluster
6. Verify cluster health

### Manual Terraform Execution

For more control over infrastructure provisioning:

```bash
# Provision infrastructure
/opt/opencenter/scripts/terraform_openstack.sh \
  --config openstack-config.yaml \
  --bastion-ip 10.0.0.5 \
  --cluster-name production

# Then continue with cluster deployment
/opt/opencenter/scripts/deploy.sh \
  --mode openstack \
  --bastion-ip 10.0.0.5 \
  --skip-inventory \
  --openstack-config openstack-config.yaml
```

## Terraform Operations

### Plan Infrastructure

Review changes before applying:

```bash
cd /opt/opencenter/terraform

# Export OpenStack credentials
export OS_AUTH_URL=...
export OS_PROJECT_NAME=...
# ... (other credentials)

# Plan
terraform plan \
  -var="cluster_name=production" \
  -var="control_plane_count=3" \
  -var="worker_count=2" \
  -var="flavor=m1.large" \
  -var="image=ubuntu-24.04" \
  -var="network=private-network" \
  -var="key_pair=my-keypair"
```

### Apply Infrastructure

Create VMs and networks:

```bash
terraform apply \
  -var="cluster_name=production" \
  -var="control_plane_count=3" \
  -var="worker_count=2" \
  -var="flavor=m1.large" \
  -var="image=ubuntu-24.04" \
  -var="network=private-network" \
  -var="key_pair=my-keypair"
```

### View Outputs

Check provisioned resources:

```bash
terraform output control_plane_ips
terraform output worker_ips
terraform output control_plane_floating_ips
```

### Destroy Infrastructure

Remove all resources:

```bash
/opt/opencenter/scripts/terraform_openstack.sh \
  --config openstack-config.yaml \
  --bastion-ip 10.0.0.5 \
  --destroy
```

Or manually:

```bash
cd /opt/opencenter/terraform
terraform destroy
```

## Verification

### Check Terraform State

```bash
cd /opt/opencenter/terraform
terraform show
```

### Verify VMs in OpenStack

```bash
# List VMs
openstack server list --name production

# Check VM details
openstack server show production-control-01
```

### Test SSH Access

```bash
# SSH to control plane node
ssh -i ~/.ssh/my-keypair ubuntu@<control-plane-ip>

# SSH to worker node
ssh -i ~/.ssh/my-keypair ubuntu@<worker-ip>
```

### Check Generated Inventory

```bash
cat /opt/opencenter/kubespray/inventory/production/hosts.yaml
```

## Troubleshooting

### Terraform init fails

**Symptom**: "Failed to query available provider packages"

**Cause**: Provider mirror not configured or missing providers.

**Fix**:
```bash
# Verify .terraformrc exists
cat /root/.terraformrc

# Check provider mirror
ls /opt/opencenter/terraform-mirror/registry.terraform.io/

# Ensure terraform-providers component was deployed
zarf package list
```

### Terraform plan fails with authentication error

**Symptom**: "Error: Authentication failed"

**Cause**: Invalid OpenStack credentials.

**Fix**:
```bash
# Verify credentials in config file
cat openstack-config.yaml

# Test credentials manually
export OS_AUTH_URL=...
openstack token issue

# Check auth URL is correct (should end with /v3)
```

### Terraform apply fails with quota exceeded

**Symptom**: "Error: Quota exceeded for instances"

**Cause**: Insufficient OpenStack quota.

**Fix**:
```bash
# Check current quota
openstack quota show

# Request quota increase from OpenStack admin
# Or reduce VM count in config:
#   control_plane_count: 1
#   worker_count: 1
```

### VMs created but not accessible

**Symptom**: Cannot SSH to VMs

**Cause**: Security group rules or network configuration.

**Fix**:
```bash
# Check security group rules
openstack security group show production-k8s-sg

# Verify SSH rule exists (port 22)
openstack security group rule list production-k8s-sg

# Check VM has correct security group
openstack server show production-control-01 | grep security_groups

# Verify network connectivity
ping <vm-ip>
```

### Inventory generation fails

**Symptom**: "Failed to extract Terraform outputs"

**Cause**: Terraform outputs not defined or VMs not created.

**Fix**:
```bash
# Check Terraform outputs
cd /opt/opencenter/terraform
terraform output

# Should show:
#   control_plane_ips = [...]
#   worker_ips = [...]

# If missing, check main.tf has output blocks
grep -A 3 "output \"control_plane_ips\"" main.tf
```

### State file corruption

**Symptom**: "Error: state snapshot was created by Terraform vX.Y.Z"

**Cause**: Terraform version mismatch or corrupted state.

**Fix**:
```bash
# Backup state file
cp /opt/opencenter/terraform/terraform.tfstate /opt/opencenter/terraform/terraform.tfstate.backup

# Try state recovery
cd /opt/opencenter/terraform
terraform state list

# If recovery fails, may need to import resources manually
# or destroy and recreate
```

## State Management

### Backup State

Always backup state before major operations:

```bash
cp /opt/opencenter/terraform/terraform.tfstate \
   /opt/opencenter/terraform/terraform.tfstate.$(date +%Y%m%d-%H%M%S)
```

### Recover from Failed Apply

If `terraform apply` fails mid-execution:

```bash
# State is preserved automatically
cd /opt/opencenter/terraform

# Check current state
terraform show

# Re-run apply to complete
terraform apply
```

### Import Existing Resources

If resources exist but not in state:

```bash
# Import VM
terraform import openstack_compute_instance_v2.control_plane[0] <vm-id>

# Import security group
terraform import openstack_networking_secgroup_v2.k8s <sg-id>
```

## Network Configuration

### Floating IPs

To assign floating IPs to control plane nodes:

```yaml
# In openstack-config.yaml
floating_ip_pool: public
```

Access cluster via floating IP:
```bash
kubectl --kubeconfig admin.conf \
  --server=https://<floating-ip>:6443 \
  get nodes
```

### Private Network Only

For fully private deployment:

```yaml
# In openstack-config.yaml
floating_ip_pool: ""  # Empty string
```

Access via bastion or VPN.

## Cost Optimization

### Reduce VM Count

For testing:
```yaml
control_plane_count: 1
worker_count: 1
```

### Use Smaller Flavors

Minimum requirements:
```yaml
flavor: m1.medium  # 2 vCPU, 4GB RAM
```

### Destroy When Not in Use

```bash
/opt/opencenter/scripts/terraform_openstack.sh \
  --config openstack-config.yaml \
  --bastion-ip 10.0.0.5 \
  --destroy
```

## Next Steps

After infrastructure provisioning:

1. **Configure Nodes**: Run offline-repo playbook
2. **Deploy Cluster**: Execute Kubespray
3. **Verify Cluster**: Check nodes and pods
4. **Deploy Services**: Install core platform services

See [Deployment Guide](deployment-guide.md) for complete workflow.
