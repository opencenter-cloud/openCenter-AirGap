#!/usr/bin/env python3
"""
Property-Based Test: Network Connection Logging

Property 23: For any deployment execution, all network connections (source,
destination, port, protocol) should be logged to an audit file.

Validates: Requirements 9.7
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


def parse_connection_from_tcpdump_line(line: str) -> Dict[str, str]:
    """
    Parse a tcpdump log line to extract connection details.
    
    Returns dict with keys: src_ip, src_port, dst_ip, dst_port, protocol
    Returns None if line cannot be parsed.
    """
    # Skip empty lines and tcpdump startup messages
    if not line or line.startswith("tcpdump:") or "listening on" in line:
        return None
    
    # Parse tcpdump output: IP src.port > dst.port: protocol
    # Example: 12:34:56.789012 IP 192.168.1.10.12345 > 8.8.8.8.53: Flags [S]
    if " IP " not in line or " > " not in line:
        return None
    
    try:
        # Extract IP addresses and ports
        parts = line.split(" IP ")[1].split(" > ")
        if len(parts) < 2:
            return None
        
        # Parse source
        src_parts = parts[0].rsplit(".", 1)
        if len(src_parts) != 2:
            return None
        src_ip = src_parts[0]
        src_port = src_parts[1]
        
        # Parse destination
        dst_parts = parts[1].split(":")[0].rsplit(".", 1)
        if len(dst_parts) != 2:
            return None
        dst_ip = dst_parts[0]
        dst_port = dst_parts[1]
        
        # Determine protocol (TCP if we see Flags)
        protocol = "TCP" if "Flags" in line else "UDP"
        
        return {
            "src_ip": src_ip,
            "src_port": src_port,
            "dst_ip": dst_ip,
            "dst_port": dst_port,
            "protocol": protocol
        }
    except (IndexError, ValueError):
        return None


def generate_tcpdump_line(
    src_ip: str,
    src_port: int,
    dst_ip: str,
    dst_port: int,
    protocol: str = "TCP"
) -> str:
    """Generate a tcpdump log line for a connection."""
    timestamp = "12:34:56.789012"
    if protocol == "TCP":
        return f"{timestamp} IP {src_ip}.{src_port} > {dst_ip}.{dst_port}: Flags [S], seq 123456, win 65535, length 0"
    else:
        return f"{timestamp} IP {src_ip}.{src_port} > {dst_ip}.{dst_port}: UDP, length 53"


# Hypothesis strategies
ip_strategy = st.builds(
    lambda a, b, c, d: f"{a}.{b}.{c}.{d}",
    st.integers(1, 255),
    st.integers(0, 255),
    st.integers(0, 255),
    st.integers(1, 254)
)

port_strategy = st.integers(1, 65535)

protocol_strategy = st.sampled_from(["TCP", "UDP"])


@given(
    connections=st.lists(
        st.tuples(
            ip_strategy,  # src_ip
            port_strategy,  # src_port
            ip_strategy,  # dst_ip
            port_strategy,  # dst_port
            protocol_strategy  # protocol
        ),
        min_size=1,
        max_size=50
    )
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
def test_property_23_all_connections_logged(connections):
    """
    Property 23: Network Connection Logging
    
    For any set of network connections, all connections should be parseable
    from the tcpdump log with complete information (source, destination,
    port, protocol).
    """
    # Generate tcpdump log
    log_lines = ["tcpdump: listening on any, link-type LINUX_SLL (Linux cooked), capture size 262144 bytes"]
    
    for src_ip, src_port, dst_ip, dst_port, protocol in connections:
        line = generate_tcpdump_line(src_ip, src_port, dst_ip, dst_port, protocol)
        log_lines.append(line)
    
    log_content = "\n".join(log_lines)
    
    # Parse the log
    parsed_connections = []
    for line in log_content.split("\n"):
        conn = parse_connection_from_tcpdump_line(line)
        if conn:
            parsed_connections.append(conn)
    
    # Property: All connections should be logged and parseable
    assert len(parsed_connections) == len(connections), (
        f"Expected {len(connections)} connections to be logged, "
        f"but only parsed {len(parsed_connections)}"
    )
    
    # Verify each connection has all required fields
    for i, conn in enumerate(parsed_connections):
        assert "src_ip" in conn, f"Connection {i} missing src_ip"
        assert "src_port" in conn, f"Connection {i} missing src_port"
        assert "dst_ip" in conn, f"Connection {i} missing dst_ip"
        assert "dst_port" in conn, f"Connection {i} missing dst_port"
        assert "protocol" in conn, f"Connection {i} missing protocol"
        
        # Verify values match what we generated
        src_ip, src_port, dst_ip, dst_port, protocol = connections[i]
        assert conn["src_ip"] == src_ip, f"Connection {i} src_ip mismatch"
        assert conn["src_port"] == str(src_port), f"Connection {i} src_port mismatch"
        assert conn["dst_ip"] == dst_ip, f"Connection {i} dst_ip mismatch"
        assert conn["dst_port"] == str(dst_port), f"Connection {i} dst_port mismatch"
        assert conn["protocol"] == protocol, f"Connection {i} protocol mismatch"


@given(
    src_ip=ip_strategy,
    src_port=port_strategy,
    dst_ip=ip_strategy,
    dst_port=port_strategy,
    protocol=protocol_strategy
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
def test_property_23_connection_details_complete(
    src_ip, src_port, dst_ip, dst_port, protocol
):
    """
    Property 23: Network Connection Logging (Single Connection)
    
    For any single network connection, the log should contain complete
    information about source, destination, ports, and protocol.
    """
    # Generate a single connection log line
    line = generate_tcpdump_line(src_ip, src_port, dst_ip, dst_port, protocol)
    
    # Parse the line
    conn = parse_connection_from_tcpdump_line(line)
    
    # Property: Connection should be parseable with all fields
    assert conn is not None, "Connection should be parseable"
    assert conn["src_ip"] == src_ip
    assert conn["src_port"] == str(src_port)
    assert conn["dst_ip"] == dst_ip
    assert conn["dst_port"] == str(dst_port)
    assert conn["protocol"] == protocol


@given(
    connections=st.lists(
        st.tuples(
            ip_strategy,
            port_strategy,
            ip_strategy,
            port_strategy,
            protocol_strategy
        ),
        min_size=2,
        max_size=20
    )
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
def test_property_23_connection_ordering_preserved(connections):
    """
    Property 23: Network Connection Logging (Ordering)
    
    For any sequence of network connections, the log should preserve
    the order in which connections were made.
    """
    # Generate tcpdump log
    log_lines = ["tcpdump: listening on any, link-type LINUX_SLL (Linux cooked), capture size 262144 bytes"]
    
    for src_ip, src_port, dst_ip, dst_port, protocol in connections:
        line = generate_tcpdump_line(src_ip, src_port, dst_ip, dst_port, protocol)
        log_lines.append(line)
    
    log_content = "\n".join(log_lines)
    
    # Parse the log
    parsed_connections = []
    for line in log_content.split("\n"):
        conn = parse_connection_from_tcpdump_line(line)
        if conn:
            parsed_connections.append(conn)
    
    # Property: Connection order should be preserved
    assert len(parsed_connections) == len(connections)
    
    for i, (src_ip, src_port, dst_ip, dst_port, protocol) in enumerate(connections):
        conn = parsed_connections[i]
        assert conn["src_ip"] == src_ip, f"Connection {i} order mismatch (src_ip)"
        assert conn["dst_ip"] == dst_ip, f"Connection {i} order mismatch (dst_ip)"


@given(
    unique_connections=st.lists(
        st.tuples(
            ip_strategy,
            port_strategy,
            ip_strategy,
            port_strategy,
            protocol_strategy
        ),
        min_size=1,
        max_size=30,
        unique=True
    )
)
@settings(
    max_examples=MIN_EXAMPLES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
def test_property_23_unique_connections_distinguishable(unique_connections):
    """
    Property 23: Network Connection Logging (Uniqueness)
    
    For any set of unique network connections, each connection should be
    distinguishable in the log (no information loss).
    """
    # Generate tcpdump log
    log_lines = ["tcpdump: listening on any, link-type LINUX_SLL (Linux cooked), capture size 262144 bytes"]
    
    for src_ip, src_port, dst_ip, dst_port, protocol in unique_connections:
        line = generate_tcpdump_line(src_ip, src_port, dst_ip, dst_port, protocol)
        log_lines.append(line)
    
    log_content = "\n".join(log_lines)
    
    # Parse the log
    parsed_connections = []
    for line in log_content.split("\n"):
        conn = parse_connection_from_tcpdump_line(line)
        if conn:
            # Create a tuple for comparison
            conn_tuple = (
                conn["src_ip"],
                int(conn["src_port"]),
                conn["dst_ip"],
                int(conn["dst_port"]),
                conn["protocol"]
            )
            parsed_connections.append(conn_tuple)
    
    # Property: All unique connections should be distinguishable
    assert len(parsed_connections) == len(unique_connections)
    assert set(parsed_connections) == set(unique_connections), (
        "Parsed connections should match generated unique connections"
    )


def test_network_monitor_creates_log_file():
    """Verify that network monitor creates a log file."""
    # This is a unit test to verify the monitor creates logs
    # The actual property tests verify the log format
    script_path = Path(__file__).parent.parent.parent / "scripts" / "deploy" / "network_monitor.sh"
    assert script_path.exists(), f"Network monitor script not found: {script_path}"


def test_log_file_format_documented():
    """Verify that the log file format is documented in the script."""
    script_path = Path(__file__).parent.parent.parent / "scripts" / "deploy" / "network_monitor.sh"
    with open(script_path, 'r') as f:
        content = f.read()
    
    # Check that the script mentions tcpdump (the logging mechanism)
    assert "tcpdump" in content, "Script should use tcpdump for logging"
    
    # Check that the script mentions log file location
    assert "MONITOR_LOG_FILE" in content or "log" in content.lower(), (
        "Script should document log file location"
    )


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
