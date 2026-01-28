# Coding Standards

**doc_type**: reference
**audience**: Platform Engineers, Developers
**scope**: Language selection, error handling, logging, testing, and linting standards

This document defines when to use Python vs Bash, error handling patterns, logging conventions, and testing requirements for openCenter AirGap.

## Language Decision Matrix

| Use Case | Language | Rationale |
|:---------|:---------|:----------|
| JSON/YAML parsing | Python | Native dict/list handling, jsonschema validation |
| Complex validation logic | Python | Type safety, testability, maintainability |
| State management | Python | Atomic operations, file locking, error handling |
| HTTP API calls | Python | requests library, retry logic, error handling |
| Data transformation | Python | List comprehensions, functional operations |
| Container image operations | Python | Structured parsing, manifest manipulation |
| File operations (cp, mv, rm) | Bash | Native efficiency, no overhead |
| Tool orchestration (git, podman, tar) | Bash | Direct invocation, exit code handling |
| Text processing (grep, sed, awk) | Bash | Native tools, pipeline composition |
| Build orchestration | Bash | Script coordination, environment setup |
| Deployment workflows | Bash | SSH operations, remote execution |
| Simple conditionals | Bash | Quick checks, file existence tests |

### Decision Rules

**Use Python when**:
- Parsing structured data (JSON, YAML, TOML)
- Implementing validation or business logic
- Managing state or configuration
- Handling errors with context and recovery
- Writing testable, reusable code
- Performing calculations or data transformations

**Use Bash when**:
- Orchestrating external tools (git, podman, zarf)
- Performing file system operations
- Executing remote commands via SSH
- Building pipelines with standard Unix tools
- Writing deployment or setup scripts
- Coordinating multiple processes

**Avoid mixing**:
- Don't embed Python in Bash via heredocs
- Don't shell out from Python for simple operations
- Keep language boundaries clean at script level

## Python Standards

### Style and Formatting

**Line Length**: 100 characters

**Indentation**: 4 spaces (no tabs)

**Imports**:
```python
# Standard library
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

# Third-party
import jsonschema

# Local
from opencenter_build.exceptions import ValidationError
from opencenter_build.logging import get_logger
```

**Naming Conventions**:
- Functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`

### Type Hints

All functions require type hints:

```python
def validate_config(
    config: Dict[str, str],
    schema_path: Path
) -> None:
    """Validate configuration against schema."""
    pass

def load_state(state_file: Path) -> Dict[str, Any]:
    """Load state from file."""
    return {}

def parse_version(version_str: str) -> Optional[tuple[int, int, int]]:
    """Parse semantic version string."""
    return None
```

**Type Checking**: Run `mypy --strict src/` before committing.

### Docstrings

Use Google-style docstrings for all public functions:

```python
def collect_assets(
    output_dir: Path,
    versions: Dict[str, str],
    force: bool = False
) -> List[Path]:
    """Collect offline assets for air-gap deployment.

    Downloads Kubernetes binaries, container images, and system packages
    required for offline installation. Assets are organized by type and
    verified with checksums.

    Args:
        output_dir: Directory to store collected assets
        versions: Version mapping from versions.env
        force: Skip existing assets and re-download

    Returns:
        List of paths to collected asset files

    Raises:
        AssetCollectionError: If download fails or checksum mismatch
        ValidationError: If versions dict is invalid
    """
    pass
```

### Error Handling

**Use specific exceptions**:
```python
from opencenter_build.exceptions import (
    ValidationError,
    StateError,
    AssetCollectionError
)

# Good
if not config_file.exists():
    raise ValidationError(f"Config file not found: {config_file}")

# Bad - too generic
if not config_file.exists():
    raise Exception("Config file not found")
```

**Never use bare except**:
```python
# Bad
try:
    result = risky_operation()
except:
    pass

# Good
try:
    result = risky_operation()
except NetworkError as e:
    logger.error("Network operation failed: %s", e, exc_info=True)
    raise AssetCollectionError("Failed to download asset") from e
```

**Chain exceptions**:
```python
try:
    data = json.loads(content)
except json.JSONDecodeError as e:
    raise StateError(f"Invalid state file: {state_file}") from e
```

### Logging

**Import logger**:
```python
from opencenter_build.logging import get_logger

