"""Property-based tests for structured logging.

Tests Property 12: JSON Log Structure
Validates: Requirements 7.2
"""

import json
import logging
from io import StringIO

from hypothesis import given, strategies as st

from opencenter_build.logging import (
    JSONFormatter,
    setup_logging,
    set_trace_id,
    get_trace_id,
)


@given(
    message=st.text(min_size=1, max_size=200),
    level=st.sampled_from(
        [
            logging.DEBUG,
            logging.INFO,
            logging.WARNING,
            logging.ERROR,
            logging.CRITICAL,
        ]
    ),
    trace_id=st.one_of(st.none(), st.uuids().map(str)),
)
def test_json_log_structure_property(message: str, level: int, trace_id: str | None):
    """Property 12: JSON Log Structure.

    **Validates: Requirements 7.2**

    For any log entry in JSON format, it should contain all required fields:
    timestamp, level, message, and trace_id.
    """
    # Set trace_id if provided
    if trace_id:
        set_trace_id(trace_id)
    else:
        set_trace_id("test-trace")

    # Create a log record
    logger = logging.getLogger("test_logger")
    record = logger.makeRecord(
        name="test_logger",
        level=level,
        fn="test.py",
        lno=1,
        msg=message,
        args=(),
        exc_info=None,
    )

    # Format with JSONFormatter
    formatter = JSONFormatter()
    formatted = formatter.format(record)

    # Parse JSON
    log_data = json.loads(formatted)

    # Verify all required fields are present
    assert "timestamp" in log_data, "JSON log must contain timestamp"
    assert "level" in log_data, "JSON log must contain level"
    assert "message" in log_data, "JSON log must contain message"
    assert "trace_id" in log_data, "JSON log must contain trace_id"

    # Verify field values
    assert log_data["level"] == logging.getLevelName(level)
    assert log_data["message"] == message
    assert log_data["trace_id"] == (trace_id or "test-trace")

    # Verify timestamp is ISO format
    from datetime import datetime

    datetime.fromisoformat(log_data["timestamp"])  # Should not raise


@given(
    messages=st.lists(st.text(min_size=1, max_size=100), min_size=1, max_size=10),
)
def test_trace_id_propagation_property(messages: list[str]):
    """Property: Trace ID propagates across log entries in same context.

    **Validates: Requirements 7.2**

    For any sequence of log entries with a set trace_id, all entries
    should contain the same trace_id.
    """
    # Set a trace_id
    trace_id = set_trace_id()

    # Create multiple log records
    logger = logging.getLogger("test_logger")
    formatter = JSONFormatter()

    parsed_logs = []
    for message in messages:
        record = logger.makeRecord(
            name="test_logger",
            level=logging.INFO,
            fn="test.py",
            lno=1,
            msg=message,
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)
        parsed_logs.append(json.loads(formatted))

    # All logs should have the same trace_id
    trace_ids = [log["trace_id"] for log in parsed_logs]
    assert all(
        tid == trace_id for tid in trace_ids
    ), "All log entries in same context must have same trace_id"


@given(
    message=st.text(min_size=1, max_size=200),
)
def test_json_format_valid_json_property(message: str):
    """Property: JSON formatter always produces valid JSON.

    **Validates: Requirements 7.2**

    For any log message, the JSON formatter should produce valid JSON
    that can be parsed without errors.
    """
    set_trace_id("test-trace")

    logger = logging.getLogger("test_logger")
    record = logger.makeRecord(
        name="test_logger",
        level=logging.INFO,
        fn="test.py",
        lno=1,
        msg=message,
        args=(),
        exc_info=None,
    )

    formatter = JSONFormatter()
    formatted = formatter.format(record)

    # Should parse without error
    log_data = json.loads(formatted)

    # Should be a dictionary
    assert isinstance(log_data, dict), "JSON log must be a dictionary"

    # Should contain at least the required fields
    required_fields = {"timestamp", "level", "message", "trace_id"}
    assert required_fields.issubset(
        log_data.keys()
    ), f"JSON log must contain all required fields: {required_fields}"
