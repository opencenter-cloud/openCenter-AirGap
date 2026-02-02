**doc_type: reference**

# Troubleshooting

Common errors and solutions.

## Build Phase

### Connection Timeout During Download

**Symptom**: `ERROR [network] Failed to download: connection timeout`

**Causes**:
- Firewall blocking outbound HTTPS
- Proxy not configured
- Rate limiting from upstream

**Solutions**:

Check firewall rules:
```bash
curl -I https://registry.k8s.io
curl -I https://github.com
```

Configure proxy if needed:
```bash
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
opencenter-build build --config components.yaml
```

Add retry with backoff (automatic in v1.1.0+):
```bash
opencenter-build build --config components.yaml --retry 5 --backoff exponential
```

See [Firewall Whitelist](firewall-whitelist.md) for required endpoints.

### Disk Space Exhausted

**Symptom**: `ERROR [build] No space left on device`

**Check usage**:
```bash
df -h build/ dist/
du -sh build/* | sort -h
```

**Solutions**:

Clean previous builds:
```bash
opencenter-build build --clean
```

Use external volume:
```bash
opencenter-build build --work-dir /mnt/large-disk/build --output-dir /mnt/large-disk/dist
```

Remove intermediate files after successful build (automatic):
```bash
rm -rf build/kubespray-offline/outputs/cache
```

### Image Pull Fails with Digest Mismatch

**Symptom**: `ERROR [images] Digest mismatch for nginx:1.25.0`

**Cause**: Upstream image was updated with same tag (mutable tag).

**Solution**:

Update digest in manifest:
```bash
# Get current digest
skopeo inspect docker://docker.io/library/nginx:1.25.0 | jq -r '.Digest'

# Update components.yaml
- name: nginx
  type: image
  image: docker.io/library/nginx:1.25.0
  digest: sha256:NEW_DIGEST_HERE
```

Or remove digest to pull by tag (not recommended for production):
```yaml
- name: nginx
  type: image
  image: docker.io/library/nginx:1.25.0
  # digest removed
```

### Validation Error: Invalid Component Name

**Symptom**: `ERROR [validation] Component name 'My_Component' is invalid`

**Rule**: Names must be lowercase alphanumeric with hyphens, start with letter.

**Fix**:
```yaml
# Bad
- name: My_Component

# Good
- name: my-component
```

### SBOM Generation Fails

**Symptom**: `ERROR [sbom] Failed to generate SBOM: syft not found`

**Solution**:

Install syft:
```bash
curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin
```

Or skip SBOM (not recommended):
```bash
opencenter-build build --skip-sbom
```

## Deploy Phase

### Zarf Deploy Fails: Package Corrupted

**Symptom**: `ERROR: failed to extract package: unexpected EOF`

**Verify integrity**:
```bash
sha256sum -c zarf-package-*.sha256
```

If checksum fails, package was corrupted during transfer. Re-copy from source.

### Registry Fails to Start

**Symptom**: `ERROR: registry container exited with code 1`

**Check logs**:
```bash
podman logs registry
```

**Common causes**:

Port 5000 already in use:
```bash
lsof -i :5000
# Kill conflicting process or change port
```

Insufficient disk space:
```bash
df -h /opt/opencenter
```

Permission denied:
```bash
sudo chown -R $(whoami):$(whoami) /opt/opencenter/images
```

### Nginx Fails to Serve Packages

**Symptom**: `curl http://localhost:8080/debs/ returns 404`

**Check nginx status**:
```bash
systemctl status nginx-opencenter
journalctl -u nginx-opencenter -n 50
```

**Verify files exist**:
```bash
ls -la /opt/opencenter/debs/
```

**Check nginx config**:
```bash
cat /etc/nginx/sites-enabled/opencenter.conf
```

Expected:
```nginx
server {
    listen 8080;
    root /opt/opencenter;
    autoindex on;
}
```

Restart nginx:
```bash
sudo systemctl restart nginx-opencenter
```

### Ansible Fails: Unreachable Host

**Symptom**: `UNREACHABLE! => {"changed": false, "msg": "Failed to connect to the host via ssh"}`

**Test SSH manually**:
```bash
ssh -i ~/.ssh/id_rsa user@node1
```

**Common fixes**:

Add SSH key to agent:
```bash
eval $(ssh-agent)
ssh-add ~/.ssh/id_rsa
```

Update inventory with correct user:
```yaml
all:
  hosts:
    node1:
      ansible_host: 192.168.1.101
      ansible_user: ubuntu  # Add this
      ansible_ssh_private_key_file: ~/.ssh/id_rsa  # Add this
```

Disable host key checking (first run only):
```bash
export ANSIBLE_HOST_KEY_CHECKING=False
ansible-playbook -i inventory.yml cluster.yml
```

### Kubespray Fails: Package Not Found

**Symptom**: `E: Unable to locate package kubelet`

**Cause**: Nodes not configured to use bastion repos.

**Fix**:

Run offline-repo playbook:
```bash
cd /opt/opencenter/playbook
ansible-playbook -i ../kubespray/inventory/mycluster/inventory.yml offline-repo.yml
```

