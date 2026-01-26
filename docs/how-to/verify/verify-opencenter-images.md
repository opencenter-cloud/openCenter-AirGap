# Verify openCenter Platform Service Images

**doc_type**: how-to

This guide shows how to verify that all openCenter platform service images (20+ services) are available in the bastion registry after deployment.

## Prerequisites

- Bastion host with registry running on port 35000
- `curl` and `jq` installed
- Network access to bastion host

## Verify Image Availability

Run the verification script:

```bash
./scripts/deploy/verify_opencenter_images.sh --bastion-ip <BASTION_IP>
```

For localhost:

```bash
./scripts/deploy/verify_opencenter_images.sh
```

## What Gets Verified

The script checks for 100+ images across 25+ services:

- **FluxCD** (6 controllers): source-controller, kustomize-controller, helm-controller, notification-controller, image-reflector-controller, image-automation-controller
- **Gitea** (1 image): In-cluster Git server
- **cert-manager** (5 images): TLS certificate management
- **Gateway API** (2 images): Next-generation ingress
- **Keycloak** (2 images): Identity and access management
- **kube-prometheus-stack** (8 images): Prometheus, Grafana, Alertmanager, operators
- **Loki** (3 images): Log aggregation
- **Tempo** (5 images): Distributed tracing
- **Mimir** (5 images): Metrics storage
- **OpenTelemetry** (3 images): Observability framework
- **Longhorn** (7 images): Distributed block storage
- **vSphere CSI** (8 images): vSphere storage integration
- **OpenStack CSI** (7 images): OpenStack Cinder storage
- **OpenStack CCM** (1 image): Cloud controller manager
- **External Snapshotter** (2 images): Volume snapshot management
- **Kyverno** (5 images): Policy engine
- **OLM** (2 images): Operator lifecycle manager
- **RBAC Manager** (1 image): RBAC automation
- **Velero** (3 images): Backup and disaster recovery
- **Harbor** (10 images): Container registry with security scanning
- **Headlamp** (1 image): Kubernetes dashboard
- **Weave GitOps** (1 image): GitOps dashboard for Flux
- **MetalLB** (4 images): Load balancer for bare-metal
- **Sealed Secrets** (1 image): GitOps-friendly secret management
- **Postgres Operator** (3 images): PostgreSQL cluster management
- **Strimzi Kafka** (3 images): Apache Kafka management
- **Alert Proxy** (1 image): Rackspace managed service

## Output

The script generates:

1. **Console output**: Real-time verification status
2. **Verification report**: Saved to `build/opencenter-images-verification-<timestamp>.txt`
3. **Registry catalog**: Saved to `build/registry-catalog.json`

## Example Output

```
========================================
openCenter Platform Service Images Verification
========================================

[INFO] Checking prerequisites...
[INFO] Prerequisites satisfied
[INFO] Checking registry connectivity...
[INFO] Registry URL: http://192.168.1.100:35000
[INFO] Registry is accessible
[INFO] Fetching registry catalog...
[INFO] Registry contains 127 repositories
[INFO] Catalog saved to: build/registry-catalog.json

========================================
Verifying openCenter Platform Service Images
========================================

[INFO] Checking section: FluxCD Controllers (GitOps Engine)
[INFO] Checking section: Gitea (In-Cluster Git Server)
[INFO] Checking section: cert-manager (TLS Certificate Management)
...

========================================
Verification Summary
========================================

[INFO] Total images checked: 105
[INFO] Found in registry:    105
[INFO] Coverage: 100%
[INFO] Verification report saved to: build/opencenter-images-verification-20260126-143022.txt
[INFO] Verification passed: All images available
```

## Troubleshooting

### Registry Not Accessible

```
[ERROR] Cannot connect to registry at http://localhost:35000
```

**Solution**: Check registry is running:

```bash
curl http://localhost:35000/v2/
```

If not running, restart bastion services:

```bash
./scripts/deploy/verify_bastion_services.sh
```

### Images Missing

```
[WARN] Missing: ghcr.io/fluxcd/source-controller:v2.4.0
```

**Causes**:
1. Images not included in `config/opencenter-images.txt` before build
2. kubespray-offline download failed for some images
3. Image push to registry failed

**Solution**: Check build logs and re-run build with updated image list:

```bash
# Update config/opencenter-images.txt
# Re-run build
./scripts/build/build.sh
```

### Wrong Image Tags

```
[WARN] Missing: quay.io/keycloak/keycloak:26.3.0
```

**Cause**: Image tag in `config/opencenter-images.txt` doesn't match what was downloaded.

**Solution**: Verify image tags match gitops-base helm chart versions:

```bash
grep -r "version:" assets/gitops-base/applications/base/services/keycloak/
```

## Manual Verification

Query registry directly:

```bash
# List all repositories
curl http://localhost:35000/v2/_catalog | jq .

# List tags for specific image
curl http://localhost:35000/v2/source-controller/tags/list | jq .

# Pull image
podman pull localhost:35000/source-controller:v2.4.0
```

## Next Steps

After verification passes:

1. **Document handoff**: All images available for openCenter platform
2. **Deploy services**: openCenter platform handles service deployment via Flux CD
3. **Monitor deployment**: Check Flux CD reconciliation status

## Related Documentation

- [Deploy Bare-Metal Cluster](../deploy/deploy-baremetal-cluster.md)
- [Verify Bastion Services](./verify-bastion-services.md)
- [Troubleshooting Guide](../../reference/troubleshooting.md)
