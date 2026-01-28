# Architecture Improvements - Design Document

**doc_type**: explanation
**audience**: Platform Engineers, Developers
**scope**: Technical design for implementing architecture review recommendations

## Overview

This design implements 8 weeks of architecture improvements to the openCenter AirGap build system. The improvements address critical maintainability, testability, and operational resilience gaps identified in the architecture review.

The design follows a phased approach:
- **Weeks 1-2**: Critical infrastructure (Python packaging, config validation, atomic state)
- **Week 3**: Error handling and logging standardization
- **Week 4**: Security and recovery mechanisms
- **Weeks 5-6**: Testing and observability
- **Week 7**: CI/CD and developer tooling
- **Week 8**: Security validation (checksums, image scanning)

### Design Principles

1. **Backward Compatibility**: All changes maintain existing script interfaces
2. **Fail-Fast**: Invalid configurations caught at validation time, not runtime
3. **Atomic Operations**: State changes are all-or-nothing with rollback capability
4. **Testability**: All new code designed for unit and property-based testing

## Architecture

### Current State

```
opencenter-airgap/
├── scripts/
│   ├── build/          # Mixed Python/Bash, no dependency management
│   └── deploy/         # Bash scripts with custom logging
├── config/
│   └── versions.env    # Shell variables, no validation
└── build/
    └── .build-state.json  # Non-atomic writes
```

**Issues**:
- No Python package structure or dependency management
- Configuration files lack schema validation
- State file updates not atomic (corruption risk)
- Mixed error handling patterns across languages
- No centralized logging
- Secrets passed via environment variables
- No rollback mechanisms
- Limited test coverage (~20%)

### Target State

```
opencenter-airgap/
├── pyproject.toml                    # Python package definition
├── src/
│   └── opencenter_build/             # Reusable Python package
│       ├── __init__.py
│       ├── exceptions.py             # Exception hierarchy
│       ├── logging.py                # Centralized logging
│       ├── state.py                  # Atomic state management
│       ├── config.py                 # Configuration loading
│       ├── validation.py             # Schema validation
│       ├── secrets.py                # Secure secrets management
│       ├── transaction.py            # Rollback support
│       ├── metrics.py                # Build metrics
│       ├── image_utils.py            # Skopeo/Podman image operations
│       ├── version_utils.py          # Version validation
│       └── zarf_utils.py             # Zarf generation
├── scripts/
│   ├── build/                        # Thin wrappers using src/
│   ├── deploy/                       # Enhanced with new logging
│   └── lib/                          # Shared utilities
├── config/
│   ├── versions.env                  # Validated against schema
│   └── schemas/                      # JSON schemas
│       ├── versions.schema.json
│       ├── nodes.schema.json
│       └── openstack-config.schema.json
├── .secrets/                         # File-based secrets (0600)
│   └── github-token
├── tests/
│   ├── unit/                         # Unit tests
│   ├── property/                     # Property-based tests
│   └── integration/                  # End-to-end tests
├── .github/
│   └── workflows/
│       └── ci.yml                    # Automated testing
├── Makefile                          # Developer commands
└── docs/
    └── reference/
        └── coding-standards.md       # Language decision matrix
```

**Improvements**:
- Python package with dependency management
- Schema validation for all config files
- Atomic state operations with locking
- Standardized exception hierarchy
- Centralized structured logging
- File-based secrets with permission checks
- Transaction-based rollback
- Skopeo/Podman for container operations (no Docker)
- Comprehensive test coverage (target 80%)

## Components and Interfaces

### 1. Python Package Structure

**Component**: `opencenter_build` package

**Purpose**: Provide reusable, testable Python modules for build operations

**Interface**:
```python
# pyproject.toml
[project]
name = "opencenter-build"
version = "1.0.0"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-timeout>=2.1",
    "hypothesis>=6.0",  # Property-based testing
    "black>=23.0",
    "mypy>=1.0",
    "pylint>=2.17"
]

[tool.black]
line-length = 100

[tool.mypy]
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
```

**Installation**:
```bash
pip install -e .              # Development install
pip install -e ".[dev]"       # With dev dependencies
```

