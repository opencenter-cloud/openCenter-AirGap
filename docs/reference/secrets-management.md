# Secrets Management

**doc_type**: reference
**audience**: Platform Engineers, Security Engineers

File-based secrets management with permission enforcement for openCenter AirGap builds.

## Overview

Secrets are stored in individual files within `.secrets/` directory. All secret files must have `0600` permissions (owner read/write only). This prevents credential exposure in shell history, process listings, and log files.

## SecretsManager API

### Initialization

```python
from pathlib import Path
from opencenter_build.secrets import SecretsManager

secrets = SecretsManager(Path(".secrets"))
```

### Methods

#### get_secret(secret_name: str) -> str

Read secret from file with validation.

**Parameters**:
- `secret_name`: Name of secret file (without path)

**Returns**: Secret value (whitespace stripped)

**Raises**:
- `SecretsError`: If file missing, wrong permissions, or empty

**Example**:
```python
token = secrets.get_secret("github-token")
```

#### set_secret(secret_name: str, value: str) -> None

Write secret to file with secure permissions.

Creates `.secrets/` directory (0700) if missing. Creates or overwrites secret file with 0600 permissions.

**Parameters**:
- `secret_name`: Name of secret file (without path)
- `value`: Secret value to write

**Raises**:
- `SecretsError`: If unable to create directory or write file

**Example**:
```python
secrets.set_secret("github-token", "ghp_xxxxxxxxxxxx")
```

#### secret_exists(secret_name: str) -> bool

Check if secret file exists.

**Parameters**:
- `secret_name`: Name of secret file (without path)

**Returns**: True if file exists, False otherwise

**Example**:
```python
if secrets.secret_exists("github-token"):
    token = secrets.get_secret("github-token")
```

#### delete_secret(secret_name: str) -> None

Delete secret file.

**Parameters**:
- `secret_name`: Name of secret file (without path)

**Raises**:
- `SecretsError`: If file doesn't exist or cannot be deleted

**Example**:
```python
secrets.delete_secret("old-token")
```

#### list_secrets() -> list[str]

List all secret files in directory.

**Returns**: List of secret file names (without paths)

**Example**:
```python
all_secrets = secrets.list_secrets()
print(f"Found {len(all_secrets)} secrets")
```

## Permission Requirements

### File Permissions

Secret files MUST have `0600` permissions:
- Owner: read, write
- Group: none
- Other: none

```bash
# Set correct permissions
chmod 600 .secrets/github-token

# Verify
ls -l .secrets/github-token
# Output: -rw------- 1 user user 40 Jan 27 14:30 .secrets/github-token
```

### Directory Permissions

`.secrets/` directory should have `0700` permissions:
- Owner: read, write, execute
- Group: none
- Other: none

```bash
# Set correct permissions
chmod 700 .secrets/

# Verify
ls -ld .secrets/
# Output: drwx------ 2 user user 64 Jan 27 14:30 .secrets/
```

### Validation

`SecretsManager.get_secret()` validates permissions before reading. Invalid permissions raise `SecretsError`:

```python
# File has 0644 permissions (world-readable)
try:
    token = secrets.get_secret("insecure-token")
except SecretsError as e:
    print(e)
    # Output: Insecure permissions on .secrets/insecure-token: 0o644
    #         Secret files must be readable/writable by owner only.
    #         Fix with: chmod 600 .secrets/insecure-token
```

## Required Secrets

### github-token

**Purpose**: Access GitHub Container Registry for private openCenter images

**Format**: GitHub Personal Access Token (classic) with `read:packages` scope

**Creation**:
1. GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token with `read:packages` scope
3. Copy token
4. Save to file:
   ```bash
   echo 'ghp_xxxxxxxxxxxx' > .secrets/github-token
   chmod 600 .secrets/github-token
   ```

**Validation**:
```bash
curl -H "Authorization: Bearer $(cat .secrets/github-token)" \
     https://api.github.com/user
```

**Used by**:
- `scripts/build/collect_opencenter_assets.sh`

## Secret Rotation

### Rotation Process

1. **Generate new credential** in source system (GitHub, etc.)

2. **Update secret file**:
   ```bash
   echo 'new_secret_value' > .secrets/github-token
   chmod 600 .secrets/github-token
   ```

3. **Test build** with new secret:
   ```bash
   make test
   ```

4. **Revoke old credential** in source system

### Rotation Schedule

| Secret | Rotation Frequency | Trigger |
|--------|-------------------|---------|
| github-token | 90 days | Personnel changes, suspected compromise |
| api-keys | Per policy | Personnel changes, suspected compromise |

### Rotation Checklist

- [ ] Generate new credential in source system
- [ ] Update `.secrets/` file with new value
- [ ] Verify file permissions (0600)
- [ ] Test build process
- [ ] Verify all operations succeed
- [ ] Revoke old credential
- [ ] Document rotation in change log

## Migration from Environment Variables

### Old Method (Insecure)

```bash
# Shell history exposes token
export GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# Process listing exposes token
ps aux | grep GITHUB_TOKEN

# Logs may capture token
echo "Using token: $GITHUB_TOKEN"
```

### New Method (Secure)