Verify apt sources on node:
```bash
ssh node1 "cat /etc/apt/sources.list.d/opencenter.list"
```

Expected:
```
deb [trusted=yes] http://BASTION_IP:8080/debs/ubuntu jammy main
```

Test package availability:
```bash
ssh node1 "apt-cache policy kubelet"
```

### Pods Stuck in ImagePullBackOff

**Symptom**: `kubectl get pods shows ImagePullBackOff`

**Check containerd config on node**:
```bash
ssh node1 "cat /etc/containerd/config.toml | grep registry"
```

Expected:
```toml
[plugins."io.containerd.grpc.v1.cri".registry.mirrors."docker.io"]
  endpoint = ["http://BASTION_IP:5000"]
```

**Verify registry is reachable**:
```bash
ssh node1 "curl http://BASTION_IP:5000/v2/_catalog"
```

**Check image exists in registry**:
```bash
curl http://BASTION_IP:5000/v2/_catalog | jq '.repositories'
```

**Restart containerd on node**:
```bash
ssh node1 "sudo systemctl restart containerd"
```

### FluxCD Fails to Reconcile

**Symptom**: `kubectl get kustomizations shows "reconciliation failed"`

**Check Flux logs**:
```bash
kubectl logs -n flux-system deploy/source-controller
kubectl logs -n flux-system deploy/kustomize-controller
```

**Common causes**:

Gitea not reachable:
```bash
kubectl get svc -n gitea
curl http://gitea.gitea.svc.cluster.local:3000
```

Git credentials missing:
```bash
kubectl get secret -n flux-system flux-system
```

Kustomization syntax error:
```bash
flux reconcile kustomization flux-system --with-source
```

## Verification Phase

### SBOM Validation Fails

**Symptom**: `ERROR [verify] SBOM validation failed: missing components`

**Inspect SBOM**:
```bash
jq '.artifacts[] | select(.name == "kubectl")' zarf-package-*-sbom.json
```

**Regenerate SBOM**:
```bash
opencenter-build build --config components.yaml --force-sbom
```

### Signature Verification Fails

**Symptom**: `ERROR [verify] Signature verification failed: invalid signature`

**Check public key**:
```bash
cat ~/.opencenter/cosign.pub
```

**Verify manually with cosign**:
```bash
cosign verify --key ~/.opencenter/cosign.pub zarf-package-*.tar.zst
```

**Re-sign package** (if you have private key):
```bash
cosign sign --key ~/.opencenter/cosign.key zarf-package-*.tar.zst
```

## Performance Issues

### Build Takes Too Long

**Symptom**: Build exceeds 60 minutes

**Profile build**:
```bash
opencenter-build build --config components.yaml --profile
```

**Common bottlenecks**:

Network downloads (30-40 minutes expected):
- Use faster network
- Enable parallel downloads: `--parallel 8`
- Use local mirror for common images

Image compression (5-10 minutes expected):
- Use faster CPU
- Reduce compression level: `--compression-level 6` (default: 9)

SBOM generation (2-5 minutes expected):
- Skip for development builds: `--skip-sbom`

### Deploy Takes Too Long

**Symptom**: Kubespray exceeds 45 minutes

**Enable Ansible profiling**:
```bash
export ANSIBLE_CALLBACK_WHITELIST=profile_tasks
ansible-playbook -i inventory.yml cluster.yml
```

**Common bottlenecks**:

Serial node processing:
- Increase batch size in kubespray config: `serial: 10`

Slow package installation:
- Verify bastion network bandwidth
- Check disk I/O: `iostat -x 1`

## Recovery Procedures

### Resume Failed Build

```bash
opencenter-build build --config components.yaml --resume
```

State is saved in `build/.state.json`. Delete to start fresh.

### Rollback Failed Deployment

```bash
# On bastion
cd /opt/opencenter/kubespray
ansible-playbook -i inventory/mycluster/inventory.yml reset.yml

# Clean node state
ansible -i inventory/mycluster/inventory.yml all -m shell -a "rm -rf /etc/kubernetes /var/lib/kubelet /var/lib/etcd"
```

### Recover from Bastion Failure

If bastion loses power during deployment:

1. Restart services:
```bash
sudo systemctl start registry-opencenter
sudo systemctl start nginx-opencenter
```

2. Verify services:
```bash
curl http://localhost:5000/v2/_catalog
curl http://localhost:8080/debs/
```

3. Resume Kubespray:
```bash
cd /opt/opencenter/kubespray
ansible-playbook -i inventory/mycluster/inventory.yml cluster.yml
```

Kubespray is idempotent. Re-running is safe.

## Getting Help

**Check logs**:
- Build: `build.log`
- Deploy: `/opt/opencenter/logs/deploy.log`
- Kubespray: `/opt/opencenter/kubespray/inventory/mycluster/artifacts/ansible.log`

**Enable debug logging**:
```bash
opencenter-build --log-level DEBUG build --config components.yaml
```

**Report issues**:
Include:
- `build.log` or relevant log excerpt
- `components.yaml`
- Output of `opencenter-build --version`
- OS version: `lsb_release -a`

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for issue reporting guidelines.
