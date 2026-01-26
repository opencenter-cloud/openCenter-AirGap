# Firewall Whitelist for openCenter AirGap Build

**doc_type:** reference

Complete list of URLs required for building the openCenter AirGap package in Zone A (Factory/Connected Environment).

## Overview

The build system requires internet access to download:
- Container images from registries
- Git repositories (Kubespray, kubespray-offline, gitops-base)
- Kubernetes binaries
- Python packages (PyPI)
- System packages (apt/deb repositories)
- Terraform providers

## Container Registries

### Primary Registries

```
# Kubernetes Official Registry
registry.k8s.io
k8s.gcr.io

# Google Container Registry
gcr.io
*.gcr.io

# GitHub Container Registry
ghcr.io

# Docker Hub
docker.io
registry-1.docker.io
index.docker.io
auth.docker.io
production.cloudflare.docker.com

# Quay.io
quay.io

# Grafana
grafana.com
docker.grafana.com
```

### Specific Service Registries

```
# Harbor
goharbor.io

# Bitnami
bitnami.com

# Zalando (Postgres Operator)
registry.opensource.zalan.do

# VMware/Broadcom (vSphere CSI)
gcr.io/cloud-provider-vsphere

# OpenStack
registry.k8s.io/provider-os

# Headlamp
headlamp-k8s.github.io

# Envoy
docker.io/envoyproxy

# Grafana Labs
grafanalabs-global

# Apache
docker.io/apache
```

## Git Repositories

### Required Repositories

```
# GitHub
github.com
api.github.com
raw.githubusercontent.com
codeload.github.com

# Specific repositories
github.com/kubernetes-sigs/kubespray
github.com/kubespray-offline/kubespray-offline
github.com/rackerlabs/genestack
github.com/rpc-environments/
github.com/defenseunicorns/zarf
```

### Git Protocol

```
# Git protocol (if using git:// instead of https://)
git://github.com
```

## Kubernetes Binaries

### Official Kubernetes Downloads

```
# Kubernetes releases
dl.k8s.io
storage.googleapis.com/kubernetes-release

# Specific binaries
dl.k8s.io/release/v1.28.6/bin/linux/amd64/kubectl
dl.k8s.io/release/v1.28.6/bin/linux/amd64/kubeadm
dl.k8s.io/release/v1.28.6/bin/linux/amd64/kubelet

# CNI plugins
github.com/containernetworking/plugins/releases

# etcd
github.com/etcd-io/etcd/releases

# Helm
get.helm.sh
github.com/helm/helm/releases
```

## Python Package Index (PyPI)

### PyPI Mirrors

```
# Official PyPI
pypi.org
pypi.python.org
files.pythonhosted.org

# PyPI CDN
pythonhosted.org
*.pythonhosted.org
```

### Specific Python Packages

```
# Ansible and dependencies
pypi.org/project/ansible
pypi.org/project/ansible-core
pypi.org/project/jinja2
pypi.org/project/netaddr
pypi.org/project/pyyaml
pypi.org/project/cryptography
pypi.org/project/cffi
pypi.org/project/markupsafe
pypi.org/project/resolvelib
pypi.org/project/packaging

# Build tools
pypi.org/project/pip
pypi.org/project/setuptools
pypi.org/project/wheel

# Testing (optional)
pypi.org/project/pytest
pypi.org/project/hypothesis
```

## System Package Repositories

### Ubuntu/Debian Repositories

```
# Ubuntu official
archive.ubuntu.com
security.ubuntu.com
ports.ubuntu.com

# Ubuntu mirrors (common)
us.archive.ubuntu.com
mirror.ubuntu.com

# Specific for Ubuntu 24.04 (Noble)
archive.ubuntu.com/ubuntu/dists/noble
archive.ubuntu.com/ubuntu/dists/noble-updates
archive.ubuntu.com/ubuntu/dists/noble-security
```

### Package Dependencies

```
# Common packages needed
# - python3, python3-pip, python3-venv
# - git, curl, wget
# - podman or docker
# - containerd, runc
# - build-essential (for compiling Python packages)
```

## Terraform

### Terraform Registry

```
# HashiCorp Terraform
releases.hashicorp.com
registry.terraform.io
checkpoint-api.hashicorp.com

# Terraform binary
releases.hashicorp.com/terraform

# Provider registry
registry.terraform.io/v1/providers
```

### Terraform Providers

```
# OpenStack provider
registry.terraform.io/providers/terraform-provider-openstack/openstack

# HashiCorp providers
registry.terraform.io/providers/hashicorp/local
registry.terraform.io/providers/hashicorp/null
registry.terraform.io/providers/hashicorp/tls
registry.terraform.io/providers/hashicorp/random

# Provider binaries
releases.hashicorp.com/terraform-provider-*
```

## Zarf

### Zarf Installation

```
# Zarf releases
github.com/defenseunicorns/zarf/releases
get.zarf.dev

# Zarf binary
github.com/defenseunicorns/zarf/releases/download
```

## CDN and Mirrors

### Content Delivery Networks

```
# Cloudflare CDN
cloudflare.com
*.cloudflare.com

# Fastly CDN
fastly.com
*.fastly.com

# Akamai CDN
akamai.com
*.akamai.com

# Google Cloud CDN
googleapis.com
*.googleapis.com
storage.googleapis.com
```

## DNS and Certificate Validation

### Required for HTTPS

