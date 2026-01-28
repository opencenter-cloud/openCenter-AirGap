# Container Image Security Scanning

**doc_type**: reference
**audience**: Security Engineers, Platform Engineers
**scope**: Vulnerability scanning policy and procedures for container images

## Overview

All container images packaged in openCenter AirGap undergo vulnerability scanning using Trivy. The build fails if any image contains CRITICAL severity vulnerabilities.

## Scanning Tool

**Trivy** (Aqua Security)
- Version: Latest stable
- Database: Automatically updated from GitHub
- Coverage: OS packages, application dependencies, known CVEs

## Installation

```bash
# Install Trivy
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

# Verify installation
trivy --version
```

## Vulnerability Policy

### Severity Levels

Trivy classifies vulnerabilities into five severity levels:

| Severity | Policy | Action |
|----------|--------|--------|
| CRITICAL | **FAIL** | Build blocked, immediate remediation required |
| HIGH | **WARN** | Build continues, remediation recommended |
| MEDIUM | **INFO** | Logged for awareness |
| LOW | **INFO** | Logged for awareness |
| UNKNOWN | **INFO** | Logged for awareness |

### Threshold Enforcement

The build pipeline enforces the following thresholds:

- **CRITICAL vulnerabilities**: Zero tolerance. Any CRITICAL CVE blocks the build.
- **HIGH vulnerabilities**: Logged and reported but do not block the build.
- **MEDIUM/LOW vulnerabilities**: Tracked for informational purposes.

## Scanning Process

### Automated Scanning

Image scanning runs automatically during the build process:

```bash
# Scan all images in config/all-images.txt
./scripts/build/scan_images.sh
```

The script:
1. Reads image list from `config/all-images.txt`
2. Scans each image using Trivy
3. Aggregates results into `build/image-scan-results.json`
4. Generates summary report in `build/image-vulnerabilities.txt`
5. Fails build if CRITICAL vulnerabilities found

### Manual Scanning

Scan a single image:

```bash
trivy image --severity CRITICAL,HIGH registry.k8s.io/pause:3.9
```

Scan with JSON output:

```bash
trivy image --format json --output results.json registry.k8s.io/pause:3.9
```

## Output Files

### Scan Results (JSON)

**Location**: `build/image-scan-results.json`

**Structure**:
```json
{
  "scan_timestamp": "2026-01-27T14:30:00Z",
  "images": [
    {
      "image": "registry.k8s.io/pause:3.9",
      "scan_result": {
        "Results": [
          {
            "Target": "registry.k8s.io/pause:3.9 (alpine 3.19.0)",
            "Vulnerabilities": [
              {
                "VulnerabilityID": "CVE-2024-1234",
                "PkgName": "openssl",
                "InstalledVersion": "3.1.0-r1",
                "FixedVersion": "3.1.0-r2",
                "Severity": "CRITICAL",
                "Title": "OpenSSL buffer overflow",
                "Description": "...",
                "References": ["https://cve.mitre.org/..."]
              }
            ]
          }
        ]
      }
    }
  ]
}
```

### Vulnerability Summary (Text)

**Location**: `build/image-vulnerabilities.txt`

**Contents**:
- Scan metadata (timestamp, policy)
- Per-image vulnerability counts
- Top CRITICAL CVEs for each affected image
- Summary statistics
- Policy decision (PASS/FAIL)
- Remediation guidance

**Example**:
```
Container Image Vulnerability Scan Report
==========================================
Scan Date: 2026-01-27 14:30:00 UTC
Policy: Fail on CRITICAL, Warn on HIGH

Image: registry.k8s.io/pause:3.9
  CRITICAL: 0
  HIGH: 2

Image: docker.io/library/nginx:1.29.2
  CRITICAL: 1
  HIGH: 5
  Top Critical CVEs:
    - CVE-2024-1234: OpenSSL buffer overflow

==========================================
Summary Statistics
==========================================
Total Images: 139
Successfully Scanned: 139
Failed Scans: 0
Total CRITICAL Vulnerabilities: 1
Total HIGH Vulnerabilities: 7
Images with CRITICAL: 1

==========================================
POLICY VIOLATION
==========================================
Build FAILED: 1 image(s) contain CRITICAL vulnerabilities.
```

## Remediation Process

### Step 1: Identify Affected Images

Review `build/image-vulnerabilities.txt` to identify images with CRITICAL vulnerabilities.

### Step 2: Check for Updates

For each affected image:

1. Check upstream registry for patched versions
2. Review CVE details and fixed versions
3. Identify the minimum version that resolves the CVE

### Step 3: Update Configuration

Update `config/versions.env` with new image tags:

```bash
# Before
NGINX_VERSION=1.29.2

# After (patched version)
NGINX_VERSION=1.29.3
```

### Step 4: Rebuild and Rescan

