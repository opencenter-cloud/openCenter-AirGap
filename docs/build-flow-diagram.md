# openCenter AirGap Build Flow

## Build Process Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MASTER BUILD SCRIPT                             │
│                        scripts/build/build.sh                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 0: Setup Python Virtual Environment                               │
│ ─────────────────────────────────────────────────────────────────────── │
│ • Check Python 3.12+ available                                          │
│ • Create/activate venv at PROJECT_ROOT/venv                             │
│ • Install: pyyaml, jinja2, requests, hypothesis, pytest                 │
│                                                                         │
│ Output: Active Python 3.12+ venv with build dependencies               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 1: Run kubespray-offline Asset Collection                         │
│ ─────────────────────────────────────────────────────────────────────── │
│ • Execute: build/kubespray-offline/download-all.sh                      │
│ • Download K8s binaries, images, packages, wheels                       │
│ • Time: 30-60 minutes                                                   │
│ • Skip: --skip-download                                                 │
│                                                                         │
│ Output: build/kubespray-offline/outputs/                                │
│   ├── files/          (K8s binaries)                                    │
│   ├── images/         (container images as tar.gz)                      │
│   ├── debs/           (apt repository)                                  │
│   ├── pypi/           (Python wheels)                                   │
│   ├── playbook/       (offline-repo.yml)                                │
│   └── kubespray-*.tar.gz                                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 2: Organize Assets for Zarf                                       │
│ ─────────────────────────────────────────────────────────────────────── │
│ • Execute: scripts/build/organize_assets_for_zarf.sh                   │
│ • Copy outputs to assets/ directory                                     │
│ • Structure by component type                                           │
│ • Time: 2-5 minutes                                                     │
│                                                                         │
│ Output: assets/                                                         │
│   ├── k8s-binaries/   (from outputs/files/)                             │
│   ├── python-wheels/  (from outputs/pypi/)                              │
│   ├── repos/apt/      (from outputs/debs/)                              │
│   ├── target-scripts/ (from outputs/)                                   │
│   ├── kubespray/      (extracted from tarball)                          │
│   └── playbook/       (from outputs/playbook/)                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 3: Collect Terraform Providers (OpenStack mode only)              │
│ ─────────────────────────────────────────────────────────────────────── │
│ • Execute: scripts/build/mirror_terraform_providers.sh                 │
│ • Download providers for offline use                                    │
│ • Time: 5-10 minutes                                                    │
│ • Enable: --openstack                                                   │
│ • Skip: --skip-terraform                                                │
│                                                                         │
│ Output: assets/terraform-mirror/                                        │
│   └── registry.terraform.io/                                            │
│       ├── hashicorp/local/                                              │
│       ├── hashicorp/null/                                               │
│       ├── hashicorp/tls/                                                │
│       └── terraform-provider-openstack/openstack/                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 4: Validate Version Pinning                                       │
│ ─────────────────────────────────────────────────────────────────────── │
│ • Execute: scripts/build/version_validator.py                          │
│ • Scan config files for unpinned versions                               │
│ • Fail if "latest", "stable", wildcards found                           │
│ • Time: < 1 minute                                                      │
│ • Skip: --skip-validation (not recommended)                             │
│                                                                         │
│ Output: Validation report (pass/fail)                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 5: Generate zarf.yaml and Create Package                          │
│ ─────────────────────────────────────────────────────────────────────── │
│ • Execute: scripts/build/generate_zarf_yaml.py                          │
│   - Create package definition from asset inventory                      │
│   - Define components and deployment sequence                           │
│ • Execute: scripts/build/create_zarf_package.sh                         │
│   - Run: zarf package create --confirm                                  │
│   - Compress assets into single artifact                                │
│ • Time: 10-30 minutes                                                   │
│                                                                         │
│ Output: dist/zarf-package-openCenter-airgap-amd64-<version>.tar.zst    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 6: Verify SBOM Generation                                         │
│ ─────────────────────────────────────────────────────────────────────── │
│ • SBOM automatically generated by Zarf (Syft)                           │
│ • Execute: scripts/build/verify_sbom.py                                 │
│ • Check completeness and accuracy                                       │
│ • Time: < 1 minute                                                      │
│                                                                         │
│ Output: dist/package-sbom.txt                                           │
│         dist/sbom-verification-report.txt                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 7: Generate Checksums                                             │
│ ─────────────────────────────────────────────────────────────────────── │
│ • Execute: scripts/build/checksum_utils.py                              │
│ • Compute MD5 and SHA256                                                │
│ • Time: 1-5 minutes                                                     │
│                                                                         │
│ Output: dist/<package>.checksums                                        │
│   MD5: <hash>                                                           │
│   SHA256: <hash>                                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 8: Sign Package (Optional)                                        │
│ ─────────────────────────────────────────────────────────────────────── │
│ • Execute: scripts/build/sign_package.sh                                │
│ • Sign with Cosign if COSIGN_KEY set                                    │
│ • Time: < 1 minute                                                      │
│ • Skip: --skip-signing                                                  │
│                                                                         │
│ Output: dist/<package>.sig (detached signature)                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         BUILD COMPLETE                                  │
│ ─────────────────────────────────────────────────────────────────────── │
│ Artifacts in dist/:                                                     │
│ • zarf-package-openCenter-airgap-amd64-<version>.tar.zst               │
│ • <package>.checksums (MD5 + SHA256)                                    │
│ • <package>.sig (Cosign signature, if signed)                           │
│ • package-inspection.txt                                                │
│ • package-sbom.txt                                                      │
│ • sbom-verification-report.txt                                          │
│                                                                         │
│ Ready for transfer to air-gapped environment!                           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Build Time Breakdown

