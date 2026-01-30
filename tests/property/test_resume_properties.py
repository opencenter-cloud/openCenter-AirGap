"""Property-based tests for resume behavior.

Tests Property 5: Resume Skips Completed Steps
Tests Property 6: Resume Starts at First Incomplete
Validates: Requirements 4.3, 4.4
"""

import tempfile
from datetime import datetime
from pathlib import Path

from hypothesis import given, strategies as st

from opencenter_build.config import BuildConfig
from opencenter_build.orchestrator import BuildOrchestrator
from opencenter_build.state import (
    BuildState,
    StateManager,
    StepCheckpoint,
    StepStatus,
)


@given(
    num_completed=st.integers(min_value=1, max_value=5),
    num_pending=st.integers(min_value=1, max_value=5),
)
def test_resume_skips_completed_steps(num_completed: int, num_pending: int) -> None:
    """Property 5: Resume Skips Completed Steps.

    **Validates: Requirements 4.3**

    For any build state with completed steps, resuming the build should
    skip those steps and not re-execute them.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        state_mgr = StateManager(state_file)

        # Create state with some completed and some pending steps
        start_time = datetime.now().isoformat()
        steps = []

        # Add completed steps
        for i in range(num_completed):
            steps.append(
                StepCheckpoint(
                    name=f"completed_step_{i}",
                    status=StepStatus.COMPLETED,
                    start_time=start_time,
                    end_time=start_time,
                    artifacts={"test": f"artifact_{i}"},
                )
            )

        # Add pending steps
        for i in range(num_pending):
            steps.append(
                StepCheckpoint(
                    name=f"pending_step_{i}",
                    status=StepStatus.PENDING,
                )
            )

        state = BuildState(
            build_id="test_build",
            start_time=start_time,
            steps=steps,
            config_hash="test_hash",
        )

        state_mgr.write_build_state(state)

        # Find resume point
        resume_index = state_mgr.find_resume_point(state)

        # Verify resume point is at first pending step
        assert resume_index == num_completed

        # Verify all steps before resume point are completed
        for i in range(resume_index):
            assert state.steps[i].status == StepStatus.COMPLETED

        # Verify all steps at or after resume point are not completed
        for i in range(resume_index, len(state.steps)):
            assert state.steps[i].status != StepStatus.COMPLETED


@given(
    num_steps=st.integers(min_value=2, max_value=10),
    first_incomplete_index=st.integers(min_value=0, max_value=9),
    incomplete_status=st.sampled_from([StepStatus.PENDING, StepStatus.RUNNING, StepStatus.FAILED]),
)
def test_resume_starts_at_first_incomplete(
    num_steps: int, first_incomplete_index: int, incomplete_status: StepStatus
) -> None:
    """Property 6: Resume Starts at First Incomplete.

    **Validates: Requirements 4.4**

    For any build state with mixed step statuses (completed, failed, pending),
    resuming should start execution at the first non-completed step.
    """
    # Ensure first_incomplete_index is within bounds
    first_incomplete_index = first_incomplete_index % num_steps

    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        state_mgr = StateManager(state_file)

        # Create state with mixed statuses
        start_time = datetime.now().isoformat()
        steps = []

        for i in range(num_steps):
            if i < first_incomplete_index:
                # Steps before first incomplete are completed
                steps.append(
                    StepCheckpoint(
                        name=f"step_{i}",
                        status=StepStatus.COMPLETED,
                        start_time=start_time,
                        end_time=start_time,
                    )
                )
            elif i == first_incomplete_index:
                # First incomplete step (could be PENDING, RUNNING, or FAILED)
                steps.append(
                    StepCheckpoint(
                        name=f"step_{i}",
                        status=incomplete_status,
                        start_time=start_time if incomplete_status != StepStatus.PENDING else None,
                        error="test error" if incomplete_status == StepStatus.FAILED else None,
                    )
                )
            else:
                # Steps after first incomplete are pending
                steps.append(
                    StepCheckpoint(
                        name=f"step_{i}",
                        status=StepStatus.PENDING,
                    )
                )

        state = BuildState(
            build_id="test_build",
            start_time=start_time,
            steps=steps,
            config_hash="test_hash",
        )

        state_mgr.write_build_state(state)

        # Find resume point
        resume_index = state_mgr.find_resume_point(state)

        # Verify resume point is at first incomplete step
        assert resume_index == first_incomplete_index

        # Verify all steps before resume point are completed
        for i in range(resume_index):
            assert state.steps[i].status == StepStatus.COMPLETED

        # Verify step at resume point is not completed
        if resume_index < len(state.steps):
            assert state.steps[resume_index].status != StepStatus.COMPLETED


@given(
    num_steps=st.integers(min_value=1, max_value=10),
)
def test_resume_all_completed(num_steps: int) -> None:
    """Property 6: Resume with all steps completed.

    **Validates: Requirements 4.4**

    For any build state where all steps are completed, resume point
    should be at the end (no steps to execute).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        state_mgr = StateManager(state_file)

        # Create state with all completed steps
        start_time = datetime.now().isoformat()
        steps = [
            StepCheckpoint(
                name=f"step_{i}",
                status=StepStatus.COMPLETED,
                start_time=start_time,
                end_time=start_time,
            )
            for i in range(num_steps)
        ]

        state = BuildState(
            build_id="test_build",
            start_time=start_time,
            steps=steps,
            config_hash="test_hash",
        )

        state_mgr.write_build_state(state)

        # Find resume point
        resume_index = state_mgr.find_resume_point(state)

        # Verify resume point is at end (all steps completed)
        assert resume_index == len(state.steps)