```bash
# Create secret file
echo "$GITHUB_TOKEN" > .secrets/github-token
chmod 600 .secrets/github-token

# Clear environment variable
unset GITHUB_TOKEN

# Remove from shell profiles
sed -i '/GITHUB_TOKEN/d' ~/.bashrc
sed -i '/GITHUB_TOKEN/d' ~/.zshrc
```

### Script Migration

**Before**:
```bash
#!/bin/bash
if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo "Error: GITHUB_TOKEN not set"
    exit 1
fi

curl -H "Authorization: Bearer ${GITHUB_TOKEN}" ...
```

**After**:
```bash
#!/bin/bash
SECRETS_DIR="${PROJECT_ROOT}/.secrets"
GITHUB_TOKEN_FILE="${SECRETS_DIR}/github-token"

if [ ! -f "${GITHUB_TOKEN_FILE}" ]; then
    echo "Error: ${GITHUB_TOKEN_FILE} not found"
    echo "Create with: echo 'token' > ${GITHUB_TOKEN_FILE}"
    echo "Set permissions: chmod 600 ${GITHUB_TOKEN_FILE}"
    exit 1
fi

# Check permissions
if [ "$(stat -f %A "${GITHUB_TOKEN_FILE}")" != "600" ]; then
    echo "Error: Insecure permissions on ${GITHUB_TOKEN_FILE}"
    echo "Fix with: chmod 600 ${GITHUB_TOKEN_FILE}"
    exit 1
fi

GITHUB_TOKEN=$(cat "${GITHUB_TOKEN_FILE}")
curl -H "Authorization: Bearer ${GITHUB_TOKEN}" ...
```

## Error Handling

### Missing Secret

```python
try:
    token = secrets.get_secret("missing-token")
except SecretsError as e:
    logger.error(f"Secret not found: {e}")
    # Handle error: prompt user, use fallback, etc.
```

### Invalid Permissions

```python
try:
    token = secrets.get_secret("insecure-token")
except SecretsError as e:
    logger.error(f"Permission error: {e}")
    # Error message includes chmod command to fix
```

### Empty Secret

```python
try:
    token = secrets.get_secret("empty-token")
except SecretsError as e:
    logger.error(f"Empty secret: {e}")
    # Error message includes instructions to add value
```

## Security Controls

### Git Exclusion

`.secrets/` is excluded from git via `.gitignore`:

```gitignore
# Secrets
.secrets/
```

Verify exclusion:
```bash
git status .secrets/
# Output: fatal: pathspec '.secrets/' did not match any files
```

### Pre-commit Hook

Pre-commit hook detects accidentally committed secrets:

```yaml
# .pre-commit-config.yaml
- repo: https://github.com/Yelp/detect-secrets
  hooks:
    - id: detect-secrets
```

### Audit

Check for exposed secrets:

```bash
# Check git history
git log -p | grep -i "ghp_"

# Check shell history
history | grep -i "token"

# Check for world-readable files
find .secrets/ -type f ! -perm 600

# Check for secrets in environment
env | grep -i "token"
```

## Backup and Recovery

### Backup

Store secrets in password manager or encrypted vault. Do not backup to unencrypted locations.

**Recommended tools**:
- 1Password
- LastPass
- HashiCorp Vault
- AWS Secrets Manager

### Recovery

If secrets are lost:

1. **Regenerate credentials** in source system
2. **Recreate secret files**:
   ```bash
   echo 'new_token' > .secrets/github-token
   chmod 600 .secrets/github-token
   ```
3. **Test build process**
4. **Document incident**

## Troubleshooting

### Permission Denied

**Symptom**:
```
PermissionError: [Errno 13] Permission denied: '.secrets/github-token'
```

**Cause**: File permissions too restrictive (e.g., 0400)

**Fix**:
```bash
chmod 600 .secrets/github-token
```

### File Not Found

**Symptom**:
```
SecretsError: Secret not found: .secrets/github-token
```

**Cause**: Secret file doesn't exist

**Fix**:
```bash
echo 'your_token' > .secrets/github-token
chmod 600 .secrets/github-token
```

### Empty Secret

**Symptom**:
```
SecretsError: Secret file is empty: .secrets/github-token
```

**Cause**: File exists but contains no data

**Fix**:
```bash
echo 'your_token' > .secrets/github-token
```

### Insecure Permissions

**Symptom**:
```
SecretsError: Insecure permissions on .secrets/github-token: 0o644
```

**Cause**: File is readable by group or others

**Fix**:
```bash
chmod 600 .secrets/github-token
```

## Best Practices

1. **Never commit secrets** to version control
2. **Use unique secrets** per environment (dev, staging, prod)
3. **Rotate secrets regularly** (90 days for tokens)
4. **Revoke immediately** on personnel changes
5. **Audit regularly** for exposed secrets
6. **Use password manager** for backup
7. **Document rotation** in change log
8. **Test after rotation** before revoking old credential
9. **Monitor access** to secrets directory
10. **Encrypt backups** if stored outside password manager

## References

- [GitHub Personal Access Tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [CIS Controls: Secure Configuration](https://www.cisecurity.org/controls)
