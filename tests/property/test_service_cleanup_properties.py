"""Property-based tests for service cleanup on failure.

This module tests the correctness property that service cleanup
removes all partially deployed artifacts and containers when
deployment fails.

**Property 14: Service Cleanup on Failure**

For any service startup failure, the cleanup process should remove
all partially deployed artifacts and containers.

**Validates: Requirements 9.5**
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, call

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from opencenter_build.cli import _cleanup_services


@pytest.fixture
def mock_subprocess():
    """Mock subprocess for testing cleanup."""
    with patch("opencenter_build.cli.subprocess") as mock_sub:
        yield mock_sub


@pytest.fixture
def mock_console():
    """Mock console for testing output."""
    with patch("opencenter_build.cli.console") as mock_cons:
        yield mock_cons


# Strategy for container names
container_names = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"), min_codepoint=ord("a"), max_codepoint=ord("z")
    ),
    min_size=5,
    max_size=30,
).filter(lambda x: x and x[0].isalpha())


@given(container_name=container_names)
@settings(
    max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_14_cleanup_stops_and_removes_container(
    container_name, mock_subprocess, mock_console
):
    """
    Property 14: Service Cleanup on Failure (Container Removal)

    For any container name, cleanup should execute both stop and remove
    commands in the correct order.

    **Validates: Requirements 9.5**
    """
    # Reset mock for this example
    mock_subprocess.run.reset_mock()

    # Configure mock to succeed
    mock_subprocess.run.return_value = Mock(returncode=0)

    # Execute cleanup
    _cleanup_services(container_name, verbose=False)

    # Property: Both stop and remove commands should be called
    assert mock_subprocess.run.call_count == 2

    # Property: Stop should be called before remove
    calls = mock_subprocess.run.call_args_list

    stop_call = calls[0]
    remove_call = calls[1]

    # Verify stop command
    assert stop_call[0][0] == ["docker", "stop", container_name]
    assert stop_call[1]["check"] is False

    # Verify remove command
    assert remove_call[0][0] == ["docker", "rm", container_name]
    assert remove_call[1]["check"] is False


@given(container_name=container_names)
@settings(
    max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_14_cleanup_continues_on_stop_failure(
    container_name, mock_subprocess, mock_console
):
    """
    Property 14: Service Cleanup on Failure (Resilience)

    For any container name, if stop fails, cleanup should still
    attempt to remove the container.

    **Validates: Requirements 9.5**
    """
    # Reset mock for this example
    mock_subprocess.run.reset_mock()

    # Configure mock: stop fails, remove succeeds
    def run_side_effect(cmd, **kwargs):
        if "stop" in cmd:
            raise subprocess.CalledProcessError(1, cmd)
        return Mock(returncode=0)

    mock_subprocess.run.side_effect = run_side_effect

    # Execute cleanup (should not raise)
    _cleanup_services(container_name, verbose=False)

    # Property: Both commands should be attempted despite stop failure
    assert mock_subprocess.run.call_count == 2


@given(container_name=container_names)
@settings(
    max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_14_cleanup_suppresses_output_by_default(
    container_name, mock_subprocess, mock_console
):
    """
    Property 14: Service Cleanup on Failure (Output Suppression)

    For any container name, cleanup should suppress command output
    when verbose is False.

    **Validates: Requirements 9.5**
    """
    # Configure mock to succeed
    mock_subprocess.run.return_value = Mock(returncode=0)

    # Execute cleanup with verbose=False
    _cleanup_services(container_name, verbose=False)

    # Property: capture_output should be True for both commands
    calls = mock_subprocess.run.call_args_list

    for call_args in calls:
        assert call_args[1]["capture_output"] is True


@given(container_name=container_names)
@settings(
    max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_14_cleanup_shows_output_when_verbose(
    container_name, mock_subprocess, mock_console
):
    """
    Property 14: Service Cleanup on Failure (Verbose Output)

    For any container name, cleanup should show command output
    when verbose is True.

    **Validates: Requirements 9.5**
    """
    # Configure mock to succeed
    mock_subprocess.run.return_value = Mock(returncode=0)

    # Execute cleanup with verbose=True
    _cleanup_services(container_name, verbose=True)

    # Property: capture_output should be False for both commands
    calls = mock_subprocess.run.call_args_list

    for call_args in calls:
        assert call_args[1]["capture_output"] is False


@given(container_name=container_names)
@settings(
    max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_14_cleanup_handles_all_exceptions(container_name, mock_subprocess, mock_console):
    """
    Property 14: Service Cleanup on Failure (Exception Handling)

    For any container name, cleanup should handle all exceptions
    gracefully and not propagate them.

    **Validates: Requirements 9.5**
    """
    # Configure mock to raise various exceptions
    exceptions = [
        subprocess.CalledProcessError(1, ["docker", "stop"]),
        FileNotFoundError("docker not found"),
        PermissionError("permission denied"),
        Exception("unexpected error"),
    ]

    for exc in exceptions:
        mock_subprocess.run.side_effect = exc

        # Property: Should not raise any exception
        try:
            _cleanup_services(container_name, verbose=False)
        except Exception as e:
            pytest.fail(f"Cleanup raised exception: {e}")


@given(container_name=container_names, verbose=st.booleans())
@settings(
    max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_14_cleanup_idempotent(container_name, verbose, mock_subprocess, mock_console):
    """
    Property 14: Service Cleanup on Failure (Idempotency)

    For any container name, calling cleanup multiple times should
    be safe and produce the same result.

    **Validates: Requirements 9.5**
    """
    # Reset mock for this example
    mock_subprocess.run.reset_mock()

    # Configure mock to succeed
    mock_subprocess.run.return_value = Mock(returncode=0)

    # Execute cleanup multiple times
    _cleanup_services(container_name, verbose=verbose)
    first_call_count = mock_subprocess.run.call_count

    mock_subprocess.run.reset_mock()

    _cleanup_services(container_name, verbose=verbose)
    second_call_count = mock_subprocess.run.call_count

    # Property: Same number of calls each time
    assert first_call_count == second_call_count == 2


@given(container_name=container_names)
@settings(
    max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_14_cleanup_uses_check_false(container_name, mock_subprocess, mock_console):
    """
    Property 14: Service Cleanup on Failure (Error Tolerance)

    For any container name, cleanup should use check=False to
    tolerate command failures.

    **Validates: Requirements 9.5**
    """
    # Configure mock to succeed
    mock_subprocess.run.return_value = Mock(returncode=0)

    # Execute cleanup
    _cleanup_services(container_name, verbose=False)

    # Property: All commands should use check=False
    calls = mock_subprocess.run.call_args_list

    for call_args in calls:
        assert call_args[1]["check"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
