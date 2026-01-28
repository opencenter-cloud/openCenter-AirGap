# Recovery Procedures

**doc_type**: reference
**audience**: Platform Engineers, Operations Team
**scope**: Recovery procedures for build failures, state corruption, and operational issues

## Overview

This document provides step-by-step recovery procedures for common failure scenarios in the openCenter AirGap build system. Each procedure includes diagnosis steps, recovery actions, and prevention measures.

## Quick Reference

| Scenario | Severity | Recovery Time | Procedure |
|----------|----------|---------------|-----------|
| State file corruption | High | 5 minutes | [State Corruption Recovery](#state-corruption-recovery) |
| Failed build (partial) | Medium | 10-30 minutes | [Failed Build Recovery](#failed-build-recovery) |
| Invalid zarf.yaml | Medium | 5 minutes | [Zarf YAML Recovery](#zarf-yaml-recovery) |
| Missing secrets | High | 2 minutes | [Secrets Recovery](#secrets-recovery) |
| Disk space exhaustion | High | 15 minutes | [Disk Space Recovery](#disk-space-recovery) |
| Corrupted asset cache | Medium | 30-60 minutes | [Asset Cache Recovery](#asset-cache-recovery) |

## State Corruption Recovery

### Symptoms

- Build fails with `StateError: State file corrupted`
- JSON parse errors when reading `.build-state.json`
- Build reports incorrect completion status
- State file contains invalid JSON

### Diagnosis

```bash
# Check if state file exists
ls -lh build/.build-state.json

# Validate JSON syntax
python -m json.tool build/.build-state.json

# Check for backup
ls -lh build/.build-state.backup
```

### Recovery Steps

#### Option 1: Automatic Recovery (Recommended)

```python
from pathlib import Path
from opencenter_build.state import StateManager

state_mgr = StateManager(Path("build/.build-state.json"))

# Attempt automatic recovery from backup
if state_mgr.recover():
    print("State recovered successfully")
    # Verify recovered state
    state = state_mgr.read()
    print(f"Recovered state: {state}")
else:
    print("No valid backup found, manual recovery required")
```

#### Option 2: Manual Recovery from Backup

```bash
# Verify backup is valid JSON
python -m json.tool build/.build-state.backup

# Restore from backup
cp build/.build-state.backup build/.build-state.json

# Verify restoration
python -m json.tool build/.build-state.json
```

#### Option 3: Reset State (Last Resort)

```bash
# Backup corrupted state for analysis
mv build/.build-state.json build/.build-state.corrupted

# Remove lock file
rm -f build/.build-state.lock

# Restart build from beginning
python scripts/build/build.py
```

### Prevention

- State operations use atomic writes with automatic backup
- File locking prevents concurrent access corruption
- Regular state validation during writes
- Transaction support ensures rollback on failures

### Post-Recovery

1. Analyze corrupted state file to identify root cause
2. Check logs for errors preceding corruption: `tail -100 build/build-*.log`
3. Verify disk space and filesystem health
4. Report issue if corruption was not due to manual intervention

## Failed Build Recovery

### Symptoms

- Build exits with non-zero status
- Partial artifacts in `build/` directory
- State shows incomplete steps
- Error messages in build logs

### Diagnosis

```bash
# Check build state
cat build/.build-state.json | python -m json.tool

# Review recent logs
tail -100 build/build-$(date +%Y%m%d)*.log

# Check disk space
df -h .

# Verify prerequisites
python scripts/build/verify_prerequisites.py
```

### Recovery Steps

#### Step 1: Identify Failed Step

```bash
# Check state for last completed step
python -c "
import json
from pathlib import Path
state = json.loads(Path('build/.build-state.json').read_text())
print(f\"Last step: {state.get('last_step', 'unknown')}\")
print(f\"Completed steps: {[k for k, v in state.items() if v is True]}\")
"
```

#### Step 2: Clean Partial Artifacts

```bash
# Remove incomplete artifacts from failed step
# Example: If kubespray collection failed
rm -rf build/kubespray-offline/outputs/*

# Keep state file to resume from last successful step
```

#### Step 3: Resume Build

```bash
# Build system automatically resumes from last successful step
python scripts/build/build.py

# Or force restart from specific step
python scripts/build/build.py --from-step=collect_kubespray
```

#### Step 4: Verify Recovery

```bash
# Check build completed successfully
echo $?  # Should be 0

# Verify package created
ls -lh dist/zarf-package-*.tar.zst

# Inspect package
zarf package inspect dist/zarf-package-*.tar.zst --sbom
```

### Common Failure Causes

#### Network Failures

**Symptoms**: Timeout errors, connection refused, DNS failures

**Recovery**:
```bash
# Verify network connectivity
ping -c 3 github.com

# Check proxy settings if applicable
echo $HTTP_PROXY $HTTPS_PROXY

# Retry build (automatic retry for transient failures)
python scripts/build/build.py
```

#### Insufficient Disk Space

**Symptoms**: "No space left on device" errors

**Recovery**: See [Disk Space Recovery](#disk-space-recovery)

#### Missing Dependencies

**Symptoms**: Command not found, import errors

**Recovery**:
```bash
# Verify all prerequisites
python scripts/build/verify_prerequisites.py

# Install missing dependencies
pip install -e ".[dev]"

# Verify tools available
which git terraform zarf
```

#### Permission Errors

**Symptoms**: Permission denied errors

**Recovery**:
```bash
# Check file permissions
ls -la build/

# Fix ownership if needed
sudo chown -R $USER:$USER build/

# Verify secrets permissions
ls -la .secrets/
chmod 600 .secrets/*
```

### Prevention

- Use transaction support for multi-step operations
- Implement automatic retry for transient failures
- Validate prerequisites before starting build
- Monitor disk space during build
- Use atomic operations for file writes

## Zarf YAML Recovery

### Symptoms

- `zarf.yaml` validation fails
- Package creation fails with schema errors
- Missing or invalid components in zarf.yaml
- Zarf CLI rejects package definition

### Diagnosis

```bash
# Validate zarf.yaml syntax
zarf package inspect zarf.yaml

# Check for backup
ls -lh zarf.yaml.backup

# Compare with template
diff zarf.yaml.template zarf.yaml
```

### Recovery Steps

#### Option 1: Restore from Backup

```bash
# Verify backup exists and is valid
zarf package inspect zarf.yaml.backup

# Restore from backup
cp zarf.yaml.backup zarf.yaml

# Verify restoration
zarf package inspect zarf.yaml
```

#### Option 2: Regenerate from Template

```bash
# Regenerate zarf.yaml
python scripts/build/generate_zarf_yaml.py

# Verify generation
zarf package inspect zarf.yaml

# Check image count
grep -c "image:" zarf.yaml
```

#### Option 3: Manual Fix

```bash
# Edit zarf.yaml
vim zarf.yaml

# Validate after each change
zarf package inspect zarf.yaml

# Test package creation
zarf package create --confirm --dry-run
```

### Prevention

- Automatic backup before zarf.yaml modification
- Transaction support ensures rollback on validation failure
- Pre-commit hooks validate zarf.yaml syntax
- Template-based generation reduces manual errors

## Secrets Recovery

### Symptoms

- Build fails with `SecretsError: Secret not found`
- Permission errors accessing secrets
- Empty secret files
- Secrets in wrong location

### Diagnosis

```bash
# Check secrets directory
ls -la .secrets/

# Verify permissions
stat -c "%a %n" .secrets/*  # Linux
stat -f "%Lp %N" .secrets/*  # macOS

# Check secret content (without displaying)
test -s .secrets/github-token && echo "Secret exists and non-empty" || echo "Secret missing or empty"
```

### Recovery Steps

#### Missing Secret File

```bash
# Create secret file
echo "your-secret-value" > .secrets/github-token

# Set correct permissions
chmod 600 .secrets/github-token

# Verify
ls -la .secrets/github-token
```

#### Incorrect Permissions

```bash
# Fix directory permissions
chmod 700 .secrets/

# Fix file permissions
chmod 600 .secrets/*

# Verify
ls -la .secrets/
```

#### Empty Secret File

```bash
# Re-add secret value
echo "your-secret-value" > .secrets/github-token

# Verify non-empty
test -s .secrets/github-token && echo "OK" || echo "Still empty"
```

### Prevention

- Use `SecretsManager` class for all secret access
- Automatic permission validation on read
- Never commit secrets to git (`.secrets/` in `.gitignore`)
- Pre-commit hooks detect accidental secret commits
- Document secret rotation procedures

## Disk Space Recovery

### Symptoms

- "No space left on device" errors
- Build fails during asset download
- Cannot create temporary files
- Slow build performance

### Diagnosis

```bash
# Check disk usage
df -h .

# Check build directory size
du -sh build/

# Find large files
find build/ -type f -size +100M -exec ls -lh {} \;

# Check for old builds
ls -lht dist/
```

### Recovery Steps

#### Step 1: Clean Old Artifacts

```bash
# Remove old build artifacts
rm -rf build/kubespray-offline/outputs/*

# Remove old packages (keep latest 2)
ls -t dist/zarf-package-*.tar.zst | tail -n +3 | xargs rm -f

# Remove old logs (keep latest 5)
ls -t build/build-*.log | tail -n +6 | xargs rm -f
```

#### Step 2: Clean Temporary Files

```bash
# Remove Python cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null

# Remove pytest cache
rm -rf .pytest_cache/

# Remove mypy cache
rm -rf .mypy_cache/

# Remove hypothesis cache
rm -rf .hypothesis/
```

#### Step 3: Clean Docker/Podman

```bash
# Remove unused images
podman image prune -a -f

# Remove unused volumes
podman volume prune -f

# Check space freed
df -h .
```

#### Step 4: Verify Space Available

```bash
# Ensure at least 100GB free
df -h . | awk 'NR==2 {print $4}'

# Resume build if space sufficient
python scripts/build/build.py
```

### Prevention

- Monitor disk space before starting build
- Implement automatic cleanup of old artifacts
- Set retention policy for build artifacts (keep latest N)
- Use separate partition for build artifacts if possible
- Alert when disk usage exceeds 80%

## Asset Cache Recovery

### Symptoms

- Downloaded assets corrupted or incomplete
- Checksum verification failures
- Missing files in asset directories
- Build fails during asset organization

### Diagnosis

```bash
# Check asset directories
ls -lh build/kubespray-offline/outputs/

# Verify checksums if available
sha256sum -c build/asset-checksums.txt

# Check for incomplete downloads
find build/ -name "*.tmp" -o -name "*.partial"
```

### Recovery Steps

#### Option 1: Re-download Specific Assets

```bash
# Identify failed assets from logs
grep "Failed to download" build/build-*.log

# Remove corrupted assets
rm -f build/kubespray-offline/outputs/files/corrupted-file

# Re-run asset collection
python scripts/build/collect_assets.sh
```

#### Option 2: Full Cache Rebuild

```bash
# Backup state
cp build/.build-state.json build/.build-state.backup

# Clear asset cache
rm -rf build/kubespray-offline/outputs/*

# Reset state for asset collection
python -c "
import json
from pathlib import Path
state = json.loads(Path('build/.build-state.json').read_text())
state['kubespray_collected'] = False
state['assets_organized'] = False
Path('build/.build-state.json').write_text(json.dumps(state, indent=2))
"

# Re-run build
python scripts/build/build.py
```

### Prevention

- Implement checksum verification for all downloads
- Use atomic file operations for downloads
- Retry failed downloads automatically
- Validate assets before marking step complete
- Generate and verify asset manifest

## Log Analysis for Troubleshooting

### Log Locations

```bash
# Build logs
build/build-YYYYMMDD-HHMMSS.log

# Deployment logs (on bastion)
/opt/opencenter/logs/deploy-YYYYMMDD-HHMMSS.log

# Kubespray logs (on bastion)
/opt/opencenter/kubespray/inventory/mycluster/artifacts/
```

### Common Log Patterns

#### Identify Errors

```bash
# Find all errors
grep -i "error" build/build-*.log | tail -20

# Find exceptions
grep -i "exception\|traceback" build/build-*.log

# Find failures
grep -i "failed\|failure" build/build-*.log
```

#### Identify Warnings

```bash
# Find warnings
grep -i "warning\|warn" build/build-*.log

# Find deprecation warnings
grep -i "deprecat" build/build-*.log
```

#### Track Progress

```bash
# Find completed steps
grep "completed successfully" build/build-*.log

# Find current step
tail -50 build/build-*.log | grep "Starting\|Running"
```

#### Performance Analysis

```bash
# Find slow operations
grep "duration\|took\|elapsed" build/build-*.log

# Find large downloads
grep "downloaded\|MB\|GB" build/build-*.log
```

### Log Analysis Tools

```bash
# View logs with context
grep -C 5 "error" build/build-*.log

# Follow logs in real-time
tail -f build/build-*.log

# Search across all logs
find build/ -name "*.log" -exec grep -l "pattern" {} \;

# Extract timestamps
awk '/ERROR/ {print $1, $2, $0}' build/build-*.log
```

## Common Failure Scenarios

### Scenario 1: GitHub Rate Limit Exceeded

**Symptoms**: HTTP 403 errors, "rate limit exceeded" messages

**Diagnosis**:
```bash
# Check rate limit status
curl -H "Authorization: token $(cat .secrets/github-token)" \
  https://api.github.com/rate_limit
```

**Recovery**:
```bash
# Wait for rate limit reset (shown in API response)
# Or use different GitHub token
echo "new-token" > .secrets/github-token
chmod 600 .secrets/github-token

# Resume build
python scripts/build/build.py
```

**Prevention**:
- Use authenticated GitHub API requests
- Implement rate limit checking before API calls
- Cache GitHub API responses
- Use GitHub Enterprise if available

### Scenario 2: Kubespray Version Mismatch

**Symptoms**: Incompatible Kubernetes version, missing playbooks

**Diagnosis**:
```bash
# Check configured versions
grep KUBESPRAY config/versions.env
grep KUBERNETES config/versions.env

# Verify compatibility
cat build/kubespray-offline/kubespray/docs/kubernetes-versions.md
```

**Recovery**:
```bash
# Update versions.env with compatible versions
vim config/versions.env

# Clear kubespray cache
rm -rf build/kubespray-offline/

# Rebuild
python scripts/build/build.py
```

**Prevention**:
- Pin Kubespray to specific commit SHA
- Validate version compatibility before build
- Test version combinations in CI
- Document supported version matrix

### Scenario 3: Container Registry Timeout

**Symptoms**: Image pull timeouts, registry connection errors

**Diagnosis**:
```bash
# Test registry connectivity
curl -I https://registry-1.docker.io/v2/

# Check for rate limiting
docker pull alpine:latest
```

**Recovery**:
```bash
# Configure registry mirror if available
# Edit /etc/containers/registries.conf

# Or retry with exponential backoff (automatic in build system)
python scripts/build/build.py
```

**Prevention**:
- Use container registry mirror
- Implement retry logic with backoff
- Cache pulled images locally
- Monitor registry status before build

### Scenario 4: Corrupted Python Package

**Symptoms**: Import errors, module not found, version conflicts

**Diagnosis**:
```bash
# Check installed packages
pip list | grep opencenter

# Verify package integrity
pip check

# Check for conflicts
pip list --outdated
```

**Recovery**:
```bash
# Uninstall package
pip uninstall opencenter-build -y

# Clear pip cache
pip cache purge

# Reinstall
pip install -e ".[dev]"

# Verify
python -c "import opencenter_build; print('OK')"
```

**Prevention**:
- Pin all dependencies in pyproject.toml
- Use virtual environments
- Regular dependency updates
- CI testing with fresh installs

## Escalation Paths

### Level 1: Self-Service Recovery

**Scope**: Common issues with documented recovery procedures

**Actions**:
1. Identify issue using symptoms in this document
2. Follow recovery procedure
3. Verify recovery successful
4. Document any deviations from procedure

**Escalate if**:
- Recovery procedure fails after 2 attempts
- Issue not covered in documentation
- Data loss risk identified
- Security incident suspected

### Level 2: Team Support

**Contact**: Platform Engineering Team

**Scope**: Complex issues requiring team expertise

**Actions**:
1. Gather diagnostic information:
   - Error messages and logs
   - State file contents
   - System information (disk, memory, network)
   - Steps to reproduce
2. Create support ticket with gathered information
3. Follow team guidance

**Escalate if**:
- Issue affects multiple users
- Production deployment blocked
- Security vulnerability identified
- Data corruption detected

### Level 3: Vendor Support

**Contact**: Zarf, Kubespray, or infrastructure vendor

**Scope**: Issues with third-party components

**Actions**:
1. Verify issue is with third-party component
2. Gather vendor-specific diagnostics
3. Check vendor documentation and known issues
4. Open vendor support ticket
5. Provide detailed reproduction steps

**Escalate if**:
- Vendor component bug confirmed
- Security vulnerability in vendor component
- Vendor component incompatibility

## Emergency Contacts

| Role | Contact | Availability |
|------|---------|--------------|
| Platform Engineering Lead | [Contact Info] | 24/7 |
| Security Team | [Contact Info] | 24/7 |
| Infrastructure Team | [Contact Info] | Business Hours |
| Vendor Support | [Contact Info] | Per SLA |

## Post-Incident Review

After resolving any incident:

1. **Document Incident**:
   - What happened
   - Root cause
   - Impact
   - Resolution steps
   - Time to resolve

2. **Update Procedures**:
   - Add new recovery procedures if needed
   - Update existing procedures with lessons learned
   - Improve diagnostic steps

3. **Implement Prevention**:
   - Add monitoring for early detection
   - Automate recovery where possible
   - Update validation checks
   - Improve error messages

4. **Share Knowledge**:
   - Brief team on incident and resolution
   - Update training materials
   - Add to FAQ if common issue

## Additional Resources

- [Rollback Patterns](rollback.md) - Transaction and rollback mechanisms
- [State Management](../reference/state-management-integration.md) - State file operations
- [Secrets Management](secrets-management.md) - Secure secrets handling
- [Logging](logging.md) - Centralized logging configuration
- [Coding Standards](coding-standards.md) - Development guidelines
