# Troubleshooting Guide

**doc_type: reference**

Common issues and solutions for openCenter AirGap build system.

## Build Issues

### Network Timeout During Asset Collection

**Symptom**:
```
Error: Network timeout downloading kubernetes-cni
Build failed at step: collect_kubespray_offline
```

**Cause**: Transient network issues or rate limiting.

**Solution**:
```bash
# Resume build after network recovers
opencenter-airgap build --resume
```

Build state persists to `build/state.json`. Resume skips completed steps.

### Insufficient Disk Space

**Symptom**:
```
Error: No space left on device
OSError: [Errno 28] No space left on device
```

**Cause**: Build requires 100GB+ free space.

**Solution**:
```bash
# Check available space
df -h

# Clean previous builds
opencenter-airgap clean

# Remove Docker images/containers
docker system prune -a

# Retry build
opencenter-airgap build
```

### Build State Corrupted

**Symptom**:
```
Error: Invalid state file
JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**Cause**: Corrupted `build/state.json` from interrupted write.

**Solution**:
```bash
# Remove corrupted state
rm build/state.json

# Clean build
opencenter-airgap build --clean
```

### Python Dependency Conflict

**Symptom**:
```
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed
```

**Cause**: Conflicting Python package versions.

**Solution**:
```bash
# Create clean virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .

# Retry build
opencenter-airgap build
```

## Configuration Issues

### Invalid Component Manifest

**Symptom**:
```
Error: Invalid YAML syntax in config/components.yaml
yaml.scanner.ScannerError: mapping values are not allowed here
```

**Cause**: YAML indentation error.

**Solution**:
```bash
# Validate YAML syntax
yamllint config/components.yaml

# Check indentation (2 spaces recommended)
cat -A config/components.yaml | grep "^  "
```

YAML requires consistent indentation. Use 2 spaces, not tabs.

### Missing Required Fields

**Symptom**:
```
Error: Missing required field 'version' in tool 'helm'
ValidationError: 1 validation error for ToolSpec
```

**Cause**: Component manifest missing required fields.

**Solution**:
```bash
# Validate manifest
opencenter-airgap validate --strict

# Check schema
cat docs/reference/component-manifest-schema.md
```

Required fields:
- Tools: `name`, `version`, `url`
- Repositories: `name`, `url`, `ref`
- Charts: `name`, `repo`, `version`

### URL Not Reachable

**Symptom**:
```
Warning: URL not reachable: https://example.com/tool.tar.gz
HTTPError: 404 Client Error: Not Found
```

**Cause**: Invalid URL or network issue.

**Solution**:
```bash
# Test URL manually
curl -I https://example.com/tool.tar.gz

# Validate with upstream check
opencenter-airgap validate --check-upstream

# Fix URL in config/components.yaml
```

## Discovery Issues

### No Images Discovered

**Symptom**:
```
Warning: No images discovered from repositories.kubespray
config/all-images.txt is empty
```

**Cause**: Discovery patterns don't match actual file paths.

**Solution**:
```bash
# List files in repository
find build/kubespray -name "*.yml" | head -20

# Check pattern matches
grep -r "image:" build/kubespray/roles/*/defaults/main.yml

# Adjust patterns in config/components.yaml
```

Example fix:
```yaml
images:
  auto_discover:
    - source: repositories.kubespray
      patterns:
        - "roles/*/defaults/main.yml"  # Add this
        - "roles/*/defaults/main.yaml" # And this
```

### Image Discovery Misses Images

**Symptom**: Expected images not in `config/all-images.txt`.

**Cause**: Images in files not matched by patterns.

**Solution**:
```bash
# Search for missing image
grep -r "missing/image:tag" build/

# Add explicit image
opencenter-airgap add image docker.io/missing/image:tag

# Or expand discovery patterns
```

### Duplicate Images

**Symptom**:
```
Warning: Duplicate image: registry.k8s.io/kube-apiserver:v1.34.3
```

**Cause**: Image in both auto-discovery and explicit additions.

**Solution**:
```bash
# Remove from explicit additions in config/components.yaml
# Auto-discovery will find it
```

## Package Issues

### Zarf Package Creation Failed

**Symptom**:
```
Error: failed to create package
zarf package create failed with exit code 1
```

**Cause**: Invalid `zarf.yaml` or missing artifacts.

**Solution**:
```bash
# Validate Zarf manifest
zarf package create --confirm --dry-run

# Check Zarf logs
cat /tmp/zarf-*.log

# Regenerate manifest
opencenter-airgap generate-manifest
```

### Package Signature Verification Failed

**Symptom**:
```
Error: signature verification failed
cosign verify failed: no matching signatures
```

**Cause**: Package not signed or invalid signature.

**Solution**:
```bash
# Verify package manually
cosign verify --key cosign.pub dist/zarf-package-*.tar.zst

# Deploy without verification (not recommended)
opencenter-airgap serve dist/zarf-package-*.tar.zst --no-verify
```

### Package Size Unexpected

**Symptom**: Package size significantly different from expected.

**Cause**: Auto-discovery found more/fewer images than expected.

**Solution**:
```bash
# Check artifact manifest
cat dist/artifact-manifest.md