### 2. Exception Hierarchy

**Component**: `src/opencenter_build/exceptions.py`

**Purpose**: Provide structured exception types for error handling

**Interface**:
```python
class OpenCenterError(Exception):
    """Base exception for all openCenter errors."""
    pass

class BuildError(OpenCenterError):
    """Build operation failed."""
    pass

class AssetCollectionError(BuildError):
    """Asset collection failed."""
    pass

class ValidationError(OpenCenterError):
    """Configuration validation failed."""
    pass

class StateError(OpenCenterError):
    """State management operation failed."""
    pass

class SecretsError(OpenCenterError):
    """Secrets management operation failed."""
    pass

class DeploymentError(OpenCenterError):
    """Deployment operation failed."""
    pass
```

**Usage**:
```python
from opencenter_build.exceptions import ValidationError

def validate_config(config: dict) -> None:
    if "KUBERNETES_VERSION" not in config:
        raise ValidationError(
            "Missing required field: KUBERNETES_VERSION"
        )
```

### 3. Centralized Logging

**Component**: `src/opencenter_build/logging.py`

**Purpose**: Provide structured logging with consistent format

**Interface**:
```python
import logging
from pathlib import Path
from typing import Optional

def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    log_to_console: bool = True
) -> None:
    """Configure logging for build operations.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
        log_to_console: Whether to log to stderr
    """
    handlers = []

    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        )
        handlers.append(console_handler)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            )
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True
    )

def get_logger(name: str) -> logging.Logger:
    """Get logger for module."""
    return logging.getLogger(name)
```

**Usage**:
```python
from opencenter_build.logging import setup_logging, get_logger

setup_logging(log_file=Path("build/build.log"))
logger = get_logger(__name__)

logger.info("Starting asset collection")
logger.error("Failed to download: %s", url, exc_info=True)
```

### 4. Atomic State Management

**Component**: `src/opencenter_build/state.py`

**Purpose**: Provide atomic state file operations with recovery

**Interface**:
```python
import json
import fcntl
from pathlib import Path
from typing import Any, Dict
from contextlib import contextmanager

class StateManager:
    """Manage build state with atomic operations."""

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.lock_file = state_file.with_suffix('.lock')

    @contextmanager
    def lock(self):
        """Acquire exclusive lock on state file."""
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.lock_file, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def read(self) -> Dict[str, Any]:
        """Read state atomically."""
        with self.lock():
            if not self.state_file.exists():
                return {}
            return json.loads(self.state_file.read_text())

    def write(self, state: Dict[str, Any]) -> None:
        """Write state atomically with backup."""
        with self.lock():
            # Create backup
            if self.state_file.exists():
                backup = self.state_file.with_suffix('.backup')
                backup.write_bytes(self.state_file.read_bytes())

            # Atomic write
            temp_file = self.state_file.with_suffix('.tmp')
            temp_file.write_text(json.dumps(state, indent=2))
            temp_file.replace(self.state_file)

    def recover(self) -> bool:
        """Recover from backup if state corrupted."""
        backup = self.state_file.with_suffix('.backup')
        if not backup.exists():
            return False

        try:
            # Validate backup
            json.loads(backup.read_text())
            # Restore
            backup.replace(self.state_file)
            return True
        except json.JSONDecodeError:
            return False
```

**Usage**:
```python
from opencenter_build.state import StateManager

state_mgr = StateManager(Path("build/.build-state.json"))

# Read state
state = state_mgr.read()

# Update state
state["kubespray_collected"] = True
state_mgr.write(state)

# Recover if corrupted
if state_mgr.recover():
    logger.info("State recovered from backup")
```

### 5. Configuration Validation

**Component**: `src/opencenter_build/validation.py`

**Purpose**: Validate configuration files against JSON schemas