| Step | Description | Time | Skippable |
|:-----|:------------|:-----|:----------|
| 0 | Python venv setup | < 1 min | No |
| 1 | Asset collection | 30-60 min | Yes (--skip-download) |
| 2 | Asset organization | 2-5 min | No |
| 3 | Terraform providers | 5-10 min | Yes (--skip-terraform) |
| 4 | Version validation | < 1 min | Yes (--skip-validation) |
| 5 | Package creation | 10-30 min | No |
| 6 | SBOM verification | < 1 min | No |
| 7 | Checksum generation | 1-5 min | No |
| 8 | Package signing | < 1 min | Yes (--skip-signing) |
| **Total** | **First build** | **45-90 min** | |
| **Total** | **Rebuild** | **15-40 min** | (with --skip-download) |

## Disk Space Usage

```
build/kubespray-offline/outputs/  ~20GB  (Step 1)
assets/                           ~25GB  (Step 2)
dist/                             ~10GB  (Step 5-8)
───────────────────────────────────────
Total required:                   ~50GB
```

## Command-Line Options

```bash
# Full build (first time)
./scripts/build/build.sh

# OpenStack mode
./scripts/build/build.sh --openstack

# Rebuild without re-downloading
./scripts/build/build.sh --skip-download

# Skip Terraform (bare-metal only)
./scripts/build/build.sh --skip-terraform

# Skip version validation (not recommended)
./scripts/build/build.sh --skip-validation

# Skip signing
./scripts/build/build.sh --skip-signing

# Build with signing
COSIGN_KEY=cosign.key ./scripts/build/build.sh

# Combine options
./scripts/build/build.sh --openstack --skip-download
```

## Error Handling

Each step validates prerequisites and outputs before proceeding:

```
Step N: Description
├── Check prerequisites
│   ├── Required files exist
│   ├── Required commands available
│   └── Sufficient disk space
├── Execute operation
│   ├── Log progress
│   ├── Capture errors
│   └── Validate outputs
└── Verify results
    ├── Check expected files created
    ├── Validate file contents
    └── Report success/failure
```

If any step fails:
- Clear error message with context
- Build halts immediately
- Logs preserved for troubleshooting
- Exit code indicates failure

## Integration Points

The master build script integrates these existing scripts:

1. `kubespray-offline/download-all.sh` - Asset collection
2. `organize_assets_for_zarf.sh` - Asset organization
3. `mirror_terraform_providers.sh` - Terraform providers
4. `version_validator.py` - Version validation
5. `generate_zarf_yaml.py` - Package definition
6. `create_zarf_package.sh` - Package creation
7. `verify_sbom.py` - SBOM verification
8. `checksum_utils.py` - Checksum generation
9. `sign_package.sh` - Package signing

Each script is called in the correct order with proper error handling and output validation.
