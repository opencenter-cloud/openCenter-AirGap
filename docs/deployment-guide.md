# Deployment Guide

doc_type: how-to

## Purpose

Deploy a Kubernetes cluster in an air-gapped environment using the openCenter AirGap package. This guide covers both automated and manual deployment methods.

## Prerequisites

### Bastion Host
- Ubuntu 24.04 LTS
- 100GB+ free disk space
- Zarf package deployed
- Bastion services running:
  - Nginx on port 80 (serving files, debs, pypi)
  - Registry on port 35000 (serving container images)

### Target Nodes
- Ubuntu 24.04 LTS
- SSH access from bastion
- Sudo privileges for deployment user
- Network connectivity to bastion
- Minimum 2 CPU, 4GB RAM per node

### Node List File

Create a YAML or JSON file describing your cluster topology:

```yaml
# nodes.yaml
control_plane:
  - hostname: control-01
    ip: 192.168.1.10
  - hostname: control-02
    ip: 192.168.1.11
  - hostname: control-03
    ip: 192.168.1.12

workers:
  - hostname: worker-01
    ip: 192.168.1.20
  - hostname: worker-02
    ip: 192.168.1.21
```

## Automated Deployment (Recommended)

The main deployment script orchestrates all phases automatically.

### Basic Usage

```bash
/opt/opencenter/scripts/deploy.sh \
  --mode baremetal \
  --bastion-ip 192.168.1.5 \
  --nodes nodes.yaml
```

### With Custom Options

```bash
/opt/opencenter/scripts/deploy.sh \
  --mode baremetal \
  --bastion-ip 192.168.1.5 \
  --nodes nodes.yaml \
  --cluster-name production \
  --ssh-user deployer
```

### Deployment Phases

The script executes five phases:

1. **Validate Prerequisites**
   - Check installation directory
   - Verify deployment scripts
   - Test bastion services (nginx, registry)

2. **Generate Inventory**
   - Parse node list file
   - Generate Kubespray inventory
   - Create offline.yml configuration

3. **Configure Nodes**
   - Run offline-repo.yml playbook
   - Configure apt to use bastion
   - Verify configuration on all nodes

4. **Deploy Cluster**
   - Extract Kubespray
   - Install Ansible dependencies
   - Run cluster.yml playbook (20-30 minutes)
   - Export kubeconfig

5. **Verify Cluster**
   - Check node status
   - List system pods
   - Display summary

### Skip Phases

Skip specific phases if already completed:

```bash
# Skip inventory generation (use existing)
/opt/opencenter/scripts/deploy.sh \
  --mode baremetal \
  --bastion-ip 192.168.1.5 \
  --skip-inventory

# Skip offline configuration (already done)
/opt/opencenter/scripts/deploy.sh \
  --mode baremetal \
  --bastion-ip 192.168.1.5 \
  --skip-offline-config

# Only deploy cluster (inventory and offline config done)
/opt/opencenter/scripts/deploy.sh \
  --mode baremetal \
  --bastion-ip 192.168.1.5 \
  --skip-inventory \
  --skip-offline-config
```

## Manual Deployment

For more control, execute each phase manually.

### Phase 1: Generate Inventory

```bash
python3 /opt/opencenter/scripts/generate_inventory_baremetal.py \
  --nodes nodes.yaml \
  --bastion-ip 192.168.1.5 \
  --cluster-name mycluster \
  --output-dir /opt/opencenter/kubespray/inventory
```

Verify:
```bash
ls /opt/opencenter/kubespray/inventory/mycluster/
# Should show: hosts.yaml, group_vars/all/offline.yml
```

### Phase 2: Configure Nodes

```bash
/opt/opencenter/scripts/configure_nodes_offline.sh \
  --bastion-ip 192.168.1.5 \
  --inventory-path /opt/opencenter/kubespray/inventory/mycluster
```

Verify:
```bash
# Check offline.list on a node
ansible -i /opt/opencenter/kubespray/inventory/mycluster/hosts.yaml worker-01 \
  -m shell -a "cat /etc/apt/sources.list.d/offline.list" --become
```

### Phase 3: Deploy Cluster

#### Option A: Using deploy_kubespray.sh (Recommended)

