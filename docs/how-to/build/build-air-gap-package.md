---
type: how-to
audience: platform-engineer
difficulty: intermediate
version: 2.0.0
last_updated: 2026-01-26
doc_type: how-to
---

# Build Air-Gap Package

Create the openCenter deployment artifact in a connected environment using the resumable build system.

## Prerequisites

- Ubuntu 24.04 LTS (AMD64)
- Python 3.12+
- Skopeo 1.x+
- Podman 4.x+ or Docker 20.x+
- Git, jq, zarf
- 100GB+ free disk
- Internet access
- GitHub Personal Access Token (for private images)

Verify:
```bash
python3 --version
skopeo --version
podman --version  # or docker --version
git --version
jq --version
zarf version
df -h .
```

Install missing tools:
```bash
sudo apt-get install skopeo git jq  # Ubuntu/Debian
# or
sudo dnf install skopeo git jq      # Fedora/RHEL
```

## Setup GitHub Token

Private images from `ghcr.io/opencenter-cloud` require authentication:

```bash
# Create token at https://github.com/settings/tokens
# Scopes: read:packages

# Export token
export GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# Or add to .env file
echo "GITHUB_TOKEN=ghp_xxxxxxxxxxxx" > .env
```

Skip private registry images (optional):
```bash
python3 scripts/build/build.py --skip-opencenter-private
```

## Build

Fresh build:
```bash
# Clone and setup
git clone <repo-url> opencenter-airgap
cd opencenter-airgap

# Build package (Python environment created automatically)
python3 scripts/build/build.py --clean
```

Duration: 30-60 minutes.

Output: `dist/zarf-package-opencenter-airgap-amd64-<version>.tar.zst`

## Resume After Failure

The build system tracks progress and resumes automatically:

```bash
# Resume from last incomplete step (default)
python3 scripts/build/build.py

# Resume from specific step
python3 scripts/build/build.py --from-step validate_versions

# Skip a specific step
python3 scripts/build/build.py --skip-step sign_package

# Force re-execution of all steps
python3 scripts/build/build.py --force
```

Check build state:
```bash
cat build/.build-state.json | python3 -m json.tool
```

View logs:
```bash
ls -lt build/build-*.log | head -1 | awk '{print $NF}' | xargs tail -f
```

## Build Options

All CLI flags:

```bash
# Resume control
--clean                      # Delete state and start fresh
--resume                     # Resume from last incomplete step (default)
--from-step STEP_NAME        # Resume from specific step
--skip-step STEP_NAME        # Skip specific step (repeatable)

# Execution control
--force                      # Force re-execution (bypass change detection)
--no-parallel                # Disable parallel execution
--max-parallel N             # Max concurrent steps (default: 2)

# Legacy compatibility
--skip-opencenter-private    # Skip private registry images
--skip-kubespray-offline     # Skip kubespray-offline download
--skip-zarf                  # Skip Zarf packaging
--non-interactive            # Run without prompts (CI/CD)
```

Examples:

```bash
# Fresh build with all steps
python3 scripts/build/build.py --clean

# Resume after fixing an issue
python3 scripts/build/build.py

# Skip private images and run sequentially
python3 scripts/build/build.py --skip-opencenter-private --no-parallel

# CI/CD mode
GITHUB_TOKEN=xxx python3 scripts/build/build.py --clean --non-interactive

# Skip multiple steps
python3 scripts/build/build.py --skip-step sign_package --skip-step validate_sbom
```

## Verify

```bash
# Check package exists
ls -lh dist/zarf-package-*.tar.zst

# Verify integrity
sha256sum -c dist/zarf-package-*.tar.zst.sha256

# Inspect SBOM
zarf package inspect dist/zarf-package-*.tar.zst --sbom
```

## Troubleshooting

**Build fails at specific step**
```bash
# Check logs for details
tail -100 build/build-*.log | grep ERROR

# Resume after fixing issue
python3 scripts/build/build.py

# Skip problematic step temporarily
python3 scripts/build/build.py --skip-step problematic_step
```

**Python version mismatch**
```bash
python3 --version  # Must be 3.12+
sudo apt install python3.12 python3.12-venv
```

**Prerequisites check fails**
```bash
# Run prerequisites check manually
python3 -c "from scripts.build.workers.prerequisites import check_prerequisites_worker; check_prerequisites_worker('/opt/opencenter')"

# Install missing tools
sudo apt-get install git jq skopeo podman
```

**GitHub token authentication failed**
```bash
# Test token
curl -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  https://api.github.com/user

# Verify token has read:packages scope
# Regenerate at https://github.com/settings/tokens

# Skip private images if unavailable
python3 scripts/build/build.py --skip-opencenter-private
```

**Build state corrupted**
```bash
# Start fresh
python3 scripts/build/build.py --clean

# Or manually delete state
rm build/.build-state.json
rm -rf build/.completed/
```

**Parallel execution issues**
```bash
# Disable parallel execution
python3 scripts/build/build.py --no-parallel

# Reduce parallelism
python3 scripts/build/build.py --max-parallel 1
```

**Asset download failures**
```bash
# Resume will retry failed downloads
python3 scripts/build/build.py

# Force re-download
python3 scripts/build/build.py --force --from-step collect_kubespray_offline
```

**Disk space exhausted**
```bash
# Clean container cache
podman system prune -a -f
# or
docker system prune -a -f

# Clean build artifacts
rm -rf build/kubespray-offline/outputs
python3 scripts/build/build.py --clean
```

**Step takes too long**
```bash
# Check progress in another terminal
tail -f build/build-*.log

# Some steps (kubespray-offline) can take 20+ minutes
# Timeout is 300s (5 minutes) for bash workers
```

## Next Steps

- [Transfer package](../deploy/deploy-baremetal-cluster.md#package-transfer)
- [Verify package integrity](../verify/verify-package-integrity.md)