# Compare image counts
grep "Image Count:" dist/artifact-manifest.md

# Inspect package contents
zarf package inspect dist/zarf-package-*.tar.zst --sbom
```

## Deployment Issues

### Services Not Accessible

**Symptom**: Cannot access registry or nginx after deployment.

**Cause**: Services not started or port conflicts.

**Solution**:
```bash
# Check service status
docker ps

# Check logs
docker logs <container-id>

# Verify ports
netstat -tlnp | grep -E '(80|5000|3000)'

# Restart services
docker restart <container-id>
```

### Registry Not Serving Images

**Symptom**:
```
Error: failed to pull image: registry:5000/image:tag
Get "http://registry:5000/v2/": dial tcp: connection refused
```

**Cause**: Registry container not running or not accessible.

**Solution**:
```bash
# Check registry container
docker ps | grep registry

# Test registry endpoint
curl http://localhost:5000/v2/_catalog

# Check registry logs
docker logs <registry-container-id>

# Restart registry
docker restart <registry-container-id>
```

### Nginx Not Serving Files

**Symptom**:
```
Error: 404 Not Found
curl http://localhost/files/kubectl
```

**Cause**: Nginx container not running or volume mounts incorrect.

**Solution**:
```bash
# Check nginx container
docker ps | grep nginx

# Check volume mounts
docker inspect <nginx-container-id> | grep -A 10 Mounts

# Test nginx endpoint
curl http://localhost/files/

# Check nginx logs
docker logs <nginx-container-id>
```

### Deployment Fails on Target Nodes

**Symptom**: Kubespray deployment fails on target nodes.

**Cause**: Nodes cannot reach bastion services.

**Solution**:
```bash
# Test connectivity from node
ssh node1
curl http://bastion:5000/v2/_catalog
curl http://bastion/files/kubectl

# Check firewall rules
sudo iptables -L -n

# Verify bastion IP in inventory
cat /opt/opencenter/kubespray/inventory/mycluster/hosts.yml
```

## Performance Issues

### Slow Repository Scanning

**Symptom**: Repository scanning takes >5 minutes.

**Cause**: Sequential processing or low worker count.

**Solution**:
```bash
# Increase concurrency
opencenter-airgap scan --discover-images --concurrency 16

# Check CPU count
nproc

# Default uses all CPUs
opencenter-airgap scan --discover-images
```

### Slow Asset Collection

**Symptom**: Asset collection takes >30 minutes.

**Cause**: Network bandwidth or kubespray-offline performance.

**Solution**:
```bash
# Check network speed
speedtest-cli

# Monitor download progress
tail -f build/kubespray-offline/download.log

# Resume if interrupted
opencenter-airgap build --resume
```

## CLI Issues

### Command Not Found

**Symptom**:
```
bash: opencenter-airgap: command not found
```

**Cause**: Binary not in PATH.

**Solution**:
```bash
# Check installation
which opencenter-airgap

# Add to PATH
export PATH=$PATH:/path/to/binary

# Or install to system location
sudo mv opencenter-airgap /usr/local/bin/
```

### Permission Denied

**Symptom**:
```
bash: ./opencenter-airgap: Permission denied
```

**Cause**: Binary not executable.

**Solution**:
```bash
# Make executable
chmod +x opencenter-airgap

# Retry
./opencenter-airgap version
```

### Import Error (Running from Source)

**Symptom**:
```
ImportError: No module named 'opencenter_build'
ModuleNotFoundError: No module named 'typer'
```

**Cause**: Dependencies not installed.

**Solution**:
```bash
# Install in development mode
pip install -e .

# Or install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import opencenter_build; print(opencenter_build.__version__)"
```

## Verification Issues

### Checksum Mismatch

**Symptom**:
```
Error: Checksum mismatch for kubectl
Expected: a1b2c3d4...
Got: e5f6g7h8...
```

**Cause**: File corrupted during transfer or tampering.

**Solution**:
```bash
# Re-download artifact
rm build/kubespray-offline/outputs/files/kubectl
opencenter-airgap build --resume

# Verify package integrity
opencenter-airgap verify dist/zarf-package-*.tar.zst
```

### Manifest Comparison Failed

**Symptom**:
```
Error: Artifact manifest does not match package contents
Missing artifacts: 3
Extra artifacts: 1
```

**Cause**: Package modified after manifest generation.

**Solution**:
```bash
# Rebuild package
opencenter-airgap build --clean

# Verify new package
opencenter-airgap verify dist/zarf-package-*.tar.zst \
  --manifest dist/artifact-manifest.json
```

## Getting Help

### Enable Verbose Logging

```bash
# Verbose output
opencenter-airgap build --verbose

# JSON logs for parsing
opencenter-airgap build --json > build.log
```

### Check Logs

```bash
# Build logs
cat build/build.log

# Zarf logs
cat /tmp/zarf-*.log

# Docker logs
docker logs <container-id>
```

### Report Issues

Include:
- Command executed
- Error message
- `opencenter-airgap version` output
- Relevant logs
- `config/components.yaml` (if applicable)

File issues: https://github.com/rackerlabs/opencenter-airgap/issues
