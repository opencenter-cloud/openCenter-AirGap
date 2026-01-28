# Implementation Plan: Architecture Review Recommendations

**doc_type**: reference
**audience**: Engineering team, project managers
**scope**: Detailed implementation plan for all architecture review recommendations

## Overview

**Total Duration**: 8 weeks
**Total Effort**: 12 engineer-weeks
**Team Size**: 1-2 engineers
**Start Date**: TBD
**Priority**: Critical issues first, then high priority, then medium priority

## Sprint Structure

- **Sprint 0**: Week 1 - Critical Issues + Quick Wins
- **Sprint 1**: Week 2 - Critical Issues Completion
- **Sprint 2**: Week 3 - High Priority (Error Handling & Logging)
- **Sprint 3**: Week 4 - High Priority (State & Secrets)
- **Sprint 4**: Week 5 - High Priority (Testing & Rollback)
- **Sprint 5**: Week 6 - High Priority (Observability & Pinning)
- **Sprint 6**: Week 7 - Medium Priority (CI/CD & Tooling)
- **Sprint 7**: Week 8 - Medium Priority (Security & Validation)

---

## Sprint 0: Week 1 - Critical Issues + Quick Wins

**Goal**: Address critical blockers and implement immediate improvements
**Effort**: 5 days, 1 engineer

### Day 1: Quick Wins (4 hours)

**Tasks**:
1. Add `.editorconfig`
2. Add `CODEOWNERS`
3. Add `SECURITY.md`
4. Add `.github/ISSUE_TEMPLATE/`
5. Add `CONTRIBUTING.md` skeleton

**Deliverables**:
```
.editorconfig
CODEOWNERS
SECURITY.md
.github/ISSUE_TEMPLATE/bug_report.yml
.github/ISSUE_TEMPLATE/feature_request.yml
CONTRIBUTING.md
```

**Acceptance Criteria**:
- All files committed and merged
- Team notified of new contribution guidelines

### Day 2-3: Python Package Structure (12 hours)

**Tasks**:
1. Create `pyproject.toml`

2. Create `src/opencenter_build/` package structure
3. Move reusable Python code to package
4. Add type hints to all functions
5. Configure mypy strict mode
6. Update imports in existing scripts

**File Structure**:
```
src/
└── opencenter_build/
    ├── __init__.py
    ├── exceptions.py      # Custom exception hierarchy
    ├── logging.py         # Centralized logging
    ├── state.py           # Atomic state management
    ├── config.py          # Configuration loading
    ├── image_utils.py     # Image list operations
    ├── version_utils.py   # Version validation
    └── zarf_utils.py      # Zarf YAML generation
```

**pyproject.toml**:
```toml
[project]
name = "opencenter-build"
version = "1.0.0"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "black>=23.0.0",
    "mypy>=1.5.0",
    "pylint>=2.17.0",
]

[tool.black]
line-length = 100
target-version = ['py310']

[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

**Acceptance Criteria**:
- `pip install -e .` works
- `mypy src/` passes with no errors
- All existing scripts still functional
- Tests pass

### Day 4-5: Configuration Schema Validation (12 hours)

**Tasks**:
1. Create `config/schemas/` directory
2. Define JSON schemas for all config files
3. Implement validation module
4. Add validation to build pipeline
5. Write tests for validation

**Schemas**:
```
config/schemas/
├── versions.schema.json
├── nodes.schema.json
├── openstack-config.schema.json
└── zarf-variables.schema.json
```

**Implementation**:
```python
# src/opencenter_build/validation.py
import json
from pathlib import Path
from typing import Dict, Any
import jsonschema

class ConfigValidator:
    def __init__(self, schema_dir: Path):
        self.schema_dir = schema_dir
        self._schemas: Dict[str, Any] = {}

    def load_schema(self, name: str) -> Dict[str, Any]:
        if name not in self._schemas:
            schema_path = self.schema_dir / f"{name}.schema.json"
            self._schemas[name] = json.loads(schema_path.read_text())
        return self._schemas[name]

    def validate_versions_env(self, config: Dict[str, str]) -> None:
        schema = self.load_schema("versions")
        jsonschema.validate(config, schema)

    def validate_nodes_file(self, config: Dict[str, Any]) -> None:
        schema = self.load_schema("nodes")
        jsonschema.validate(config, schema)
