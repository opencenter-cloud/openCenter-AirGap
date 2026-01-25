# openCenter AirGap Deployment Runbook - Bare-Metal

**doc_type**: how-to

**Purpose**: Deploy Kubernetes cluster on bare-metal or pre-provisioned hardware in an air-gapped environment (Zone C).

**Audience**: Field operators executing deployments in disconnected environments.

## Prerequisites

### Bastion Host Requirements

- **Operating System**: Ubuntu 24.04 LTS (AMD64)
- **Disk Space**: 100GB free minimum
- **Memory**: 8GB RAM minimum
- **Container Runtime**: Podman installed
- **Network**: Access to target nodes via SSH
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
```

### Target Node Requirements

Each node (control plane and workers):
- **Operating System**: Ubuntu 24.04 LTS (AMD64)
- **Disk Space**: 50GB free minimum
- **Memory**: 4GB RAM minimum (8GB for control plane)
- **CPU**: 2 cores minimum (4 cores for control plane)
- **SSH**: SSH access from bastion with sudo privileges
- **Network**: Connectivity to bastion and other nodes

### Network Requirements

- Bastion can reach all target nodes on port 22 (SSH)
- All nodes can reach bastion on ports 80 and 35000
- All nodes can reach each other (Kubernetes networking)
- No internet connectivity required

## Inventory Preparation

### 1. Create Inventory File

Create `inventory.yaml` with your node topology:

```yaml
all:
  hosts:
    node1:
      ansible_host: 192.168.1.101
      ip: 192.168.1.101
      access_ip: 192.168.1.101
    node2:
      ansible_host: 192.168.1.102
      ip: 192.168.1.102
      access_ip: 192.168.1.102
    node3:
      ansible_host: 192.168.1.103
      ip: 192.168.1.103
      access_ip: 192.168.1.103
    node4:
      ansible_host: 192.168.1.104
      ip: 192.168.1.104
      access_ip: 192.168.1.104
    node5:
      ansible_host: 192.168.1.105
      ip: 192.168.1.105
      access_ip: 192.168.1.105
  children:
    kube_control_plane:
      hosts:
        node1:
        node2:
        node3:
    kube_node:
      hosts:
        node1:
        node2:
        node3:
        node4:
        node5:
    etcd:
      hosts:
        node1:
        node2:
        node3:
    k8s_cluster:
      children:
        kube_control_plane:
        kube_node:
    calico_rr:
      hosts: {}
```

**Topology Notes**:
- Minimum 3 control plane nodes for HA
- Control plane nodes can also be workers (shown above)
- etcd should run on control plane nodes
- Adjust IPs to match your environment

### 2. Verify SSH Access

Test connectivity from bastion to all nodes:

```bash
# Test SSH access
for ip in 192.168.1.101 192.168.1.102 192.168.1.103 192.168.1.104 192.168.1.105; do
  echo "Testing $ip..."
  ssh -o ConnectTimeout=5 deployer@$ip "hostname"
done
```

All nodes should respond with their hostnames.

### 3. Configure SSH Keys

If password authentication is required, set up key-based auth:

```bash
# Generate SSH key (if not exists)
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""

# Copy to all nodes
for ip in 192.168.1.101 192.168.1.102 192.168.1.103 192.168.1.104 192.168.1.105; do
  ssh-copy-id deployer@$ip
done
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
  --mode baremetal \
  --bastion-ip 192.168.1.100 \
  --inventory /opt/inventory.yaml \
  --ssh-user deployer
```

**Parameters**:
- `--mode`: Deployment mode (use `baremetal`)
- `--bastion-ip`: IP address of bastion host
- `--inventory`: Path to inventory file
- `--ssh-user`: SSH user for node access (default: deployer)

Expected duration: 30-60 minutes depending on cluster size.

### 3. Monitor Deployment

The script outputs progress and logs to `/opt/opencenter/logs/deployment-<timestamp>.log`.

Watch for these phases:
```
==> Phase 1: Package verification
==> Phase 2: Bastion setup (setup-all.sh)
==> Phase 3: Inventory generation
==> Phase 4: Cluster bootstrap (Kubespray)
==> Phase 5: Cluster health verification
==> Phase 6: Core services deployment
==> Phase 7: Service readiness verification
```

## Verification

### 1. Check Bastion Services

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

### 2. Check Cluster Status

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
NAME    STATUS   ROLES           AGE   VERSION
node1   Ready    control-plane   10m   v1.30.0
node2   Ready    control-plane   10m   v1.30.0
node3   Ready    control-plane   10m   v1.30.0
node4   Ready    <none>          9m    v1.30.0
node5   Ready    <none>          9m    v1.30.0
```