@given(
    num_steps=st.integers(min_value=1, max_value=10),
)
def test_resume_orchestrator_integration(num_steps: int) -> None:
    """Property 5 & 6: Integration test with BuildOrchestrator.

    **Validates: Requirements 4.3, 4.4**

    Verify that BuildOrchestrator correctly uses resume point to skip
    completed steps and start at first incomplete step.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        config_file = Path(tmpdir) / "versions.env"

        # Create minimal config file
        config_file.write_text(
            """
KUBERNETES_VERSION=v1.34.3
KUBESPRAY_VERSION=master
KUBESPRAY_COMMIT_SHA=abc123
UBUNTU_VERSION=24.04
CONTAINER_RUNTIME=containerd
CNI_PLUGIN=calico
TERRAFORM_VERSION=1.6.6
FLUXCD_VERSION=v2.2.0
GITEA_VERSION=1.21.0
CERT_MANAGER_VERSION=v1.13.0
INGRESS_NGINX_VERSION=v1.9.0
KEYCLOAK_VERSION=21.1.1
PROMETHEUS_VERSION=v2.48.0
GRAFANA_VERSION=10.2.0
OPENCENTER_GITOPS_BASE_REPO=https://github.com/example/repo.git
OPENCENTER_GITOPS_BASE_VERSION=v1.0.0
OPENCENTER_GITOPS_BASE_COMMIT_SHA=def456
OPENCENTER_CONTAINER_REGISTRY=registry.example.com
TARGET_ARCH=amd64
PYTHON_VERSION=3.10
"""
        )

        config = BuildConfig.from_env_file(config_file)
        state_mgr = StateManager(state_file)

        # Create orchestrator with limited steps
        orchestrator = BuildOrchestrator(config, state_mgr, clean=False)
        orchestrator.steps = [f"step_{i}" for i in range(num_steps)]

        # Initialize state
        state = orchestrator._initialize_state()

        # Mark some steps as completed
        num_completed = num_steps // 2
        for i in range(num_completed):
            step = state.steps[i]
            step.status = StepStatus.COMPLETED
            step.start_time = datetime.now().isoformat()
            step.end_time = datetime.now().isoformat()
            state_mgr.update_step(step.name, step)

        # Reload state
        loaded_state = state_mgr.read_build_state()
        assert loaded_state is not None

        # Find resume point
        resume_index = state_mgr.find_resume_point(loaded_state)

        # Verify resume point is correct
        assert resume_index == num_completed

        # Verify completed steps are before resume point
        for i in range(resume_index):
            assert loaded_state.steps[i].status == StepStatus.COMPLETED

        # Verify incomplete steps are at or after resume point
        for i in range(resume_index, len(loaded_state.steps)):
            assert loaded_state.steps[i].status != StepStatus.COMPLETED
