# openCenter AirGap Deployment Runbook - OpenStack

**doc_type**: how-to

**Purpose**: Deploy Kubernetes cluster on OpenStack infrastructure in an air-gapped environment (Zone C).

**Audience**: Field operators executing deployments in disconnected OpenStack environments.

## Prerequisites

### Bastion Host Requirements

- **Operating System**: Ubuntu 24.04 LTS (AMD64)
- **Disk Space**: 100GB free minimum
- **Memory**: 8GB RAM minimum
- **Container Runtime**: Podman installed
- **Terraform**: Installed and in PATH
- **Network**: Access to OpenStack API endpoints
- **Ports**: 80 (nginx) and 35000 (registry) available

Verify bastion readiness:
```bash
# Check OS version
lsb_release -a
# Expected: Ubuntu 24.04

# Check disk space
df -h /opt
# Expected: 100GB+ available

# Check podman
podman --version
# Expected: podman version 4.x or higher

# Check Terraform
terraform version
# Expected: Terraform v1.6.6 or compatible
```

### OpenStack Requirements

- **API Access**: Bastion can reach OpenStack API endpoints
- **Credentials**: Valid OpenStack credentials with project access
- **Quotas**: Sufficient quota for VMs, networks, and storage
- **Images**: Ubuntu 24.04 image available in OpenStack
- **Flavors**: Appropriate flavors for control plane and workers
- **Network**: Existing network or ability to create one

Verify OpenStack access:
```bash
# Source OpenStack credentials
source openrc.sh

# Test API access
openstack server list
openstack network list
openstack flavor list
openstack image list | grep -i ubuntu
```

### Network Requirements

- Bastion can reach OpenStack API
- Provisioned VMs can reach bastion on ports 80 and 35000
- VMs can reach each other (Kubernetes networking)
- No internet connectivity required for VMs

## Cloud Credentials Setup

### 1. Create OpenStack Configuration

Create `openstack_config.yaml`:

```yaml
# OpenStack authentication
auth_url: "https://openstack.example.com:5000/v3"
project_name: "kubernetes-prod"
project_domain_name: "Default"
user_domain_name: "Default"
username: "k8s-deployer"
# Password provided at runtime via environment variable

# Region
region_name: "RegionOne"

# Infrastructure configuration
control_plane_count: 3
worker_count: 3

# VM specifications
control_plane_flavor: "m1.large"    # 4 vCPU, 8GB RAM
worker_flavor: "m1.medium"          # 2 vCPU, 4GB RAM
image_name: "ubuntu-24.04-amd64"

# Network configuration
network_name: "k8s-network"
subnet_cidr: "10.0.0.0/24"
external_network: "public"

# Storage
root_volume_size: 50  # GB

# SSH
ssh_key_name: "k8s-deployer-key"
```

### 2. Set OpenStack Password

Export password as environment variable (not stored in file):

```bash
export OS_PASSWORD="your-openstack-password"
```

Or use a secure credential store.

### 3. Verify SSH Key

Ensure SSH key exists in OpenStack:

```bash
openstack keypair list | grep k8s-deployer-key
```

If not, create it:

```bash
# Generate key
ssh-keygen -t ed25519 -f ~/.ssh/k8s-deployer -N ""

# Upload to OpenStack
openstack keypair create --public-key ~/.ssh/k8s-deployer.pub k8s-deployer-key
```

## Package Transfer and Verification

### 1. Transfer Package to Bastion

From Zone B (Airlock), copy package to bastion:

```bash
# Using removable media
cp /media/usb/zarf-package-*.tar.zst /opt/
cp /media/usb/zarf-package-*.tar.zst.sha256 /opt/

# Or using SCP (if bastion has temporary network access)
scp zarf-package-*.tar.zst deployer@bastion:/opt/
scp zarf-package-*.tar.zst.sha256 deployer@bastion:/opt/
```

### 2. Verify Package Integrity

On bastion:

```bash
cd /opt
sha256sum -c zarf-package-*.tar.zst.sha256
```

Expected output: `zarf-package-*.tar.zst: OK`

If verification fails, do not proceed. Re-transfer the package.

## Deployment

### 1. Extract Package

```bash
cd /opt
zarf package deploy zarf-package-*.tar.zst --confirm
```

This extracts assets to `/opt/opencenter/` and runs initial setup.

### 2. Run Deployment Script

Execute the master deployment script:

```bash
cd /opt/opencenter
./scripts/deploy/deploy.sh \
  --mode openstack \
  --bastion-ip 192.168.1.100 \
  --config /opt/openstack_config.yaml \
  --ssh-user ubuntu
```

**Parameters**:
- `--mode`: Deployment mode (use `openstack`)
- `--bastion-ip`: IP address of bastion host
- `--config`: Path to OpenStack configuration file
- `--ssh-user`: SSH user for VM access (default: ubuntu for Ubuntu images)

Expected duration: 45-90 minutes depending on OpenStack performance and cluster size.

### 3. Monitor Deployment

The script outputs progress and logs to `/opt/opencenter/logs/deployment-<timestamp>.log`.

