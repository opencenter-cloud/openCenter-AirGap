"""Property-based tests for dependency resolution.

Feature: resumable-build-system
Properties:
- Property 4: Dependency Order Enforcement
- Property 5: Circular Dependency Detection
"""

import sys
from pathlib import Path

# Add scripts/build to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "build"))

from hypothesis import given, strategies as st, assume, settings
import pytest

from build_steps import StepDefinition, WorkerType
from build_executor import BuildExecutor, CircularDependencyError


# Strategy for generating valid step names
step_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_"),
    min_size=1,
    max_size=30
).filter(lambda x: x[0].isalpha())


def dummy_worker(project_root: Path) -> bool:
    """Dummy worker function for testing."""
    return True


@st.composite
def acyclic_dag_strategy(draw, min_steps=2, max_steps=10):
    """Generate an acyclic directed graph (DAG) of steps.
    
    Creates steps in layers where each step can only depend on steps
    from previous layers, ensuring no cycles.
    """
    num_steps = draw(st.integers(min_value=min_steps, max_value=max_steps))
    
    # Generate unique step names
    step_names = []
    for i in range(num_steps):
        name = f"step_{i}"
        step_names.append(name)
    
    # Create steps with dependencies only on earlier steps
    steps = []
    for i, name in enumerate(step_names):
        # Can depend on any earlier step
        possible_deps = step_names[:i]
        
        if possible_deps:
            # Choose 0 to min(3, len(possible_deps)) dependencies
            num_deps = draw(st.integers(min_value=0, max_value=min(3, len(possible_deps))))
            dependencies = draw(st.lists(
                st.sampled_from(possible_deps),
                min_size=num_deps,
                max_size=num_deps,
                unique=True
            ))
        else:
            dependencies = []
        
        step = StepDefinition(
            name=name,
            description=f"Test step {name}",
            dependencies=dependencies,
            worker_type=WorkerType.PYTHON,
            worker_func=dummy_worker
        )
        steps.append(step)
    
    return steps


@st.composite
def cyclic_graph_strategy(draw, min_steps=3, max_steps=6):
    """Generate a graph with at least one cycle.
    
    Creates a simple cycle: step_0 -> step_1 -> ... -> step_n-1 -> step_0
    This ensures a proper cycle exists in the graph.
    """
    num_steps = draw(st.integers(min_value=min_steps, max_value=max_steps))
    
    # Generate unique step names
    step_names = [f"step_{i}" for i in range(num_steps)]
    
    # Create a cycle: each step depends on the previous, and the first depends on the last
    steps = []
    for i, name in enumerate(step_names):
        if i == 0:
            # First step depends on the last step (creates the cycle)
            dependencies = [step_names[-1]]
        else:
            # Each other step depends on the previous step
            dependencies = [step_names[i-1]]
        
        step = StepDefinition(
            name=name,
            description=f"Test step {name}",
            dependencies=dependencies,
            worker_type=WorkerType.PYTHON,
            worker_func=dummy_worker
        )
        steps.append(step)
    
    return steps


# Feature: resumable-build-system, Property 4: Dependency Order Enforcement
@given(steps=acyclic_dag_strategy(min_steps=2, max_steps=10))
@settings(max_examples=100, deadline=None)
def test_dependency_order_enforcement(steps):
    """
    Property 4: Dependency Order Enforcement
    
    For any step with dependencies, the build orchestrator should verify
    all dependencies are completed before executing the step, and if not,
    execute dependencies first.
    
    Validates: Requirements 2.1, 2.2, 2.4
    """
    executor = BuildExecutor(steps=steps)
    
    # Resolve dependencies
    execution_order = executor.get_execution_order()
    
    # Verify all steps are included
    assert len(execution_order) == len(steps)
    assert set(execution_order) == set(step.name for step in steps)
    
    # Build position map
    position = {name: i for i, name in enumerate(execution_order)}
    
    # Verify dependency order: for each step, all dependencies must appear earlier
    for step in steps:
        step_pos = position[step.name]
        for dep in step.dependencies:
            dep_pos = position[dep]
            assert dep_pos < step_pos, (
                f"Dependency order violated: step '{step.name}' at position {step_pos} "
                f"depends on '{dep}' at position {dep_pos}"
            )


# Feature: resumable-build-system, Property 5: Circular Dependency Detection
@given(steps=cyclic_graph_strategy(min_steps=3, max_steps=6))
@settings(max_examples=100, deadline=None)
def test_circular_dependency_detection(steps):
    """
    Property 5: Circular Dependency Detection
    
    For any step configuration with circular dependencies (A depends on B,
    B depends on A), the build orchestrator should detect the cycle and
    raise an error before execution.
    
    Validates: Requirements 2.3
    """
    executor = BuildExecutor(steps=steps)
    
    # Should raise CircularDependencyError
    with pytest.raises(CircularDependencyError):
        executor.resolve_dependencies()


