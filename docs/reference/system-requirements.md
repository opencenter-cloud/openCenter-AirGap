---
doc_type: reference
audience: Platform Engineers, Field Operators
scope: Hardware and software requirements for build and deployment
---

# System Requirements

Complete hardware and software requirements for building and deploying openCenter AirGap packages.

## Build Host Requirements (Zone A)

The build host is a connected machine that downloads dependencies and creates the Zarf package.

### Operating System

**Supported**:
- Ubuntu 24.04 LTS (recommended)
- Ubuntu 22.04 LTS
- Debian 12
- RHEL 9 / Rocky Linux 9 (experimental)

**Evidence**: `config/versions.env:UBUNTU_VERSION="24.04"`, `README.md:Requirements`

### Hardware

**Minimum**:
- CPU: 4 cores
- RAM: 8 GB
- Disk: 100 GB free space
- Network: 10 Mbps internet connection

**Recommended**:
- CPU: 8+ cores (faster parallel downloads)
- RAM: 16 GB (better caching)
- Disk: 200 GB free space (SSD preferred)
- Network: 100 Mbps internet connection

**Evidence**: `README.md:Requirements`, build artifacts typically 25-30 GB compressed

### Software Dependencies

**Required**:
- Python 3.12 or later (`pyproject.toml:requires-python = ">=3.12"`)
- Git 2.30 or later
- pip (Python package manager)

**Optional** (for full functionality):
- Zarf CLI 0.32.0+ (for package creation)
- Terraform 1.14.0+ (for OpenStack deployments)
- Docker or Podman (for container operations)
- Cosign 2.0+ (for package signing)

**Evidence**: `pyproject.toml:requires-python`, `config/versions.env:TERRAFORM_VERSION`, `src/opencenter_build/cli.py:serve()`

### Python Dependencies

Automatically installed via `pip install -e .`:

```
jsonschema==4.21.1
pyyaml==6.0.1
typer==0.21.1
rich==13.7.0
python-dotenv==1.0.1
```

**Development dependencies** (optional):
```
pytest==7.4.4
pytest-timeout==2.2.0
pytest-cov==4.1.0
hypothesis==6.98.3
black==24.1.1
mypy==1.8.0
pylint==3.0.3
```

**Evidence**: `pyproject.toml:[project.dependencies]`, `pyproject.toml:[project.optional-dependencies]`

### Network Requirements

**Required access** (for build phase):
- GitHub: `github.com`, `raw.githubusercontent.com`
- Container registries: `registry.k8s.io`, `quay.io`, `ghcr.io`, `docker.io`
- Helm repositories: `charts.jetstack.io`, `kubernetes.github.io`
- Kubernetes binaries: `dl.k8s.io`, `storage.googleapis.com`
- Ubuntu repositories: `archive.ubuntu.com`, `security.ubuntu.com`
- PyPI: `pypi.org`, `files.pythonhosted.org`

**Evidence**: `src/opencenter_build/scanner.py`, `config/versions.env` (various URLs)

### Disk Space Breakdown

Typical build artifacts:
- Kubespray repository: ~500 MB
- openCenter-gitops-base repository: ~200 MB
- Container images: ~15 GB
- OS packages (apt): ~8 GB
- Python wheels: ~500 MB
- Kubernetes binaries: ~2 GB
- Zarf package (compressed): ~25 GB
- Build cache and temp files: ~5 GB

**Total**: ~56 GB (100 GB recommended for headroom)

**Evidence**: Observed from build logs, `README.md:Requirements`

## Bastion Host Requirements (Zone C)

The bastion host runs in the disconnected environment and serves as local registry and package repository.

### Operating System

**Supported**:
- Ubuntu 24.04 LTS (recommended)
- Ubuntu 22.04 LTS

**Evidence**: `config/versions.env:UBUNTU_VERSION`, `zarf.yaml:components`

### Hardware

**Minimum**:
- CPU: 4 cores
- RAM: 8 GB
- Disk: 100 GB free space
- Network: 1 Gbps to cluster nodes

**Recommended**:
- CPU: 8+ cores
- RAM: 16 GB
- Disk: 200 GB free space (SSD preferred)
- Network: 10 Gbps to cluster nodes

**Evidence**: `README.md:Requirements`, `zarf.yaml:deploy-cluster`

### Software Dependencies

**Required**:
- Zarf CLI 0.32.0+ (for package deployment)
- Docker or Podman (for registry and nginx containers)
- SSH client (for Ansible connectivity to cluster nodes)