Watch for these phases:
```
==> Phase 1: Package verification
==> Phase 2: Bastion setup (setup-all.sh)
==> Phase 3: Infrastructure provisioning (Terraform)
==> Phase 4: Inventory generation (from Terraform outputs)
==> Phase 5: Cluster bootstrap (Kubespray)
==> Phase 6: Cluster health verification
==> Phase 7: Core services deployment
==> Phase 8: Service readiness verification
```

### 4. Monitor Terraform Progress

In another terminal, watch Terraform state:

```bash
cd /opt/opencenter/terraform
terraform show
```

Check OpenStack resources:

```bash
openstack server list
openstack network list
openstack floating ip list
```

## Verification

### 1. Check Infrastructure

Verify Terraform state:
```bash
cd /opt/opencenter/terraform
terraform show
```

List provisioned VMs:
```bash
openstack server list --name k8s-
```

Expected output:
```
+------+------------------+--------+----------------------+
| ID   | Name             | Status | Networks             |
+------+------------------+--------+----------------------+
| ...  | k8s-control-1    | ACTIVE | k8s-network=10.0.0.11|
| ...  | k8s-control-2    | ACTIVE | k8s-network=10.0.0.12|
| ...  | k8s-control-3    | ACTIVE | k8s-network=10.0.0.13|
| ...  | k8s-worker-1     | ACTIVE | k8s-network=10.0.0.21|
| ...  | k8s-worker-2     | ACTIVE | k8s-network=10.0.0.22|
| ...  | k8s-worker-3     | ACTIVE | k8s-network=10.0.0.23|
+------+------------------+--------+----------------------+
```

All VMs should be `ACTIVE`.

### 2. Check Bastion Services

Verify nginx serving files:
```bash
curl http://localhost/files/
# Expected: Directory listing of K8s binaries
```

Verify registry catalog:
```bash
curl http://localhost:35000/v2/_catalog
# Expected: JSON with list of repositories
```

Check running containers:
```bash
podman ps
# Expected: nginx and registry containers running
```

### 3. Check Cluster Status

Export kubeconfig:
```bash
export KUBECONFIG=/opt/opencenter/kubespray-master/inventory/mycluster/artifacts/admin.conf
```

Check nodes:
```bash
kubectl get nodes
```

Expected output:
```
NAME            STATUS   ROLES           AGE   VERSION
k8s-control-1   Ready    control-plane   10m   v1.30.0
k8s-control-2   Ready    control-plane   10m   v1.30.0
k8s-control-3   Ready    control-plane   10m   v1.30.0
k8s-worker-1    Ready    <none>          9m    v1.30.0
k8s-worker-2    Ready    <none>          9m    v1.30.0
k8s-worker-3    Ready    <none>          9m    v1.30.0
```

All nodes should show `Ready` status.

Check control plane components:
```bash
kubectl get pods -n kube-system
```

All pods should be `Running` or `Completed`.

### 4. Check Core Services

List all pods:
```bash
kubectl get pods -A
```

Verify these namespaces exist with running pods:
- `flux-system`: FluxCD controllers
- `gitea`: Gitea Git server
- `cert-manager`: Certificate management
- `ingress-nginx`: Ingress controller
- `keycloak`: Identity management
- `monitoring`: Prometheus and Grafana

Check service endpoints:
```bash
kubectl get ingress -A
```

### 5. Verify Offline Operation

Check that no external connections were made (except OpenStack API):
```bash
grep -i "external" /opt/opencenter/logs/deployment-*.log | grep -v openstack
# Expected: No matches
```

## Post-Deployment

### 1. Save Terraform State

Backup Terraform state for disaster recovery:
```bash
cp /opt/opencenter/terraform/terraform.tfstate /opt/terraform-state-backup-$(date +%Y%m%d).json
```

Store this securely outside the bastion.

### 2. Save Kubeconfig

Copy kubeconfig for external access:
```bash
cp /opt/opencenter/kubespray-master/inventory/mycluster/artifacts/admin.conf ~/kubeconfig
chmod 600 ~/kubeconfig
```

### 3. Access Services

Get ingress endpoints:
```bash
kubectl get ingress -A
```

Access services via ingress (configure DNS or use /etc/hosts).

### 4. Review Deployment Summary

Check the deployment summary:
```bash
cat /opt/opencenter/logs/deployment-summary-*.txt
```

This shows:
- Deployment duration
- Completed phases
- Any warnings or errors
- Service endpoints
- Infrastructure details

## Troubleshooting

### Terraform Provisioning Failures

**Symptom**: Terraform apply fails

**Check**:
```bash
cd /opt/opencenter/terraform
terraform show
cat terraform.log
```

**Common causes**:
- Insufficient quota
- Invalid credentials
- Network configuration errors
- Image not found

**Solution**:
```bash
# Check quotas
openstack quota show

# Verify credentials
openstack token issue

# Fix configuration in openstack_config.yaml
# Re-run terraform
terraform plan
terraform apply
```

### VM Not Reachable

**Symptom**: Kubespray fails with "Unreachable host"