```bash
# Re-collect assets with updated versions
./scripts/build/collect_assets.sh

# Rebuild package
./scripts/build/create_package.sh

# Verify vulnerabilities resolved
./scripts/build/scan_images.sh
```

### Step 5: Document Changes

Update `CHANGELOG.md` with vulnerability fixes:

```markdown
## [1.2.1] - 2026-01-27

### Security
- Updated nginx to 1.29.3 to fix CVE-2024-1234 (CRITICAL)
- Updated openssl to 3.1.0-r2 to fix CVE-2024-5678 (HIGH)
```

## Risk Acceptance

If a CRITICAL vulnerability cannot be immediately remediated:

### Temporary Bypass

**WARNING**: Only use in exceptional circumstances with documented approval.

```bash
# Override threshold for emergency builds
FAIL_ON_SEVERITY="NONE" ./scripts/build/scan_images.sh
```

### Documentation Requirements

Create risk acceptance document in `docs/security/risk-acceptance-YYYY-MM-DD.md`:

```markdown
# Risk Acceptance: CVE-2024-1234

**Date**: 2026-01-27
**Approver**: Security Team Lead
**Expiration**: 2026-02-15

## Vulnerability Details
- CVE ID: CVE-2024-1234
- Affected Image: nginx:1.29.2
- Severity: CRITICAL
- CVSS Score: 9.8

## Risk Assessment
- Impact: Remote code execution
- Likelihood: Low (requires specific network configuration)
- Mitigation: Network segmentation, WAF rules

## Justification
No patched version available. Vendor ETA for fix: 2026-02-10.

## Compensating Controls
1. Network isolation of affected services
2. WAF rules blocking exploit patterns
3. Enhanced monitoring for suspicious activity

## Remediation Plan
Update to nginx:1.29.3 when released (target: 2026-02-15)
```

## Integration with Build Pipeline

### Build Script Integration

Add scanning to `scripts/build/build.py` or main build script:

```bash
#!/usr/bin/env bash
set -euo pipefail

# ... existing build steps ...

# Scan images for vulnerabilities
log_info "Scanning container images for vulnerabilities..."
if ! ./scripts/build/scan_images.sh; then
    log_error "Image scanning failed due to CRITICAL vulnerabilities"
    log_error "Review: build/image-vulnerabilities.txt"
    exit 1
fi

# ... continue with package creation ...
```

### CI/CD Integration

Add to `.github/workflows/build.yml`:

```yaml
- name: Scan Container Images
  run: |
    ./scripts/build/scan_images.sh

- name: Upload Scan Results
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: vulnerability-scan-results
    path: |
      build/image-scan-results.json
      build/image-vulnerabilities.txt
```

## SBOM Integration

Vulnerability scan results are included in the Software Bill of Materials (SBOM):

```bash
# Generate SBOM with vulnerability data
zarf package inspect dist/zarf-package-*.tar.zst --sbom --output-dir build/sbom

# SBOM includes:
# - Component inventory
# - Vulnerability scan results
# - License information
# - Dependency graph
```

## Monitoring and Alerting

### Scan Metrics

Track vulnerability trends over time:

- Total images scanned
- CRITICAL vulnerabilities per build
- HIGH vulnerabilities per build
- Mean time to remediation (MTTR)
- Images requiring updates

### Alert Thresholds

Configure alerts for:

- Build failures due to CRITICAL CVEs
- Increase in HIGH vulnerabilities (>10% week-over-week)
- Scan failures or timeouts
- Images with unpatched CRITICAL CVEs >7 days

## Compliance and Audit

### Audit Trail

Maintain records of:
- All scan results (JSON files)
- Risk acceptance documents
- Remediation actions and timelines
- Version updates and justifications

### Reporting

Generate monthly security reports:

```bash
# Extract vulnerability trends
jq '.images[].scan_result.Results[].Vulnerabilities[] | select(.Severity == "CRITICAL")' \
   build/image-scan-results-*.json | \
   jq -s 'group_by(.VulnerabilityID) | map({cve: .[0].VulnerabilityID, count: length})'
```

## Troubleshooting

### Trivy Database Update Failures

```bash
# Manually update Trivy database
trivy image --download-db-only

# Use offline database
trivy image --skip-db-update --cache-dir /path/to/cache <image>
```

### Scan Timeouts

```bash
# Increase timeout for large images
trivy image --timeout 20m <image>
```

### False Positives

```bash
# Ignore specific CVEs (use sparingly)
trivy image --ignore-unfixed --ignorefile .trivyignore <image>
```

Create `.trivyignore`:
```
# Ignore CVE-2024-1234 - false positive, not applicable to our use case
CVE-2024-1234
```

## References

- [Trivy Documentation](https://aquasecurity.github.io/trivy/)
- [CVE Database](https://cve.mitre.org/)
- [National Vulnerability Database](https://nvd.nist.gov/)
- [CVSS Calculator](https://www.first.org/cvss/calculator/3.1)

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-27 | Initial policy documentation |
