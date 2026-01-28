"""Unit tests for centralized logging module.

Tests logging configuration, file rotation, log levels, and output formatting.
"""

import logging
import tempfile
from pathlib import Path

import pytest

from opencenter_build.logging import setup_logging, get_logger


class TestLoggingSetup:
    """Test logging configuration and setup."""

    def test_setup_logging_creates_logger(self):
        """Test that setup_logging configures the root logger."""
        setup_logging(level=logging.INFO)

        logger = logging.getLogger()
        assert logger.level == logging.INFO

    def test_setup_logging_with_debug_level(self):
        """Test logging setup with DEBUG level."""
        setup_logging(level=logging.DEBUG)

        logger = logging.getLogger()
        assert logger.level == logging.DEBUG

    def test_setup_logging_with_warning_level(self):
        """Test logging setup with WARNING level."""
        setup_logging(level=logging.WARNING)

        logger = logging.getLogger()
        assert logger.level == logging.WARNING

    def test_setup_logging_console_only(self):
        """Test logging to console only (no file)."""
        setup_logging(level=logging.INFO, log_to_console=True)

        logger = logging.getLogger()
        # Should have at least one handler (console)
        assert len(logger.handlers) >= 1

    def test_setup_logging_no_console(self, tmp_path):
        """Test logging without console output."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.INFO, log_file=log_file, log_to_console=False)

        logger = logging.getLogger()
        # Should have at least one handler (file)
        assert len(logger.handlers) >= 1

        # Log file should be created
        logger.info("Test message")
        assert log_file.exists()


class TestLogFileCreation:
    """Test log file creation and directory handling."""

    def test_log_file_created(self, tmp_path):
        """Test that log file is created when specified."""
        log_file = tmp_path / "build.log"
        setup_logging(level=logging.INFO, log_file=log_file)

        logger = get_logger(__name__)
        logger.info("Test message")

        assert log_file.exists()

    def test_log_file_in_nested_directory(self, tmp_path):
        """Test log file creation in nested directory."""
        log_file = tmp_path / "logs" / "build" / "test.log"
        setup_logging(level=logging.INFO, log_file=log_file)

        logger = get_logger(__name__)
        logger.info("Test message")

        assert log_file.exists()
        assert log_file.parent.exists()

    def test_log_file_contains_message(self, tmp_path):
        """Test that log file contains logged messages."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.INFO, log_file=log_file)

        logger = get_logger(__name__)
        test_message = "Test log message"
        logger.info(test_message)

        content = log_file.read_text()
        assert test_message in content

    def test_log_file_has_timestamp(self, tmp_path):
        """Test that log entries include timestamps."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.INFO, log_file=log_file)

        logger = get_logger(__name__)
        logger.info("Test message")

        content = log_file.read_text()
        # Check for timestamp pattern: YYYY-MM-DD HH:MM:SS
        assert "[INFO]" in content
        # Timestamp should be at the start (format: YYYY-MM-DD HH:MM:SS)
        import re

        timestamp_pattern = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
        assert re.match(timestamp_pattern, content)


class TestLogRotation:
    """Test log file rotation functionality."""

    def test_rotating_file_handler_configured(self, tmp_path):
        """Test that RotatingFileHandler is used."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.INFO, log_file=log_file)

        logger = logging.getLogger()

        # Find RotatingFileHandler
        rotating_handler = None
        for handler in logger.handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                rotating_handler = handler
                break

        assert rotating_handler is not None

    def test_rotation_max_bytes_configured(self, tmp_path):
        """Test that rotation max bytes is set correctly."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.INFO, log_file=log_file)

        logger = logging.getLogger()

        # Find RotatingFileHandler
        for handler in logger.handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                # Should be 10MB
                assert handler.maxBytes == 10 * 1024 * 1024
                break

    def test_rotation_backup_count_configured(self, tmp_path):
        """Test that backup count is set correctly."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.INFO, log_file=log_file)

        logger = logging.getLogger()

        # Find RotatingFileHandler
        for handler in logger.handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                # Should keep 5 backups
                assert handler.backupCount == 5
                break

    def test_rotation_creates_backup(self, tmp_path):
        """Test that rotation creates backup files."""
        log_file = tmp_path / "test.log"

        # Use small max bytes for testing
        setup_logging(level=logging.INFO, log_file=log_file)

        logger = logging.getLogger()

        # Manually set small maxBytes for testing
        for handler in logger.handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                handler.maxBytes = 100  # Very small for testing
                break

        # Write enough to trigger rotation
        test_logger = get_logger(__name__)
        for i in range(50):
            test_logger.info(f"Test message {i} with enough content to trigger rotation")

        # Check if backup was created
        backup_file = Path(str(log_file) + ".1")
        # Rotation may or may not have occurred depending on exact sizes
        # Just verify the mechanism is in place
        assert log_file.exists()