```
# Certificate authorities
letsencrypt.org
*.letsencrypt.org

# OCSP (Certificate revocation checking)
ocsp.digicert.com
ocsp.sectigo.com
ocsp.godaddy.com

# DNS resolution
# Allow DNS queries (UDP/TCP port 53) to configured DNS servers
```

## Complete Firewall Rules

### Outbound HTTPS (TCP 443)

```
# Container registries
registry.k8s.io:443
gcr.io:443
ghcr.io:443
docker.io:443
quay.io:443
grafana.com:443

# Git repositories
github.com:443
api.github.com:443
raw.githubusercontent.com:443

# Kubernetes downloads
dl.k8s.io:443
storage.googleapis.com:443

# PyPI
pypi.org:443
files.pythonhosted.org:443

# Ubuntu repositories
archive.ubuntu.com:443
security.ubuntu.com:443

# Terraform
releases.hashicorp.com:443
registry.terraform.io:443

# Zarf
get.zarf.dev:443
```

### Outbound HTTP (TCP 80)

```
# Some mirrors may use HTTP
archive.ubuntu.com:80
security.ubuntu.com:80

# Note: Most services redirect HTTP to HTTPS
```

### Outbound Git (TCP 9418)

```
# Only if using git:// protocol
github.com:9418

# Recommendation: Use HTTPS instead
```

### DNS (UDP/TCP 53)

```
# Allow DNS queries to configured DNS servers
# Required for all hostname resolution
```

## Wildcard Rules (Simplified)

For simplified firewall configuration:

```
# Container registries
*.gcr.io
*.docker.io
*.docker.com
*.quay.io
*.k8s.io
*.ghcr.io
*.grafana.com
*.goharbor.io

# Git and GitHub
*.github.com
*.githubusercontent.com

# Google services
*.googleapis.com
*.google.com

# HashiCorp
*.hashicorp.com

# Python
*.python.org
*.pythonhosted.org

# Ubuntu
*.ubuntu.com

# CDNs
*.cloudflare.com
*.fastly.com
*.akamai.com
```

## IP-Based Rules (Alternative)

If DNS is restricted, use IP ranges:

```
# GitHub (subject to change)
140.82.112.0/20
185.199.108.0/22
192.30.252.0/22

# Google Cloud (GCR, GCS)
# See: https://www.gstatic.com/ipranges/cloud.json

# Cloudflare
# See: https://www.cloudflare.com/ips/

# Note: IP ranges change frequently. DNS-based rules preferred.
```

## Verification Script

Test connectivity to required URLs:

```bash
#!/bin/bash
# Test firewall whitelist

URLS=(
    "https://registry.k8s.io"
    "https://gcr.io"
    "https://ghcr.io"
    "https://docker.io"
    "https://quay.io"
    "https://github.com"
    "https://dl.k8s.io"
    "https://pypi.org"
    "https://archive.ubuntu.com"
    "https://releases.hashicorp.com"
    "https://registry.terraform.io"
)

for url in "${URLS[@]}"; do
    if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "200\|301\|302"; then
        echo "✓ $url"
    else
        echo "✗ $url"
    fi
done
```

## Security Considerations

### Recommended Practices

1. **Use HTTPS Only:** Disable HTTP where possible
2. **Certificate Validation:** Enable SSL/TLS certificate verification
3. **Proxy Server:** Route through authenticated proxy
4. **Logging:** Log all outbound connections for audit
5. **Time-Limited:** Open firewall only during build window
6. **Least Privilege:** Whitelist only required URLs

### Proxy Configuration

If using HTTP proxy:

```bash
# Set proxy environment variables
export HTTP_PROXY="http://proxy.example.com:8080"
export HTTPS_PROXY="http://proxy.example.com:8080"
export NO_PROXY="localhost,127.0.0.1"

# For apt
echo 'Acquire::http::Proxy "http://proxy.example.com:8080";' > /etc/apt/apt.conf.d/proxy

# For docker/podman
mkdir -p /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/http-proxy.conf << EOF
[Service]
Environment="HTTP_PROXY=http://proxy.example.com:8080"
Environment="HTTPS_PROXY=http://proxy.example.com:8080"
EOF
```

## Troubleshooting

### Connection Failures

**Symptom:** Download fails with connection timeout

**Check:**
```bash
# Test DNS resolution
nslookup registry.k8s.io

# Test connectivity
curl -v https://registry.k8s.io

# Check proxy
echo $HTTPS_PROXY
```

**Solution:** Verify URL is whitelisted and DNS is working

### Certificate Errors

**Symptom:** SSL certificate verification failed

**Check:**
```bash
# Test certificate
openssl s_client -connect registry.k8s.io:443

# Check CA certificates
ls /etc/ssl/certs/
```

**Solution:** Update CA certificates or configure proxy with proper certificates

### Slow Downloads

**Symptom:** Downloads are very slow

**Cause:** Firewall inspection, bandwidth limits, or CDN routing

**Solution:** 
- Use CDN-aware firewall rules
- Increase bandwidth allocation
- Consider local mirror/cache

## Maintenance

### Regular Updates

1. **Review Quarterly:** Check for new registries or URLs
2. **Monitor Logs:** Identify blocked connections
3. **Test Builds:** Verify whitelist is complete
4. **Update Documentation:** Keep this list current

### Change Management

When adding new services:

1. Identify required URLs
2. Test connectivity
3. Update firewall rules
4. Update this document
5. Notify security team

## Related Documentation

- [Build Runbook](../how-to/build/build-package.md)
- [Network Architecture](architecture/three-zone-model.md)
- [Security Requirements](security-requirements.md)
