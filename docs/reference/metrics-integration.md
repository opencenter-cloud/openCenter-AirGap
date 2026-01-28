# Build Metrics Integration Guide

**doc_type**: how-to
**audience**: Platform Engineers

## Purpose

Integrate BuildMetrics into the build orchestrator to track and export build performance metrics.

## Prerequisites

- `opencenter_build` package installed (`pip install -e .`)
- Access to `scripts/build/build.py`
- Write access to `build/` directory

## Integration Steps

### 1. Import BuildMetrics

Add import at top of `scripts/build/build.py`:

```python
from opencenter_build.metrics import BuildMetrics
```

### 2. Initialize Metrics

In `main()` function, after creating build state:

```python
# Create metrics tracker
metrics = BuildMetrics(
    build_id=state.build_id,
    start_time=state.start_time
)
logger.info(f"Initialized metrics tracking for {metrics.build_id}")
```

### 3. Track Step Execution

In `run_build()` function, pass metrics to executor:

```python
executor = BuildExecutor(
    steps=STEPS,
    state=state,
    project_root=project_root,
    max_parallel=1 if args.no_parallel else args.max_parallel,
    console=console,
    force=args.force,
    logger=logger,
    metrics=metrics  # Add this parameter
)
```

In `BuildExecutor.execute_build()`, update metrics after each step:

```python
# After successful step completion
metrics.steps_completed += 1

# After step failure
metrics.steps_failed += 1
```

### 4. Track Resource Metrics

After package creation step completes:

```python
# Track package size
package_file = project_root / "dist" / "zarf-package-opencenter-airgap-amd64.tar.zst"
if package_file.exists():
    metrics.package_size_bytes = package_file.stat().st_size
    logger.info(f"Package size: {metrics.package_size_bytes} bytes")

# Track image count
image_list = project_root / "config" / "all-images.txt"
if image_list.exists():
    image_lines = image_list.read_text().strip().split('\n')
    metrics.image_count = len([line for line in image_lines if line.strip()])
    logger.info(f"Image count: {metrics.image_count}")
```

### 5. Export Metrics

In `main()` function, before displaying summary:

```python
# Complete metrics tracking
metrics.complete(success=success)

# Export metrics
try:
    metrics.save(build_dir)
    logger.info(f"Metrics exported to {build_dir}/metrics.json and {build_dir}/metrics.prom")
    console.print(f"[cyan]Metrics saved to {build_dir}/metrics.json[/cyan]")
except Exception as e:
    logger.error(f"Failed to save metrics: {e}")
```

### 6. Display Metrics in Summary

Add metrics to `display_summary()` function:

```python
def display_summary(state: BuildState, metrics: BuildMetrics, console: Console, success: bool) -> None:
    """Display build summary with metrics."""
    # ... existing code ...

    # Add metrics rows
    if metrics.package_size_bytes:
        size_gb = metrics.package_size_bytes / (1024**3)
        table.add_row("Package Size", f"{size_gb:.2f} GB")

    if metrics.image_count:
        table.add_row("Images", str(metrics.image_count))

    # ... rest of function ...
```

## Verification

After integration, verify metrics are collected:

```bash
# Run build
python3 scripts/build/build.py

# Check metrics files exist
ls -lh build/metrics.json build/metrics.prom

# View JSON metrics
cat build/metrics.json

# View Prometheus metrics
cat build/metrics.prom
```

## Metrics Files

### JSON Format (`build/metrics.json`)

```json
{
  "build_id": "build-20260127-1430",
  "start_time": "2026-01-27T14:30:00",
  "end_time": "2026-01-27T15:15:00",
  "duration_seconds": 2700.0,
  "steps_completed": 12,
  "steps_failed": 0,
  "package_size_bytes": 8589934592,
  "image_count": 139,
  "success": true
}
```

### Prometheus Format (`build/metrics.prom`)

```prometheus
# HELP opencenter_build_duration_seconds Build duration
# TYPE opencenter_build_duration_seconds gauge
opencenter_build_duration_seconds{build_id="build-20260127-1430"} 2700.0

# HELP opencenter_build_success Build success (1=success, 0=failure)
# TYPE opencenter_build_success gauge
opencenter_build_success{build_id="build-20260127-1430"} 1

# HELP opencenter_build_steps_completed Steps completed
# TYPE opencenter_build_steps_completed counter
opencenter_build_steps_completed{build_id="build-20260127-1430"} 12

# HELP opencenter_build_steps_failed Steps failed
# TYPE opencenter_build_steps_failed counter
opencenter_build_steps_failed{build_id="build-20260127-1430"} 0

# HELP opencenter_build_package_size_bytes Package size in bytes
# TYPE opencenter_build_package_size_bytes gauge
opencenter_build_package_size_bytes{build_id="build-20260127-1430"} 8589934592

# HELP opencenter_build_image_count Number of container images
# TYPE opencenter_build_image_count gauge
opencenter_build_image_count{build_id="build-20260127-1430"} 139
```

## Prometheus Integration

To scrape metrics into Prometheus:

1. Configure file-based service discovery:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'opencenter-builds'
    file_sd_configs:
      - files:
        - '/path/to/build/metrics.prom'
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: 'build-server'
```

2. Or use pushgateway:

```bash
# Push metrics to Prometheus Pushgateway
cat build/metrics.prom | curl --data-binary @- \
  http://pushgateway:9091/metrics/job/opencenter-build
```

## Troubleshooting

### Metrics not saved

Check build directory permissions:
```bash
ls -ld build/
# Should be writable
```

### Import error

Verify package installed:
```bash
pip show opencenter-build
# Should show package info
```

Reinstall if needed:
```bash
pip install -e .
```

### Missing metrics values

Check step tracking logic:
```python
# Ensure metrics updated in BuildExecutor
logger.debug(f"Steps completed: {metrics.steps_completed}")
logger.debug(f"Steps failed: {metrics.steps_failed}")
```

## Next Steps

- Set up Grafana dashboard (see Task 6.4)
- Configure alerting on build failures
- Track metrics trends over time
