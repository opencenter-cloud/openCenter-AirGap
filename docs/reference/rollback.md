# Rollback Patterns

**doc_type**: reference
**audience**: Platform Engineers, Developers
**scope**: Transaction and rollback mechanisms for critical operations

## Overview

The transaction module provides automatic rollback capability for multi-step operations. When an operation fails partway through, registered rollback actions execute in reverse order to restore the system to a consistent state.

## Transaction Class

### Basic Usage

```python
from opencenter_build.transaction import Transaction

tx = Transaction()

# Register rollback actions
tx.add_rollback(lambda: cleanup_temp_files())
tx.add_rollback(lambda: restore_backup())

# Perform operations
try:
    perform_critical_operation()
    tx.commit()  # Clear rollback actions on success
except Exception:
    tx.rollback()  # Execute rollback actions on failure
    raise
```

### Context Manager

```python
from opencenter_build.transaction import transactional_operation

with transactional_operation() as tx:
    # Backup original
    shutil.copy("config.yaml", "config.yaml.backup")
    tx.add_rollback(lambda: shutil.move("config.yaml.backup", "config.yaml"))

    # Modify file
    update_config("config.yaml")

    # Automatic rollback on exception
```

## Rollback Execution Order

Actions execute in **LIFO (Last-In-First-Out)** order during rollback:

```python
with transactional_operation() as tx:
    tx.add_rollback(action1)  # Executes third
    tx.add_rollback(action2)  # Executes second
    tx.add_rollback(action3)  # Executes first
```

This ensures proper cleanup sequence: most recent changes are undone first.

## Error Handling

### Rollback Action Failures

Rollback continues even if individual actions fail:

```python
tx.add_rollback(lambda: os.remove("file1.txt"))  # May fail
tx.add_rollback(lambda: os.remove("file2.txt"))  # Still executes
tx.add_rollback(lambda: os.remove("file3.txt"))  # Still executes

tx.rollback()  # All actions attempted, failures logged
```

Failures are logged at ERROR level but do not stop remaining rollback actions.

### Original Exception Preservation

The original exception is always re-raised after rollback:

```python
try:
    with transactional_operation() as tx:
        tx.add_rollback(cleanup)
        raise ValueError("Operation failed")
except ValueError as e:
    # Original ValueError is raised, not rollback errors
    assert str(e) == "Operation failed"
```

## Critical Operations

### Zarf YAML Generation

```python
from pathlib import Path
import shutil
from opencenter_build.transaction import transactional_operation

def generate_zarf_yaml_transactional(output_path: Path) -> None:
    """Generate zarf.yaml with automatic rollback on failure."""
    with transactional_operation() as tx:
        # Backup existing file
        if output_path.exists():
            backup_path = output_path.with_suffix(".yaml.backup")
            shutil.copy(output_path, backup_path)
            tx.add_rollback(lambda: shutil.move(backup_path, output_path))

        # Generate new file
        generate_zarf_yaml(output_path)

        # Validate generated file
        validate_zarf_yaml(output_path)

        # On exception, backup is restored automatically
```

### Asset Organization

```python
from opencenter_build.transaction import transactional_operation

def organize_assets_transactional(source_dir: Path, target_dir: Path) -> None:
    """Organize assets with rollback on failure."""
    with transactional_operation() as tx:
        moved_files = []

        for asset_file in source_dir.glob("**/*"):
            if asset_file.is_file():
                target_file = target_dir / asset_file.relative_to(source_dir)
                target_file.parent.mkdir(parents=True, exist_ok=True)

                # Move file
                shutil.move(str(asset_file), str(target_file))
                moved_files.append((target_file, asset_file))

                # Register rollback for this file
                tx.add_rollback(
                    lambda src=target_file, dst=asset_file: shutil.move(str(src), str(dst))
                )

        # Validate organization
        validate_asset_structure(target_dir)

        # On exception, all files are moved back
```

### State Updates