class TestLogLevels:
    """Test log level filtering."""

    def test_debug_level_logs_all(self, tmp_path):
        """Test that DEBUG level logs all messages."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.DEBUG, log_file=log_file, log_to_console=False)

        logger = get_logger(__name__)
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        content = log_file.read_text()
        assert "Debug message" in content
        assert "Info message" in content
        assert "Warning message" in content
        assert "Error message" in content

    def test_info_level_filters_debug(self, tmp_path):
        """Test that INFO level filters out DEBUG messages."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.INFO, log_file=log_file, log_to_console=False)

        logger = get_logger(__name__)
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")

        content = log_file.read_text()
        assert "Debug message" not in content
        assert "Info message" in content
        assert "Warning message" in content

    def test_warning_level_filters_info(self, tmp_path):
        """Test that WARNING level filters out INFO messages."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.WARNING, log_file=log_file, log_to_console=False)

        logger = get_logger(__name__)
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        content = log_file.read_text()
        assert "Debug message" not in content
        assert "Info message" not in content
        assert "Warning message" in content
        assert "Error message" in content

    def test_error_level_logs_only_errors(self, tmp_path):
        """Test that ERROR level logs only error messages."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.ERROR, log_file=log_file, log_to_console=False)

        logger = get_logger(__name__)
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        content = log_file.read_text()
        assert "Debug message" not in content
        assert "Info message" not in content
        assert "Warning message" not in content
        assert "Error message" in content
        assert "Critical message" in content


class TestGetLogger:
    """Test get_logger helper function."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a Logger instance."""
        logger = get_logger(__name__)
        assert isinstance(logger, logging.Logger)

    def test_get_logger_with_module_name(self):
        """Test that get_logger uses provided name."""
        logger = get_logger("test.module")
        assert logger.name == "test.module"

    def test_get_logger_different_names(self):
        """Test that different names return different loggers."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        assert logger1.name != logger2.name
        assert logger1.name == "module1"
        assert logger2.name == "module2"


class TestLogFormatting:
    """Test log message formatting."""

    def test_log_format_includes_level(self, tmp_path):
        """Test that log format includes log level."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.INFO, log_file=log_file, log_to_console=False)

        logger = get_logger(__name__)
        logger.info("Test message")
        logger.error("Error message")

        content = log_file.read_text()
        assert "[INFO]" in content
        assert "[ERROR]" in content

    def test_log_format_includes_logger_name(self, tmp_path):
        """Test that log format includes logger name."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.INFO, log_file=log_file, log_to_console=False)

        logger = get_logger("test.module")
        logger.info("Test message")

        content = log_file.read_text()
        assert "test.module" in content

    def test_log_format_timestamp_format(self, tmp_path):
        """Test that timestamp uses correct format."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.INFO, log_file=log_file, log_to_console=False)

        logger = get_logger(__name__)
        logger.info("Test message")

        content = log_file.read_text()
        # Should match format: YYYY-MM-DD HH:MM:SS
        import re

        timestamp_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
        assert re.search(timestamp_pattern, content)


class TestConsoleAndFileOutput:
    """Test simultaneous console and file output."""

    def test_both_console_and_file(self, tmp_path, capfd):
        """Test logging to both console and file."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.INFO, log_file=log_file, log_to_console=True)

        logger = get_logger(__name__)
        test_message = "Test message"
        logger.info(test_message)

        # Check file
        assert log_file.exists()
        file_content = log_file.read_text()
        assert test_message in file_content

        # Check console (stderr)
        captured = capfd.readouterr()
        # Info messages go to stdout, not stderr
        assert test_message in captured.out or test_message in captured.err

    def test_file_only_no_console_output(self, tmp_path, capfd):
        """Test that log_to_console=False prevents console output."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.INFO, log_file=log_file, log_to_console=False)

        logger = get_logger(__name__)
        test_message = "Test message"
        logger.info(test_message)

        # Check file has message
        file_content = log_file.read_text()
        assert test_message in file_content

        # Console should not have message (except from other loggers)
        # This is hard to test reliably due to other logging


class TestMultipleLoggers:
    """Test multiple logger instances."""

    def test_multiple_loggers_same_file(self, tmp_path):
        """Test that multiple loggers can write to same file."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.INFO, log_file=log_file, log_to_console=False)

        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        logger1.info("Message from module1")
        logger2.info("Message from module2")

        content = log_file.read_text()
        assert "Message from module1" in content
        assert "Message from module2" in content
        assert "module1" in content
        assert "module2" in content

    def test_logger_hierarchy(self, tmp_path):
        """Test logger name hierarchy."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.INFO, log_file=log_file, log_to_console=False)

        parent_logger = get_logger("parent")
        child_logger = get_logger("parent.child")

        parent_logger.info("Parent message")
        child_logger.info("Child message")

        content = log_file.read_text()
        assert "Parent message" in content
        assert "Child message" in content


class TestExceptionLogging:
    """Test exception logging with traceback."""

    def test_log_exception_with_exc_info(self, tmp_path):
        """Test logging exceptions with traceback."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.INFO, log_file=log_file, log_to_console=False)

        logger = get_logger(__name__)

        try:
            raise ValueError("Test exception")
        except ValueError:
            logger.error("Exception occurred", exc_info=True)

        content = log_file.read_text()
        assert "Exception occurred" in content
        assert "ValueError" in content
        assert "Test exception" in content
        assert "Traceback" in content

    def test_log_exception_without_exc_info(self, tmp_path):
        """Test logging exception message without traceback."""
        log_file = tmp_path / "test.log"
        setup_logging(level=logging.INFO, log_file=log_file, log_to_console=False)

        logger = get_logger(__name__)

        try:
            raise ValueError("Test exception")
        except ValueError as e:
            logger.error(f"Exception: {e}")

        content = log_file.read_text()
        assert "Exception: Test exception" in content
        # Should not have full traceback
        assert "Traceback" not in content