**Interface**:
```python
import json
from pathlib import Path
from typing import Dict, Any
import jsonschema
from opencenter_build.exceptions import ValidationError

class ConfigValidator:
    """Validate configuration files against schemas."""

    def __init__(self, schema_dir: Path):
        self.schema_dir = schema_dir

    def _load_schema(self, schema_name: str) -> Dict[str, Any]:
        """Load JSON schema."""
        schema_path = self.schema_dir / schema_name
        if not schema_path.exists():
            raise ValidationError(f"Schema not found: {schema_name}")
        return json.loads(schema_path.read_text())

    def validate_versions_env(self, config: Dict[str, str]) -> None:
        """Validate versions.env configuration."""
        schema = self._load_schema("versions.schema.json")
        try:
            jsonschema.validate(config, schema)
        except jsonschema.ValidationError as e:
            raise ValidationError(
                f"Invalid versions.env: {e.message}\n"
                f"Path: {'.'.join(str(p) for p in e.path)}"
            ) from e

    def validate_nodes_file(self, config: Dict[str, Any]) -> None:
        """Validate nodes.yaml configuration."""
        schema = self._load_schema("nodes.schema.json")
        try:
            jsonschema.validate(config, schema)
        except jsonschema.ValidationError as e:
            raise ValidationError(
                f"Invalid nodes.yaml: {e.message}"
            ) from e

    def validate_openstack_config(self, config: Dict[str, Any]) -> None:
        """Validate OpenStack configuration."""
        schema = self._load_schema("openstack-config.schema.json")
        try:
            jsonschema.validate(config, schema)
        except jsonschema.ValidationError as e:
            raise ValidationError(
                f"Invalid OpenStack config: {e.message}"
            ) from e
```

**Usage**:
```python
from opencenter_build.validation import ConfigValidator

validator = ConfigValidator(Path("config/schemas"))

# Validate versions
versions = parse_versions_env()
validator.validate_versions_env(versions)

# Validate nodes
nodes = yaml.safe_load(Path("nodes.yaml").read_text())
validator.validate_nodes_file(nodes)
```

### 6. Secrets Management

**Component**: `src/opencenter_build/secrets.py`

**Purpose**: Secure file-based secrets with permission validation

**Interface**:
```python
import os
from pathlib import Path
from opencenter_build.exceptions import SecretsError

class SecretsManager:
    """Manage secrets with security checks."""

    def __init__(self, secrets_dir: Path):
        self.secrets_dir = secrets_dir

    def _check_permissions(self, file_path: Path) -> None:
        """Verify file has secure permissions (0600)."""
        stat_info = file_path.stat()
        mode = stat_info.st_mode & 0o777

        if mode != 0o600:
            raise SecretsError(
                f"Insecure permissions on {file_path}: {oct(mode)}\n"
                f"Fix with: chmod 600 {file_path}"
            )

    def get_secret(self, secret_name: str) -> str:
        """Read secret from file with validation."""
        secret_file = self.secrets_dir / secret_name

        if not secret_file.exists():
            raise SecretsError(
                f"Secret not found: {secret_file}\n"
                f"Create with: echo 'secret_value' > {secret_file}\n"
                f"Set permissions: chmod 600 {secret_file}"
            )

        self._check_permissions(secret_file)

        secret = secret_file.read_text().strip()
        if not secret:
            raise SecretsError(f"Secret file is empty: {secret_file}")

        return secret

    def set_secret(self, secret_name: str, value: str) -> None:
        """Write secret to file with secure permissions."""
        self.secrets_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        secret_file = self.secrets_dir / secret_name
        secret_file.write_text(value)
        secret_file.chmod(0o600)
```

**Usage**:
```python
from opencenter_build.secrets import SecretsManager

secrets = SecretsManager(Path(".secrets"))

# Read secret
github_token = secrets.get_secret("github-token")

# Write secret
secrets.set_secret("github-token", "ghp_xxxxxxxxxxxx")
```

### 7. Transaction and Rollback

**Component**: `src/opencenter_build/transaction.py`

**Purpose**: Provide rollback capability for multi-step operations

