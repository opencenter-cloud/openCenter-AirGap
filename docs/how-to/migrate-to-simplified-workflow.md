**doc_type: how-to**

# Migrate to Simplified Workflow

Migrate from the old workflow (manual `components.yaml` management) to the new simplified workflow where `versions.env` is the single source of truth.

## Who This Is For

Existing users who have projects using the old workflow with manually maintained `components.yaml` files.

## What Changed

**Old Workflow:**
```bash
opencenter-build init --create-manifest
vim config/components.yaml  # Manual editing
opencenter-build build
```

**New Workflow:**
```bash
opencenter-build init
vim config/versions.env     # Single source of truth
opencenter-build build      # Auto-generates components.yaml
```

**Key Changes:**
- `init` no longer creates `components.yaml` or accepts `--create-manifest` flag
- `build` auto-generates `components.yaml` from `versions.env`
- `build` accepts `--force-regenerate` flag to override existing manifest
- `scan` accepts `--repos` flag to clone and scan repositories automatically
- Manual edits to `components.yaml` are preserved during regeneration

## Backward Compatibility

Existing projects continue to work without changes:
- If `components.yaml` exists and is newer than `versions.env`, it's used as-is
- No automatic regeneration unless `versions.env` is modified
- All existing commands and flags remain functional

## Migration Scenarios

### Scenario 1: Fresh Start

Start a new project with the simplified workflow.

```bash
# Initialize with new workflow
opencenter-build init

# Edit versions
vim config/versions.env

# Build (auto-generates components.yaml)
opencenter-build build

# Optional: Discover additional components
opencenter-build scan --repos
```

### Scenario 2: Existing Project, No Customization

You have an existing project with standard `components.yaml` and no custom additions.

**Steps:**

1. Ensure `versions.env` contains all version information:
```bash
# Verify versions.env is complete
cat config/versions.env
```

2. Backup existing manifest:
```bash
cp config/components.yaml config/components.yaml.backup
```

3. Regenerate from versions.env:
```bash
opencenter-build build --force-regenerate
```

4. Verify the new manifest:
```bash
diff config/components.yaml.backup config/components.yaml
```

5. If satisfied, remove backup:
```bash
rm config/components.yaml.backup
```

### Scenario 3: Existing Project with Custom Components

You have custom images, charts, or tools added to `components.yaml` that aren't in `versions.env`.

**Steps:**

1. Identify custom additions:
```bash
# Review your components.yaml for manual additions
vim config/components.yaml
```

2. Update `versions.env` if needed:
```bash
# Add any missing version variables
vim config/versions.env
```

3. Build with automatic merge:
```bash
# Touch versions.env to make it newer
touch config/versions.env

# Build regenerates and preserves custom additions
opencenter-build build
```

The build process automatically:
- Regenerates standard components from `versions.env`
- Preserves custom images in `images.additional`
- Preserves custom charts not in generated manifest
- Preserves custom tools not in generated manifest

4. Verify custom components preserved:
```bash
# Check that your custom additions are still present
grep "custom-registry.io" config/components.yaml
```

### Scenario 4: Migrate Custom Components to versions.env

You want to move custom components into `versions.env` for better version management.

**Steps:**

1. Add custom component versions to `versions.env`:
```bash
# Example: Add custom application version
echo "MYAPP_VERSION=v1.2.3" >> config/versions.env
echo "MYAPP_IMAGE=custom-registry.io/myapp" >> config/versions.env
```

2. Update manifest generation logic (if needed):
```python
# In your custom build script or fork
# Add logic to create_default_manifest() to include custom components
```

3. Regenerate manifest:
```bash
opencenter-build build --force-regenerate
```

### Scenario 5: Continue Using Manual Workflow

You prefer to maintain `components.yaml` manually.

**Steps:**

1. Keep `components.yaml` newer than `versions.env`:
```bash
# After editing components.yaml
touch config/components.yaml
```

2. Build as usual:
```bash
opencenter-build build
```

The build process detects that `components.yaml` is newer and uses it without regeneration.

## Verification

After migration, verify the workflow:

```bash
# 1. Check that components.yaml exists
ls -l config/components.yaml

# 2. Verify it contains expected components
grep -A 5 "images:" config/components.yaml

# 3. Test build
opencenter-build build --clean

# 4. Verify generated artifacts
ls -l dist/
```

## Troubleshooting

### components.yaml keeps getting regenerated

**Cause:** `versions.env` is newer than `components.yaml`.

**Solution:**
```bash
# Option 1: Touch components.yaml to make it newer
touch config/components.yaml

# Option 2: Accept regeneration and let it preserve your edits
opencenter-build build
```

### Custom components disappeared after build

**Cause:** Used `--force-regenerate` which discards manual edits.

**Solution:**
```bash
# Restore from backup
cp config/components.yaml.backup config/components.yaml

# Or restore from git
git checkout config/components.yaml

# Rebuild without --force-regenerate
opencenter-build build
```

### Build fails with "versions.env not found"

**Cause:** Old project structure without `versions.env`.

**Solution:**
```bash
# Create versions.env from template
opencenter-build init --force

# Or manually create versions.env
cp config/versions.env.example config/versions.env
vim config/versions.env
```

### Merge didn't preserve my custom components

**Cause:** Custom components may have conflicting names with generated components.

**Solution:**
```bash
# Check the build log for merge details
grep "Preserved" build.log

# Manually re-add components if needed
opencenter-build add image custom-registry.io/myapp:v1.0
```

## Best Practices

1. **Use versions.env as source of truth:** Define all standard component versions in `versions.env`

2. **Use add command for custom components:** Add project-specific components via CLI:
```bash
opencenter-build add image custom-registry.io/app:v1.0
```

3. **Commit both files:** Commit both `versions.env` and `components.yaml` to version control

4. **Document custom additions:** Add comments in `components.yaml` to explain custom components:
```yaml
images:
  additional:
    - custom-registry.io/app:v1.0  # Custom application for site X
```

5. **Test regeneration:** Periodically test `--force-regenerate` to ensure versions.env is complete:
```bash
# Backup first
cp config/components.yaml config/components.yaml.test
opencenter-build build --force-regenerate
diff config/components.yaml.test config/components.yaml
```

## Rollback

If you need to rollback to the old workflow:

```bash
# 1. Restore old components.yaml from git history
git log --all --full-history -- config/components.yaml
git checkout <commit> -- config/components.yaml

# 2. Make it newer than versions.env
touch config/components.yaml

# 3. Build uses existing manifest
opencenter-build build
```

## See Also

- [CLI Commands Reference](../reference/cli-commands.md)
- [Component Manifest Schema](../reference/component-manifest-schema.md)
- [First Deployment Tutorial](../tutorials/01-first-deployment.md)
