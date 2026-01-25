# kubespray-offline Script Idempotency

doc_type: reference

This document describes the idempotency behavior of kubespray-offline target scripts used in openCenter AirGap deployments.

## Purpose

Idempotency ensures that deployment scripts can be safely re-run without causing errors or duplicate operations. This is critical for recovery scenarios where a deployment may need to be restarted after a failure.

## Script Behavior

### setup-container.sh

**Purpose**: Install containerd runtime and load nginx/registry images.

**Idempotency Behavior**:
- **containerd installation**: The `install-containerd.sh` script checks if containerd is already installed
  - If installed: Skips installation, exits successfully
  - If not installed: Installs containerd from local binaries
- **Image loading**: Uses `nerdctl load` to import images
  - If image already loaded: nerdctl reports "already exists" but exits successfully
  - If image not loaded: Loads image into containerd

**Re-run Safety**: ✓ Safe to re-run
- Will not reinstall containerd if already present
- Will not duplicate images in containerd image store

**Expected Output on Re-run**:
```
==> Load registry, nginx images
INFO[0000] unpacking docker.io/library/registry:2.8.3 (sha256:...)
INFO[0000] done
```

### start-nginx.sh

**Purpose**: Start nginx container to serve files, debs, and pypi repositories.

**Idempotency Behavior**:
- **Container cleanup**: Explicitly stops and removes existing nginx container
  ```bash
  nerdctl container update --restart no nginx
  nerdctl container stop nginx
  nerdctl container rm nginx
  ```
- **Container creation**: Creates fresh nginx container with same configuration
  - Port: 80
  - Volumes: outputs directory mounted as /usr/share/nginx/html
  - Restart policy: always

**Re-run Safety**: ✓ Safe to re-run
- Explicitly designed to be idempotent
- Stops existing container before creating new one
- No risk of port conflicts or duplicate containers

**Expected Output on Re-run**:
```
===> Stop nginx
nginx
nginx
===> Start nginx
<container-id>
```

**Verification**:
```bash
curl http://localhost/files/
curl http://localhost/debs/
curl http://localhost/pypi/
```

### start-registry.sh

**Purpose**: Start private container registry on port 35000.

**Idempotency Behavior**:
- **Container creation**: Attempts to create registry container
  - If container does not exist: Creates and starts container
  - If container already exists: **Fails with error**

**Re-run Safety**: ⚠️ **NOT idempotent by default**
- Will fail if registry container already exists
- Error message: `Error: container name "registry" is already in use`
- Exit code: 1

**Workaround for Re-run**:
```bash
# Stop and remove existing registry container
sudo /usr/local/bin/nerdctl container stop registry
sudo /usr/local/bin/nerdctl container rm registry

# Then re-run start-registry.sh
./start-registry.sh
```

**Expected Output on First Run**:
```
===> Start registry
<container-id>
```

**Expected Output on Re-run** (without cleanup):
```
===> Start registry
Error: container name "registry" is already in use
```

**Verification**:
```bash
curl http://localhost:35000/v2/_catalog
```

**Design Note**: The registry container is intentionally not stopped/removed automatically to preserve registry data. If the registry needs to be restarted, it should be done explicitly.

### load-push-all-images.sh

**Purpose**: Load all container images and push them to local registry.

**Idempotency Behavior**:
- **Image loading**: Uses `nerdctl load` for each tar.gz file
  - If image already loaded: nerdctl reports success (no error)
  - If image not loaded: Loads image
- **Image tagging**: Tags images with local registry prefix
  - If tag already exists: Overwrites existing tag
  - If tag does not exist: Creates new tag
- **Image pushing**: Pushes images to local registry
  - If image already in registry: Overwrites with new push
  - If image not in registry: Pushes new image

**Re-run Safety**: ✓ Safe to re-run
- Will re-load all images (idempotent operation)
- Will re-tag all images (overwrites existing tags)
- Will re-push all images (overwrites existing images in registry)

**Performance Note**: Re-running this script will re-push all images, which can take 10-20 minutes depending on image count and size. However, it will not create duplicate images in the registry.

**Expected Output on Re-run**:
```
===> Loading ./images/docker.io_library_nginx-1.29.2.tar.gz
INFO[0000] unpacking docker.io/library/nginx:1.29.2 (sha256:...)
===> Tag docker.io/library/nginx:1.29.2 -> localhost:35000/nginx:1.29.2
===> Push localhost:35000/nginx:1.29.2
INFO[0000] pushing manifest for localhost:35000/nginx:1.29.2
```

**Verification**:
```bash
# Check image count in registry
curl -s http://localhost:35000/v2/_catalog | jq '.repositories | length'

# List all images
curl -s http://localhost:35000/v2/_catalog | jq '.repositories'
```

### setup-all.sh

**Purpose**: Orchestrate complete bastion setup workflow.

**Workflow**:
1. `setup-container.sh` - Install containerd and load base images
2. `start-nginx.sh` - Start nginx web server
3. `setup-offline.sh` - Configure local apt/pip repositories
4. `setup-py.sh` - Setup Python venv for Ansible
5. `start-registry.sh` - Start private registry
6. `load-push-all-images.sh` - Load and push all images