**Interface**:
```python
from contextlib import contextmanager
from typing import Callable, List
import logging

logger = logging.getLogger(__name__)

class Transaction:
    """Transaction with rollback support."""

    def __init__(self):
        self.rollback_actions: List[Callable[[], None]] = []
        self.committed = False

    def add_rollback(self, action: Callable[[], None]) -> None:
        """Add rollback action (executed in reverse order)."""
        self.rollback_actions.append(action)

    def commit(self) -> None:
        """Commit transaction (clear rollback actions)."""
        self.rollback_actions.clear()
        self.committed = True

    def rollback(self) -> None:
        """Execute rollback actions in reverse order."""
        for action in reversed(self.rollback_actions):
            try:
                action()
            except Exception as e:
                logger.error(f"Rollback action failed: {e}", exc_info=True)

@contextmanager
def transactional_operation():
    """Context manager for transactional operations."""
    tx = Transaction()
    try:
        yield tx
        tx.commit()
    except Exception:
        logger.error("Operation failed, rolling back...")
        tx.rollback()
        raise
```

**Usage**:
```python
from opencenter_build.transaction import transactional_operation
import shutil

with transactional_operation() as tx:
    # Backup original
    shutil.copy("zarf.yaml", "zarf.yaml.backup")
    tx.add_rollback(lambda: shutil.move("zarf.yaml.backup", "zarf.yaml"))

    # Perform operation
    generate_zarf_yaml()

    # If exception occurs, rollback restores zarf.yaml
```

### 8. Build Metrics

**Component**: `src/opencenter_build/metrics.py`

**Purpose**: Collect and export build metrics

**Interface**:
```python
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
import json

@dataclass
class BuildMetrics:
    """Build operation metrics."""
    build_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    steps_completed: int = 0
    steps_failed: int = 0
    package_size_bytes: Optional[int] = None
    image_count: int = 0
    success: bool = False

    def complete(self, success: bool = True) -> None:
        """Mark build complete."""
        self.end_time = datetime.now()
        self.duration_seconds = (
            self.end_time - self.start_time
        ).total_seconds()
        self.success = success

    def to_json(self) -> str:
        """Export as JSON."""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        if self.end_time:
            data['end_time'] = self.end_time.isoformat()
        return json.dumps(data, indent=2)

    def to_prometheus(self) -> str:
        """Export in Prometheus format."""
        lines = [
            f'# HELP opencenter_build_duration_seconds Build duration',
            f'# TYPE opencenter_build_duration_seconds gauge',
            f'opencenter_build_duration_seconds{{build_id="{self.build_id}"}} {self.duration_seconds or 0}',
            f'',
            f'# HELP opencenter_build_success Build success (1=success, 0=failure)',
            f'# TYPE opencenter_build_success gauge',
            f'opencenter_build_success{{build_id="{self.build_id}"}} {1 if self.success else 0}',
            f'',
            f'# HELP opencenter_build_steps_completed Steps completed',
            f'# TYPE opencenter_build_steps_completed counter',
            f'opencenter_build_steps_completed{{build_id="{self.build_id}"}} {self.steps_completed}',
            f'',
            f'# HELP opencenter_build_package_size_bytes Package size in bytes',
            f'# TYPE opencenter_build_package_size_bytes gauge',
            f'opencenter_build_package_size_bytes{{build_id="{self.build_id}"}} {self.package_size_bytes or 0}',
        ]
        return '\n'.join(lines)

    def save(self, output_dir: Path) -> None:
        """Save metrics to files."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # JSON format
        (output_dir / "metrics.json").write_text(self.to_json())

        # Prometheus format
        (output_dir / "metrics.prom").write_text(self.to_prometheus())
```

**Usage**:
```python
from opencenter_build.metrics import BuildMetrics
from datetime import datetime

metrics = BuildMetrics(
    build_id="build-20260127-1430",
    start_time=datetime.now()
)

# Track progress
metrics.steps_completed += 1

# Complete
metrics.complete(success=True)
metrics.save(Path("build"))
```

### 9. Image Utilities (Skopeo/Podman)

**Component**: `src/opencenter_build/image_utils.py`

**Purpose**: Container image operations using Skopeo (primary) and Podman (secondary)