# Additional test: Verify parallel layers respect dependencies
@given(steps=acyclic_dag_strategy(min_steps=3, max_steps=10))
@settings(max_examples=50, deadline=None)
def test_parallel_layers_respect_dependencies(steps):
    """
    Verify that parallel execution layers respect dependencies.
    
    Steps in the same layer should have no dependency relationship,
    and all dependencies should be in earlier layers.
    """
    executor = BuildExecutor(steps=steps)
    
    # Get parallel layers
    layers = executor.get_parallel_layers()
    
    # Verify all steps are included
    all_steps_in_layers = [step for layer in layers for step in layer]
    assert len(all_steps_in_layers) == len(steps)
    assert set(all_steps_in_layers) == set(step.name for step in steps)
    
    # Build step lookup
    step_map = {step.name: step for step in steps}
    
    # Track which steps have been processed
    processed = set()
    
    for layer_idx, layer in enumerate(layers):
        # All dependencies of steps in this layer must be in processed set
        for step_name in layer:
            step = step_map[step_name]
            for dep in step.dependencies:
                assert dep in processed, (
                    f"Layer {layer_idx}: step '{step_name}' depends on '{dep}' "
                    f"which has not been processed yet"
                )
        
        # Add current layer to processed
        processed.update(layer)


# Test: Resume point validation
@given(
    steps=acyclic_dag_strategy(min_steps=5, max_steps=10),
    resume_index=st.integers(min_value=1, max_value=4)
)
@settings(max_examples=50, deadline=None)
def test_resume_point_validation(steps, resume_index):
    """
    Verify that resume point validation correctly checks dependencies.
    
    When resuming from a step, all its dependencies must be marked complete.
    """
    # Ensure resume_index is valid
    assume(resume_index < len(steps))
    
    executor = BuildExecutor(steps=steps)
    execution_order = executor.get_execution_order()
    
    resume_step = execution_order[resume_index]
    step_def = executor.step_map[resume_step]
    
    # Case 1: All dependencies completed - should succeed
    completed = set(execution_order[:resume_index])
    try:
        executor.validate_resume_point(resume_step, completed)
        # Should succeed if all dependencies are in completed set
        for dep in step_def.dependencies:
            assert dep in completed
    except ValueError:
        # Should only fail if dependencies are missing
        missing_deps = [dep for dep in step_def.dependencies if dep not in completed]
        assert len(missing_deps) > 0
    
    # Case 2: Missing dependencies - should fail
    if step_def.dependencies:
        # Remove one dependency from completed set
        incomplete = completed - {step_def.dependencies[0]}
        with pytest.raises(ValueError, match="unsatisfied dependencies"):
            executor.validate_resume_point(resume_step, incomplete)


# Test: Empty step list
def test_empty_step_list():
    """Verify executor handles empty step list."""
    executor = BuildExecutor(steps=[])
    
    layers = executor.resolve_dependencies()
    assert layers == []
    
    execution_order = executor.get_execution_order()
    assert execution_order == []


# Test: Single step with no dependencies
def test_single_step_no_dependencies():
    """Verify executor handles single step correctly."""
    step = StepDefinition(
        name="single_step",
        description="Single test step",
        dependencies=[],
        worker_type=WorkerType.PYTHON,
        worker_func=dummy_worker
    )
    
    executor = BuildExecutor(steps=[step])
    
    layers = executor.resolve_dependencies()
    assert layers == [["single_step"]]
    
    execution_order = executor.get_execution_order()
    assert execution_order == ["single_step"]


# Test: Linear chain of dependencies
def test_linear_dependency_chain():
    """Verify executor handles linear chain correctly."""
    steps = [
        StepDefinition(
            name="step_1",
            description="Step 1",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=dummy_worker
        ),
        StepDefinition(
            name="step_2",
            description="Step 2",
            dependencies=["step_1"],
            worker_type=WorkerType.PYTHON,
            worker_func=dummy_worker
        ),
        StepDefinition(
            name="step_3",
            description="Step 3",
            dependencies=["step_2"],
            worker_type=WorkerType.PYTHON,
            worker_func=dummy_worker
        ),
    ]
    
    executor = BuildExecutor(steps=steps)
    
    execution_order = executor.get_execution_order()
    assert execution_order == ["step_1", "step_2", "step_3"]
    
    layers = executor.get_parallel_layers()
    assert layers == [["step_1"], ["step_2"], ["step_3"]]


# Test: Diamond dependency pattern
def test_diamond_dependency_pattern():
    """Verify executor handles diamond pattern correctly.
    
    Pattern:
        A
       / \\
      B   C
       \\ /
        D
    """
    steps = [
        StepDefinition(
            name="A",
            description="Step A",
            dependencies=[],
            worker_type=WorkerType.PYTHON,
            worker_func=dummy_worker
        ),
        StepDefinition(
            name="B",
            description="Step B",
            dependencies=["A"],
            worker_type=WorkerType.PYTHON,
            worker_func=dummy_worker
        ),
        StepDefinition(
            name="C",
            description="Step C",
            dependencies=["A"],
            worker_type=WorkerType.PYTHON,
            worker_func=dummy_worker
        ),
        StepDefinition(
            name="D",
            description="Step D",
            dependencies=["B", "C"],
            worker_type=WorkerType.PYTHON,
            worker_func=dummy_worker
        ),
    ]
    
    executor = BuildExecutor(steps=steps)
    
    execution_order = executor.get_execution_order()
    
    # A must be first
    assert execution_order[0] == "A"
    
    # B and C must come before D
    d_index = execution_order.index("D")
    b_index = execution_order.index("B")
    c_index = execution_order.index("C")
    
    assert b_index < d_index
    assert c_index < d_index
    
    # B and C can be in either order (parallel)
    layers = executor.get_parallel_layers()
    assert layers[0] == ["A"]
    assert set(layers[1]) == {"B", "C"}
    assert layers[2] == ["D"]