logger = get_logger(__name__)
```

**Log levels**:
- `DEBUG`: Verbose details for troubleshooting
- `INFO`: Progress updates, milestones
- `WARNING`: Recoverable issues, deprecations
- `ERROR`: Operation failures requiring attention
- `CRITICAL`: System-level failures

**Usage**:
```python
logger.debug("Parsing config file: %s", config_file)
logger.info("Collected %d assets in %.2fs", count, duration)
logger.warning("Using cached asset, checksum not verified")
logger.error("Failed to download %s: %s", url, error, exc_info=True)
```

**Never use print()**:
```python
# Bad
print(f"Processing {filename}")

# Good
logger.info("Processing %s", filename)
```

### Testing

**Unit test naming**:
```python
def test_validate_config_missing_required_field():
    """Test validation fails when required field is missing."""
    pass

def test_state_manager_atomic_write_creates_backup():
    """Test atomic write creates backup before updating state."""
    pass
```

**Property-based tests**:
```python
from hypothesis import given, strategies as st

@given(st.dictionaries(st.text(), st.text()))
def test_state_roundtrip_preserves_data(state_data):
    """Test state can be written and read back unchanged."""
    state_mgr = StateManager(tmp_path / "state.json")
    state_mgr.write(state_data)
    assert state_mgr.read() == state_data
```

**Test structure**:
```python
def test_operation_name_scenario():
    """Brief description of what is tested."""
    # Arrange
    config = {"KUBERNETES_VERSION": "v1.34.3"}
    validator = ConfigValidator(schema_dir)

    # Act
    result = validator.validate_versions_env(config)

    # Assert
    assert result is None  # Validation passed
```

### Code Patterns

**Good patterns**:
```python
# Context managers for cleanup
with transactional_operation() as tx:
    perform_operation()
    tx.add_rollback(cleanup_action)

# Path operations
config_file = Path("config/versions.env")
if config_file.exists():
    content = config_file.read_text()

# List comprehensions
valid_versions = [
    v for v in versions
    if v.startswith("v") and len(v.split(".")) == 3
]

# Early returns
def validate_input(value: str) -> None:
    if not value:
        raise ValidationError("Value cannot be empty")
    if len(value) > 100:
        raise ValidationError("Value too long")
    # Continue with validation
```

**Anti-patterns**:
```python
# Bad - nested conditionals
if condition1:
    if condition2:
        if condition3:
            do_something()

# Good - early returns
if not condition1:
    return
if not condition2:
    return
if not condition3:
    return
do_something()

# Bad - mutable defaults
def process_items(items=[]):
    items.append("new")
    return items

# Good - None default
def process_items(items: Optional[List[str]] = None) -> List[str]:
    if items is None:
        items = []
    items.append("new")
    return items
```

## Bash Standards

### Script Header

All Bash scripts must start with:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Script: collect_assets.sh
# Purpose: Download offline assets for air-gap deployment
# Usage: ./collect_assets.sh [--force]
```

**Flags explained**:
- `set -e`: Exit on any command failure
- `set -u`: Exit on undefined variable
- `set -o pipefail`: Fail if any pipeline command fails

### Error Handling

**Check exit codes**:
```bash
# Good - explicit check
if ! git clone "$REPO_URL" "$DEST_DIR"; then
    log_error "Failed to clone repository: $REPO_URL"
    exit 1
fi

# Good - capture and check
if output=$(command 2>&1); then
    log_info "Command succeeded: $output"
else
    log_error "Command failed with exit code $?"
    exit 1
fi

# Acceptable - failure is expected
rm -f /tmp/tempfile || true
```

**Trap for cleanup**:
```bash
cleanup() {
    local exit_code=$?
    log_info "Cleaning up temporary files"
    rm -rf "$TEMP_DIR"
    exit "$exit_code"
}

trap cleanup EXIT INT TERM

TEMP_DIR=$(mktemp -d)
# Script operations
```

### Logging

**Source logging library**:
```bash
# shellcheck source=scripts/lib/logging.sh
source "$(dirname "$0")/../lib/logging.sh"

log_info "Starting asset collection"
log_warn "Using cached assets, skipping download"
log_error "Failed to verify checksum for $ASSET_FILE"
```

