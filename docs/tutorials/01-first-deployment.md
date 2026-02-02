**doc_type: tutorial**
**audience: Platform Engineers, Field Operators**
**duration: 60 minutes**

# First Deployment

Build and deploy an air-gapped Kubernetes cluster from scratch. You'll create a Zarf package on a connected machine, transfer it to a disconnected environment, and deploy a working cluster.

## What You'll Build

- A Zarf package containing all dependencies for a 3-node Kubernetes cluster
- A bastion host serving local registry and package repositories
- A functional Kubernetes cluster with FluxCD, Gitea, and ingress-nginx

## Prerequisites

**Zone A (Build Host)**:
- Ubuntu 24.04 with internet access
- 100GB free disk space
- Python 3.10+, Git installed
- Zarf CLI installed: `curl -sL https://get.zarf.dev | bash`

**Zone C (Target Environment)**:
- 4 Ubuntu 24.04 nodes (1 bastion + 3 cluster nodes)
- SSH access between bastion and cluster nodes
- 100GB free disk on bastion
- Network connectivity: bastion can reach cluster nodes on ports 22, 6443, 10250

## Step 1: Clone and Configure

On your build host:

```bash
git clone https://github.com/your-org/opencenter-airgap.git
cd opencenter-airgap
```

Review the component manifest:

```bash
cat config/components.yaml
```

This defines what gets packaged. For your first build, use the defaults.

Check pinned versions:

```bash
cat config/versions.env
```

These versions are tested together. Don't change them unless you're troubleshooting a specific issue.

## Step 2: Run the Build

```bash
python3 -m opencenter_build build --config config/components.yaml
```

This takes 30-45 minutes. It will:

1. Clone kubespray-offline
2. Download container images (~15GB)
3. Download OS packages (~8GB)
4. Download Python wheels (~500MB)
5. Download Kubernetes binaries (~2GB)
6. Create Zarf package (~25GB compressed)

Watch for errors. If a download fails, the build will retry automatically.

## Step 3: Verify the Package

```bash
ls -lh dist/
```

You should see:
- `zarf-package-opencenter-airgap-amd64-<version>.tar.zst` (the artifact)
- `zarf-package-opencenter-airgap-amd64-<version>-sbom.json` (bill of materials)
- `zarf-package-opencenter-airgap-amd64-<version>.sha256` (checksum)

Verify integrity:

```bash
zarf package inspect dist/zarf-package-*.tar.zst --sbom
```

Check that the SBOM lists expected components (kubelet, containerd, calico, flux, etc.).

## Step 4: Transfer to Zone C

Copy the package to removable media:

```bash
cp dist/zarf-package-*.tar.zst /media/usb/
```

Physically transport the media to your disconnected environment.

On the bastion host in Zone C:

```bash
cp /media/usb/zarf-package-*.tar.zst /opt/
cd /opt
```

## Step 5: Deploy the Package

On the bastion:

```bash
zarf package deploy zarf-package-*.tar.zst --confirm
```

Zarf will:
1. Extract the package to `/opt/opencenter/`
2. Start local registry on port 5000
3. Start nginx on port 8080 serving packages
4. Load container images into registry
5. Set up apt and pip repositories

This takes 10-15 minutes.

## Step 6: Prepare Cluster Nodes

Create an inventory file on the bastion:

```bash
cat > /opt/opencenter/kubespray/inventory/mycluster/inventory.yml <<EOF
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
    kube_node:
      hosts:
        node1:
        node2:
        node3:
    etcd:
      hosts:
        node1:
    k8s_cluster:
      children:
        kube_control_plane:
        kube_node:
EOF
```

Replace the IPs with your actual node addresses.

Configure nodes to use bastion repositories:

```bash
cd /opt/opencenter/playbook
ansible-playbook -i ../kubespray/inventory/mycluster/inventory.yml offline-repo.yml
```

This configures apt and pip on each node to pull from the bastion instead of the internet.

## Step 7: Deploy Kubernetes

```bash
cd /opt/opencenter/kubespray
ansible-playbook -i inventory/mycluster/inventory.yml cluster.yml
```

This takes 20-30 minutes. Kubespray will:
1. Install container runtime (runc, containerd)
2. Install Kubernetes binaries (kubelet, kubectl, kubeadm)
3. Bootstrap etcd and control plane
4. Join worker nodes
5. Install Calico CNI

## Step 8: Verify the Cluster

On the bastion:

```bash
export KUBECONFIG=/opt/opencenter/kubespray/inventory/mycluster/artifacts/admin.conf
kubectl get nodes
```

Expected output:

```
NAME    STATUS   ROLES           AGE   VERSION
node1   Ready    control-plane   5m    v1.34.3
node2   Ready    <none>          4m    v1.34.3
node3   Ready    <none>          4m    v1.34.3
```

Check that all pods are running:

```bash
kubectl get pods -A
```

You should see pods in namespaces: kube-system, calico-system, flux-system, gitea, ingress-nginx.

## Step 9: Access Gitea

Find the Gitea ingress:

```bash
kubectl get ingress -n gitea
```

Add the hostname to your `/etc/hosts` on a machine that can reach the cluster:

```
192.168.1.101 gitea.local
```

Open `http://gitea.local` in a browser. Default credentials are in `/opt/opencenter/secrets/gitea-admin.txt` on the bastion.

## Check Your Work

Run these checks:

```bash
# All nodes ready
kubectl get nodes | grep -c Ready
# Should output: 3

# Core pods running
kubectl get pods -n kube-system | grep -c Running
# Should be > 10

# FluxCD reconciling
kubectl get kustomizations -n flux-system
# Should show "Applied" status

# Registry accessible from nodes
ssh node1 "curl -s http://bastion-ip:5000/v2/_catalog | jq '.repositories | length'"
# Should output a number > 50
```

## What You Learned

- How to build a Zarf package with all Kubernetes dependencies
- How to transfer and deploy in an air-gapped environment
- How the bastion serves as a local registry and package repository
- How to verify cluster health after deployment

## Next Steps

- Add a custom Helm chart: [Custom Component Tutorial](02-custom-component.md)
- Deploy to OpenStack VMs: [OpenStack Deployment Tutorial](03-openstack-deployment.md)
- Explore component manifest options: [Component Manifest Reference](../reference/component-manifest-schema.md)
- Understand the architecture: [Architecture Overview](../explanation/architecture/architecture-overview.md)

## Troubleshooting

**Build fails with "connection timeout"**: Check firewall rules. See [Firewall Whitelist](../reference/firewall-whitelist.md).

**Zarf deploy fails with "disk space"**: Bastion needs 100GB free. Check with `df -h /opt`.

**Ansible fails with "unreachable host"**: Verify SSH keys are set up. Test with `ssh node1` from bastion.

**Pods stuck in ImagePullBackOff**: Check registry is running on bastion: `curl http://localhost:5000/v2/_catalog`. Verify nodes can reach bastion on port 5000.

For more issues, see [Troubleshooting Reference](../reference/troubleshooting.md).
