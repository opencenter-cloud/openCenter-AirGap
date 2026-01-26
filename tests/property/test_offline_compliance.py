#!/usr/bin/env python3
"""
Property-Based Test: Offline Operation Compliance

Property 22: For any deployment execution, monitoring all network connections
should show zero outbound connections to external internet addresses (only
connections to bastion host and cluster nodes).

Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6
"""

import subprocess
import tempfile
import os
from pathlib import Path
from typing import List, Tuple
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

# Test configuration
MIN_EXAMPLES = 100
MAX_EXAMPLES = 200

# Internal IP ranges (RFC 1918)
INTERNAL_RANGES = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
]


def is_internal_ip(ip: str) -> bool:
    """Check if an IP address is in internal ranges."""
    # Simple check for common internal ranges
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


def parse_tcpdump_log(log_content: str, bastion_ip: str = "") -> Tuple[List[str], List[str]]:
    """
    Parse tcpdump log and extract internal and external connections.
    
    Returns:
        Tuple of (internal_ips, external_ips)
    """
    internal_ips = []
    external_ips = []
    
    for line in log_content.split("\n"):
        # Skip empty lines and tcpdump startup messages
        if not line or line.startswith("tcpdump:") or "listening on" in line:
            continue
        
        # Parse tcpdump output: IP src.port > dst.port
        # Example: 12:34:56.789012 IP 192.168.1.10.12345 > 8.8.8.8.53: Flags [S]
        if " IP " in line and " > " in line:
            try:
                # Extract IP addresses
                parts = line.split(" IP ")[1].split(" > ")
                if len(parts) >= 2:
                    src = parts[0].rsplit(".", 1)[0]  # Remove port
                    dst = parts[1].split(":")[0].rsplit(".", 1)[0]  # Remove port and flags
                    
                    # Check if destination is external
                    if dst and not is_internal_ip(dst) and dst != bastion_ip:
                        if dst not in external_ips:
                            external_ips.append(dst)
                    elif dst:
                        if dst not in internal_ips:
                            internal_ips.append(dst)
            except (IndexError, ValueError):
                # Skip malformed lines
                continue
    
    return internal_ips, external_ips


def generate_mock_tcpdump_log(
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


# Hypothesis strategies for generating test data
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
def test_property_22_no_external_connections_passes(internal_connections, bastion_ip):
    """
    Property 22: Offline Operation Compliance (Positive Case)
    
    For any deployment with only internal connections, the offline compliance
    check should pass (return 0 external connections).
    """
    # Generate mock log with only internal connections
    log_content = generate_mock_tcpdump_log(internal_connections, [])
    
    # Parse the log
    internal_ips, external_ips = parse_tcpdump_log(log_content, bastion_ip)
    
    # Property: No external connections should be detected
    assert len(external_ips) == 0, (
        f"Expected no external connections, but found {len(external_ips)}: {external_ips}"
    )
    
    # Additional check: Internal connections should be detected
    assert len(internal_ips) > 0, "Expected internal connections to be detected"


@given(
    internal_connections=st.lists(
        st.tuples(internal_ip_strategy, internal_ip_strategy),
        min_size=0,
        max_size=10
    ),
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
def test_property_22_external_connections_detected(
    internal_connections, external_connections, bastion_ip
):
    """
    Property 22: Offline Operation Compliance (Negative Case)
    
    For any deployment with external connections, the offline compliance
    check should detect them and report a violation.
    """
    # Generate mock log with both internal and external connections
    log_content = generate_mock_tcpdump_log(internal_connections, external_connections)
    
    # Parse the log
    internal_ips, external_ips = parse_tcpdump_log(log_content, bastion_ip)
    
    # Property: External connections should be detected
    assert len(external_ips) > 0, (
        f"Expected external connections to be detected, but found none. "
        f"Generated {len(external_connections)} external connections."
    )
    
    # Verify the detected external IPs match what we generated
    generated_external_ips = [dst for _, dst in external_connections]
    for detected_ip in external_ips:
        assert detected_ip in generated_external_ips, (
            f"Detected IP {detected_ip} not in generated external IPs: {generated_external_ips}"
        )


@given(
    bastion_ip=internal_ip_strategy,
    connections_to_bastion=st.lists(
        st.tuples(internal_ip_strategy, st.just("BASTION")),
        min_size=1,
        max_size=10
    )
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
def test_property_22_bastion_connections_excluded(bastion_ip, connections_to_bastion):
    """
    Property 22: Offline Operation Compliance (Bastion Exclusion)
    
    For any deployment, connections to the bastion host should not be
    counted as external connections.
    """
    # Replace "BASTION" placeholder with actual bastion IP
    connections = [(src, bastion_ip) for src, _ in connections_to_bastion]
    
    # Generate mock log with connections to bastion
    log_content = generate_mock_tcpdump_log(connections, [])
    
    # Parse the log
    internal_ips, external_ips = parse_tcpdump_log(log_content, bastion_ip)
    
    # Property: Bastion connections should not be counted as external
    assert len(external_ips) == 0, (
        f"Expected no external connections (bastion should be excluded), "
        f"but found {len(external_ips)}: {external_ips}"
    )


def test_network_monitor_script_exists():
    """Verify the network monitor script exists and is executable."""
    script_path = Path(__file__).parent.parent.parent / "scripts" / "deploy" / "network_monitor.sh"
    assert script_path.exists(), f"Network monitor script not found: {script_path}"
    assert os.access(script_path, os.X_OK), f"Network monitor script not executable: {script_path}"


def test_detect_external_access_script_exists():
    """Verify the external access detection script exists and is executable."""
    script_path = Path(__file__).parent.parent.parent / "scripts" / "deploy" / "detect_external_access.sh"
    assert script_path.exists(), f"External access detection script not found: {script_path}"
    assert os.access(script_path, os.X_OK), f"External access detection script not executable: {script_path}"


@pytest.mark.integration
def test_network_monitor_help():
    """Test that network monitor script shows help."""
    script_path = Path(__file__).parent.parent.parent / "scripts" / "deploy" / "network_monitor.sh"
    result = subprocess.run(
        [str(script_path)],
        capture_output=True,
        text=True
    )
    assert "Usage:" in result.stdout or "Usage:" in result.stderr
    assert "start" in result.stdout or "start" in result.stderr
    assert "stop" in result.stdout or "stop" in result.stderr
    assert "analyze" in result.stdout or "analyze" in result.stderr


@pytest.mark.integration
def test_detect_external_access_help():
    """Test that external access detection script shows help."""
    script_path = Path(__file__).parent.parent.parent / "scripts" / "deploy" / "detect_external_access.sh"
    result = subprocess.run(
        [str(script_path), "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "LOG_FILE" in result.stdout


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