**Design Rationale**:
- **Skopeo-first**: Daemonless, no root required, optimized for registry operations
- **Podman-secondary**: Docker-compatible CLI for tar archive operations
- **No Docker**: Eliminates daemon dependency, improves security posture

**Interface**:
```python
import subprocess
import logging
from pathlib import Path
from typing import List
from opencenter_build.exceptions import BuildError

logger = logging.getLogger(__name__)

class ImageManager:
    """Manage container images using Skopeo and Podman."""

    def __init__(self):
        self._verify_tools()

    def _verify_tools(self) -> None:
        """Verify Skopeo and Podman are installed."""
        for tool in ["skopeo", "podman"]:
            result = subprocess.run(
                [tool, "--version"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                raise BuildError(
                    f"{tool} not found. Install: sudo apt-get install {tool}"
                )
            logger.info(f"{tool}: {result.stdout.strip()}")

    def copy_image_to_dir(
        self,
        source_image: str,
        dest_dir: Path,
        insecure: bool = False
    ) -> None:
        """Copy image from registry to directory using Skopeo."""
        dest_dir.mkdir(parents=True, exist_ok=True)

        cmd = ["skopeo", "copy"]
        if insecure:
            cmd.append("--insecure-policy")
        cmd.extend([source_image, f"dir:{dest_dir}"])

        logger.info(f"Copying {source_image} to {dest_dir}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise BuildError(f"Failed to copy image: {result.stderr}")

    def sync_images(
        self,
        image_list: Path,
        dest_dir: Path,
        src_transport: str = "docker",
        dest_transport: str = "dir"
    ) -> None:
        """Sync multiple images using Skopeo sync."""
        cmd = [
            "skopeo", "sync",
            "--src", src_transport,
            "--dest", dest_transport,
            str(image_list),
            str(dest_dir)
        ]

        logger.info(f"Syncing images from {image_list} to {dest_dir}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise BuildError(f"Failed to sync images: {result.stderr}")

    def save_image_to_tar(
        self,
        image_ref: str,
        output_file: Path,
        format: str = "oci-archive"
    ) -> None:
        """Save image to tar archive using Podman."""
        output_file.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "podman", "save",
            "--format", format,
            "-o", str(output_file),
            image_ref
        ]

        logger.info(f"Saving {image_ref} to {output_file}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise BuildError(f"Failed to save image: {result.stderr}")

    def load_image_from_tar(
        self,
        tar_file: Path,
        quiet: bool = False
    ) -> str:
        """Load image from tar archive using Podman."""
        if not tar_file.exists():
            raise BuildError(f"Tar file not found: {tar_file}")

        cmd = ["podman", "load"]
        if quiet:
            cmd.append("--quiet")
        cmd.extend(["-i", str(tar_file)])

        logger.info(f"Loading image from {tar_file}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise BuildError(f"Failed to load image: {result.stderr}")

        # Extract image reference from output
        for line in result.stdout.splitlines():
            if "Loaded image:" in line:
                return line.split("Loaded image:")[-1].strip()

        return ""

    def list_local_images(self) -> List[str]:
        """List locally stored images using Podman."""
        cmd = ["podman", "images", "--format", "{{.Repository}}:{{.Tag}}"]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise BuildError(f"Failed to list images: {result.stderr}")

        return [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip() and not line.startswith("<none>")
        ]

    def inspect_image(self, image_ref: str) -> dict:
        """Inspect image metadata using Skopeo."""
        cmd = ["skopeo", "inspect", f"docker://{image_ref}"]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise BuildError(f"Failed to inspect image: {result.stderr}")

        import json
        return json.loads(result.stdout)
```

**Usage**:
```python
from opencenter_build.image_utils import ImageManager

img_mgr = ImageManager()

# Copy image from registry to directory (air-gap collection)
img_mgr.copy_image_to_dir(
    "docker://registry.k8s.io/pause:3.9",
    Path("build/images/pause")
)

# Sync multiple images from YAML list
img_mgr.sync_images(
    Path("config/images.yaml"),
    Path("build/images")
)

# Save/load tar archives
img_mgr.save_image_to_tar(
    "registry.k8s.io/pause:3.9",
    Path("build/images/pause.tar")
)
image_ref = img_mgr.load_image_from_tar(Path("build/images/pause.tar"))

# List and inspect
images = img_mgr.list_local_images()
metadata = img_mgr.inspect_image("registry.k8s.io/pause:3.9")
```