**Logging functions**:
- `log_debug`: Verbose details (only if DEBUG=1)
- `log_info`: Progress updates
- `log_warn`: Recoverable issues
- `log_error`: Failures requiring attention

### Variable Naming

```bash
# Constants - uppercase
readonly KUBERNETES_VERSION="v1.34.3"
readonly ASSETS_DIR="/opt/opencenter/assets"

# Local variables - lowercase
local temp_file="/tmp/download.tmp"
local retry_count=0

# Environment variables - uppercase
export KUBECONFIG="/etc/kubernetes/admin.conf"
```

### Quoting

**Always quote variables**:
```bash
# Good
if [[ -f "$config_file" ]]; then
    cp "$config_file" "$backup_dir/"
fi

# Bad - word splitting issues
if [[ -f $config_file ]]; then
    cp $config_file $backup_dir/
fi
```

**Use arrays for lists**:
```bash
# Good
images=(
    "registry.k8s.io/kube-apiserver:v1.34.3"
    "registry.k8s.io/kube-controller-manager:v1.34.3"
)

for image in "${images[@]}"; do
    podman pull "$image"
done

# Bad - word splitting
images="image1 image2 image3"
for image in $images; do
    podman pull $image
done
```

### Functions

```bash
# Function with documentation
# Downloads asset from URL with retry logic
# Arguments:
#   $1 - URL to download
#   $2 - Output file path
# Returns:
#   0 on success, 1 on failure
download_asset() {
    local url="$1"
    local output="$2"
    local retry_count=0
    local max_retries=3

    while [[ $retry_count -lt $max_retries ]]; do
        if curl -fsSL -o "$output" "$url"; then
            log_info "Downloaded: $url"
            return 0
        fi

        retry_count=$((retry_count + 1))
        log_warn "Download failed, retry $retry_count/$max_retries"
        sleep 5
    done

    log_error "Failed to download after $max_retries attempts: $url"
    return 1
}
```

### Conditionals

**Use [[ ]] for tests**:
```bash
# Good - modern test syntax
if [[ -f "$file" && -r "$file" ]]; then
    cat "$file"
fi

if [[ "$version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    log_info "Valid version: $version"
fi

# Bad - old test syntax
if [ -f $file ] && [ -r $file ]; then
    cat $file
fi
```

### Code Patterns

**Good patterns**:
```bash
# Check prerequisites
check_prerequisites() {
    local missing=()

    command -v git >/dev/null || missing+=("git")
    command -v podman >/dev/null || missing+=("podman")

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing[*]}"
        exit 1
    fi
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)
            FORCE=1
            shift
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Idempotent operations
if [[ ! -d "$OUTPUT_DIR" ]]; then
    mkdir -p "$OUTPUT_DIR"
fi
```

**Anti-patterns**:
```bash
# Bad - unquoted variables
cd $HOME/project
rm -rf $TEMP_DIR/*

# Good
cd "$HOME/project"
rm -rf "${TEMP_DIR:?}/"*

# Bad - useless cat
cat file.txt | grep pattern

# Good
grep pattern file.txt

# Bad - parsing ls
for file in $(ls *.txt); do
    process "$file"
done

# Good
for file in *.txt; do
    [[ -f "$file" ]] || continue
    process "$file"
done
```

### ShellCheck

Run `shellcheck` on all Bash scripts:

```bash
shellcheck scripts/**/*.sh
```

**Common issues**:
- SC2086: Quote variables to prevent word splitting
- SC2046: Quote command substitution
- SC2155: Declare and assign separately
- SC2164: Use `cd ... || exit` to handle failures

**Disable warnings sparingly**:
```bash
# shellcheck disable=SC2086
# Intentional word splitting for array expansion
command $OPTIONS
```

## Error Handling Standards

### Python Error Context

Include operation context in all exceptions:

```python
try:
    with open(config_file) as f:
        config = json.load(f)
except FileNotFoundError as e:
    raise ValidationError(
        f"Config file not found: {config_file}\n"
        f"Expected location: {config_file.absolute()}\n"
        f"Create with: cp config/versions.env.example {config_file}"
    ) from e
except json.JSONDecodeError as e:
    raise ValidationError(
        f"Invalid JSON in config file: {config_file}\n"
        f"Error at line {e.lineno}, column {e.colno}: {e.msg}"
    ) from e
```

### Bash Error Messages

