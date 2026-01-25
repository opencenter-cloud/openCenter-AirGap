# openCenter AirGap Troubleshooting Guide

**doc_type**: reference

**Purpose**: Diagnostic procedures and recovery steps for common failure scenarios.

**Audience**: Field operators and platform engineers troubleshooting deployment issues.

## Log Locations

### Bastion Host

| Component | Log Location | Description |
|:----------|:------------|:------------|
| Deployment | `/opt/opencenter/logs/deployment-<timestamp>.log` | Master deployment script output |
| Deployment Summary | `/opt/opencenter/logs/deployment-summary-<timestamp>.txt` | Phase completion summary |
| Nginx | `podman logs nginx` | Web server logs |
| Registry | `podman logs registry` | Container registry logs |
| Terraform | `/opt/opencenter/terraform/terraform.log` | Infrastructure provisioning |
| Kubespray | `/opt/opencenter/kubespray-master/inventory/mycluster/artifacts/` | Ansible playbook execution |

### Cluster Nodes

| Component | Log Location | Description |
|:----------|:------------|:------------|
| System | `/var/log/syslog` | System-level events |
| Kubelet | `journalctl -u kubelet` | Kubernetes node agent |
| Containerd | `journalctl -u containerd` | Container runtime |
| Pods | `kubectl logs <pod> -n <namespace>` | Application logs |

## Common Failure Modes

### 1. Registry Startup Failure

**Symptoms**:
- `podman ps` shows registry container not running
- `curl http://localhost:35000/v2/_catalog` fails
- Deployment fails at "Phase 2: Bastion setup"

**Diagnostic Steps**:

```bash
# Check if registry container exists
podman ps -a | grep registry

# Check container logs
podman logs registry

# Check port availability
sudo netstat -tlnp | grep 35000
```

**Common Causes**:

#### Port Conflict

Another process using port 35000.

**Solution**:
```bash
# Identify process
sudo lsof -i :35000

# Stop conflicting process or change registry port
# Edit config.sh and rebuild package
```

#### Insufficient Disk Space

Registry data directory full.

**Solution**:
```bash
# Check disk space
df -h /var/lib/registry

# Clean up old images if needed
podman system prune -a -f

# Restart registry
podman restart registry
```

#### Permission Issues

Registry cannot write to data directory.

**Solution**:
```bash
# Check permissions
ls -ld /var/lib/registry

# Fix ownership
sudo chown -R $(id -u):$(id -g) /var/lib/registry

# Restart registry
podman restart registry
```

**Recovery Procedure**:

```bash
# Stop and remove existing container
podman stop registry
podman rm registry

# Re-run setup script
cd /opt/opencenter
./target-scripts/start-registry.sh

# Verify
curl http://localhost:35000/v2/_catalog
```

### 2. Image Push Failure

**Symptoms**:
- `load-push-all-images.sh` fails
- Registry catalog incomplete
- Deployment fails at "Phase 2: Bastion setup"

**Diagnostic Steps**:

```bash
# Check registry logs
podman logs registry | tail -50

# Check disk space
df -h /var/lib/registry

# List images in registry
curl http://localhost:35000/v2/_catalog | jq .
```

**Common Causes**:

#### Disk Space Exhausted

Registry storage full during image push.

**Solution**:
```bash
# Check usage
du -sh /var/lib/registry

# Expand disk or clean up
# Re-run image push
cd /opt/opencenter
./target-scripts/load-push-all-images.sh
```

#### Corrupted Image Tarball

Image tar.gz file corrupted during transfer.

**Solution**:
```bash
# Verify checksums
cd /opt/opencenter/images
sha256sum -c checksums.txt

# Re-transfer corrupted files
# Re-run image push
```

**Recovery Procedure**:

```bash
# Clear registry data
podman stop registry
sudo rm -rf /var/lib/registry/*
podman start registry

# Re-push all images
cd /opt/opencenter
./target-scripts/load-push-all-images.sh
```

### 3. Kubespray Failure - Node Unreachable

**Symptoms**:
- Ansible playbook fails with "Unreachable host"
- SSH connection errors in logs
- Deployment fails at "Phase 4: Cluster bootstrap"

**Diagnostic Steps**:

```bash
# Test SSH connectivity
ssh -v ubuntu@<node-ip> "hostname"

# Check inventory file
cat /opt/opencenter/kubespray-master/inventory/mycluster/hosts.yaml

# Check Ansible logs
tail -100 /opt/opencenter/kubespray-master/inventory/mycluster/artifacts/ansible.log
```

**Common Causes**:

#### SSH Key Not Configured

Bastion cannot authenticate to nodes.

**Solution**:
```bash
# Copy SSH key to nodes
for ip in <node-ips>; do
  ssh-copy-id ubuntu@$ip
done

# Verify
ssh ubuntu@<node-ip> "hostname"
```