**Skopeo vs Podman Decision Matrix**:

| Operation | Tool | Rationale |
|-----------|------|-----------|
| Registry → Directory | Skopeo | Direct copy, no daemon, optimized for air-gap |
| Registry → Registry | Skopeo | Efficient multi-image sync |
| Image inspection | Skopeo | No local pull required |
| Tar → Local storage | Podman | Docker-compatible load |
| Local storage → Tar | Podman | Docker-compatible save |
| List local images | Podman | Manages local storage |

**Ubuntu 24.04 Installation**:
```bash
sudo apt-get update
sudo apt-get install -y skopeo podman

# Verify
skopeo --version  # 1.13.x+
podman --version  # 4.3.x+
```

## Data Models
    build_id="build-20260127-1430",
    start_time=datetime.now()
)

# Track progress
metrics.steps_completed += 1

# Complete
metrics.complete(success=True)
metrics.save(Path("build"))
```

## Data Models

### Configuration Schemas

#### versions.schema.json
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": [
    "KUBERNETES_VERSION",
    "TERRAFORM_VERSION",
    "KUBESPRAY_VERSION",
    "KUBESPRAY_COMMIT_SHA"
  ],
  "properties": {
    "KUBERNETES_VERSION": {
      "type": "string",
      "pattern": "^v[0-9]+\\.[0-9]+\\.[0-9]+$",
      "description": "Kubernetes version (e.g., v1.34.3)"
    },
    "TERRAFORM_VERSION": {
      "type": "string",
      "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$",
      "description": "Terraform version (e.g., 1.6.6)"
    },
    "KUBESPRAY_VERSION": {
      "type": "string",
      "pattern": "^v[0-9]+\\.[0-9]+\\.[0-9]+$",
      "description": "Kubespray version tag"
    },
    "KUBESPRAY_COMMIT_SHA": {
      "type": "string",
      "pattern": "^[0-9a-f]{40}$",
      "description": "Kubespray commit SHA for verification"
    },
    "FLUX_VERSION": {
      "type": "string",
      "pattern": "^v[0-9]+\\.[0-9]+\\.[0-9]+$"
    },
    "GITEA_VERSION": {
      "type": "string",
      "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"
    }
  }
}
```

#### nodes.schema.json
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["control_plane", "workers"],
  "properties": {
    "control_plane": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["hostname", "ip"],
        "properties": {
          "hostname": {
            "type": "string",
            "pattern": "^[a-z0-9-]+$"
          },
          "ip": {
            "type": "string",
            "format": "ipv4"
          }
        }
      }
    },
    "workers": {
      "type": "array",
      "minItems": 0,
      "items": {
        "type": "object",
        "required": ["hostname", "ip"],
        "properties": {
          "hostname": {
            "type": "string",
            "pattern": "^[a-z0-9-]+$"
          },
          "ip": {
            "type": "string",
            "format": "ipv4"
          }
        }
      }
    }
  }
}
```

### Build State Model

```python
{
  "build_id": "build-20260127-1430",
  "started_at": "2026-01-27T14:30:00Z",
  "kubespray_collected": true,
  "assets_organized": true,
  "zarf_yaml_generated": true,
  "package_created": false,
  "last_step": "organize_assets",
  "checkpoints": [
    {
      "step": "collect_kubespray",
      "timestamp": "2026-01-27T14:35:00Z",
      "success": true
    }
  ]
}
```

### Metrics Model

```python
{
  "build_id": "build-20260127-1430",
  "start_time": "2026-01-27T14:30:00Z",
  "end_time": "2026-01-27T15:15:00Z",
  "duration_seconds": 2700,
  "steps_completed": 5,
  "steps_failed": 0,
  "package_size_bytes": 8589934592,
  "image_count": 139,
  "success": true
}
```
