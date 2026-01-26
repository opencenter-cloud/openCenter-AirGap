---
type: how-to
audience: platform-engineer
difficulty: intermediate
version: 1.0.0
last_updated: 2026-01-25
doc_type: how-to
---

# Add openCenter Assets

Collect openCenter GitOps base repository and container images for air-gap packaging.

## Prerequisites

- GitHub Personal Access Token with `read:packages` scope
- Podman or Docker
- Git
- `jq` for JSON parsing

## Setup GitHub Token

Create token at https://github.com/settings/tokens with these scopes:
- `read:packages` - Read packages from GitHub Container Registry
- `repo` - Access private repositories (if needed)

Export token:
```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Collect Assets

```bash
# Run collection script
./scripts/build/collect_opencenter_assets.sh
```

This script:
1. Clones `rackerlabs/openCenter-gitops-base` repository
2. Queries GitHub API for all packages in `opencenter-cloud` org
3. Pulls all container images from `ghcr.io/opencenter-cloud`
4. Extracts image references from GitOps manifests
5. Saves images as tar.gz archives

Duration: 10-30 minutes depending on image count and size.

## Output

**GitOps Base**:
```
assets/gitops-base/
├── .git/
├── apps/
├── infrastructure/
└── platform/
```

**Container Images**:
```
build/opencenter-images/
├── ghcr.io_opencenter-cloud_app1_latest.tar.gz
├── ghcr.io_opencenter-cloud_app2_v1.0.0.tar.gz
└── ...
```

**Image Lists**:
```
build/opencenter-image-list.txt           # From GitHub API
build/gitops-manifest-images.txt          # From manifests
build/opencenter-images-merged.txt        # Combined unique list
```

## Verify

Check collected assets:
```bash
# GitOps base
ls -la assets/gitops-base/

# Container images
ls -lh build/opencenter-images/

# Image count
wc -l build/opencenter-images-merged.txt
```

## Integration with Build

The main build script automatically includes these assets:

```bash
# Full build with openCenter assets
./scripts/build/build.sh
```

Assets are packaged into Zarf components:
- `opencenter-gitops-base` - GitOps repository
- `opencenter-images` - Container images

## Manual Image Pull

Pull specific image:
```bash
export GITHUB_TOKEN=ghp_xxx
echo "${GITHUB_TOKEN}" | podman login ghcr.io -u USERNAME --password-stdin

podman pull ghcr.io/opencenter-cloud/app-name:tag
```

## Update Assets

Re-run to fetch latest versions:
```bash
# Pull latest from main branch
export OPENCENTER_GITOPS_BASE_VERSION=main
./scripts/build/collect_opencenter_assets.sh

# Or specify different branch
export OPENCENTER_GITOPS_BASE_VERSION=develop
./scripts/build/collect_opencenter_assets.sh
```

## Troubleshooting

**GitHub API rate limit**:
```bash
# Check rate limit
curl -H "Authorization: Bearer ${GITHUB_TOKEN}" \
     https://api.github.com/rate_limit
```

Wait for reset or use different token.

**Authentication failed**:
```bash
# Verify token has correct scopes
curl -H "Authorization: Bearer ${GITHUB_TOKEN}" \
     https://api.github.com/user
```

Token must have `read:packages` scope.

**Image pull fails**:
```bash
# Login manually
echo "${GITHUB_TOKEN}" | podman login ghcr.io -u USERNAME --password-stdin

# Test pull
podman pull ghcr.io/opencenter-cloud/package-name:latest
```

Check package visibility (public vs private).

**No packages found**:
```bash
# Verify organization name
curl -H "Authorization: Bearer ${GITHUB_TOKEN}" \
     https://api.github.com/orgs/opencenter-cloud/packages?package_type=container
```

Ensure token has access to organization.

## Configuration

Edit `config/versions.env`:

```bash
# GitOps repository
OPENCENTER_GITOPS_BASE_REPO="https://github.com/rackerlabs/openCenter-gitops-base"
OPENCENTER_GITOPS_BASE_VERSION="main"

# Container registry
OPENCENTER_CONTAINER_REGISTRY="ghcr.io/opencenter-cloud"
```

## Cleanup

Remove collected assets:
```bash
# Remove images
rm -rf build/opencenter-images/

# Remove GitOps base
rm -rf assets/gitops-base/

# Remove image lists
rm -f build/opencenter-*.txt build/gitops-manifest-images.txt
```

## Next Steps

- [Build air-gap package](build-air-gap-package.md)
- [Verify package integrity](../verify/verify-package-integrity.md)