#### Firewall Blocking SSH

Node firewall blocks port 22.

**Solution**:
```bash
# On each node
sudo ufw allow 22/tcp
sudo ufw reload

# Or disable firewall temporarily
sudo ufw disable
```

#### Incorrect IP Addresses

Inventory contains wrong IPs.

**Solution**:
```bash
# Verify node IPs
# Bare-metal: check physical network
# OpenStack: terraform output

# Update inventory
vim /opt/opencenter/kubespray-master/inventory/mycluster/hosts.yaml
```

**Recovery Procedure**:

```bash
# Fix connectivity issue
# Re-run Kubespray
cd /opt/opencenter/kubespray-master
source ~/.venv/kubespray/bin/activate
ansible-playbook -i inventory/mycluster/hosts.yaml --become cluster.yml
```

### 4. Kubespray Failure - Package Installation

**Symptoms**:
- Ansible task fails: "Failed to install package"
- Apt or pip errors in logs
- Deployment fails at "Phase 4: Cluster bootstrap"

**Diagnostic Steps**:

```bash
# Check Ansible logs
grep -i "failed" /opt/opencenter/kubespray-master/inventory/mycluster/artifacts/ansible.log

# Check node can reach bastion
ssh ubuntu@<node-ip> "curl http://<bastion-ip>/files/"
ssh ubuntu@<node-ip> "curl http://<bastion-ip>/debs/"
```

**Common Causes**:

#### Offline Repo Not Configured

Nodes not configured to use bastion repositories.

**Solution**:
```bash
# Run offline-repo playbook
cd /opt/opencenter/kubespray-master
ansible-playbook -i inventory/mycluster/hosts.yaml ../playbook/offline-repo.yml

# Verify on node
ssh ubuntu@<node-ip> "cat /etc/apt/sources.list.d/offline.list"
ssh ubuntu@<node-ip> "cat /etc/pip.conf"
```

#### Nginx Not Serving Files

Nginx container not running or misconfigured.

**Solution**:
```bash
# Check nginx
podman ps | grep nginx
curl http://localhost/files/

# Restart if needed
cd /opt/opencenter
./target-scripts/start-nginx.sh
```

**Recovery Procedure**:

```bash
# Ensure bastion services running
cd /opt/opencenter
./target-scripts/setup-all.sh

# Re-run offline-repo playbook
cd /opt/opencenter/kubespray-master
ansible-playbook -i inventory/mycluster/hosts.yaml ../playbook/offline-repo.yml

# Re-run cluster.yml
ansible-playbook -i inventory/mycluster/hosts.yaml --become cluster.yml
```

### 5. FluxCD Reconciliation Failure

**Symptoms**:
- Core services not deploying
- Kustomization shows "Failed" status
- Deployment completes but services missing

**Diagnostic Steps**:

```bash
# Check FluxCD status
kubectl get gitrepositories -n flux-system
kubectl get kustomizations -n flux-system

# Check controller logs
kubectl logs -n flux-system -l app=source-controller
kubectl logs -n flux-system -l app=kustomize-controller

# Check Gitea accessibility
kubectl get pods -n gitea
kubectl logs -n gitea -l app=gitea
```

**Common Causes**:

#### Gitea Not Ready

Gitea pod not running or not accessible.

**Solution**:
```bash
# Check Gitea status
kubectl get pods -n gitea
kubectl describe pod -n gitea -l app=gitea

# Check service
kubectl get svc -n gitea

# Restart if needed
kubectl rollout restart deployment/gitea -n gitea
```

#### Git Repository Not Initialized

FluxCD cannot clone from Gitea.

**Solution**:
```bash
# Check GitRepository resource
kubectl describe gitrepository cluster-config -n flux-system

# Verify repository exists in Gitea
# Access Gitea UI or use API

# Force reconciliation
flux reconcile source git cluster-config
```

#### Image Pull Failures

Core service images not in registry.

**Solution**:
```bash
# Check registry catalog
curl http://<bastion-ip>:35000/v2/_catalog

# Verify images pushed
cd /opt/opencenter
./target-scripts/load-push-all-images.sh

# Check pod events
kubectl describe pod <pod-name> -n <namespace>
```

**Recovery Procedure**:

```bash
# Ensure Gitea running
kubectl get pods -n gitea

# Force FluxCD reconciliation
flux reconcile source git cluster-config
flux reconcile kustomization infrastructure
flux reconcile kustomization platform

# Check status
kubectl get kustomizations -n flux-system
```

### 6. Control Plane Unhealthy

**Symptoms**:
- `kubectl get nodes` shows control plane NotReady
- API server not responding
- Control plane pods CrashLoopBackOff

**Diagnostic Steps**:

```bash
# Check node status
kubectl get nodes

# Check control plane pods
kubectl get pods -n kube-system

# Check specific component
kubectl logs -n kube-system kube-apiserver-<node>
kubectl logs -n kube-system kube-controller-manager-<node>
kubectl logs -n kube-system kube-scheduler-<node>

# Check etcd
kubectl exec -n kube-system etcd-<node> -- etcdctl endpoint health
```

**Common Causes**:

#### etcd Quorum Lost

Insufficient etcd members available.

**Solution**:
```bash
# Check etcd members
kubectl exec -n kube-system etcd-<node> -- etcdctl member list

# Check etcd logs
kubectl logs -n kube-system etcd-<node>

# If member failed, remove and re-add
# Follow etcd recovery procedures
```

#### Certificate Expiration

Kubernetes certificates expired.

**Solution**:
```bash
# Check certificate expiration
ssh ubuntu@<control-plane-node>
sudo kubeadm certs check-expiration

# Renew certificates
sudo kubeadm certs renew all
sudo systemctl restart kubelet
```

#### Insufficient Resources

Control plane node out of memory or disk.

**Solution**:
```bash
# Check node resources
kubectl describe node <control-plane-node>

# SSH to node and check
ssh ubuntu@<control-plane-node>
free -h
df -h
```

**Recovery Procedure**:

```bash
# Re-run Kubespray (idempotent)
cd /opt/opencenter/kubespray-master
source ~/.venv/kubespray/bin/activate
ansible-playbook -i inventory/mycluster/hosts.yaml --become cluster.yml

# If etcd corrupted, restore from backup
# Follow etcd disaster recovery procedures
```

## Log Analysis Techniques

### Search for Errors

```bash
# Deployment logs
grep -i "error" /opt/opencenter/logs/deployment-*.log

# Ansible logs
grep -i "failed" /opt/opencenter/kubespray-master/inventory/mycluster/artifacts/ansible.log

# System logs on node
ssh ubuntu@<node-ip> "sudo journalctl -xe | grep -i error"
```

### Check Ansible Task Failures

```bash
# Find failed tasks
cd /opt/opencenter/kubespray-master
grep "fatal:" inventory/mycluster/artifacts/ansible.log

# Get task details
grep -A 20 "TASK \[failed-task-name\]" inventory/mycluster/artifacts/ansible.log
```

### Check Pod Events

```bash
# Get events for specific pod
kubectl describe pod <pod-name> -n <namespace>

# Get all events in namespace
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# Filter for warnings and errors
kubectl get events -A --field-selector type=Warning
```

### Check Container Logs

```bash
# Current logs
kubectl logs <pod-name> -n <namespace>

# Previous container (if crashed)
kubectl logs <pod-name> -n <namespace> --previous

# Follow logs
kubectl logs -f <pod-name> -n <namespace>

# All containers in pod
kubectl logs <pod-name> -n <namespace> --all-containers
```

## Recovery Procedures Summary

| Component | Recovery Command | Notes |
|:----------|:----------------|:------|
| Bastion Services | `./target-scripts/setup-all.sh` | Idempotent, safe to re-run |
| Terraform | `terraform apply` | Uses existing state |
| Kubespray | `ansible-playbook cluster.yml` | Idempotent, safe to re-run |
| FluxCD | `flux reconcile source git <name>` | Forces reconciliation |
| Individual Service | `kubectl rollout restart deployment/<name>` | Restarts pods |

## Emergency Procedures

### Complete Cluster Reset

**Warning**: Destroys all cluster data.

```bash
cd /opt/opencenter/kubespray-master
source ~/.venv/kubespray/bin/activate
ansible-playbook -i inventory/mycluster/hosts.yaml --become reset.yml
```

### Terraform Infrastructure Destroy

**Warning**: Destroys all VMs (OpenStack only).

```bash
cd /opt/opencenter/terraform
terraform destroy
```

### Bastion Services Reset

```bash
# Stop all containers
podman stop $(podman ps -aq)
podman rm $(podman ps -aq)

# Clear data
sudo rm -rf /var/lib/registry/*
sudo rm -rf /opt/opencenter/nginx-data/*

# Re-run setup
cd /opt/opencenter
./target-scripts/setup-all.sh
```

## Getting Help

### Collect Diagnostic Bundle

```bash
# Create diagnostic archive
tar czf diagnostic-$(date +%Y%m%d-%H%M%S).tar.gz \
  /opt/opencenter/logs/ \
  /opt/opencenter/kubespray-master/inventory/mycluster/artifacts/ \
  /opt/opencenter/terraform/terraform.tfstate

# Include cluster state
kubectl cluster-info dump --output-directory=cluster-dump
tar czf cluster-dump-$(date +%Y%m%d-%H%M%S).tar.gz cluster-dump/
```

### Contact Support

Provide:
- Deployment mode (bare-metal or OpenStack)
- Package version
- Deployment logs
- Error messages
- Steps to reproduce
- Diagnostic bundle
