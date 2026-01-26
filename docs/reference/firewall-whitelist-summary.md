# Firewall Whitelist Summary

**doc_type:** reference

Quick reference for firewall configuration required for openCenter AirGap build.

## Quick Start

### Verify Current Configuration

```bash
./scripts/build/verify_firewall_whitelist.sh
```

### Minimum Required URLs

```
# Container Registries (HTTPS/443)
registry.k8s.io
gcr.io
ghcr.io
docker.io
quay.io

# Git Repositories (HTTPS/443)
github.com
api.github.com
raw.githubusercontent.com

# Kubernetes Downloads (HTTPS/443)
dl.k8s.io
storage.googleapis.com

# Python Packages (HTTPS/443)
pypi.org
files.pythonhosted.org

# Ubuntu Repositories (HTTP/80, HTTPS/443)
archive.ubuntu.com
security.ubuntu.com

# Terraform (HTTPS/443)
releases.hashicorp.com
registry.terraform.io

# DNS (UDP/53, TCP/53)
# Allow DNS queries to configured DNS servers
```

## URL Categories

| Category | Count | Examples |
|:---------|:------|:---------|
| Container Registries | 15+ | registry.k8s.io, gcr.io, ghcr.io, docker.io, quay.io |
| Git Repositories | 4 | github.com, api.github.com |
| Kubernetes Binaries | 2 | dl.k8s.io, storage.googleapis.com |
| Python Packages | 3 | pypi.org, files.pythonhosted.org |
| System Packages | 5 | archive.ubuntu.com, security.ubuntu.com |
| Terraform | 3 | releases.hashicorp.com, registry.terraform.io |
| Zarf | 1 | get.zarf.dev |
| CDN & Support | 8+ | cloudflare.com, googleapis.com, letsencrypt.org |

**Total:** 40+ unique domains

## Required Ports

| Port | Protocol | Purpose |
|:-----|:---------|:--------|
| 53 | UDP/TCP | DNS resolution |
| 80 | TCP | HTTP (some mirrors) |
| 443 | TCP | HTTPS (primary) |
| 9418 | TCP | Git protocol (optional) |

## Wildcard Rules (Simplified)

For easier firewall configuration:

```
*.gcr.io
*.docker.io
*.docker.com
*.quay.io
*.k8s.io
*.ghcr.io
*.github.com
*.githubusercontent.com
*.googleapis.com
*.hashicorp.com
*.python.org
*.pythonhosted.org
*.ubuntu.com
*.cloudflare.com
```

## Files Provided

### Documentation

- **docs/reference/firewall-whitelist.md** - Complete reference with all URLs, troubleshooting, and security considerations

### Configuration Files

- **config/firewall-whitelist.txt** - Plain text list (one URL per line)
- **config/firewall-whitelist.json** - Machine-readable JSON format with categories and metadata

### Scripts

- **scripts/build/verify_firewall_whitelist.sh** - Test connectivity to all required URLs

## Usage Examples

### Test Connectivity

```bash
# Test all URLs
./scripts/build/verify_firewall_whitelist.sh

# Test specific URL
curl -v https://registry.k8s.io

# Test with proxy
HTTP_PROXY=http://proxy:8080 curl -v https://registry.k8s.io
```

### Export for Firewall Team

```bash
# Plain text list
cat config/firewall-whitelist.txt

# JSON format
cat config/firewall-whitelist.json | jq .

# Extract just URLs
grep -v "^#" config/firewall-whitelist.txt | grep -v "^$"
```

### Generate Firewall Rules

```bash
# Example: Generate iptables rules
while read -r url; do
    [[ "$url" =~ ^#.*$ ]] && continue
    [[ -z "$url" ]] && continue
    echo "iptables -A OUTPUT -d $url -p tcp --dport 443 -j ACCEPT"
done < config/firewall-whitelist.txt
```

## Proxy Configuration

If using HTTP proxy:

```bash
# Set environment variables
export HTTP_PROXY="http://proxy.example.com:8080"
export HTTPS_PROXY="http://proxy.example.com:8080"
export NO_PROXY="localhost,127.0.0.1"

# Verify
./scripts/build/verify_firewall_whitelist.sh
```

## Common Issues

### All Tests Fail

**Cause:** No internet connectivity or firewall blocking all traffic

**Solution:** Verify basic connectivity with `ping 8.8.8.8` or `curl https://google.com`

### DNS Resolution Fails

**Cause:** DNS servers not accessible or misconfigured

**Solution:** Check `/etc/resolv.conf` and verify DNS servers are reachable

### Certificate Errors

**Cause:** Corporate proxy with SSL inspection

**Solution:** Install corporate CA certificates or configure proxy with proper certificates

### Partial Failures

**Cause:** Some URLs not whitelisted

**Solution:** Review failed URLs and add to firewall whitelist

## Security Recommendations

1. **Time-Limited Access:** Open firewall only during build window
2. **Audit Logging:** Log all outbound connections
3. **Least Privilege:** Whitelist only required URLs
4. **Certificate Validation:** Enable SSL/TLS verification
5. **Proxy Authentication:** Use authenticated proxy if available

## Maintenance

### When to Update

- Adding new services to openCenter platform
- Updating Kubernetes version
- Changing container registries
- Adding new dependencies

### How to Update

1. Identify new URLs required
2. Test connectivity: `curl -v https://new-url.com`
3. Add to `config/firewall-whitelist.txt`
4. Update `config/firewall-whitelist.json`
5. Update `docs/reference/firewall-whitelist.md`
6. Test: `./scripts/build/verify_firewall_whitelist.sh`
7. Commit changes

## Related Documentation

- [Complete Firewall Whitelist](firewall-whitelist.md) - Detailed reference
- [Build Runbook](../how-to/build/build-package.md) - Build process
- [Network Architecture](architecture/three-zone-model.md) - Zone model
- [Troubleshooting](../how-to/troubleshooting.md) - Common issues

## Support

For firewall configuration assistance:

1. Review complete documentation: `docs/reference/firewall-whitelist.md`
2. Test connectivity: `./scripts/build/verify_firewall_whitelist.sh`
3. Check logs for blocked connections
4. Contact network/security team with specific URLs from whitelist
