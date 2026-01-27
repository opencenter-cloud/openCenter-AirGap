#!/usr/bin/env python3
"""Main build orchestrator for the resumable build system.

This script coordinates the execution of all build steps with state management,
resume capability, parallel execution, and comprehensive error handling.
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from build_state import BuildState, StepStatus
from build_steps import STEPS, validate_step_definitions
from build_executor import BuildExecutor


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Resumable build system for openCenter AirGap package",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start a fresh build
  python3 scripts/build/build.py --clean
  
  # Resume from last incomplete step (default)
  python3 scripts/build/build.py
  
  # Resume from specific step
  python3 scripts/build/build.py --from-step validate_versions
  
  # Skip a specific step
  python3 scripts/build/build.py --skip-step sign_package
  
  # Force re-execution of all steps
  python3 scripts/build/build.py --force
  
  # Disable parallel execution
  python3 scripts/build/build.py --no-parallel
"""
    )
    
    # Resume control
    resume_group = parser.add_mutually_exclusive_group()
    resume_group.add_argument(
        "--clean",
        action="store_true",
        help="Delete state and start fresh build"
    )
    resume_group.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="Resume from last incomplete step (default)"
    )
    
    parser.add_argument(
        "--from-step",
        metavar="STEP_NAME",
        help="Resume from specific step"
    )
    
    parser.add_argument(
        "--skip-step",
        metavar="STEP_NAME",
        action="append",
        dest="skip_steps",
        help="Skip specific step (can be used multiple times)"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-execution of all steps (bypass input change detection)"
    )
    
    # Parallel execution control
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Disable parallel execution (run all steps sequentially)"
    )
    
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=2,
        metavar="N",
        help="Maximum concurrent steps (default: 2)"
    )
    
    # Legacy environment variable compatibility
    parser.add_argument(
        "--skip-opencenter-private",
        action="store_true",
        help="Skip private registry images (sets SKIP_OPENCENTER_PRIVATE=1)"
    )
    
    parser.add_argument(
        "--skip-kubespray-offline",
        action="store_true",
        help="Skip kubespray-offline download (sets SKIP_KUBESPRAY_OFFLINE=1)"
    )
    
    parser.add_argument(
        "--skip-zarf",
        action="store_true",
        help="Skip Zarf package creation (sets SKIP_ZARF=1)"
    )
    
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run without prompts (sets NON_INTERACTIVE=1)"
    )
    
    args = parser.parse_args()
    
    # Initialize skip_steps if None
    if args.skip_steps is None:
        args.skip_steps = []
    
    return args


def setup_logging(log_file: Path) -> logging.Logger:
    """Configure logging to file and console.
    
    Args:
        log_file: Path to log file
        
    Returns:
        Configured logger
    """
    # Create logger
    logger = logging.getLogger("build")
    logger.setLevel(logging.DEBUG)
    
    # File handler (detailed)
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler (less verbose)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger


def load_state(state_file: Path) -> Optional[BuildState]:
    """Load previous build state or create new.
    
    Args:
        state_file: Path to state file
        
    Returns:
        BuildState object or None if no previous state
    """
    if state_file.exists():
        try:
            return BuildState.load_from_file(state_file)
        except Exception as e:
            print(f"WARNING: Failed to load state file: {e}")
            print("Starting fresh build")
            return None
    return None


def save_state(state: BuildState, state_file: Path) -> None:
    """Persist build state to JSON.
    
    Args:
        state: Build state to save
        state_file: Path to state file
    """
    try:
        state.save_to_file(state_file)
    except Exception as e:
        print(f"ERROR: Failed to save state: {e}")


def run_build(args: argparse.Namespace, state: BuildState, console: Console, logger: logging.Logger) -> bool:
    """Execute the build process.
    
    Args:
        args: Parsed command-line arguments
        state: Build state
        console: Rich console for output
        logger: Logger instance
        
    Returns:
        True if build succeeds, False otherwise
    """
    project_root = Path.cwd()
    
    # Validate step definitions
    try:
        validate_step_definitions()
        logger.info("Step definitions validated")
    except Exception as e:
        console.print(f"[red]ERROR: Invalid step definitions: {e}[/red]")
        return False
    
    # Create executor
    executor = BuildExecutor(
        steps=STEPS,
        state=state,
        project_root=project_root,
        max_parallel=1 if args.no_parallel else args.max_parallel,
        console=console,
        force=args.force,
        logger=logger
    )
    
    # Determine starting point
    start_from = args.from_step if args.from_step else None
    
    # Convert skip_steps list to set
    skip_steps_set = set(args.skip_steps) if args.skip_steps else set()
    
    # Execute build
    try:
        success = executor.execute_build(
            start_from=start_from,
            skip_steps=skip_steps_set
        )
        return success
    except KeyboardInterrupt:
        console.print("\n[yellow]Build interrupted by user[/yellow]")
        logger.warning("Build interrupted by user")
        return False
    except Exception as e:
        console.print(f"\n[red]Build failed with exception: {e}[/red]")
        logger.exception("Build failed with exception")
        return False


