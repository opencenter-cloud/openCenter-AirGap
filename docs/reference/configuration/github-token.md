---
type: reference
audience: platform-engineer
version: 1.0.0
last_updated: 2026-01-25
doc_type: reference
---

# GitHub Token Configuration

GitHub Personal Access Token (PAT) configuration for openCenter asset collection.

## Token Scopes

Required scopes for asset collection:

| Scope | Purpose | Required |
|-------|---------|----------|
| `read:packages` | Read container images from GHCR | Yes |
| `repo` | Access private repositories | If private |
| `read:org` | List organization packages | If private org |

## Create Token

**Classic Token**:
1. Navigate to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Name: `openCenter-airgap-build`
4. Expiration: 90 days (or custom)
5. Select scopes:
   - `read:packages`
   - `repo` (if accessing private repos)
6. Click "Generate token"
7. Copy token immediately (shown once)

**Fine-grained Token**:
1. Navigate to https://github.com/settings/tokens?type=beta
2. Click "Generate new token"
3. Name: `openCenter-airgap-build`
4. Expiration: 90 days
5. Repository access: Select repositories or all
6. Permissions:
   - Contents: Read-only
   - Packages: Read-only
7. Click "Generate token"
8. Copy token

## Token Format

Classic token:
```
ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Fine-grained token:
```
github_pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Set Token

**Environment variable**:
```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Persist in shell**:
```bash
# Add to ~/.bashrc or ~/.zshrc
echo 'export GITHUB_TOKEN=ghp_xxx' >> ~/.bashrc
source ~/.bashrc
```

**Secure storage** (recommended):
```bash
# Store in password manager or secrets vault
# Retrieve when needed
export GITHUB_TOKEN=$(pass show github/opencenter-token)
```

## Verify Token

**Check authentication**:
```bash
curl -H "Authorization: Bearer ${GITHUB_TOKEN}" \
     https://api.github.com/user
```

Expected: User information JSON.

**Check scopes**:
```bash
curl -I -H "Authorization: Bearer ${GITHUB_TOKEN}" \
     https://api.github.com/user | grep x-oauth-scopes
```

Expected: `x-oauth-scopes: read:packages, repo`

**Check rate limit**:
```bash
curl -H "Authorization: Bearer ${GITHUB_TOKEN}" \
     https://api.github.com/rate_limit
```

Expected:
```json
{
  "resources": {
    "core": {
      "limit": 5000,
      "remaining": 4999,
      "reset": 1234567890
    }
  }
}
```

## Login to GHCR

**Podman**:
```bash
echo "${GITHUB_TOKEN}" | podman login ghcr.io -u USERNAME --password-stdin
```

**Docker**:
```bash
echo "${GITHUB_TOKEN}" | docker login ghcr.io -u USERNAME --password-stdin
```

Replace `USERNAME` with your GitHub username.

## Token Security

**Do not**:
- Commit tokens to git
- Share tokens in chat/email
- Use tokens in CI logs
- Store tokens in plain text files

**Do**:
- Use environment variables
- Store in password manager
- Rotate tokens regularly
- Use minimal required scopes
- Set expiration dates

## Token Rotation

Rotate tokens every 90 days:

1. Generate new token with same scopes
2. Update environment variable
3. Test asset collection
4. Revoke old token

## Revoke Token

Revoke compromised token immediately:

1. Navigate to https://github.com/settings/tokens
2. Find token in list
3. Click "Delete"
4. Generate new token

## CI/CD Integration

**GitHub Actions**:
```yaml
- name: Collect openCenter assets
  env:
    GITHUB_TOKEN: ${{ secrets.OPENCENTER_BUILD_TOKEN }}
  run: ./scripts/build/collect_opencenter_assets.sh
```

**GitLab CI**:
```yaml
collect_assets:
  script:
    - export GITHUB_TOKEN=${OPENCENTER_BUILD_TOKEN}
    - ./scripts/build/collect_opencenter_assets.sh
  variables:
    OPENCENTER_BUILD_TOKEN:
      vault: production/github/token@secret
```

## Troubleshooting

**401 Unauthorized**:
- Token expired
- Token revoked
- Incorrect token format

**403 Forbidden**:
- Missing required scopes
- No access to organization
- Rate limit exceeded

**404 Not Found**:
- Package doesn't exist
- Package is private (need `read:packages`)
- Organization name incorrect

## Rate Limits

| Authentication | Limit | Reset |
|----------------|-------|-------|
| Unauthenticated | 60/hour | 1 hour |
| Authenticated | 5000/hour | 1 hour |
| GHCR pulls | Unlimited | - |

Check current limit:
```bash
curl -H "Authorization: Bearer ${GITHUB_TOKEN}" \
     https://api.github.com/rate_limit | jq '.rate'
```

## Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `GITHUB_TOKEN` | Authentication token | `ghp_xxx` |
| `GITHUB_API_URL` | API endpoint (custom) | `https://api.github.com` |
| `GITHUB_ACTOR` | Username for login | `myusername` |

## Examples

**Minimal setup**:
```bash
export GITHUB_TOKEN=ghp_xxx
./scripts/build/collect_opencenter_assets.sh
```

**With custom registry**:
```bash
export GITHUB_TOKEN=ghp_xxx
export OPENCENTER_CONTAINER_REGISTRY=ghcr.io/my-org
./scripts/build/collect_opencenter_assets.sh
```

**Test token**:
```bash
export GITHUB_TOKEN=ghp_xxx

# Test API access
curl -H "Authorization: Bearer ${GITHUB_TOKEN}" \
     https://api.github.com/orgs/opencenter-cloud/packages?package_type=container

# Test GHCR login
echo "${GITHUB_TOKEN}" | podman login ghcr.io -u USERNAME --password-stdin

# Test image pull
podman pull ghcr.io/opencenter-cloud/test:latest
```
