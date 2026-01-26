---
type: how-to
audience: platform-engineer
difficulty: beginner
version: 1.0.0
last_updated: 2026-01-25
doc_type: how-to
---

# Setup GitHub Token

Configure GitHub Personal Access Token for openCenter asset collection.

## Quick Setup

```bash
./scripts/build/setup_github_token.sh
```

Interactive script that:
1. Opens GitHub token creation page in browser
2. Guides through token configuration
3. Validates token and scopes
4. Tests package access
5. Saves token securely

Duration: 5 minutes.

## What the Script Does

**Token Creation Guidance**:
- Opens correct GitHub page
- Shows required scopes
- Provides step-by-step instructions

**Validation**:
- Tests GitHub API authentication
- Verifies `read:packages` scope
- Tests access to `opencenter-cloud` packages
- Tests GHCR login with podman/docker

**Secure Storage Options**:
1. Environment variable (session only)
2. Shell profile (~/.bashrc or ~/.zshrc)
3. Project .env file (gitignored)
4. Manual export

## Token Types

**Classic Token** (simpler):
- Format: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- Broader access
- Easier to configure

**Fine-grained Token** (more secure):
- Format: `github_pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- Granular permissions
- Repository-specific access

## Required Scopes

**Classic Token**:
- `read:packages` - Read container images
- `repo` - Access private repos (if needed)

**Fine-grained Token**:
- Contents: Read-only
- Packages: Read-only

## Manual Setup

If script fails or manual setup preferred:

**1. Create token**:
- Classic: https://github.com/settings/tokens/new
- Fine-grained: https://github.com/settings/tokens?type=beta

**2. Configure**:
- Name: `openCenter-airgap-build`
- Expiration: 90 days
- Scopes: `read:packages`, `repo`

**3. Export**:
```bash
export GITHUB_TOKEN=ghp_xxx
```

**4. Validate**:
```bash
curl -H "Authorization: Bearer ${GITHUB_TOKEN}" \
     https://api.github.com/user
```

## Verify Setup

```bash
# Check token is set
echo $GITHUB_TOKEN

# Test API access
curl -H "Authorization: Bearer ${GITHUB_TOKEN}" \
     https://api.github.com/orgs/opencenter-cloud/packages?package_type=container

# Test GHCR login
echo "${GITHUB_TOKEN}" | podman login ghcr.io -u USERNAME --password-stdin
```

## Troubleshooting

**Script can't open browser**:
```bash
# Manually open URL shown in output
# Continue with script prompts
```

**Token validation fails**:
- Verify token copied correctly (no spaces)
- Check token hasn't expired
- Ensure required scopes selected

**Package access denied**:
- Token needs `read:packages` scope
- Verify access to `opencenter-cloud` org
- Check token hasn't been revoked

**GHCR login fails**:
- Replace `USERNAME` with your GitHub username
- Verify token has package read permissions
- Check container runtime (podman/docker) installed

## Security

**Token storage**:
- Never commit to git
- Use .env file (gitignored)
- Or store in password manager

**Token rotation**:
- Rotate every 90 days
- Revoke old token after rotation
- Update saved token location

## Next Steps

After token setup:

```bash
# Collect openCenter assets
./scripts/build/collect_opencenter_assets.sh

# Build air-gap package
./scripts/build/build.sh
```

## Reference

- [GitHub Token Reference](../../reference/configuration/github-token.md)
- [Add openCenter Assets](add-opencenter-assets.md)
- [Build Air-Gap Package](build-air-gap-package.md)
