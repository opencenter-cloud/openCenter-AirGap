# Logging Reference

**doc_type**: reference
**audience**: Platform Engineers, Developers
**scope**: Centralized logging configuration and usage

## Overview

openCenter AirGap uses centralized structured logging across all Python and Bash scripts. Logs include timestamps, log levels, and module names for efficient troubleshooting.

## Python Logging

### Setup

```python
from opencenter_build.logging import setup_logging, get_logger

# Configure logging at script entry point
setup_logging(
    level=logging.INFO,
    log_file=Path("build/build.log"),
    log_to_console=True
)

# Get logger for your module
logger = get_logger(__name__)
```

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `level` | `int` | `logging.INFO` | Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `log_file` | `Path \| None` | `None` | Path to log file. If None, no file logging |
| `log_to_console` | `bool` | `True` | Whether to log to stderr |

### Log Levels

```python
logger.debug("Detailed diagnostic information")
logger.info("General informational messages")
logger.warning("Warning messages for unexpected situations")
logger.error("Error messages for failures")
logger.critical("Critical failures requiring immediate attention")
```

**Level Filtering**:
- `DEBUG`: All messages
- `INFO`: INFO, WARNING, ERROR, CRITICAL
- `WARNING`: WARNING, ERROR, CRITICAL
- `ERROR`: ERROR, CRITICAL
- `CRITICAL`: CRITICAL only

### Exception Logging

```python
try:
    risky_operation()
except Exception as e:
    logger.error("Operation failed", exc_info=True)
```

The `exc_info=True` parameter includes full traceback in logs.

### Log Format

```
YYYY-MM-DD HH:MM:SS [LEVEL] module.name: message
```

Example:
```
2026-01-27 14:30:15 [INFO] opencenter_build.state: State file updated
2026-01-27 14:30:16 [ERROR] opencenter_build.validation: Invalid config: missing KUBERNETES_VERSION
```

### File Rotation

Log files automatically rotate when they exceed 10MB. The system keeps 5 backup files:

```
build.log          # Current log
build.log.1        # Most recent backup
build.log.2
build.log.3
build.log.4
build.log.5        # Oldest backup
```

Rotation is handled by `logging.handlers.RotatingFileHandler`.

## Bash Logging

### Setup

```bash
#!/bin/bash
set -euo pipefail

# Source logging library
source scripts/lib/logging.sh

# Initialize logging
init_logging

# Use logging functions
log_info "Starting build process"
```

### Configuration

Set environment variables before calling `init_logging`:

```bash
export LOG_DIR="build/logs"
export LOG_FILE="build.log"
export LOG_LEVEL="INFO"

init_logging
```

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_DIR` | `build/logs` | Directory for log files |
| `LOG_FILE` | `build.log` | Log file name |
| `LOG_LEVEL` | `INFO` | Minimum log level (DEBUG, INFO, WARN, ERROR) |

### Log Functions

```bash
log_debug "Detailed diagnostic information"
log_info "General informational messages"
log_warn "Warning messages"
log_error "Error messages"
```

### Command Logging

Log command execution with timing:

```bash
log_command "Download kubespray" \
    git clone https://github.com/kubernetes-sigs/kubespray.git
```

Output:
```
[2026-01-27 14:30:15] [INFO] Executing: Download kubespray
[2026-01-27 14:30:15] [DEBUG] Command: git clone https://github.com/kubernetes-sigs/kubespray.git
[2026-01-27 14:30:20] [INFO] Completed: Download kubespray (5s)
```

### Phase Logging

Track multi-step operations:

```bash
log_phase_start "Asset Collection"

# ... perform operations ...

