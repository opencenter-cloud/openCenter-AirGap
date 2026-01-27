"""Build execution engine with dependency resolution and parallel execution.

This module provides the core execution logic for the resumable build system,
including topological sort, circular dependency detection, and parallel execution.
"""

from typing import List, Dict, Set, Optional, Callable
from pathlib import Path
import subprocess
import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from datetime import datetime

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.table import Table
from rich.panel import Panel

from build_steps import StepDefinition, STEPS, get_step_by_name, WorkerType
from build_state import BuildState, StepStatus


class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected in the build graph."""
    pass


class DependencyResolutionError(Exception):
    """Raised when dependency resolution fails."""
    pass


class BuildExecutor:
    """Executes build steps with dependency resolution and parallel execution support.
    
    Attributes:
        steps: List of step definitions to execute
        state: Build state for tracking progress
        project_root: Root directory of the project
        max_parallel: Maximum number of parallel steps (default: 2)
        console: Rich console for output (optional)
    """
    
    def __init__(
        self,
        steps: Optional[List[StepDefinition]] = None,
        state: Optional[BuildState] = None,
        project_root: Optional[Path] = None,
        max_parallel: int = 2,
        console=None,
        force: bool = False,
        logger: Optional[logging.Logger] = None
    ):
        """Initialize the build executor.
        
        Args:
            steps: List of step definitions (defaults to STEPS from build_steps)
            state: Build state for tracking progress
            project_root: Project root directory (defaults to current directory)
            max_parallel: Maximum concurrent steps
            console: Rich console for output (optional)
            force: Force re-execution of all steps (bypass input change detection)
            logger: Logger instance for structured logging (optional)
        """
        self.steps = steps if steps is not None else STEPS
        self.state = state
        self.project_root = project_root if project_root is not None else Path.cwd()
        self.max_parallel = max_parallel
        self.console = console
        self.force = force
        self.logger = logger if logger is not None else logging.getLogger("build")
        
        # Build step lookup map
        self.step_map: Dict[str, StepDefinition] = {
            step.name: step for step in self.steps
        }
    
    def validate_steps(self) -> None:
        """Validate step definitions.
        
        Checks for:
        - Duplicate step names
        - Non-existent dependencies
        - Valid worker references
        
        Raises:
            ValueError: If validation fails
        """
        step_names = set(self.step_map.keys())
        
        # Check for duplicates
        if len(step_names) != len(self.steps):
            raise ValueError("Duplicate step names detected")
        
        # Validate dependencies exist
        for step in self.steps:
            for dep in step.dependencies:
                if dep not in step_names:
                    raise ValueError(
                        f"Step '{step.name}' has non-existent dependency: '{dep}'"
                    )
        
        # Validate worker references
        for step in self.steps:
            if step.worker_type.value == "bash" and not step.worker_path:
                raise ValueError(
                    f"Step '{step.name}' is BASH type but has no worker_path"
                )
            elif step.worker_type.value == "python" and not step.worker_func:
                raise ValueError(
                    f"Step '{step.name}' is PYTHON type but has no worker_func"
                )
    
    def _has_cycle_util(
        self,
        node: str,
        visited: Set[str],
        rec_stack: Set[str],
        graph: Dict[str, Set[str]]
    ) -> bool:
        """Utility function for cycle detection using DFS.
        
        Args:
            node: Current node being visited
            visited: Set of all visited nodes
            rec_stack: Set of nodes in current recursion stack
            graph: Adjacency list representation of dependency graph
            
        Returns:
            True if cycle detected, False otherwise
        """
        visited.add(node)
        rec_stack.add(node)
        
        # Visit all dependencies
        for neighbor in graph.get(node, set()):
            if neighbor not in visited:
                if self._has_cycle_util(neighbor, visited, rec_stack, graph):
                    return True
            elif neighbor in rec_stack:
                # Back edge found - cycle detected
                return True
        
        rec_stack.remove(node)
        return False
    
    def _has_cycle(self, graph: Dict[str, Set[str]]) -> bool:
        """Detect cycles in dependency graph using DFS.
        
        Args:
            graph: Adjacency list where graph[step] = set of dependencies
            
        Returns:
            True if cycle exists, False otherwise
        """
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        
        for node in graph:
            if node not in visited:
                if self._has_cycle_util(node, visited, rec_stack, graph):
                    return True
        
        return False
    
    def resolve_dependencies(self) -> List[List[str]]:
        """Resolve dependencies and return execution layers.
        
        Uses topological sort with layer detection. Each layer contains steps
        that can execute in parallel (all dependencies satisfied).
        
        Returns:
            List of layers, where each layer is a list of step names that can
            execute in parallel
            
        Raises:
            CircularDependencyError: If circular dependencies detected
            DependencyResolutionError: If resolution fails for other reasons
        """
        # Build adjacency list (step -> set of dependencies)
        graph: Dict[str, Set[str]] = {}
        in_degree: Dict[str, int] = {}
        
        for step in self.steps:
            graph[step.name] = set(step.dependencies)
            in_degree[step.name] = len(step.dependencies)
        
        # Detect cycles
        if self._has_cycle(graph):
            raise CircularDependencyError(
                "Circular dependency detected in build steps"
            )
        
        # Topological sort with layer detection
        layers: List[List[str]] = []
        remaining = set(step.name for step in self.steps)
        
        while remaining:
            # Find all steps with no unsatisfied dependencies
            ready = [
                name for name in remaining
                if all(dep not in remaining for dep in graph[name])
            ]
            
            if not ready:
                # This should not happen if cycle detection worked
                raise DependencyResolutionError(
                    f"Dependency resolution failed. Remaining steps: {remaining}"
                )
            
            layers.append(ready)
            remaining -= set(ready)
        
        return layers
    
    def get_execution_order(self) -> List[str]:
        """Get flattened execution order (sequential).
        
        Returns:
            List of step names in topological order
        """
        layers = self.resolve_dependencies()
        return [step for layer in layers for step in layer]
    
    def get_parallel_layers(self) -> List[List[str]]:
        """Get execution layers for parallel execution.
        
        Returns:
            List of layers where each layer can execute in parallel
        """
        return self.resolve_dependencies()
    
    def validate_resume_point(
        self,
        resume_step: str,
        completed_steps: Set[str]
    ) -> None:
        """Validate that all dependencies of resume point are satisfied.
        
        Args:
            resume_step: Step name to resume from
            completed_steps: Set of already completed step names
            
        Raises:
            ValueError: If resume point is invalid or dependencies not satisfied
        """
        if resume_step not in self.step_map:
            raise ValueError(f"Invalid resume step: '{resume_step}'")
        
        step = self.step_map[resume_step]
        
        # Check all dependencies are completed
        unsatisfied = [
            dep for dep in step.dependencies
            if dep not in completed_steps
        ]
        
        if unsatisfied:
            raise ValueError(
                f"Cannot resume from '{resume_step}': "
                f"unsatisfied dependencies: {', '.join(unsatisfied)}"
            )
    
    def get_steps_to_execute(
        self,
        from_step: Optional[str] = None,
        completed_steps: Optional[Set[str]] = None
    ) -> List[str]:
        """Get list of steps to execute based on resume point and completed steps.
        
        Args:
            from_step: Optional step name to resume from
            completed_steps: Set of already completed step names
            
        Returns:
            List of step names to execute in order
        """
        if completed_steps is None:
            completed_steps = set()
        
        # Get full execution order
        execution_order = self.get_execution_order()
        
        # If no resume point, start from first incomplete step
        if from_step is None:
            return [
                step for step in execution_order
                if step not in completed_steps
            ]
        
        # Validate resume point
        self.validate_resume_point(from_step, completed_steps)
        
        # Find index of resume step
        try:
            resume_index = execution_order.index(from_step)
        except ValueError:
            raise ValueError(f"Step '{from_step}' not found in execution order")
        
        # Return steps from resume point onward (excluding already completed)
        return [
            step for step in execution_order[resume_index:]
            if step not in completed_steps or step == from_step
        ]
    
    def execute_build(
        self,
        start_from: Optional[str] = None,
        skip_steps: Optional[Set[str]] = None
    ) -> bool:
        """Execute all steps starting from start_from.
        
        Args:
            start_from: Optional step name to start from
            skip_steps: Optional set of step names to skip
            
        Returns:
            True if all steps succeed, False otherwise
        """
        if skip_steps is None:
            skip_steps = set()
        
        self.logger.info("=" * 60)
        self.logger.info("BUILD EXECUTION STARTED")
        self.logger.info("=" * 60)
        self.logger.info(f"Project root: {self.project_root}")
        self.logger.info(f"Max parallel: {self.max_parallel}")
        self.logger.info(f"Force mode: {self.force}")
        if start_from:
            self.logger.info(f"Resume from: {start_from}")
        if skip_steps:
            self.logger.info(f"Skip steps: {', '.join(skip_steps)}")
        
        # Validate steps
        self.logger.info("Validating step definitions...")
        self.validate_steps()
        self.logger.info("Step definitions validated")
        
        # Get execution layers for parallel execution
        self.logger.info("Resolving dependencies...")
        layers = self.resolve_dependencies()
        self.logger.info(f"Resolved {len(layers)} execution layers")
        
        # Determine which steps to execute
        completed_steps = set()
        if self.state:
            completed_steps = {
                name for name, result in self.state.steps.items()
                if result.status == StepStatus.COMPLETED
            }
            if completed_steps:
                self.logger.info(f"Previously completed steps: {', '.join(completed_steps)}")
        
        # Handle start_from
        if start_from:
            # Validate resume point
            self.validate_resume_point(start_from, completed_steps)
            
            # Find which layer contains start_from
            start_layer_idx = None
            for idx, layer in enumerate(layers):
                if start_from in layer:
                    start_layer_idx = idx
                    break
            
            if start_layer_idx is not None:
                layers = layers[start_layer_idx:]
                self.logger.info(f"Resuming from layer {start_layer_idx}")
        
        # Count total steps to execute
        total_steps = sum(
            len([s for s in layer if s not in completed_steps and s not in skip_steps])
            for layer in layers
        )
        
        if total_steps == 0:
            self._log("[green]All steps already completed[/green]")
            self.logger.info("All steps already completed")
            return True
        
        self.logger.info(f"Total steps to execute: {total_steps}")
        
        # Display build start
        self._display_build_start(total_steps)
        
        build_start_time = time.time()
        steps_executed = 0
        
        # Execute layers
        for layer_idx, layer in enumerate(layers):
            self.logger.info(f"Executing layer {layer_idx + 1}/{len(layers)}: {', '.join(layer)}")
            
            # Filter out completed and skipped steps
            steps_to_run = [
                step_name for step_name in layer
                if step_name not in completed_steps and step_name not in skip_steps
            ]
            
            # Handle skipped steps
            for step_name in layer:
                if step_name in skip_steps:
                    if self.state:
                        self.state.mark_step_skipped(step_name)
                    self._log(f"[yellow]WARN: Skipping step '{step_name}'[/yellow]")
            
            if not steps_to_run:
                continue
            
            # Execute layer
            if not self.execute_layer(steps_to_run):
                # Display failure summary
                build_duration = time.time() - build_start_time
                self._display_build_summary(steps_executed, total_steps, build_duration, success=False)
                return False
            
            # Mark steps as completed
            for step_name in steps_to_run:
                completed_steps.add(step_name)
                steps_executed += 1
        
        # Display success summary
        build_duration = time.time() - build_start_time
        self._display_build_summary(steps_executed, total_steps, build_duration, success=True)
        
        return True
    
    def execute_layer(self, step_names: List[str]) -> bool:
        """Execute all steps in a layer (potentially in parallel).
        
        Args:
            step_names: List of step names to execute
            
        Returns:
            True if all steps succeed, False otherwise
        """
        if len(step_names) == 1 or self.max_parallel == 1:
            # Sequential execution
            for step_name in step_names:
                step = self.step_map[step_name]
                if not self.execute_step(step):
                    return False
            return True
        
        # Parallel execution
        with ThreadPoolExecutor(max_workers=min(self.max_parallel, len(step_names))) as executor:
            futures: Dict[Future, str] = {}
            
            for step_name in step_names:
                step = self.step_map[step_name]
                future = executor.submit(self.execute_step, step)
                futures[future] = step_name
            
            # Wait for all to complete
            success = True
            for future in as_completed(futures):
                step_name = futures[future]
                try:
                    if not future.result():
                        self._log(f"ERROR: Step '{step_name}' failed")
                        success = False
                except Exception as e:
                    self._log(f"ERROR: Step '{step_name}' raised exception: {e}")
                    success = False
            
            return success
    
    def check_input_changes(self, step: StepDefinition) -> bool:
        """Check if input files have changed since last execution.
        
        Args:
            step: Step definition to check
            
        Returns:
            True if inputs changed or cannot determine, False if unchanged
        """
        # If force flag is set, always return True (inputs "changed")
        if self.force:
            return True
        
        # If no input files defined, assume changed
        if not step.input_files:
            return True
        
        # If no output files defined, assume changed
        if not step.output_files:
            return True
        
        # Check if all output files exist
        for output_path_str in step.output_files:
            output_path = self.project_root / output_path_str
            if not output_path.exists():
                self._log(f"  [dim]Output missing: {output_path_str}[/dim]")
                return True
        
        # Get the oldest output file modification time
        output_mtimes = []
        for output_path_str in step.output_files:
            output_path = self.project_root / output_path_str
            if output_path.is_file():
                output_mtimes.append(output_path.stat().st_mtime)
            elif output_path.is_dir():
                # For directories, get the newest file inside
                try:
                    dir_files = list(output_path.rglob('*'))
                    if dir_files:
                        dir_mtimes = [f.stat().st_mtime for f in dir_files if f.is_file()]
                        if dir_mtimes:
                            output_mtimes.append(min(dir_mtimes))
                except Exception:
                    # If we can't check directory, assume changed
                    return True
        
        if not output_mtimes:
            # No output files found
            return True
        
        oldest_output_mtime = min(output_mtimes)
        
        # Check if any input file is newer than the oldest output
        for input_path_str in step.input_files:
            input_path = self.project_root / input_path_str
            
            if not input_path.exists():
                # Input file doesn't exist - assume changed
                self._log(f"  [dim]Input not found: {input_path_str}[/dim]")
                return True
            
            if input_path.is_file():
                input_mtime = input_path.stat().st_mtime
                if input_mtime > oldest_output_mtime:
                    self._log(f"  [dim]Input changed: {input_path_str}[/dim]")
                    return True
            elif input_path.is_dir():
                # For directories, check all files inside
                try:
                    for file_path in input_path.rglob('*'):
                        if file_path.is_file():
                            file_mtime = file_path.stat().st_mtime
                            if file_mtime > oldest_output_mtime:
                                self._log(f"  [dim]Input changed: {file_path.relative_to(self.project_root)}[/dim]")
                                return True
                except Exception:
                    # If we can't check directory, assume changed
                    return True
        
        # All inputs are older than outputs - no changes
        return False
    
    def should_skip_step(self, step: StepDefinition) -> bool:
        """Determine if a step should be skipped based on input/output analysis.
        
        Args:
            step: Step definition to check
            
        Returns:
            True if step should be skipped, False if it should execute
        """
        # Don't skip if force flag is set
        if self.force:
            return False
        
        # Don't skip if no input/output files defined
        if not step.input_files or not step.output_files:
            return False
        
        # Check if inputs have changed
        inputs_changed = self.check_input_changes(step)
        
        if not inputs_changed:
            self._log(f"  [yellow]Skipping (inputs unchanged, outputs exist)[/yellow]")
            return True
        
        return False
    
    def execute_step(self, step: StepDefinition) -> bool:
        """Execute a single step.
        
        Args:
            step: Step definition to execute
            
        Returns:
            True if step succeeds, False otherwise
        """
        self.logger.info("-" * 60)
        self.logger.info(f"STEP: {step.name}")
        self.logger.info(f"Description: {step.description}")
        self.logger.info(f"Worker type: {step.worker_type.value}")
        self.logger.info(f"Start time: {datetime.now().isoformat()}")
        
        self._log(f"[cyan]▶ Starting:[/cyan] {step.name}")
        self._log(f"  [dim]{step.description}[/dim]")
        
        # Check if step should be skipped based on input/output analysis
        if self.should_skip_step(step):
            # Mark as completed (skipped but successful)
            if self.state:
                self.state.mark_step_completed(step.name, 0.0)
            self._log(f"[green]✓ Skipped:[/green] {step.name} [dim](0.00s)[/dim]")
            self.logger.info(f"Step skipped (inputs unchanged, outputs exist)")
            
            # Create completion marker
            self._create_completion_marker(step.name)
            
            return True
        
        # Mark step as started
        start_time = time.time()
        if self.state:
            self.state.mark_step_started(step.name)
        
        try:
            # Execute worker based on type
            if step.worker_type == WorkerType.BASH:
                success = self.execute_bash_worker(step)
            elif step.worker_type == WorkerType.PYTHON:
                success = self.execute_python_worker(step)
            else:
                raise ValueError(f"Unknown worker type: {step.worker_type}")
            
            if not success:
                duration = time.time() - start_time
                self.logger.error(f"Step failed: {step.name}")
                self.logger.error(f"Duration: {duration:.2f}s")
                
                # Only update error message if not already set by worker
                if self.state and step.name in self.state.steps:
                    if not self.state.steps[step.name].error_message:
                        self.state.mark_step_failed(step.name, "Worker returned failure")
                    else:
                        # Just update the status and duration
                        self.state.steps[step.name].status = StepStatus.FAILED
                        self.state.steps[step.name].end_time = datetime.now()
                        self.state.steps[step.name].duration_seconds = duration
                self._log(f"[red]✗ Failed:[/red] {step.name} [dim]({duration:.2f}s)[/dim]")
                return False
            
            # Run validation if defined
            if step.validation_func:
                self._log(f"  [dim]Validating...[/dim]")
                self.logger.info("Running validation...")
                if not self.validate_step_output(step):
                    duration = time.time() - start_time
                    if self.state:
                        self.state.mark_step_failed(step.name, "Validation failed")
                    self._log(f"[red]✗ Validation failed:[/red] {step.name} [dim]({duration:.2f}s)[/dim]")
                    self.logger.error(f"Validation failed for step: {step.name}")
                    self.logger.error(f"Duration: {duration:.2f}s")
                    return False
                self.logger.info("Validation passed")
            
            # Mark step as completed
            duration = time.time() - start_time
            end_time = datetime.now()
            if self.state:
                self.state.mark_step_completed(step.name, duration)
            
            self._log(f"[green]✓ Completed:[/green] {step.name} [dim]({duration:.2f}s)[/dim]")
            self.logger.info(f"Step completed successfully: {step.name}")
            self.logger.info(f"End time: {end_time.isoformat()}")
            self.logger.info(f"Duration: {duration:.2f}s")
            
            # Create completion marker
            self._create_completion_marker(step.name)
            
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"{type(e).__name__}: {str(e)}"
            if self.state:
                self.state.mark_step_failed(step.name, error_msg)
            self._log(f"[red]✗ Exception:[/red] {step.name} [dim]({duration:.2f}s)[/dim]")
            self._log(f"  [red]{error_msg}[/red]")
            self.logger.exception(f"Step raised exception: {step.name}")
            self.logger.error(f"Duration: {duration:.2f}s")
            return False
    
    def execute_bash_worker(self, step: StepDefinition) -> bool:
        """Execute Bash script worker.
        
        Args:
            step: Step definition with Bash worker
            
        Returns:
            True if worker succeeds, False otherwise
        """
        if not step.worker_path:
            raise ValueError(f"Step '{step.name}' has no worker_path")
        
        script_path = self.project_root / step.worker_path
        
        if not script_path.exists():
            error_msg = f"Bash worker script not found: {script_path}"
            self._log(f"ERROR: {error_msg}")
            self.logger.error(error_msg)
            return False
        
        command = ["/bin/bash", str(script_path)]
        self._log(f"INFO: Executing bash worker: {script_path}")
        self.logger.info(f"Executing command: {' '.join(command)}")
        self.logger.info(f"Working directory: {self.project_root}")
        if step.timeout_seconds:
            self.logger.info(f"Timeout: {step.timeout_seconds}s")
        
        try:
            # Execute subprocess
            result = subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=step.timeout_seconds,
                env=os.environ.copy()
            )
            
            # Log output
            if result.stdout:
                self._log(f"STDOUT:\n{result.stdout}")
                self.logger.info(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                self._log(f"STDERR:\n{result.stderr}")
                self.logger.warning(f"STDERR:\n{result.stderr}")
            
            # Check exit code
            if result.returncode != 0:
                error_msg = f"Bash worker exited with code {result.returncode}"
                self._log(f"ERROR: {error_msg}")
                self.logger.error(error_msg)
                return False
            
            self.logger.info(f"Bash worker completed successfully")
            return True
            
        except subprocess.TimeoutExpired:
            error_msg = f"Bash worker timed out after {step.timeout_seconds}s"
            self._log(f"ERROR: {error_msg}")
            self.logger.error(error_msg)
            return False
        except Exception as e:
            error_msg = f"Bash worker execution failed: {e}"
            self._log(f"ERROR: {error_msg}")
            self.logger.exception(error_msg)
            return False
    
    def execute_python_worker(self, step: StepDefinition) -> bool:
        """Execute Python function worker.
        
        Args:
            step: Step definition with Python worker
            
        Returns:
            True if worker succeeds, False otherwise
        """
        if not step.worker_func:
            raise ValueError(f"Step '{step.name}' has no worker_func")
        
        worker_name = step.worker_func.__name__
        self._log(f"INFO: Executing python worker: {worker_name}")
        self.logger.info(f"Executing Python worker: {worker_name}")
        self.logger.info(f"Worker module: {step.worker_func.__module__}")
        
        try:
            # Call worker function with project_root
            result = step.worker_func(self.project_root)
            
            # Check result
            if result is False:
                error_msg = "Python worker returned False"
                self._log(f"ERROR: {error_msg}")
                self.logger.error(error_msg)
                return False
            elif result is True:
                self.logger.info(f"Python worker completed successfully")
                return True
            else:
                # Treat any other return value as success
                self.logger.info(f"Python worker completed (returned {type(result).__name__})")
                return True
                
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            self._log(f"ERROR: Python worker raised exception: {error_msg}")
            self.logger.error(f"Python worker raised exception: {error_msg}")
            
            import traceback
            traceback_str = traceback.format_exc()
            self._log(f"Traceback:\n{traceback_str}")
            self.logger.error(f"Traceback:\n{traceback_str}")
            
            # Update state with exception details
            if self.state and step.name in self.state.steps:
                self.state.steps[step.name].error_message = error_msg
            
            return False
    
    def validate_step_output(self, step: StepDefinition) -> bool:
        """Run validation function if defined.
        
        Args:
            step: Step definition with optional validation function
            
        Returns:
            True if validation passes or no validation defined, False otherwise
        """
        if not step.validation_func:
            return True
        
        try:
            result = step.validation_func(self.project_root)
            return result is not False
        except Exception as e:
            self._log(f"ERROR: Validation raised exception: {type(e).__name__}: {str(e)}")
            return False
    
    def _create_completion_marker(self, step_name: str) -> None:
        """Create completion marker file for a step.
        
        Args:
            step_name: Name of the completed step
        """
        marker_dir = self.project_root / "build" / ".completed"
        marker_dir.mkdir(parents=True, exist_ok=True)
        
        marker_file = marker_dir / step_name
        marker_file.write_text(datetime.now().isoformat())
    
    def _log(self, message: str) -> None:
        """Log a message to console.
        
        Args:
            message: Message to log
        """
        if self.console:
            self.console.print(message)
        else:
            print(message)
    
    def _display_build_start(self, total_steps: int) -> None:
        """Display build start information.
        
        Args:
            total_steps: Total number of steps to execute
        """
        if not self.console:
            return
        
        self.console.print()
        self.console.print(Panel.fit(
            f"[bold cyan]Starting Build[/bold cyan]\n"
            f"Steps to execute: {total_steps}\n"
            f"Max parallel: {self.max_parallel}",
            border_style="cyan"
        ))
        self.console.print()
    
    def _display_build_summary(
        self,
        steps_executed: int,
        total_steps: int,
        duration: float,
        success: bool
    ) -> None:
        """Display build completion summary.
        
        Args:
            steps_executed: Number of steps executed
            total_steps: Total number of steps
            duration: Total build duration in seconds
            success: Whether build succeeded
        """
        # Log summary
        self.logger.info("=" * 60)
        self.logger.info("BUILD SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Status: {'SUCCESS' if success else 'FAILED'}")
        self.logger.info(f"Steps executed: {steps_executed}/{total_steps}")
        self.logger.info(f"Total duration: {duration:.2f}s ({duration/60:.1f}m)")
        
        if self.state:
            # Count step statuses
            completed = sum(1 for r in self.state.steps.values() if r.status == StepStatus.COMPLETED)
            failed = sum(1 for r in self.state.steps.values() if r.status == StepStatus.FAILED)
            skipped = sum(1 for r in self.state.steps.values() if r.status == StepStatus.SKIPPED)
            
            self.logger.info(f"Completed steps: {completed}")
            if failed > 0:
                self.logger.info(f"Failed steps: {failed}")
                # List failed steps
                failed_steps = [name for name, r in self.state.steps.items() if r.status == StepStatus.FAILED]
                for step_name in failed_steps:
                    step_result = self.state.steps[step_name]
                    self.logger.error(f"  - {step_name}: {step_result.error_message}")
            if skipped > 0:
                self.logger.info(f"Skipped steps: {skipped}")
        
        self.logger.info("=" * 60)
        
        if not self.console:
            return
        
        self.console.print()
        
        # Create summary table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Label", style="bold")
        table.add_column("Value")
        
        status_text = "[green]SUCCESS[/green]" if success else "[red]FAILED[/red]"
        table.add_row("Status:", status_text)
        table.add_row("Steps executed:", f"{steps_executed}/{total_steps}")
        table.add_row("Duration:", f"{duration:.2f}s ({duration/60:.1f}m)")
        
        if self.state:
            # Count step statuses
            completed = sum(1 for r in self.state.steps.values() if r.status == StepStatus.COMPLETED)
            failed = sum(1 for r in self.state.steps.values() if r.status == StepStatus.FAILED)
            skipped = sum(1 for r in self.state.steps.values() if r.status == StepStatus.SKIPPED)
            
            table.add_row("Completed:", f"[green]{completed}[/green]")
            if failed > 0:
                table.add_row("Failed:", f"[red]{failed}[/red]")
            if skipped > 0:
                table.add_row("Skipped:", f"[yellow]{skipped}[/yellow]")
        
        border_style = "green" if success else "red"
        title = "Build Complete" if success else "Build Failed"
        
        self.console.print(Panel(
            table,
            title=f"[bold]{title}[/bold]",
            border_style=border_style
        ))
        self.console.print()


def create_dependency_graph_visualization(steps: List[StepDefinition]) -> str:
    """Create a text representation of the dependency graph.
    
    Args:
        steps: List of step definitions
        
    Returns:
        String representation of the dependency graph
    """
    lines = ["Dependency Graph:", ""]
    
    for step in steps:
        if step.dependencies:
            deps_str = ", ".join(step.dependencies)
            lines.append(f"  {step.name} <- [{deps_str}]")
        else:
            lines.append(f"  {step.name} (no dependencies)")
    
    return "\n".join(lines)