```bash
/opt/opencenter/scripts/deploy_kubespray.sh \
  --mode baremetal \
  --bastion-ip 192.168.1.5 \
  --nodes nodes.yaml \
  --cluster-name mycluster
```

This script automates:
- Extracting Kubespray tarball
- Activating Python venv
- Installing Ansible dependencies
- Copying inventory structure
- Generating hosts.yaml
- Running offline-repo.yml playbook
- Executing cluster.yml playbook
- Exporting kubeconfig

#### Option B: Manual Step-by-Step

```bash
# Extract Kubespray
cd /opt/opencenter/outputs
./target-scripts/extract-kubespray.sh

# Activate Python venv
source ~/.venv/kubespray/bin/activate

# Install Ansible
cd kubespray-master
pip install -r requirements.txt

# Copy inventory structure
cp -r inventory/sample inventory/mycluster

# Copy generated inventory files
cp /opt/opencenter/kubespray/inventory/mycluster/hosts.yaml inventory/mycluster/
cp /opt/opencenter/kubespray/inventory/mycluster/group_vars/all/offline.yml inventory/mycluster/group_vars/all/

# Run offline-repo.yml playbook
ansible-playbook \
  -i inventory/mycluster/hosts.yaml \
  ../playbook/offline-repo.yml \
  --become

# Run cluster.yml playbook
ansible-playbook \
  -i inventory/mycluster/hosts.yaml \
  --become \
  --become-user=root \
  cluster.yml
```

### Phase 4: Export Kubeconfig

If using deploy_kubespray.sh, kubeconfig is exported automatically. Otherwise:

```bash
mkdir -p ~/.kube
cp /opt/opencenter/outputs/kubespray-master/inventory/mycluster/artifacts/admin.conf ~/.kube/config
chmod 600 ~/.kube/config
```

### Phase 5: Verify Cluster

```bash
kubectl get nodes
kubectl get pods -A
```

## Verification

### Check Node Status

All nodes should be Ready:
```bash
kubectl get nodes
# NAME         STATUS   ROLES           AGE   VERSION
# control-01   Ready    control-plane   10m   v1.34.3
# control-02   Ready    control-plane   10m   v1.34.3
# control-03   Ready    control-plane   10m   v1.34.3
# worker-01    Ready    <none>          9m    v1.34.3
# worker-02    Ready    <none>          9m    v1.34.3
```

### Check System Pods

All system pods should be Running:
```bash
kubectl get pods -A
# NAMESPACE     NAME                                 READY   STATUS    RESTARTS   AGE
# kube-system   calico-node-xxxxx                    1/1     Running   0          8m
# kube-system   coredns-xxxxx                        1/1     Running   0          8m
# kube-system   etcd-control-01                      1/1     Running   0          9m
# kube-system   kube-apiserver-control-01            1/1     Running   0          9m
# kube-system   kube-controller-manager-control-01   1/1     Running   0          9m
# kube-system   kube-proxy-xxxxx                     1/1     Running   0          8m
# kube-system   kube-scheduler-control-01            1/1     Running   0          9m
```

### Check Cluster Info

```bash
kubectl cluster-info
# Kubernetes control plane is running at https://192.168.1.10:6443
# CoreDNS is running at https://192.168.1.10:6443/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy
```

## Troubleshooting

### Deployment fails at "Validate Prerequisites"

**Symptom**: Script exits with "Installation directory not found"

**Fix**:
```bash
# Verify Zarf package was deployed
ls /opt/opencenter/
# Should contain: outputs/, scripts/, kubespray/, etc.

# If missing, deploy Zarf package first
zarf package deploy zarf-package-*.tar.zst --confirm
```

### Deployment fails at "Generate Inventory"

**Symptom**: "Nodes file not found" or "Invalid YAML"

**Fix**:
```bash
# Verify nodes file exists and is valid
cat nodes.yaml

# Test YAML syntax
python3 -c "import yaml; yaml.safe_load(open('nodes.yaml'))"

# Check file path is correct
ls -la nodes.yaml
```

### Deployment fails at "Configure Nodes"

**Symptom**: "Some nodes are not reachable"