Provide actionable error messages:

```bash
if [[ ! -f "$VERSIONS_FILE" ]]; then
    log_error "Versions file not found: $VERSIONS_FILE"
    log_error "Expected location: $(pwd)/config/versions.env"
    log_error "Create with: cp config/versions.env.example config/versions.env"
    exit 1
fi

if ! command -v zarf >/dev/null; then
    log_error "Zarf CLI not found in PATH"
    log_error "Install from: https://zarf.dev/install/"
    log_error "Or download: https://github.com/defenseunicorns/zarf/releases"
    exit 1
fi
```

## Logging Standards

### Python Logging Setup

```python
from opencenter_build.logging import setup_logging, get_logger
from pathlib import Path

# In main script
setup_logging(
    level=logging.INFO,
    log_file=Path("build/build.log"),
    log_to_console=True
)

logger = get_logger(__name__)
```

### Structured Logging

Include context in log messages:

```python
logger.info(
    "Asset collection started: output_dir=%s, force=%s",
    output_dir,
    force
)

logger.info(
    "Downloaded asset: url=%s, size=%d bytes, duration=%.2fs",
    url,
    size,
    duration
)

logger.error(
    "Checksum mismatch: file=%s, expected=%s, actual=%s",
    file_path,
    expected_checksum,
    actual_checksum,
    exc_info=True
)
```

### Bash Logging Format

```bash
# Timestamp format: 2026-01-27 14:30:45
log_info "Starting build process"
log_info "Kubernetes version: $KUBERNETES_VERSION"
log_info "Output directory: $OUTPUT_DIR"

log_warn "Asset already exists, skipping download: $ASSET_FILE"

log_error "Failed to download asset: $URL"
log_error "Exit code: $exit_code"
log_error "Output: $output"
```

## Testing Requirements

### Python Test Coverage

**Minimum coverage**: 80%

**Required tests**:
- Unit tests for all public functions
- Property-based tests for data transformations
- Integration tests for end-to-end workflows

**Test file naming**:
- `tests/unit/test_<module>.py`
- `tests/property/test_<module>_properties.py`
- `tests/integration/test_<workflow>.py`

### Bash Test Coverage

**Required tests**:
- Integration tests for critical scripts
- Validation of exit codes
- Error handling verification

**Test file naming**:
- `tests/integration/test_<script>.sh`

### Running Tests

```bash
# All tests
make test

# Python unit tests
pytest tests/unit/ -v

# Python property tests
pytest tests/property/ -v

# Integration tests
pytest tests/integration/ -v

# With coverage
pytest --cov=src --cov-report=html
```

## Linting and Type Checking

### Python Tools

**Black** (formatting):
```bash
black src/ tests/
black --check src/ tests/  # CI mode
```

**mypy** (type checking):
```bash
mypy --strict src/
```

**pylint** (linting):
```bash
pylint src/
```

### Bash Tools

**shellcheck** (linting):
```bash
shellcheck scripts/**/*.sh
```

**shfmt** (formatting, optional):
```bash
shfmt -i 4 -w scripts/**/*.sh
```

## Migration Plan for Mixed-Responsibility Scripts

### Current Issues

Several scripts mix Python and Bash responsibilities:
- `scripts/build/generate_zarf_yaml.py` - Python script calling Bash commands
- `scripts/build/collect_assets.sh` - Bash script with embedded Python
- `scripts/build/organize_assets.sh` - File operations mixed with JSON parsing

### Migration Strategy

**Phase 1: Extract Python Logic**
- Move data transformation to `src/opencenter_build/` modules
- Move validation logic to `validation.py`
- Move state management to `state.py`

**Phase 2: Simplify Bash Scripts**
- Keep orchestration in Bash
- Call Python modules for complex operations
- Remove embedded Python heredocs

**Phase 3: Define Clean Interfaces**
- Python modules expose CLI interfaces
- Bash scripts call Python via `python -m opencenter_build.module`
- Pass data via files or stdin/stdout, not environment variables

### Example Migration

**Before** (mixed):
```bash
#!/usr/bin/env bash
# Mixed Bash and Python

python3 <<EOF
import json
config = json.load(open("config.json"))
print(config["version"])
EOF

version=$(python3 -c "import json; print(json.load(open('config.json'))['version'])")
```