All nodes should show `Ready` status.

Check control plane components:
```bash
kubectl get pods -n kube-system
```

All pods should be `Running` or `Completed`.

### 3. Check Core Services

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

### 4. Verify Offline Operation

Check that no external connections were made:
```bash
grep -i "external" /opt/opencenter/logs/deployment-*.log
# Expected: No matches
```

## Post-Deployment

### 1. Save Kubeconfig

Copy kubeconfig for external access:
```bash
cp /opt/opencenter/kubespray-master/inventory/mycluster/artifacts/admin.conf ~/kubeconfig
chmod 600 ~/kubeconfig
```

### 2. Access Services

Get ingress endpoints:
```bash
kubectl get ingress -A
```

Access services via ingress (configure DNS or use /etc/hosts).

### 3. Review Deployment Summary

Check the deployment summary:
```bash
cat /opt/opencenter/logs/deployment-summary-*.txt
```

This shows:
- Deployment duration
- Completed phases
- Any warnings or errors
- Service endpoints

## Troubleshooting

### Bastion Service Failures

**Symptom**: Nginx or registry not accessible

**Check**:
```bash
podman ps -a
podman logs nginx
podman logs registry
```

**Solution**:
```bash
# Re-run bastion setup
cd /opt/opencenter
./target-scripts/setup-all.sh
```

### Node Unreachable

**Symptom**: Kubespray fails with "Unreachable host"

**Check**:
```bash
# Test SSH from bastion
ssh deployer@192.168.1.101 "hostname"

# Check inventory file
cat /opt/opencenter/kubespray-master/inventory/mycluster/hosts.yaml
```

**Solution**:
- Verify SSH keys are configured
- Check firewall rules on nodes
- Verify IP addresses in inventory

### Image Pull Failures

**Symptom**: Pods stuck in `ImagePullBackOff`

**Check**:
```bash
kubectl describe pod <pod-name> -n <namespace>
# Look for "Failed to pull image" errors
```

**Solution**:
```bash
# Verify registry accessible from nodes
ssh deployer@192.168.1.101 "curl http://192.168.1.100:35000/v2/_catalog"

# Check containerd configuration
ssh deployer@192.168.1.101 "cat /etc/containerd/config.toml | grep -A5 registry"

# Re-run offline-repo playbook
cd /opt/opencenter/kubespray-master
ansible-playbook -i inventory/mycluster/hosts.yaml ../playbook/offline-repo.yml
```

### Control Plane Unhealthy

**Symptom**: Control plane components not running

**Check**:
```bash
kubectl get pods -n kube-system
kubectl logs -n kube-system kube-apiserver-node1
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
  --mode baremetal \
  --bastion-ip 192.168.1.100 \
  --inventory /opt/inventory.yaml \
  --ssh-user deployer
```

The script detects existing resources and skips completed steps.

### Reset Cluster

To start over completely:

```bash
cd /opt/opencenter/kubespray-master
source ~/.venv/kubespray/bin/activate
ansible-playbook -i inventory/mycluster/hosts.yaml --become reset.yml
```

**Warning**: This destroys the cluster. All data will be lost.

## Log Locations

- **Deployment logs**: `/opt/opencenter/logs/deployment-<timestamp>.log`
- **Kubespray logs**: `/opt/opencenter/kubespray-master/inventory/mycluster/artifacts/`
- **Container logs**: `podman logs <container-name>`
- **Pod logs**: `kubectl logs <pod-name> -n <namespace>`
- **System logs**: `/var/log/syslog` on each node

## Next Steps

- Configure ingress DNS entries
- Set up backup procedures
- Configure monitoring alerts
- Deploy application workloads
- Review security hardening guide
