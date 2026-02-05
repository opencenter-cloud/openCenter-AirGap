# Update Instructions: File-Based Secrets Migration

**doc_type**: how-to
**audience**: Platform Engineers

## Task

Migrate `collect_opencenter_assets.sh` from environment variable secrets to file-based secrets.

## Prerequisites

- SecretsManager implementation in `src/opencenter_build/secrets.py`
- Bash secrets library in `scripts/lib/secrets.sh`
- GitHub Personal Access Token with `read:packages` scope

## Steps

### 1. Source Secrets Library

Add after the `PROJECT_ROOT` definition (around line 9):

```bash
# Source secrets management functions
source "${SCRIPT_DIR}/../lib/secrets.sh"
```

### 2. Update Header Comment

Change line 5 from:
```bash
# Requires GITHUB_TOKEN environment variable for private packages
```

To:
```bash
# Requires github-token secret file in .secrets/ directory for private packages
```

### 3. Update check_prerequisites Function

Replace the GITHUB_TOKEN check (around lines 60-67):

**Before**:
```bash
if [ -z "${GITHUB_TOKEN:-}" ]; then
    log_warn "GITHUB_TOKEN not set. Private packages may not be accessible."
    log_warn "Set GITHUB_TOKEN to download private container images:"
    log_warn "  export GITHUB_TOKEN=ghp_xxxxxxxxxxxx"
else
    log_info "GITHUB_TOKEN is set"
fi
```

**After**:
```bash
if GITHUB_TOKEN=$(get_github_token 2>/dev/null); then
    log_info "GitHub token loaded from .secrets/github-token"
else
    log_warn "GitHub token not found. Private packages may not be accessible."
    log_warn "Create file-based secret:"
    log_warn "  echo 'ghp_xxxxxxxxxxxx' > .secrets/github-token"
    log_warn "  chmod 600 .secrets/github-token"
fi
```

### 4. Update fetch_opencenter_images Function

Replace the GITHUB_TOKEN check (around lines 100-105):

**Before**:
```bash
if [ -z "${GITHUB_TOKEN:-}" ]; then
    log_error "GITHUB_TOKEN required to list packages from ghcr.io/opencenter-cloud"
    log_error "Set GITHUB_TOKEN or use SKIP_OPENCENTER_PRIVATE_REGISTRY=true"
    exit 1
fi
```

**After**:
```bash
if ! GITHUB_TOKEN=$(get_github_token); then
    log_error "GitHub token required to list packages from ghcr.io/opencenter-cloud"
    log_error "Create file-based secret:"
    log_error "  echo 'ghp_xxxxxxxxxxxx' > .secrets/github-token"
    log_error "  chmod 600 .secrets/github-token"
    log_error "Or use SKIP_OPENCENTER_PRIVATE_REGISTRY=true to skip"
    exit 1
fi
```

### 5. Update copy_opencenter_images Function

Replace the GITHUB_TOKEN check (around lines 198-203):

**Before**:
```bash
if [ -z "${GITHUB_TOKEN:-}" ]; then
    log_error "GITHUB_TOKEN required to copy OCI artifacts from ghcr.io/opencenter-cloud"
    log_error "Set GITHUB_TOKEN or use SKIP_OPENCENTER_PRIVATE_REGISTRY=true"
    exit 1
fi
```

**After**:
```bash
if ! GITHUB_TOKEN=$(get_github_token); then
    log_error "GitHub token required to copy OCI artifacts from ghcr.io/opencenter-cloud"
    log_error "Create file-based secret:"
    log_error "  echo 'ghp_xxxxxxxxxxxx' > .secrets/github-token"
    log_error "  chmod 600 .secrets/github-token"
    log_error "Or use SKIP_OPENCENTER_PRIVATE_REGISTRY=true to skip"
    exit 1
fi
```

### 6. Create Secret File

```bash
# If you have GITHUB_TOKEN in environment
echo "$GITHUB_TOKEN" > .secrets/github-token
chmod 600 .secrets/github-token

# Or create manually
echo 'ghp_xxxxxxxxxxxx' > .secrets/github-token
chmod 600 .secrets/github-token
```

### 7. Test Updated Script

```bash
# Verify secret is readable
cat .secrets/github-token

# Check permissions
ls -l .secrets/github-token
# Should show: -rw------- (600)

# Test the script
./scripts/build/collect_opencenter_assets.sh
```

### 8. Clean Up Environment Variables

```bash
# Remove from current shell
unset GITHUB_TOKEN

# Remove from shell profiles
sed -i.bak '/GITHUB_TOKEN/d' ~/.bashrc
sed -i.bak '/GITHUB_TOKEN/d' ~/.zshrc
sed -i.bak '/GITHUB_TOKEN/d' ~/.profile

# Remove from .env files
sed -i.bak '/GITHUB_TOKEN/d' .env
```

## Verification

### Check Secret File

```bash
# File exists
test -f .secrets/github-token && echo "✓ Secret file exists"

# Correct permissions
[ "$(stat -f %A .secrets/github-token 2>/dev/null || stat -c %a .secrets/github-token)" = "600" ] && echo "✓ Permissions correct"

# Not empty
[ -s .secrets/github-token ] && echo "✓ Secret file not empty"
```

### Test Secrets Library

```bash
# Source the library
source scripts/lib/secrets.sh

# Get token
if GITHUB_TOKEN=$(get_github_token); then
    echo "✓ Token loaded successfully"
    echo "  Length: ${#GITHUB_TOKEN} characters"
else
    echo "✗ Failed to load token"
fi
```

### Test API Access

```bash
# Validate token with GitHub API
curl -s -H "Authorization: Bearer $(cat .secrets/github-token)" \
     https://api.github.com/user | jq -r '.login'
```

## Troubleshooting

### Permission Denied

```
Error: Insecure permissions on .secrets/github-token: 644
```

**Fix**:
```bash
chmod 600 .secrets/github-token
```

### Secret Not Found

```
Error: Secret not found: .secrets/github-token
```

**Fix**:
```bash
echo 'your_token' > .secrets/github-token
chmod 600 .secrets/github-token
```

### Invalid Token

```
curl: (22) The requested URL returned error: 401
```

**Fix**: Regenerate token in GitHub with `read:packages` scope

## Rollback

If issues occur, restore environment variable usage:

```bash
# Restore from backup
cp scripts/build/collect_opencenter_assets.sh.backup scripts/build/collect_opencenter_assets.sh

# Set environment variable
export GITHUB_TOKEN='your_token'
```

## References

- `src/opencenter_build/secrets.py` - Python SecretsManager
- `scripts/lib/secrets.sh` - Bash secrets functions
- `docs/reference/secrets-management.md` - Full documentation
- `.secrets/README.md` - Secrets directory usage
