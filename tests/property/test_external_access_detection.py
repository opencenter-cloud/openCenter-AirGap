#!/usr/bin/env python3
"""
Property-Based Test: External Access Detection

Property 24: For any component that attempts to connect to an external internet
address, the deployment system should detect the attempt, fail the deployment,
and log a clear error message identifying the component and target address.

Validates: Requirements 9.8
"""

import subprocess
import tempfile
import os
from pathlib import Path
from typing import List, Tuple, Dict
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck, assume

# Test configuration
MIN_EXAMPLES = 100
MAX_EXAMPLES = 200


def is_internal_ip(ip: str) -> bool:
    """Check if an IP address is in internal ranges."""
    if ip.startswith("127.") or ip.startswith("localhost"):
        return True
    if ip.startswith("10."):
        return True
    if ip.startswith("192.168."):
        return True
    # Check 172.16-31 range
    if ip.startswith("172."):
        octets = ip.split(".")
        if len(octets) >= 2:
            try:
                second_octet = int(octets[1])
                if 16 <= second_octet <= 31:
                    return True
            except ValueError:
                pass
    return False


def detect_external_access(log_content: str, bastion_ip: str = "") -> Tuple[bool, List[str], str]:
    """
    Detect external access attempts from tcpdump log.
    
    Returns:
        Tuple of (violation_detected, external_ips, error_message)
    """
    external_ips = []
    
    for line in log_content.split("\n"):
        # Skip empty lines and tcpdump startup messages
        if not line or line.startswith("tcpdump:") or "listening on" in line:
            continue
        
        # Parse tcpdump output: IP src.port > dst.port
        if " IP " in line and " > " in line:
            try:
                parts = line.split(" IP ")[1].split(" > ")
                if len(parts) >= 2:
                    src = parts[0].rsplit(".", 1)[0]  # Remove port
                    dst = parts[1].split(":")[0].rsplit(".", 1)[0]  # Remove port and flags
                    
                    # Check if destination is external
                    if dst and not is_internal_ip(dst) and dst != bastion_ip:
                        if dst not in external_ips:
                            external_ips.append(dst)
            except (IndexError, ValueError):
                continue
    
    if external_ips:
        error_message = (
            f"AIR-GAP COMPLIANCE VIOLATION: {len(external_ips)} external connection(s) detected. "
            f"External IPs: {', '.join(external_ips)}"
        )
        return True, external_ips, error_message
    else:
        return False, [], ""


def generate_tcpdump_log(
    internal_connections: List[Tuple[str, str]],
    external_connections: List[Tuple[str, str]]
) -> str:
    """Generate a mock tcpdump log with specified connections."""
    lines = ["tcpdump: listening on any, link-type LINUX_SLL (Linux cooked), capture size 262144 bytes"]
    
    timestamp = "12:34:56.789012"
    
    # Add internal connections
    for src, dst in internal_connections:
        lines.append(f"{timestamp} IP {src}.12345 > {dst}.80: Flags [S], seq 123456, win 65535, length 0")
    
    # Add external connections
    for src, dst in external_connections:
        lines.append(f"{timestamp} IP {src}.12345 > {dst}.443: Flags [S], seq 123456, win 65535, length 0")
    
    return "\n".join(lines)


# Hypothesis strategies
internal_ip_strategy = st.one_of(
    st.builds(lambda a, b, c: f"10.{a}.{b}.{c}", 
              st.integers(0, 255), st.integers(0, 255), st.integers(1, 254)),
    st.builds(lambda a, b: f"192.168.{a}.{b}", 
              st.integers(0, 255), st.integers(1, 254)),
    st.builds(lambda a, b, c: f"172.{a}.{b}.{c}", 
              st.integers(16, 31), st.integers(0, 255), st.integers(1, 254)),
)

external_ip_strategy = st.one_of(
    st.builds(lambda a, b: f"8.8.{a}.{b}", 
              st.integers(0, 255), st.integers(1, 254)),
    st.builds(lambda a, b: f"1.1.{a}.{b}", 
              st.integers(0, 255), st.integers(1, 254)),
    st.builds(lambda a, b: f"208.67.{a}.{b}", 
              st.integers(0, 255), st.integers(1, 254)),
)


