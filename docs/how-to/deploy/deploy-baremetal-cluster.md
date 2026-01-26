---
type: how-to
audience: field-operator
difficulty: intermediate
version: 1.0.0
last_updated: 2026-01-25
doc_type: how-to
---

# Deploy Bare-Metal Cluster

Deploy Kubernetes on pre-provisioned hardware in air-gapped environment.

## Prerequisites

**Bastion**
- Ubuntu 24.04 LTS
- 100GB disk, 8GB RAM
- Podman installed
- Ports 80, 35000 available

**Nodes**
- Ubuntu 24.04 LTS
- 50GB disk, 4GB RAM (8GB for control plane)
- SSH access from bastion
- Network connectivity to bastion and peers

**Inventory**
- Node IPs and roles defined
- SSH keys configured

## Prepare Inventory

Create `inventory.yaml`:

```yaml
all:
  hosts:
    node1:
      ansible_host: 192.168.1.101
      ip: 192.168.1.101
    node2:
      ansible_host: 192.168.1.102
      ip: 192.168.1.102
    node3:
      ansible_host: 192.168.1.103
      ip: 192.168.1.103
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
    etcd:
      hosts:
        node1:
        node2:
        node3:
    k8s_cluster:
      children:
        kube_control_plane:
        kube_node:
```

Test SSH:
```bash
for ip in 192.168.1.101 192.168.1.102 192.168.1.103; do
  ssh deployer@$ip hostname
done
```

## Transfer Package

```bash
# Copy to bastion
scp zarf-package-*.tar.zst deployer@bastion:/opt/
scp zarf-package-*.tar.zst.sha256 deployer@bastion:/opt/

# Verify integrity
cd /opt
sha256sum -c zarf-package-*.tar.zst.sha256
```

## Deploy

```bash
cd /opt

# Deploy package
zarf package deploy zarf-package-*.tar.zst \
  --set DEPLOYMENT_MODE=baremetal \
  --set BASTION_IP=192.168.1.100 \
  --set SSH_USER=deployer \
  --confirm
```

Duration: 30-60 minutes.

## Verify

```bash
# Check bastion services
curl http://localhost/files/
curl http://localhost:35000/v2/_catalog

# Check cluster
export KUBECONFIG=/opt/opencenter/kubespray-master/inventory/mycluster/artifacts/admin.conf
kubectl get nodes
kubectl get pods -A
```

All nodes should be Ready, all pods Running.

## Troubleshooting

**Bastion services not accessible**
```bash
podman ps -a
cd /opt/opencenter/outputs
./target-scripts/setup-all.sh
```

**Node unreachable**
```bash
ssh deployer@192.168.1.101 hostname
# Fix SSH keys or firewall
```

**Image pull failures**
```bash
# Check registry from node
ssh deployer@192.168.1.101 "curl http://192.168.1.100:35000/v2/_catalog"

# Re-run offline-repo playbook
cd /opt/opencenter/kubespray-master
ansible-playbook -i inventory/mycluster/hosts.yaml ../playbook/offline-repo.yml
```

**Control plane unhealthy**
```bash
kubectl get pods -n kube-system
kubectl logs -n kube-system kube-apiserver-node1

# Re-run Kubespray
cd /opt/opencenter/kubespray-master
source ~/.venv/kubespray/bin/activate
ansible-playbook -i inventory/mycluster/hosts.yaml --become cluster.yml
```

## Recovery

Re-run deployment (idempotent):
```bash
cd /opt/opencenter
./scripts/deploy/deploy.sh \
  --mode baremetal \
  --bastion-ip 192.168.1.100 \
  --inventory /opt/inventory.yaml \
  --ssh-user deployer
```

Reset cluster (destructive):
```bash
cd /opt/opencenter/kubespray-master
source ~/.venv/kubespray/bin/activate
ansible-playbook -i inventory/mycluster/hosts.yaml --become reset.yml
```

## Next Steps

- [Verify cluster health](../verify/verify-cluster-health.md)
- [Add custom services](../extend/add-custom-services.md)
- [Troubleshooting guide](../operate/troubleshoot-deployment.md)