**Idempotency Behavior**:
- **Partial idempotency**: Most steps are idempotent except `start-registry.sh`
- **Failure point**: Will fail at step 5 if registry container already exists
- **Recovery**: Can be recovered by manually removing registry container

**Re-run Safety**: ⚠️ **Partially idempotent**
- Steps 1-4: Safe to re-run
- Step 5: Will fail if registry exists
- Step 6: Safe to re-run (but time-consuming)

**Recommended Re-run Procedure**:
```bash
# If setup-all.sh fails, check which step failed
# If registry already exists, remove it first
sudo /usr/local/bin/nerdctl container stop registry 2>/dev/null || true
sudo /usr/local/bin/nerdctl container rm registry 2>/dev/null || true

# Then re-run setup-all.sh
./setup-all.sh
```

**Expected Output on Re-run**:
```
=> Running: ./setup-container.sh
[containerd already installed messages]
=> Running: ./start-nginx.sh
===> Stop nginx
===> Start nginx
=> Running: ./setup-offline.sh
[repository configuration messages]
=> Running: ./setup-py.sh
[Python venv setup messages]
=> Running: ./start-registry.sh
Error: container name "registry" is already in use
Failed in : ./start-registry.sh
```

## Summary Table

| Script | Idempotent | Safe to Re-run | Notes |
|:-------|:-----------|:---------------|:------|
| `setup-container.sh` | ✓ Yes | ✓ Yes | Skips if containerd installed |
| `start-nginx.sh` | ✓ Yes | ✓ Yes | Stops existing container first |
| `start-registry.sh` | ✗ No | ⚠️ Manual cleanup required | Fails if container exists |
| `load-push-all-images.sh` | ✓ Yes | ✓ Yes | Re-pushes all images (slow) |
| `setup-all.sh` | ⚠️ Partial | ⚠️ Manual cleanup required | Fails at registry step |

## Best Practices

### Initial Deployment
```bash
# Run setup-all.sh once
cd /opt/opencenter/outputs
./setup-all.sh
```

### Recovery After Failure

**If setup-all.sh fails at registry step**:
```bash
# Remove existing registry container
sudo /usr/local/bin/nerdctl container stop registry 2>/dev/null || true
sudo /usr/local/bin/nerdctl container rm registry 2>/dev/null || true

# Re-run setup-all.sh
./setup-all.sh
```

**If only nginx needs restart**:
```bash
# Just re-run start-nginx.sh (idempotent)
./start-nginx.sh
```

**If images need to be re-pushed**:
```bash
# Re-run load-push-all-images.sh (safe but slow)
./load-push-all-images.sh
```

### Verification After Re-run

```bash
# Check containerd is running
systemctl status containerd

# Check containers are running
sudo /usr/local/bin/nerdctl ps

# Check nginx is serving
curl http://localhost/files/
curl http://localhost/debs/
curl http://localhost/pypi/

# Check registry is accessible
curl http://localhost:35000/v2/_catalog

# Check image count in registry
curl -s http://localhost:35000/v2/_catalog | jq '.repositories | length'
```

## Improvement Recommendations

To make `start-registry.sh` fully idempotent, the script could be modified to:

```bash
#!/bin/bash
source ./config.sh

REGISTRY_IMAGE=registry:${REGISTRY_VERSION}
REGISTRY_DIR=${REGISTRY_DIR:-/var/lib/registry}

if [ ! -e $REGISTRY_DIR ]; then
    sudo mkdir $REGISTRY_DIR
fi

# Check if registry container already exists
if sudo /usr/local/bin/nerdctl ps -a | grep -q "registry"; then
    echo "===> Registry container already exists, removing..."
    sudo /usr/local/bin/nerdctl container stop registry 2>/dev/null || true
    sudo /usr/local/bin/nerdctl container rm registry 2>/dev/null || true
fi

echo "===> Start registry"
sudo /usr/local/bin/nerdctl run -d \
    --network host \
    -e REGISTRY_HTTP_ADDR=0.0.0.0:${REGISTRY_PORT} \
    --restart always \
    --name registry \
    -v $REGISTRY_DIR:/var/lib/registry \
    $REGISTRY_IMAGE || exit 1
```

This change would make `start-registry.sh` behave like `start-nginx.sh` and be fully idempotent.

## Related Requirements

- **Requirement 8.1**: Zarf components detect existing resources before creating new ones
- **Requirement 8.2**: Registry container reuse instead of failing
- **Requirement 8.3**: Repository service reuse instead of failing

## Testing

Run the idempotency test suite:
```bash
sudo tests/integration/test_kubespray_offline_idempotency.sh
```

This test verifies:
- setup-container.sh can be re-run without errors
- start-nginx.sh stops and restarts container correctly
- start-registry.sh behavior with existing container
- load-push-all-images.sh can re-push images
- setup-all.sh overall idempotency behavior