def display_summary(state: BuildState, console: Console, success: bool) -> None:
    """Display build summary.
    
    Args:
        state: Build state
        console: Rich console
        success: Whether build succeeded
    """
    # Calculate statistics
    completed = sum(1 for s in state.steps.values() if s.status == StepStatus.COMPLETED)
    failed = sum(1 for s in state.steps.values() if s.status == StepStatus.FAILED)
    skipped = sum(1 for s in state.steps.values() if s.status == StepStatus.SKIPPED)
    total = len(state.steps)
    
    # Calculate total duration
    total_duration = 0.0
    for step in state.steps.values():
        if step.duration_seconds:
            total_duration += step.duration_seconds
    
    # Create summary table
    table = Table(title="Build Summary", show_header=True, header_style="bold")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green" if success else "red")
    
    table.add_row("Status", "✓ SUCCESS" if success else "✗ FAILED")
    table.add_row("Total Steps", str(total))
    table.add_row("Completed", str(completed))
    table.add_row("Failed", str(failed))
    table.add_row("Skipped", str(skipped))
    table.add_row("Duration", f"{total_duration:.1f}s ({total_duration/60:.1f}m)")
    
    console.print()
    console.print(table)
    console.print()


def main() -> int:
    """Main entry point.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Parse arguments
    args = parse_args()
    
    # Setup paths
    project_root = Path.cwd()
    build_dir = project_root / "build"
    build_dir.mkdir(exist_ok=True)
    
    state_file = build_dir / ".build-state.json"
    log_file = build_dir / f"build-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    
    # Setup logging
    logger = setup_logging(log_file)
    logger.info("=" * 80)
    logger.info("openCenter AirGap Build System")
    logger.info("=" * 80)
    logger.info(f"Log file: {log_file}")
    
    # Setup console
    console = Console()
    
    # Display header
    console.print()
    console.print(Panel.fit(
        "[bold cyan]openCenter AirGap Build System[/bold cyan]\n"
        "Resumable build with state management and parallel execution",
        border_style="cyan"
    ))
    console.print()
    
    # Set environment variables for legacy compatibility
    import os
    if args.skip_opencenter_private:
        os.environ["SKIP_OPENCENTER_PRIVATE"] = "1"
        os.environ["SKIP_OPENCENTER_PRIVATE_REGISTRY"] = "true"
    if args.skip_kubespray_offline:
        os.environ["SKIP_KUBESPRAY_OFFLINE"] = "1"
    if args.skip_zarf:
        os.environ["SKIP_ZARF"] = "1"
    if args.non_interactive:
        os.environ["NON_INTERACTIVE"] = "1"
    
    # Handle clean flag
    if args.clean:
        console.print("[yellow]Cleaning previous build state...[/yellow]")
        if state_file.exists():
            state_file.unlink()
            logger.info("Deleted state file")
        
        # Delete completion markers
        completed_dir = build_dir / ".completed"
        if completed_dir.exists():
            import shutil
            shutil.rmtree(completed_dir)
            logger.info("Deleted completion markers")
        
        console.print("[green]✓ Build state cleaned[/green]\n")
    
    # Load or create state
    state = load_state(state_file)
    if state is None:
        state = BuildState(
            build_id=f"build-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        logger.info(f"Created new build state: {state.build_id}")
    else:
        console.print(f"[cyan]Resuming build: {state.build_id}[/cyan]")
        logger.info(f"Loaded existing build state: {state.build_id}")
        
        # Show completed steps
        completed_steps = [name for name, step in state.steps.items() 
                          if step.status == StepStatus.COMPLETED]
        if completed_steps:
            console.print(f"[green]Completed steps: {len(completed_steps)}[/green]")
            for step_name in completed_steps[:5]:  # Show first 5
                console.print(f"  ✓ {step_name}")
            if len(completed_steps) > 5:
                console.print(f"  ... and {len(completed_steps) - 5} more")
        console.print()
    
    # Run build
    success = run_build(args, state, console, logger)
    
    # Save final state
    save_state(state, state_file)
    
    # Display summary
    display_summary(state, console, success)
    
    # Display next steps
    if success:
        console.print("[bold green]✓ Build completed successfully![/bold green]")
        console.print("\nNext steps:")
        console.print("  1. Verify package: zarf package inspect dist/zarf-package-*.tar.zst")
        console.print("  2. Transfer to air-gapped environment")
        console.print("  3. Deploy: zarf package deploy <package-file>")
    else:
        console.print("[bold red]✗ Build failed[/bold red]")
        console.print("\nTo resume:")
        console.print(f"  python3 scripts/build/build.py")
        console.print("\nTo start fresh:")
        console.print(f"  python3 scripts/build/build.py --clean")
        console.print(f"\nCheck logs: {log_file}")
    
    console.print()
    logger.info("=" * 80)
    logger.info(f"Build {'succeeded' if success else 'failed'}")
    logger.info("=" * 80)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