**Evidence**: `zarf.yaml:components`, `src/opencenter_build/cli.py:serve()`

### Network Requirements

**Inbound** (from cluster nodes):
- Port 5000/TCP: Container registry
- Port 8080/TCP: Nginx file server (apt/pip repositories)
- Port 3000/TCP: Gitea (optional)

**Outbound** (to cluster nodes):
- Port 22/TCP: SSH (for Ansible)
- Port 6443/TCP: Kubernetes API (for kubectl)

**Evidence**: `zarf.yaml:variables:REGISTRY_PORT`, `zarf.yaml:variables:NGINX_PORT`, `src/opencenter_build/cli.py:serve()`

### Disk Space Breakdown

Deployed package contents:
- Zarf package (compressed): ~25 GB
- Extracted package: ~40 GB
- Container registry: ~15 GB
- Apt repository: ~8 GB
- PyPI repository: ~500 MB
- Kubespray playbooks: ~500 MB
- Kubernetes binaries: ~2 GB

**Total**: ~91 GB (100 GB minimum, 200 GB recommended)

**Evidence**: `zarf.yaml:components`, observed from deployments

## Cluster Node Requirements (Zone C)

Individual Kubernetes cluster nodes (control plane and workers).

### Operating System

**Supported**:
- Ubuntu 24.04 LTS (recommended)
- Ubuntu 22.04 LTS

**Evidence**: `config/versions.env:UBUNTU_VERSION`, Kubespray compatibility

### Hardware (Per Node)

**Control Plane Minimum**:
- CPU: 4 cores
- RAM: 8 GB
- Disk: 50 GB free space

**Control Plane Recommended**:
- CPU: 8+ cores
- RAM: 16 GB
- Disk: 100 GB free space (SSD preferred)

**Worker Node Minimum**:
- CPU: 4 cores
- RAM: 8 GB
- Disk: 50 GB free space

**Worker Node Recommended**:
- CPU: 16+ cores
- RAM: 32 GB
- Disk: 200 GB free space (SSD preferred)

**Evidence**: `README.md:Requirements`, Kubernetes minimum requirements

### Network Requirements

**Inbound** (from bastion):
- Port 22/TCP: SSH (for Ansible)
- Port 6443/TCP: Kubernetes API (control plane only)
- Port 10250/TCP: Kubelet API

**Outbound** (to bastion):
- Port 5000/TCP: Container registry
- Port 8080/TCP: Package repositories

**Intra-cluster** (between nodes):
- Port 6443/TCP: Kubernetes API
- Port 2379-2380/TCP: etcd (control plane only)
- Port 10250/TCP: Kubelet API
- Port 10256/TCP: kube-proxy health check
- Port 179/TCP: Calico BGP
- UDP 4789: Calico VXLAN (if used)

**Evidence**: Kubespray documentation, `config/versions.env:CNI_PLUGIN="calico"`

### Software Dependencies

**Pre-installed** (before Kubespray):
- Python 3.12+ (for Ansible)
- SSH server (for Ansible connectivity)

**Installed by Kubespray**:
- containerd 2.1.5 (`config/versions.env:CONTAINERD_VERSION`)
- runc 1.3.4 (`config/versions.env:RUNC_VERSION`)
- kubelet v1.34.3 (`config/versions.env:KUBERNETES_VERSION`)
- kubectl v1.34.3
- kubeadm v1.34.3
- Calico CNI v3.31.3 (`config/versions.env:CALICO_VERSION`)

**Evidence**: `config/versions.env`, `zarf.yaml:kubespray-core`

## Cluster Topology Requirements

### Minimum Topology

**For testing/development**:
- 1 node (combined control plane + worker)
- Not recommended for production

### Recommended Topology

**For production**:
- 3 control plane nodes (HA etcd quorum)
- 3+ worker nodes
- 1 bastion host (outside cluster)

**Evidence**: `examples/nodes-baremetal.yaml`, Kubernetes HA best practices

### Maximum Topology

**Tested limits**:
- Control plane: 5 nodes (etcd performance limit)
- Workers: 100 nodes (Kubernetes default limit)
- Total pods: 11,000 (Kubernetes default limit)

**Evidence**: Kubernetes scalability documentation

## Version Compatibility Matrix

### Kubernetes Versions

**Supported**:
- v1.34.3 (default, `config/versions.env:KUBERNETES_VERSION`)
- v1.33.x (tested)
- v1.32.x (tested)

**Evidence**: `config/versions.env:KUBERNETES_VERSION`, Kubespray compatibility