**Fix**:
```bash
# Test SSH connectivity
ssh deployer@192.168.1.20

# Test Ansible connectivity
ansible -i /opt/opencenter/kubespray/inventory/mycluster/hosts.yaml all -m ping

# Check SSH keys
ls -la ~/.ssh/
# Ensure private key has correct permissions (600)
```

### Deployment fails at "Deploy Cluster"

**Symptom**: Ansible playbook fails with package installation errors

**Fix**:
```bash
# Verify nodes can reach bastion apt repository
ansible -i inventory/mycluster/hosts.yaml all \
  -m shell -a "apt-get update" --become

# Check bastion nginx is serving packages
curl http://192.168.1.5/debs/local/Packages.gz

# Verify offline.list is configured
ansible -i inventory/mycluster/hosts.yaml all \
  -m shell -a "cat /etc/apt/sources.list.d/offline.list" --become
```

### Cluster deployed but nodes not Ready

**Symptom**: `kubectl get nodes` shows NotReady status

**Fix**:
```bash
# Check node logs
kubectl describe node worker-01

# Check kubelet status on node
ssh worker-01 "sudo systemctl status kubelet"

# Check container runtime
ssh worker-01 "sudo crictl ps"

# Verify CNI plugin
kubectl get pods -n kube-system | grep calico
```

### Cannot pull images from registry

**Symptom**: Pods stuck in ImagePullBackOff

**Fix**:
```bash
# Verify registry is accessible from nodes
ssh worker-01 "curl http://192.168.1.5:35000/v2/_catalog"

# Check containerd configuration
ssh worker-01 "sudo cat /etc/containerd/config.toml | grep registry"

# Verify images are in registry
curl http://192.168.1.5:35000/v2/_catalog | jq .
```

## Recovery

### Re-run Failed Deployment

The deployment script is idempotent. Re-run with the same parameters:

```bash
/opt/opencenter/scripts/deploy.sh \
  --mode baremetal \
  --bastion-ip 192.168.1.5 \
  --nodes nodes.yaml
```

### Re-run Specific Phase

Skip completed phases:

```bash
# Re-run only cluster deployment
/opt/opencenter/scripts/deploy.sh \
  --mode baremetal \
  --bastion-ip 192.168.1.5 \
  --skip-inventory \
  --skip-offline-config
```

### Reset Cluster

To start over:

```bash
# Run Kubespray reset playbook
cd /opt/opencenter/outputs/kubespray-master
source ~/.venv/kubespray/bin/activate

ansible-playbook \
  -i /opt/opencenter/kubespray/inventory/mycluster/hosts.yaml \
  --become \
  reset.yml

# Then re-run deployment
/opt/opencenter/scripts/deploy.sh \
  --mode baremetal \
  --bastion-ip 192.168.1.5 \
  --nodes nodes.yaml
```

## Next Steps

After successful deployment:

1. **Deploy Core Services**
   - Gitea (in-cluster Git server)
   - FluxCD (GitOps operator)
   - cert-manager (certificate management)
   - ingress-nginx (ingress controller)
   - Keycloak (identity management)
   - kube-prometheus-stack (monitoring)

2. **Configure Networking**
   - Set up load balancer for control plane
   - Configure ingress for services
   - Set up DNS for cluster services

3. **Set Up Monitoring**
   - Access Grafana dashboards
   - Configure Prometheus alerts
   - Set up log aggregation

4. **Secure Cluster**
   - Configure RBAC policies
   - Set up network policies
   - Enable audit logging
   - Configure pod security standards

## Logs and Artifacts

Deployment logs and artifacts are stored at:

- **Ansible logs**: `/opt/opencenter/outputs/kubespray-master/ansible.log`
- **Kubespray artifacts**: `/opt/opencenter/kubespray/inventory/mycluster/artifacts/`
- **Kubeconfig**: `~/.kube/config` or `/opt/opencenter/kubespray/inventory/mycluster/artifacts/admin.conf`
- **Deployment script logs**: stdout (redirect to file if needed)

## Environment Variables

Set these to avoid passing flags:

```bash
export DEPLOYMENT_MODE=baremetal
export BASTION_IP=192.168.1.5
export SSH_USER=deployer
export CLUSTER_NAME=mycluster
export INSTALL_PATH=/opt/opencenter

# Then run without flags
/opt/opencenter/scripts/deploy.sh --nodes nodes.yaml
```