**After** (separated):
```python
# src/opencenter_build/config.py
def get_version(config_file: Path) -> str:
    """Extract version from config file."""
    config = json.loads(config_file.read_text())
    return config["version"]

if __name__ == "__main__":
    import sys
    version = get_version(Path(sys.argv[1]))
    print(version)
```

```bash
#!/usr/bin/env bash
# Pure Bash orchestration

version=$(python -m opencenter_build.config config.json)
log_info "Version: $version"
```

## Examples

### Python Module Example

```python
"""Asset collection module.

This module handles downloading and organizing offline assets for
air-gap deployment.
"""

import logging
from pathlib import Path
from typing import Dict, List

from opencenter_build.exceptions import AssetCollectionError
from opencenter_build.logging import get_logger

logger = get_logger(__name__)


def collect_kubernetes_binaries(
    version: str,
    output_dir: Path,
    architecture: str = "amd64"
) -> List[Path]:
    """Download Kubernetes binaries for offline installation.

    Args:
        version: Kubernetes version (e.g., "v1.34.3")
        output_dir: Directory to store binaries
        architecture: Target architecture (amd64, arm64)

    Returns:
        List of paths to downloaded binaries

    Raises:
        AssetCollectionError: If download fails
        ValidationError: If version format is invalid
    """
    if not version.startswith("v"):
        raise ValidationError(f"Invalid version format: {version}")

    output_dir.mkdir(parents=True, exist_ok=True)

    binaries = ["kubelet", "kubectl", "kubeadm"]
    downloaded = []

    for binary in binaries:
        url = f"https://dl.k8s.io/release/{version}/bin/linux/{architecture}/{binary}"
        output_file = output_dir / binary

        logger.info("Downloading %s from %s", binary, url)

        try:
            download_file(url, output_file)
            output_file.chmod(0o755)
            downloaded.append(output_file)
        except Exception as e:
            raise AssetCollectionError(
                f"Failed to download {binary}: {e}"
            ) from e

    logger.info("Downloaded %d binaries to %s", len(downloaded), output_dir)
    return downloaded
```

### Bash Script Example

```bash
#!/usr/bin/env bash
set -euo pipefail

# Script: deploy_cluster.sh
# Purpose: Deploy Kubernetes cluster using Kubespray
# Usage: ./deploy_cluster.sh [--inventory PATH]

# shellcheck source=scripts/lib/logging.sh
source "$(dirname "$0")/../lib/logging.sh"

readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default values
INVENTORY_FILE="${PROJECT_ROOT}/inventory/mycluster/hosts.yml"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --inventory)
            INVENTORY_FILE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--inventory PATH]"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate prerequisites
check_prerequisites() {
    local missing=()

    command -v ansible-playbook >/dev/null || missing+=("ansible-playbook")
    command -v kubectl >/dev/null || missing+=("kubectl")

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing[*]}"
        exit 1
    fi

    if [[ ! -f "$INVENTORY_FILE" ]]; then
        log_error "Inventory file not found: $INVENTORY_FILE"
        exit 1
    fi
}

# Main deployment
main() {
    log_info "Starting cluster deployment"
    log_info "Inventory: $INVENTORY_FILE"

    check_prerequisites

    log_info "Running Kubespray playbook"
    if ! ansible-playbook \
        -i "$INVENTORY_FILE" \
        cluster.yml \
        --become; then
        log_error "Deployment failed"
        exit 1
    fi

    log_info "Deployment completed successfully"
}

main "$@"
```

## Review Checklist

Before submitting code:

**Python**:
- [ ] Type hints on all functions
- [ ] Docstrings on all public functions
- [ ] No bare `except:` blocks
- [ ] No `print()` statements (use logging)
- [ ] `mypy --strict` passes
- [ ] `black --check` passes
- [ ] `pylint` score > 9.0
- [ ] Test coverage > 80%

**Bash**:
- [ ] `set -euo pipefail` at script start
- [ ] All variables quoted
- [ ] Error handling with exit codes
- [ ] Logging via `log_*` functions
- [ ] `shellcheck` passes with no warnings
- [ ] Integration tests pass

**Both**:
- [ ] Clear separation of concerns
- [ ] No mixed Python/Bash in single file
- [ ] Actionable error messages
- [ ] Documentation updated
