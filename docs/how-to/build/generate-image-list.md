# Generate openCenter Platform Image List

**doc_type:** how-to

Generate the complete list of container images required by openCenter platform services from gitops-base assets.

## Prerequisites

- Python 3.12+
- gitops-base cloned to `assets/gitops-base`
- PyYAML installed (`pip install pyyaml`)

## Quick Start

Run the automated script:

```bash
./scripts/build/update_opencenter_images.sh
```

This will:
1. Scan gitops-base assets for image references
2. Generate `config/opencenter-images.txt`
3. Copy to `build/kubespray-offline/imagelists/additional_images.txt`

## Manual Generation

### Step 1: Generate Image List

```bash
python3 scripts/build/generate_opencenter_images.py \
    --gitops-base assets/gitops-base \
    --output config/opencenter-images.txt \
    --verbose
```

### Step 2: Review Generated List

```bash
cat config/opencenter-images.txt
```

Expected output:
```
# openCenter Platform Service Images
# Generated from gitops-base assets
# Total images: 137

# Cert-Manager (5 images)
quay.io/jetstack/cert-manager-controller
quay.io/jetstack/cert-manager-webhook
...

# Observability (31 images)
grafana/grafana:10.2.0
grafana/loki:3.5.7
...
```

### Step 3: Copy to kubespray-offline

```bash
cp config/opencenter-images.txt \
    build/kubespray-offline/imagelists/additional_images.txt
```

## Advanced Usage

### Include Source File Comments

Show which files contain each image reference:

```bash
python3 scripts/build/generate_opencenter_images.py \
    --include-sources \
    --output config/opencenter-images-with-sources.txt
```

Output includes source comments:
```
grafana/loki:3.5.7
#   Source: applications/base/services/observability/loki/values.yaml
#   Source: applications/base/services/observability/helm-release.yaml
```

### Custom gitops-base Location

```bash
python3 scripts/build/generate_opencenter_images.py \
    --gitops-base /path/to/gitops-base \
    --output custom-images.txt
```

### Filter by Category

Extract only specific categories:

```bash
# Get only observability images
grep -A 100 "# Observability" config/opencenter-images.txt | \
    grep -v "^#" | \
    grep -v "^$" > observability-images.txt
```

## Image Categories

The generator organizes images into categories:

| Category | Description | Example Images |
|:---------|:------------|:---------------|
| FluxCD | GitOps controllers | source-controller, kustomize-controller |
| Gitea | In-cluster Git | gitea/gitea |
| Cert-Manager | Certificate management | cert-manager-controller, cert-manager-webhook |
| Ingress & Gateway | Traffic routing | envoyproxy/gateway, nginx-ingress |
| Identity | Authentication | keycloak/keycloak |
| Observability | Monitoring & logging | prometheus, grafana, loki, tempo |
| Storage | Persistent storage | longhorn, csi-drivers, snapshotter |
| Policy & Security | Governance | kyverno, rbac-manager, sealed-secrets |
| Backup | Disaster recovery | velero |
| Harbor | Container registry | harbor-core, harbor-portal |
| Headlamp | Kubernetes UI | headlamp-k8s/headlamp |
| Weave GitOps | GitOps UI | wego-app |
| MetalLB | Load balancing | metallb/controller, metallb/speaker |
| Postgres Operator | Database | postgres-operator, spilo |
| Kafka | Messaging | kafka, strimzi |
| Additional | Other services | Various utility images |

## Troubleshooting

### No Images Found

**Symptom:** `Warning: No images found`

**Cause:** gitops-base directory empty or wrong path

**Solution:**
```bash
# Verify gitops-base exists
ls -la assets/gitops-base/applications

# Clone if missing
git clone https://github.com/rackerlabs/genestack.git assets/gitops-base
```

### Missing Categories

**Symptom:** Expected service images not in list

**Cause:** Images not yet in gitops-base or pattern not matched

**Solution:**
1. Check if service is in gitops-base: `find assets/gitops-base -name "*service-name*"`
2. Add manual entries to `config/opencenter-images.txt`
3. Update categorization patterns in `generate_opencenter_images.py`

### Duplicate Images

**Symptom:** Same image listed multiple times with different tags

**Cause:** Multiple versions referenced in gitops-base

**Solution:**
This is expected. Keep all versions to ensure compatibility.

### Invalid Image References

**Symptom:** Non-image values in output (e.g., `name:`, `tag:`)

**Cause:** Regex pattern matched YAML field names

**Solution:**
The script filters these automatically. If any slip through, report as bug.

## Integration with Build Process

### Automated Update

Add to build script:

```bash
# In scripts/build/build.sh
echo "Updating openCenter image list..."
./scripts/build/update_opencenter_images.sh
```

### CI/CD Pipeline

```yaml
# .github/workflows/build.yml
- name: Generate image list
  run: |
    python3 scripts/build/generate_opencenter_images.py \
        --output config/opencenter-images.txt
    
- name: Verify image count
  run: |
    COUNT=$(grep -c "^[^#]" config/opencenter-images.txt)
    if [ "$COUNT" -lt 100 ]; then
      echo "Error: Too few images ($COUNT)"
      exit 1
    fi
```

### Version Tracking

Track image list changes:

```bash
# Commit generated list
git add config/opencenter-images.txt
git commit -m "Update openCenter image list (137 images)"
```

## Best Practices

1. **Regenerate Regularly:** Update list when gitops-base changes
2. **Review Changes:** Check diff before committing
3. **Pin Versions:** Ensure all images have explicit tags
4. **Test Build:** Verify kubespray-offline downloads all images
5. **Document Custom Images:** Add comments for manual additions

## Related Documentation

- [Build Package](build-package.md)
- [openCenter Platform Services](../../reference/opencenter-services.md)
- [Version Pinning](../../reference/configuration/version-pinning.md)
