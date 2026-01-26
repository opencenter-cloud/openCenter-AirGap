---
type: tutorial
audience: platform-engineer, field-operator
difficulty: beginner
time: 30
version: 1.0.0
last_updated: 2026-01-25
doc_type: tutorial
---

# Tutorial: Your First Air-Gap Deployment

Build a single-node Kubernetes cluster in a disconnected environment.

## What You'll Build

A working Kubernetes cluster with core services, deployed without internet access. You'll learn the three-zone workflow: build in Zone A, transfer through Zone B, deploy in Zone C.

## What You'll Learn

- How the three-zone model works
- Building an air-gap package
- Deploying without internet
- Verifying cluster health

## Time Required

30 minutes

## Prerequisites

**Build Host (Zone A)**
- Ubuntu 24.04 LTS
- 8GB RAM, 100GB disk
- Internet access
- Podman installed

**Target Node (Zone C)**
- Ubuntu 24.04 LTS  
- 16GB RAM, 100GB disk
- No internet access
- SSH access from build host

**Your Machine**
- SSH client
- USB drive or network file transfer

## Step 1: Set Up Build Environment

On your build host:

```bash
# Clone repository
git clone https://github.com/your-org/opencenter-airgap.git
cd opencenter-airgap

# Create Python environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install pyyaml jinja2 requests
```

Check your setup:

```bash
python --version  # Should show 3.12+
podman --version  # Should show 4.x+
```

## Step 2: Configure Versions

Open `config/versions.env`:

```bash
# These versions are already set correctly
# Just verify they're present
cat config/versions.env
```

You should see:
```
KUBESPRAY_VERSION=master
RUNC_VERSION=1.3.4
CONTAINERD_VERSION=2.1.5
...
```

No changes needed for this tutorial.

## Step 3: Build the Package

Run the build script:

```bash
./scripts/build/build.sh
```

This takes 15-20 minutes. You'll see:
- Asset downloads from internet
- Image pulls
- Package creation
- SBOM generation

When complete:
```
==> Build complete: dist/zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst
```

Check the package:
```bash
ls -lh dist/
# Should show ~5-8GB package file
```

## Step 4: Transfer to Target

Copy the package to your target node:

```bash
# Using SCP (if temporary network access)
scp dist/zarf-package-*.tar.zst deployer@target-node:/opt/

# Or copy to USB drive
cp dist/zarf-package-*.tar.zst /media/usb/
```

On the target node, verify the file:
```bash
ls -lh /opt/zarf-package-*.tar.zst
```

## Step 5: Deploy the Cluster

On the target node (which will act as both bastion and cluster node):

```bash
cd /opt

# Deploy package
zarf package deploy zarf-package-*.tar.zst \
  --set DEPLOYMENT_MODE=baremetal \
  --set BASTION_IP=127.0.0.1 \
  --set SSH_USER=deployer \
  --confirm
```

This takes 10-15 minutes. You'll see:
- Package extraction
- Bastion services starting
- Kubespray execution
- Cluster bootstrap

## Step 6: Verify the Cluster

Check bastion services:
```bash
curl http://localhost/files/
curl http://localhost:35000/v2/_catalog
```

Both should return data.

Check Kubernetes:
```bash
export KUBECONFIG=/opt/opencenter/kubespray-master/inventory/mycluster/artifacts/admin.conf

kubectl get nodes
```

You should see:
```
NAME    STATUS   ROLES           AGE   VERSION
node1   Ready    control-plane   5m    v1.30.0
```

Check pods:
```bash
kubectl get pods -A
```

All pods should be Running or Completed.

## Step 7: Access Services

Check what's running:
```bash
kubectl get pods -n flux-system
kubectl get pods -n gitea
kubectl get pods -n monitoring
```

Get service endpoints:
```bash
kubectl get ingress -A
```

## What You Accomplished

You just:
- Built an air-gap package in Zone A
- Transferred it through Zone B
- Deployed a cluster in Zone C without internet
- Verified all services are running

## What Happened Behind the Scenes

**Zone A (Build)**
- Downloaded K8s binaries, images, packages
- Packaged everything into single artifact
- Generated SBOM for compliance

**Zone B (Transfer)**
- Moved package via secure media
- No network connectivity required

**Zone C (Deploy)**
- Bastion served as local registry and repo
- Kubespray pulled everything from bastion
- FluxCD deployed core services from internal Git

## Next Steps

Try these:

**Deploy an application**
```bash
kubectl create deployment nginx --image=nginx:1.25
kubectl expose deployment nginx --port=80
```

**Check monitoring**
```bash
kubectl port-forward -n monitoring svc/grafana 3000:80
# Open http://localhost:3000
```

**Explore GitOps**
```bash
kubectl get gitrepositories -n flux-system
kubectl get kustomizations -n flux-system
```

## Troubleshooting

**Build fails with "Python 3.12+ required"**

Install Python 3.12:
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv
```

**Deploy fails with "SSH connection refused"**

Check SSH access:
```bash
ssh deployer@target-node hostname
```

Set up SSH keys if needed:
```bash
ssh-copy-id deployer@target-node
```

**Pods stuck in ImagePullBackOff**

Check registry:
```bash
curl http://localhost:35000/v2/_catalog
```

If empty, re-run image loading:
```bash
cd /opt/opencenter/outputs
./target-scripts/load-push-all-images.sh
```

## Learn More

- [OpenStack Deployment Tutorial](02-openstack-deployment.md) - Multi-node HA cluster
- [Architecture Overview](../explanation/architecture/architecture-overview.md) - How it all works
- [Deployment Guide](../how-to/deploy/deploy-baremetal-cluster.md) - Production deployments
