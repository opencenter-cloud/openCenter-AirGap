# Security Policy

**doc_type**: reference
**audience**: Security researchers, operators, platform engineers

## Reporting Security Vulnerabilities

Report security issues to the openCenter AirGap security team. Do not open public GitHub issues for security vulnerabilities.

### Contact

**Email**: security@opencenter.example.com
**PGP Key**: Available at https://opencenter.example.com/security/pgp-key.asc

For urgent issues requiring immediate attention, include `[URGENT]` in the subject line.

### What to Report

Report any security concerns related to:

- **Supply Chain**: Compromised dependencies, unsigned artifacts, checksum mismatches
- **Secrets Exposure**: Credentials in logs, environment variables, or git history
- **Container Vulnerabilities**: Critical CVEs in packaged images
- **Access Control**: Unauthorized access to build artifacts or deployment systems
- **Code Execution**: Arbitrary command injection in build or deployment scripts
- **Cryptographic Issues**: Weak signing, verification bypass, or key management flaws
- **Configuration Flaws**: Insecure defaults or missing hardening

### Out of Scope

The following are not considered security vulnerabilities:

- Issues in third-party dependencies already disclosed upstream (report to upstream project)
- Vulnerabilities requiring physical access to air-gapped systems
- Social engineering attacks
- Denial of service against build infrastructure (report as operational issue)

## Response Timeline

| Phase | Timeline | Description |
|-------|----------|-------------|
| **Acknowledgment** | 2 business days | Confirm receipt of report |
| **Initial Assessment** | 5 business days | Determine severity and impact |
| **Mitigation Plan** | 10 business days | Develop fix or workaround |
| **Patch Release** | 30 days | Release patched version (critical issues expedited) |
| **Public Disclosure** | 90 days | Coordinate disclosure after patch available |

Critical vulnerabilities (CVSS 9.0+) are expedited with target resolution in 7 days.

## Severity Classification

We use CVSS 3.1 scoring with the following thresholds:

- **Critical (9.0-10.0)**: Immediate action required, expedited patch
- **High (7.0-8.9)**: Patch within 30 days
- **Medium (4.0-6.9)**: Patch within 90 days
- **Low (0.1-3.9)**: Addressed in next regular release

## Disclosure Policy

We follow coordinated disclosure:

1. Security team acknowledges report within 2 business days
2. Team investigates and develops fix
3. Patch released to users before public disclosure
4. Public disclosure coordinated with reporter after 90 days or when patch is widely deployed
5. Reporter credited in security advisory (unless anonymity requested)

## Security Controls

### Build Phase (Zone A - Connected)

- **Dependency Pinning**: All versions locked to commit SHAs in `config/versions.env`
- **Checksum Verification**: Asset integrity validated via `build/asset-checksums.json`
- **Image Scanning**: Trivy scans all 139 container images for HIGH/CRITICAL CVEs
- **SBOM Generation**: Complete software bill of materials included in Zarf package
- **Cryptographic Signing**: Packages signed with Cosign for verification

### Transport Phase (Zone B - Airlock)

- **Single Artifact**: All dependencies packaged in one `zarf-package-*.tar.zst` file
- **Checksum Validation**: SHA256 checksums provided for transport verification
- **Signature Verification**: Cosign signature validates package authenticity

### Deployment Phase (Zone C - Air-Gapped)

- **Secrets Management**: File-based secrets with 0600 permissions in `.secrets/` directory
- **No Network Egress**: All operations run without internet connectivity
- **Local Registry**: Bastion serves images from localhost:5000 (no external exposure)
- **Audit Logging**: All deployment operations logged to `/opt/opencenter/logs/`

## Security Testing

### Automated Checks

- **Pre-commit Hooks**: `detect-secrets` prevents credential commits
- **CI Pipeline**: Linting, type checking, and security scans on every commit
- **Image Scanning**: Trivy integrated into build process (fails on CRITICAL CVEs)
- **Dependency Audits**: Regular reviews of pinned versions for known vulnerabilities

### Manual Reviews

- **Code Review**: All changes require approval from CODEOWNERS
- **Security Audits**: Quarterly reviews of build and deployment scripts
- **Penetration Testing**: Annual third-party assessment of air-gap controls

## Vulnerability Management

### Upstream Vulnerabilities

When vulnerabilities are disclosed in upstream dependencies:

1. Assess impact on openCenter AirGap
2. Update `config/versions.env` to patched version
3. Regenerate asset checksums
4. Rebuild Zarf package
5. Notify users via security advisory

### Internal Vulnerabilities

When vulnerabilities are found in openCenter code:

1. Develop fix in private security branch
2. Test fix against integration test suite
3. Release patch version
4. Publish security advisory with CVE (if applicable)
5. Update documentation with remediation steps

## Compliance

openCenter AirGap is designed for regulated environments. Security controls align with:

- **NIST SP 800-53**: Supply chain risk management (SR family)
- **ISO 27001**: Information security management
- **SOC 2 Type II**: Security, availability, and confidentiality
- **FIPS 140-2**: Cryptographic module validation (where applicable)

Audit evidence available:
- Build logs: `build/build.log`
- Asset checksums: `build/asset-checksums.json`
- Image scan results: `build/image-scan-results.json`
- SBOM: `dist/zarf-package-*-sbom.json`

## Security Updates

Subscribe to security advisories:
- **GitHub**: Watch repository for security advisories
- **Mailing List**: security-announce@opencenter.example.com
- **RSS Feed**: https://opencenter.example.com/security/advisories.xml

## Acknowledgments

We recognize security researchers who responsibly disclose vulnerabilities:

- [Security Hall of Fame](https://opencenter.example.com/security/hall-of-fame)

## Questions

For non-security questions about the project, use GitHub Discussions or open a regular issue.

For security-related questions that are not vulnerability reports, email security@opencenter.example.com with `[QUESTION]` in the subject line.

---

**Last Updated**: 2026-02-01
**Version**: 1.0.0-rc1