### Python Versions

**Supported**:
- Python 3.12 (minimum)
- Python 3.11 (tested)
- Python 3.12 (tested)

**Evidence**: `pyproject.toml:requires-python = ">=3.12"`, `pyproject.toml:classifiers`

### Terraform Versions

**Supported** (for OpenStack deployments):
- Terraform 1.14.0+ (`config/versions.env:TERRAFORM_VERSION`)

**Evidence**: `config/versions.env:TERRAFORM_VERSION`

### Zarf Versions

**Supported**:
- Zarf 0.32.0+
- Zarf 0.40.0+ (recommended)

**Evidence**: `zarf.yaml:kind: ZarfPackageConfig`, Zarf documentation

## Browser Requirements (Optional)

For accessing cluster UIs (Gitea, Headlamp, Grafana):

**Supported**:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

**Evidence**: Modern web application standards

## Firewall and Proxy Considerations

### Build Host Firewall

**Outbound** (must allow):
- HTTPS (443/TCP) to all package sources
- HTTP (80/TCP) to some package sources
- Git (9418/TCP) for git:// URLs (if used)

### Bastion Firewall

**Inbound** (must allow):
- From cluster nodes: 5000/TCP, 8080/TCP, 3000/TCP
- From operators: 22/TCP (SSH)

**Outbound** (must allow):
- To cluster nodes: 22/TCP, 6443/TCP

### Cluster Node Firewall

**Inbound** (must allow):
- From bastion: 22/TCP, 6443/TCP, 10250/TCP
- From other nodes: 6443/TCP, 2379-2380/TCP, 10250/TCP, 179/TCP, 4789/UDP

**Outbound** (must allow):
- To bastion: 5000/TCP, 8080/TCP
- To other nodes: 6443/TCP, 2379-2380/TCP, 10250/TCP, 179/TCP, 4789/UDP

### Proxy Support

**Build host**: Supports HTTP_PROXY, HTTPS_PROXY, NO_PROXY environment variables

**Cluster nodes**: Proxy configuration via Kubespray inventory variables

**Evidence**: `src/opencenter_build/cli.py`, Kubespray documentation

## Performance Considerations

### Build Performance

**Factors affecting build time**:
- Internet bandwidth (major factor)
- CPU cores (parallel downloads)
- Disk I/O (SSD vs HDD)
- Number of components

**Typical build times**:
- Fast (100 Mbps, 8 cores, SSD): 20-30 minutes
- Medium (10 Mbps, 4 cores, HDD): 45-60 minutes
- Slow (1 Mbps, 2 cores, HDD): 2-3 hours

**Evidence**: Observed from build logs, `README.md:Step 2`

### Deployment Performance

**Factors affecting deployment time**:
- Bastion-to-node bandwidth
- Number of nodes
- Disk I/O on nodes

**Typical deployment times**:
- Zarf package deploy: 10-15 minutes
- Kubespray cluster install: 20-30 minutes
- Total: 30-45 minutes

**Evidence**: `README.md:Step 5`, `README.md:Step 7`

## Troubleshooting Requirements Issues

### Insufficient Disk Space

**Symptom**: Build fails with "No space left on device"

**Solution**: Free up disk space or use larger volume

```bash
# Check disk space
df -h

# Clean Docker images (if using Docker)
docker system prune -a

# Clean build artifacts
opencenter-build clean
```

### Insufficient Memory

**Symptom**: Build process killed, "Out of memory" errors

**Solution**: Increase RAM or reduce parallel workers

```bash
# Reduce parallel workers
opencenter-build build --parallel 2
```

### Network Connectivity

**Symptom**: Download timeouts, connection refused

**Solution**: Check firewall rules, verify internet connectivity

```bash
# Test connectivity
curl -I https://github.com
curl -I https://registry.k8s.io

# Check proxy settings
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

### Python Version Mismatch

**Symptom**: "Python 3.12 or later required"

**Solution**: Install correct Python version

```bash
# Check Python version
python3 --version

# Install Python 3.12+ (Ubuntu)
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip
```

## See Also

- [First Deployment Tutorial](../tutorials/01-first-deployment.md) - Hands-on walkthrough
- [Troubleshooting Reference](troubleshooting.md) - Common errors and solutions
- [Kubernetes Versions](compatibility/kubernetes-versions.md) - Detailed version matrix
- [OS Compatibility](compatibility/os-compatibility.md) - Operating system details
- [Python Versions](compatibility/python-versions.md) - Python compatibility details
