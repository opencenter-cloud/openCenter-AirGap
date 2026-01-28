# State Management Integration Guide

**doc_type**: how-to
**audience**: Platform Engineers
**scope**: Integrating StateManager into build scripts

## Purpose

Migrate build scripts from direct JSON file operations to StateManager for atomic state operations with locking and recovery.

## StateManager vs BuildState

Two complementary components:

- **StateManager** (`src/opencenter_build/state.py`): Low-level atomic file operations with locking
- **BuildState** (`scripts/build/build_state.py`): High-level build state model with step tracking

## Integration Pattern

BuildState should use StateManager for file I/O:

```python
from pathlib import Path
from opencenter_build.state import StateManager
from build_state import BuildState

# Initialize
state_file = Path("build/.build-state.json")
state_mgr = StateManager(state_file)

# Load state
state_dict = state_mgr.read()
if state_dict:
    build_state = BuildState.from_json(json.dumps(state_dict))
else:
    build_state = BuildState(build_id="build-001", ...)

# Update state
build_state.mark_step_completed("collect_kubespray", duration=120.5)

# Save state atomically
state_mgr.write(json.loads(build_state.to_json()))
```

## Migration Checklist

### scripts/build/build_state.py

Current implementation:
```python
def save_to_file(self, file_path: Path) -> None:
    file_path.write_text(self.to_json())
    file_path.chmod(0o600)
```

Recommended update:
```python
def save_to_file(self, file_path: Path) -> None:
    """Save state atomically using StateManager."""
    from opencenter_build.state import StateManager
    state_mgr = StateManager(file_path)
    state_mgr.write(json.loads(self.to_json()))
```

### scripts/build/build.py

Replace direct state file operations:

**Before:**
```python
state_file = build_dir / ".build-state.json"
if state_file.exists():
    state_data = json.loads(state_file.read_text())
```

**After:**
```python
from opencenter_build.state import StateManager

state_file = build_dir / ".build-state.json"
state_mgr = StateManager(state_file)
state_data = state_mgr.read()
```

## Recovery Procedure

If state corruption detected:

```python
from opencenter_build.state import StateManager

state_mgr = StateManager(Path("build/.build-state.json"))

# Attempt recovery
if state_mgr.recover():
    print("State recovered from backup")
    state = state_mgr.read()
else:
    print("No valid backup, starting fresh build")
    state = {}
```

## Concurrent Access

StateManager uses fcntl file locking. Safe for:
- Multiple processes on same host
- Concurrent read/write operations

Not safe for:
- NFS without proper lock daemon
- Read-modify-write without application-level coordination

For read-modify-write atomicity:
```python
with state_mgr.lock():
    state = state_mgr.read()
    state["counter"] += 1
    state_mgr.write(state)
```

## Testing

Verify integration:

```bash
# Unit tests
pytest tests/unit/test_state.py -v

# Property-based tests
pytest tests/property/test_state_manager_properties.py -v

# Integration tests
pytest tests/integration/ -k state -v
```

## Rollback

If issues occur, StateManager maintains `.backup` files:

```bash
# Manual rollback
cp build/.build-state.json.backup build/.build-state.json
```

## Performance

StateManager overhead:
- Lock acquisition: <1ms
- Atomic write: ~2ms for typical state (10KB)
- Backup creation: ~1ms

Negligible impact on build duration (seconds vs minutes/hours).