**Check**:
```bash
# Get VM IPs from Terraform
cd /opt/opencenter/terraform
terraform output

# Test SSH
ssh -i ~/.ssh/k8s-deployer ubuntu@<vm-ip> "hostname"

# Check security groups
openstack security group list
openstack security group rule list <group-id>
```

**Solution**:
- Verify security group allows SSH (port 22) from bastion
- Check floating IPs assigned correctly
- Verify SSH key matches

### Bastion Service Failures

**Symptom**: Nginx or registry not accessible from VMs

**Check**:
```bash
# From bastion
podman ps -a
podman logs nginx
podman logs registry

# From VM
ssh ubuntu@<vm-ip> "curl http://<bastion-ip>:35000/v2/_catalog"
```

**Solution**:
```bash
# Re-run bastion setup
cd /opt/opencenter
./target-scripts/setup-all.sh

# Check firewall on bastion
sudo ufw status
```

### Image Pull Failures

**Symptom**: Pods stuck in `ImagePullBackOff`

**Check**:
```bash
kubectl describe pod <pod-name> -n <namespace>
# Look for "Failed to pull image" errors
```

**Solution**:
```bash
# Verify registry accessible from VMs
ssh ubuntu@<vm-ip> "curl http://<bastion-ip>:35000/v2/_catalog"

# Check containerd configuration
ssh ubuntu@<vm-ip> "cat /etc/containerd/config.toml | grep -A5 registry"

# Re-run offline-repo playbook
cd /opt/opencenter/kubespray-master
ansible-playbook -i inventory/mycluster/hosts.yaml ../playbook/offline-repo.yml
```

### Control Plane Unhealthy

**Symptom**: Control plane components not running

**Check**:
```bash
kubectl get pods -n kube-system
kubectl logs -n kube-system kube-apiserver-k8s-control-1
```

**Solution**:
```bash
# Re-run Kubespray cluster.yml
cd /opt/opencenter/kubespray-master
source ~/.venv/kubespray/bin/activate
ansible-playbook -i inventory/mycluster/hosts.yaml --become cluster.yml
```

### FluxCD Reconciliation Failures

**Symptom**: Core services not deploying

**Check**:
```bash
kubectl get gitrepositories -n flux-system
kubectl get kustomizations -n flux-system
kubectl logs -n flux-system -l app=source-controller
```

**Solution**:
```bash
# Force reconciliation
flux reconcile source git cluster-config
flux reconcile kustomization infrastructure
flux reconcile kustomization platform
```

## Recovery Procedures

### Re-run Deployment

If deployment fails, re-run is safe (idempotent):

```bash
cd /opt/opencenter
./scripts/deploy/deploy.sh \
  --mode openstack \
  --bastion-ip 192.168.1.100 \
  --config /opt/openstack_config.yaml \
  --ssh-user ubuntu
```

The script detects existing resources and skips completed steps.

### Terraform State Recovery

If Terraform state is corrupted:

```bash
# Restore from backup
cp /opt/terraform-state-backup-<date>.json /opt/opencenter/terraform/terraform.tfstate

# Refresh state
cd /opt/opencenter/terraform
terraform refresh
```

### Destroy and Rebuild

To destroy infrastructure and start over:

```bash
cd /opt/opencenter/terraform
terraform destroy
```

**Warning**: This destroys all VMs and data. Ensure backups exist.

Then re-run deployment script.

## Log Locations

- **Deployment logs**: `/opt/opencenter/logs/deployment-<timestamp>.log`
- **Terraform logs**: `/opt/opencenter/terraform/terraform.log`
- **Kubespray logs**: `/opt/opencenter/kubespray-master/inventory/mycluster/artifacts/`
- **Container logs**: `podman logs <container-name>`
- **Pod logs**: `kubectl logs <pod-name> -n <namespace>`
- **System logs**: `/var/log/syslog` on each VM

## Infrastructure Management

### Scaling Workers

To add more worker nodes:

1. Edit `openstack_config.yaml`:
```yaml
worker_count: 5  # Increase from 3
```

2. Apply Terraform changes:
```bash
cd /opt/opencenter/terraform
terraform plan
terraform apply
```

3. Update Kubespray inventory:
```bash
cd /opt/opencenter/kubespray-master
# Regenerate inventory from Terraform outputs
ansible-playbook -i inventory/mycluster/hosts.yaml --become scale.yml
```

### Backup Procedures

Regular backups:
```bash
# Terraform state
cp /opt/opencenter/terraform/terraform.tfstate /backup/terraform-state-$(date +%Y%m%d).json

# Kubeconfig
cp /opt/opencenter/kubespray-master/inventory/mycluster/artifacts/admin.conf /backup/kubeconfig-$(date +%Y%m%d)

# etcd backup (from control plane)
kubectl exec -n kube-system etcd-k8s-control-1 -- etcdctl snapshot save /tmp/etcd-backup.db
```

## Next Steps

- Configure ingress DNS entries
- Set up backup procedures
- Configure monitoring alerts
- Deploy application workloads
- Review security hardening guide
- Document OpenStack-specific operational procedures