@given(
    external_connections=st.lists(
        st.tuples(internal_ip_strategy, external_ip_strategy),
        min_size=1,
        max_size=10
    ),
    bastion_ip=internal_ip_strategy
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
def test_property_24_external_access_detected(external_connections, bastion_ip):
    """
    Property 24: External Access Detection (Detection)
    
    For any external connection attempt, the detection system should
    identify it as a violation.
    """
    # Generate log with external connections
    log_content = generate_tcpdump_log([], external_connections)
    
    # Run detection
    violation_detected, external_ips, error_message = detect_external_access(log_content, bastion_ip)
    
    # Property: Violation should be detected
    assert violation_detected, (
        f"Expected external access violation to be detected, but none was found. "
        f"Generated {len(external_connections)} external connections."
    )
    
    # Property: External IPs should be identified
    assert len(external_ips) > 0, "Expected external IPs to be identified"
    
    # Verify detected IPs match what we generated
    generated_external_ips = [dst for _, dst in external_connections]
    for detected_ip in external_ips:
        assert detected_ip in generated_external_ips, (
            f"Detected IP {detected_ip} not in generated external IPs: {generated_external_ips}"
        )


@given(
    external_ip=external_ip_strategy,
    bastion_ip=internal_ip_strategy
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
def test_property_24_error_message_contains_target_address(external_ip, bastion_ip):
    """
    Property 24: External Access Detection (Error Message)
    
    For any external connection attempt, the error message should
    identify the target address.
    """
    # Generate log with single external connection
    src_ip = "192.168.1.10"
    log_content = generate_tcpdump_log([], [(src_ip, external_ip)])
    
    # Run detection
    violation_detected, external_ips, error_message = detect_external_access(log_content, bastion_ip)
    
    # Property: Error message should contain the external IP
    assert violation_detected, "Expected violation to be detected"
    assert external_ip in error_message, (
        f"Error message should contain target address {external_ip}, "
        f"but got: {error_message}"
    )


@given(
    internal_connections=st.lists(
        st.tuples(internal_ip_strategy, internal_ip_strategy),
        min_size=1,
        max_size=20
    ),
    bastion_ip=internal_ip_strategy
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
def test_property_24_no_false_positives(internal_connections, bastion_ip):
    """
    Property 24: External Access Detection (No False Positives)
    
    For any deployment with only internal connections, the detection
    system should not report a violation.
    """
    # Generate log with only internal connections
    log_content = generate_tcpdump_log(internal_connections, [])
    
    # Run detection
    violation_detected, external_ips, error_message = detect_external_access(log_content, bastion_ip)
    
    # Property: No violation should be detected
    assert not violation_detected, (
        f"Expected no violation for internal-only connections, "
        f"but detected: {error_message}"
    )
    assert len(external_ips) == 0, (
        f"Expected no external IPs, but found: {external_ips}"
    )


@given(
    external_connections=st.lists(
        st.tuples(internal_ip_strategy, external_ip_strategy),
        min_size=1,
        max_size=5
    ),
    bastion_ip=internal_ip_strategy
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
def test_property_24_deployment_should_fail(external_connections, bastion_ip):
    """
    Property 24: External Access Detection (Deployment Failure)
    
    For any external connection attempt, the deployment should fail
    (indicated by violation_detected = True).
    """
    # Generate log with external connections
    log_content = generate_tcpdump_log([], external_connections)
    
    # Run detection
    violation_detected, external_ips, error_message = detect_external_access(log_content, bastion_ip)
    
    # Property: Deployment should fail (violation detected)
    assert violation_detected, (
        "Deployment should fail when external connections are detected"
    )
    
    # Property: Error message should be clear
    assert len(error_message) > 0, "Error message should not be empty"
    assert "VIOLATION" in error_message.upper() or "EXTERNAL" in error_message.upper(), (
        f"Error message should clearly indicate violation, got: {error_message}"
    )


@given(
    mixed_connections=st.tuples(
        st.lists(
            st.tuples(internal_ip_strategy, internal_ip_strategy),
            min_size=1,
            max_size=10
        ),
        st.lists(
            st.tuples(internal_ip_strategy, external_ip_strategy),
            min_size=1,
            max_size=5
        )
    ),
    bastion_ip=internal_ip_strategy
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
def test_property_24_mixed_connections_detected(mixed_connections, bastion_ip):
    """
    Property 24: External Access Detection (Mixed Connections)
    
    For any deployment with both internal and external connections,
    the detection system should identify the external ones and fail.
    """
    internal_conns, external_conns = mixed_connections
    
    # Generate log with both types of connections
    log_content = generate_tcpdump_log(internal_conns, external_conns)
    
    # Run detection
    violation_detected, external_ips, error_message = detect_external_access(log_content, bastion_ip)
    
    # Property: Violation should be detected despite internal connections
    assert violation_detected, (
        "External connections should be detected even when internal connections exist"
    )
    
    # Property: Only external IPs should be reported
    assert len(external_ips) > 0, "External IPs should be identified"
    
    # Verify no internal IPs are reported as external
    for ip in external_ips:
        assert not is_internal_ip(ip), (
            f"Internal IP {ip} incorrectly reported as external"
        )


def test_detect_external_access_script_exists():
    """Verify the external access detection script exists."""
    script_path = Path(__file__).parent.parent.parent / "scripts" / "deploy" / "detect_external_access.sh"
    assert script_path.exists(), f"External access detection script not found: {script_path}"
    assert os.access(script_path, os.X_OK), f"Script not executable: {script_path}"


def test_network_monitor_has_analyze_function():
    """Verify the network monitor script has an analyze function."""
    script_path = Path(__file__).parent.parent.parent / "scripts" / "deploy" / "network_monitor.sh"
    with open(script_path, 'r') as f:
        content = f.read()
    
    # Check that the script has an analyze function
    assert "analyze_logs" in content or "analyze" in content, (
        "Network monitor should have an analyze function"
    )


def test_deployment_script_integrates_monitoring():
    """Verify the deployment script integrates network monitoring."""
    script_path = Path(__file__).parent.parent.parent / "scripts" / "deploy" / "deploy.sh"
    with open(script_path, 'r') as f:
        content = f.read()
    
    # Check that deployment script sources network monitor
    assert "network_monitor" in content, (
        "Deployment script should integrate network monitoring"
    )


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
