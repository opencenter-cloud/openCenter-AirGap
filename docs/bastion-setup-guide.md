# Bastion Setup Guide

**doc_type**: how-to

This guide covers bastion host setup for openCenter AirGap deployments.

## Prerequisites

- Ubuntu 24.04 LTS
- 100GB+ free disk space
- Ports 80 and 35000 available
- Root or sudo access

## Setup Process

### Automatic Setup (Recommended)

Deploy the Zarf package. The bastion-setup component runs automatically:

```bash
zarf package deploy openCenter-airgap-*.tar.zst --confirm
```

This executes `setup-all.sh` which:
1. Installs containerd and nerdctl
2. Starts nginx on port 80
3. Configures local apt/pip repositories
4. Creates Python venv at ~/.venv/kubespray
5. Starts registry on port 35000
6. Loads and pushes all images

Expected runtime: 15-25 minutes depending on image count.

### Manual Setup (Troubleshooting)

If automatic setup fails, run components individually:

```bash
cd /opt/opencenter/outputs

# Install container runtime
./target-scripts/setup-container.sh

# Start web server
./target-scripts/start-nginx.sh

# Configure local repositories
./target-scripts/setup-offline.sh

# Setup Python environment
./target-scripts/setup-py.sh

# Start registry
./target-scripts/start-registry.sh

# Load and push images
./target-scripts/load-push-all-images.sh
```

## Verification

### Quick Check

```bash
./scripts/deploy/verify_bastion_services.sh
```

Expected output:
```
[OK] nginx is accessible at http://localhost:80/files/
[OK] registry is accessible at http://localhost:35000/v2/_catalog
[OK] Python venv exists at ~/.venv/kubespray
```

### Comprehensive Validation

```bash
./scripts/deploy/validate_bastion_setup.sh
```

Runs 15 tests covering all components. All tests should pass.

### Manual Verification

**Check nginx**:
```bash
curl http://localhost/files/
curl http://localhost/debs/local/Packages.gz
curl http://localhost/pypi/
```

**Check registry**:
```bash
curl http://localhost:35000/v2/_catalog
```

**Check Python venv**:
```bash
~/.venv/kubespray/bin/python --version
```

**List container images**:
```bash
curl -s http://localhost:35000/v2/_catalog | jq -r '.repositories[]' | head -n 10
```

## Service Management

### Nginx

**Status**:
```bash
sudo nerdctl ps -f name=nginx
```

**Logs**:
```bash
sudo nerdctl logs nginx
```

**Restart**:
```bash
sudo nerdctl restart nginx
```

**Stop**:
```bash
sudo nerdctl stop nginx
```

### Registry

**Status**:
```bash
sudo nerdctl ps -f name=registry
```

**Logs**:
```bash
sudo nerdctl logs registry
```

**Restart**:
```bash
sudo nerdctl restart registry
```

**Check catalog**:
```bash
curl http://localhost:35000/v2/_catalog | jq .
```

## Troubleshooting

### Nginx not accessible

**Symptom**: `curl http://localhost/files/` fails

**Check**:
```bash
sudo nerdctl ps -f name=nginx
sudo nerdctl logs nginx
```

**Fix**:
```bash
cd /opt/opencenter/outputs
./target-scripts/start-nginx.sh
```

### Registry not accessible

**Symptom**: `curl http://localhost:35000/v2/_catalog` fails

**Check**:
```bash
sudo nerdctl ps -f name=registry
sudo nerdctl logs registry
```

**Fix**:
```bash
cd /opt/opencenter/outputs
./target-scripts/start-registry.sh
```

### Port conflicts

**Symptom**: Container fails to start with "address already in use"

**Check**:
```bash
sudo netstat -tlnp | grep ':80\|:35000'
```

**Fix**: Stop conflicting service or change port in config.sh

### Disk space exhausted

**Symptom**: Image push fails with "no space left on device"

**Check**:
```bash
df -h /var/lib/registry
du -sh /var/lib/registry
```

**Fix**: Expand disk or clean up unused images

### Python venv missing

**Symptom**: `~/.venv/kubespray` does not exist

**Fix**:
```bash
cd /opt/opencenter/outputs
./target-scripts/setup-py.sh
```

## Configuration

### Registry Port

Default: 35000

To change, edit `/opt/opencenter/outputs/target-scripts/config.sh`:
```bash
REGISTRY_PORT=35000
```

Then restart registry:
```bash
sudo nerdctl stop registry
sudo nerdctl rm registry
./target-scripts/start-registry.sh
```

### Nginx Port

Default: 80

To change, edit `/opt/opencenter/outputs/target-scripts/config.sh`:
```bash
NGINX_PORT=80
```

Then restart nginx:
```bash
sudo nerdctl stop nginx
sudo nerdctl rm nginx
./target-scripts/start-nginx.sh
```

### Registry Storage

Default: `/var/lib/registry`

To change, edit `/opt/opencenter/outputs/target-scripts/start-registry.sh`:
```bash
REGISTRY_DIR=/var/lib/registry
```

## Service Endpoints

| Service | Port | Endpoint | Purpose |
|---------|------|----------|---------|
| Nginx | 80 | http://localhost/files/ | Binary files |
| Nginx | 80 | http://localhost/debs/ | APT repository |
| Nginx | 80 | http://localhost/pypi/ | PyPI mirror |
| Registry | 35000 | http://localhost:35000/v2/_catalog | Image catalog |

## Next Steps

After bastion setup completes:
1. Verify all services operational
2. Generate Kubespray inventory
3. Run offline-repo.yml playbook on nodes
4. Execute cluster.yml to bootstrap Kubernetes

See deployment runbook for complete workflow.
