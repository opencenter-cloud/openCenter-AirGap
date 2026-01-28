# Configuration Schemas

**doc_type**: reference
**audience**: Platform Engineers
**scope**: JSON schemas for configuration validation

## Purpose

This directory contains JSON Schema definitions for validating openCenter AirGap configuration files. Validation runs during the build process to catch configuration errors before asset collection begins.

## Schemas

| Schema | Validates | Required Fields |
|--------|-----------|-----------------|
| `versions.schema.json` | `config/versions.env` | KUBERNETES_VERSION, TERRAFORM_VERSION, KUBESPRAY_VERSION |
| `nodes.schema.json` | Node inventory files | control_plane, workers |
| `openstack-config.schema.json` | OpenStack credentials | auth_url, project_name, username |
| `zarf-variables.schema.json` | Zarf variable overrides | install_path, registry_host |

## Usage

```python
from opencenter_build.validation import ConfigValidator
from pathlib import Path

validator = ConfigValidator(Path("config/schemas"))
validator.validate_versions_env(versions_dict)
```

## Schema Format

All schemas follow JSON Schema Draft 7 specification. Each schema includes:
- Required field definitions
- Type constraints
- Pattern validation (regex)
- Format validation (ipv4, uri)
- Descriptive error messages

## Validation Integration

Validation runs automatically in:
1. `scripts/build/validate_config.py` - Standalone validation
2. `scripts/build/build.py` - Pre-build validation gate
3. CI pipeline - Pre-commit validation

## Adding New Schemas

1. Create `<name>.schema.json` in this directory
2. Add validation method to `ConfigValidator` class
3. Add test cases to `tests/unit/test_validation.py`
4. Update this README with schema details