```python
from opencenter_build.state import StateManager
from opencenter_build.transaction import transactional_operation

def update_build_state_transactional(
    state_mgr: StateManager,
    updates: dict
) -> None:
    """Update build state with rollback capability."""
    with transactional_operation() as tx:
        # Read current state
        current_state = state_mgr.read()

        # Register rollback to restore original state
        tx.add_rollback(lambda: state_mgr.write(current_state))

        # Apply updates
        new_state = {**current_state, **updates}
        state_mgr.write(new_state)

        # Validate new state
        validate_state(new_state)

        # On exception, original state is restored
```

## Best Practices

### Idempotent Rollback Actions

Rollback actions should be idempotent (safe to execute multiple times):

```python
# Good: Check before removing
tx.add_rollback(lambda: temp_file.unlink(missing_ok=True))

# Bad: May fail if file already removed
tx.add_rollback(lambda: temp_file.unlink())
```

### Capture Variables in Lambdas

Use default arguments to capture loop variables:

```python
# Good: Captures current value
for file in files:
    tx.add_rollback(lambda f=file: cleanup(f))

# Bad: All lambdas reference final loop value
for file in files:
    tx.add_rollback(lambda: cleanup(file))
```

### Avoid Side Effects in Rollback

Rollback actions should only undo changes, not perform new operations:

```python
# Good: Restore original state
tx.add_rollback(lambda: shutil.move(backup, original))

# Bad: Sends notification (side effect)
tx.add_rollback(lambda: send_failure_notification())
```

### Limit Rollback Scope

Keep transactions focused on related operations:

```python
# Good: Single logical operation
with transactional_operation() as tx:
    update_config_file(tx)

# Bad: Unrelated operations in same transaction
with transactional_operation() as tx:
    update_config_file(tx)
    download_assets(tx)  # Separate concern
```

## Logging

Transaction operations log at multiple levels:

- **DEBUG**: Action registration, commit, rollback start
- **INFO**: Rollback completion
- **ERROR**: Rollback action failures
- **WARNING**: Rollback completed with failures

Enable DEBUG logging to trace transaction execution:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Limitations

### Not a Database Transaction

This is not ACID-compliant database transaction:

- No isolation between concurrent operations
- No durability guarantees
- No atomicity across process boundaries

Use for in-process operation rollback only.

### No Nested Transaction Support

Each context manager creates independent transaction:

```python
with transactional_operation() as outer:
    outer.add_rollback(outer_cleanup)

    with transactional_operation() as inner:
        inner.add_rollback(inner_cleanup)
        # Inner and outer are independent
```

### Rollback Action Failures

If rollback actions fail, system may be in inconsistent state. Design rollback actions to be robust:

- Check file existence before operations
- Use `missing_ok=True` for file removal
- Handle exceptions within rollback actions when possible

## Testing

Test rollback behavior explicitly:

```python
def test_rollback_on_validation_failure():
    """Test that invalid config triggers rollback."""
    original_config = read_config()

    with pytest.raises(ValidationError):
        with transactional_operation() as tx:
            backup_config(tx)
            update_config(invalid_data)
            validate_config()  # Raises ValidationError

    # Verify original config restored
    assert read_config() == original_config
```

## Migration Guide

### Converting Existing Code

Before:
```python
def update_config(config_path: Path, data: dict) -> None:
    backup_path = config_path.with_suffix(".backup")
    shutil.copy(config_path, backup_path)

    try:
        config_path.write_text(json.dumps(data))
        validate_config(config_path)
    except Exception:
        shutil.move(backup_path, config_path)
        raise
```

After:
```python
def update_config(config_path: Path, data: dict) -> None:
    with transactional_operation() as tx:
        backup_path = config_path.with_suffix(".backup")
        shutil.copy(config_path, backup_path)
        tx.add_rollback(lambda: shutil.move(backup_path, config_path))

        config_path.write_text(json.dumps(data))
        validate_config(config_path)
```

Benefits:
- Automatic rollback on any exception
- Consistent error handling
- Logging of rollback operations
- Testable rollback behavior