```

**Acceptance Criteria**:
- All schemas defined and documented
- Validation catches common errors
- Build fails fast on invalid config
- Tests cover edge cases


---

## Sprint 1: Week 2 - Critical Issues Completion

**Goal**: Complete critical infrastructure improvements
**Effort**: 5 days, 1 engineer

### Day 1-2: Language Boundary Documentation (8 hours)

**Tasks**:
1. Create `docs/reference/coding-standards.md`
2. Document language selection criteria
3. Audit existing scripts for violations
4. Create migration plan for mixed-responsibility scripts
5. Update CONTRIBUTING.md

**Language Decision Matrix**:
```markdown
| Use Case | Language | Rationale |
|----------|----------|-----------|
| Data transformation | Python | JSON/YAML parsing, type safety |
| API calls | Python | Requests library, error handling |
| Complex logic | Python | Testability, maintainability |
| Process orchestration | Bash | Native process control |
| File operations | Bash | Shell utilities optimized |
| External tool invocation | Bash | Simple, direct |
```

**Acceptance Criteria**:
- Coding standards documented
- Team trained on guidelines
- Migration plan approved

### Day 3-5: Atomic State Management (12 hours)

**Tasks**:
1. Implement atomic file write operations
2. Add file locking for concurrent access
3. Implement state backup mechanism
4. Add state recovery for corrupted files
5. Migrate all state writes to new system
6. Write comprehensive tests

**Implementation**:
```python
# src/opencenter_build/state.py
import json
import fcntl
import tempfile
from pathlib import Path
from typing import Any, Dict
from contextlib import contextmanager

class StateManager:
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.backup_file = state_file.with_suffix('.backup')

    @contextmanager
    def lock(self):
        """Acquire exclusive lock on state file."""
        lock_file = self.state_file.with_suffix('.lock')
        lock_file.touch()

        with open(lock_file, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def atomic_write(self, data: Dict[str, Any]) -> None:
        """Write state atomically with backup."""
        # Backup existing state
        if self.state_file.exists():
            self.state_file.rename(self.backup_file)

        # Write to temp file
        fd, temp_path = tempfile.mkstemp(
            dir=self.state_file.parent,
            prefix=f".{self.state_file.name}.",
            suffix=".tmp"
        )

        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename
            os.rename(temp_path, self.state_file)

            # Remove backup on success
            if self.backup_file.exists():
                self.backup_file.unlink()
        except:
            # Restore backup on failure
            if self.backup_file.exists():
                self.backup_file.rename(self.state_file)
            if Path(temp_path).exists():
                os.unlink(temp_path)
            raise

    def read(self) -> Dict[str, Any]:
        """Read state with recovery."""
        try:
            return json.loads(self.state_file.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            # Try backup
            if self.backup_file.exists():
                return json.loads(self.backup_file.read_text())
            return {}
```

**Acceptance Criteria**:
- All state operations atomic
- Concurrent access safe
- Recovery from corruption works
- Tests verify atomicity
- No state corruption in stress tests


---

## Sprint 2: Week 3 - Error Handling & Logging

**Goal**: Standardize error handling and implement centralized logging
**Effort**: 5 days, 1 engineer

### Day 1-2: Exception Hierarchy (8 hours)

**Tasks**:
1. Define exception hierarchy in `src/opencenter_build/exceptions.py`
2. Audit all `except Exception` blocks
3. Replace with specific exceptions
4. Add error context and chaining
5. Update tests

**Exception Hierarchy**:
```python
# src/opencenter_build/exceptions.py

class OpenCenterError(Exception):
    """Base exception for all openCenter errors."""
    pass

class BuildError(OpenCenterError):
    """Build process failed."""
    pass

class AssetCollectionError(BuildError):
    """Asset collection failed."""
    pass

class ValidationError(BuildError):
    """Configuration validation failed."""
    pass

class StateError(BuildError):
    """State management error."""
    pass

class DeploymentError(OpenCenterError):
    """Deployment process failed."""
    pass

class NetworkError(DeploymentError):
    """Network operation failed."""
    pass

class InventoryError(DeploymentError):
    """Inventory generation failed."""
    pass
```

**Acceptance Criteria**:
- No bare `except:` blocks
- All exceptions inherit from `OpenCenterError`
- Error messages include context
- Exception chaining preserved

### Day 3-5: Centralized Logging (12 hours)

**Tasks**:
1. Implement structured logging module
2. Migrate all print statements to logging
3. Add log rotation
4. Implement log aggregation
5. Add logging configuration
6. Update documentation

**Implementation**:
```python
# src/opencenter_build/logging.py
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """Setup centralized logging."""

    # Root logger
    logger = logging.getLogger("opencenter")
    logger.setLevel(level)

    # Format
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)8s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler with rotation
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

# Usage in scripts
logger = logging.getLogger("opencenter.build")
logger.info("Starting asset collection")
logger.error("Failed to download: %s", url, exc_info=True)
```

**Bash Logging Extension**:
```bash
# scripts/lib/logging.sh
LOG_FILE="${LOG_DIR:-build}/build-$(date +%Y%m%d-%H%M%S).log"

log_with_context() {
    local level="$1"
    shift
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] $*" | tee -a "${LOG_FILE}"
}

log_info() { log_with_context "INFO" "$@"; }
log_warn() { log_with_context "WARN" "$@"; }
log_error() { log_with_context "ERROR" "$@"; }
```

**Acceptance Criteria**:
- All Python scripts use logging module
- All Bash scripts use logging functions
- Logs aggregated to single file per run
- Log rotation configured
- No print statements in production code