log_phase_end "Asset Collection" "success"
```

Output:
```
[2026-01-27 14:30:00] [INFO] ==========================================
[2026-01-27 14:30:00] [INFO] Phase: Asset Collection
[2026-01-27 14:30:00] [INFO] ==========================================
[2026-01-27 14:35:00] [INFO] Phase completed: Asset Collection (300s)
[2026-01-27 14:35:00] [INFO] ==========================================
```

### Log Rotation

Manually trigger rotation:

```bash
rotate_logs 10  # Rotate if log exceeds 10MB
```

Rotated logs are compressed with gzip in the background.

## Log File Locations

### Build Logs

```
build/logs/
├── 20260127_143000_build.log
├── 20260127_150000_build.log
└── 20260127_153000_build.log
```

Each build run creates a timestamped log file.

### Deployment Logs

```
/opt/opencenter/logs/
├── 20260127_143000/
│   ├── deployment.log
│   └── deployment-summary.txt
└── 20260127_150000/
    ├── deployment.log
    └── deployment-summary.txt
```

Deployment logs are organized by timestamp on the bastion host.

## Best Practices

### Use Appropriate Log Levels

```python
# DEBUG: Detailed diagnostic info (variable values, state)
logger.debug(f"Processing image: {image_ref}")

# INFO: Normal operation milestones
logger.info("Asset collection complete")

# WARNING: Unexpected but recoverable situations
logger.warning("Image uses 'latest' tag (not recommended)")

# ERROR: Operation failures
logger.error("Failed to download asset", exc_info=True)

# CRITICAL: System-level failures
logger.critical("Disk space exhausted")
```

### Include Context

```python
# Bad
logger.error("Download failed")

# Good
logger.error(f"Failed to download {url}: {error_message}")
```

### Avoid Logging Secrets

```python
# Bad
logger.debug(f"Using token: {github_token}")

# Good
logger.debug("Using GitHub token from .secrets/github-token")
```

### Use Structured Fields

```python
logger.info(
    "Asset downloaded",
    extra={
        "asset_name": "kubespray",
        "size_bytes": 1024000,
        "duration_seconds": 5.2
    }
)
```

### Log at Entry and Exit

```python
def collect_assets():
    logger.info("Starting asset collection")
    try:
        # ... operations ...
        logger.info("Asset collection complete")
    except Exception as e:
        logger.error("Asset collection failed", exc_info=True)
        raise
```

## Troubleshooting

### No Log Output

Check that logging is initialized:

```python
# Python
setup_logging(level=logging.DEBUG)

# Bash
init_logging
```

### Log File Not Created

Verify directory permissions:

```bash
ls -la build/logs/
```

Ensure parent directory exists or is created by `setup_logging`.

### Log Rotation Not Working

Check file size:

```bash
ls -lh build/build.log
```

Rotation triggers at 10MB for Python, configurable for Bash.

### Missing Log Messages

Check log level configuration:

```python
# Set to DEBUG to see all messages
setup_logging(level=logging.DEBUG)
```

```bash
export LOG_LEVEL="DEBUG"
init_logging
```

## Migration from print()

Replace print statements with logging:

```python
# Before
print(f"Processing {count} images")
print(f"Error: {error}", file=sys.stderr)

# After
logger.info(f"Processing {count} images")
logger.error(f"Error: {error}")
```

Benefits:
- Timestamps on all messages
- Consistent formatting
- Log level filtering
- File and console output
- Automatic rotation

## Examples

### Python Script

```python
#!/usr/bin/env python3
import logging
from pathlib import Path

from opencenter_build.logging import setup_logging, get_logger

logger = get_logger(__name__)

def main():
    setup_logging(
        level=logging.INFO,
        log_file=Path("build/script.log")
    )

    logger.info("Script started")

    try:
        process_data()
        logger.info("Processing complete")
    except Exception as e:
        logger.error("Processing failed", exc_info=True)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### Bash Script

```bash
#!/bin/bash
set -euo pipefail

source scripts/lib/logging.sh

main() {
    init_logging

    log_phase_start "Build Process"

    log_command "Collect assets" \
        ./scripts/build/collect_assets.sh

    log_command "Create package" \
        ./scripts/build/create_package.sh

    log_phase_end "Build Process" "success"
}

main "$@"
```

## Related Documentation

- [Coding Standards](coding-standards.md) - Language decision matrix
- [Error Handling](../architecture-improvements/design.md#exception-hierarchy) - Exception hierarchy
- [State Management](../architecture-improvements/design.md#atomic-state-management) - State operations logging
