"""Centralized logging configuration for openCenter build operations.

This module provides structured logging with consistent formatting across
all build scripts. Logs are written to both console and rotating files.
Supports JSON format output with trace_id propagation.
"""

import json
import logging
import logging.handlers
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

# Context variable for trace_id propagation across async boundaries
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


class JSONFormatter(logging.Formatter):
    """JSON log formatter with trace_id support.

    Formats log records as JSON with timestamp, level, message, and trace_id.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "trace_id": trace_id_var.get() or "none",
            "logger": record.name,
        }

        # Include exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    log_to_console: bool = True,
    json_format: bool = False,
) -> None:
    """Configure logging for build operations.

    Sets up logging handlers with consistent formatting. Supports both
    console output and file logging with automatic rotation. Can output
    in JSON format for structured logging.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output. If provided, enables
            rotating file handler with 10MB max size and 5 backups.
        log_to_console: Whether to log to stderr. Default True.
        json_format: Whether to output logs in JSON format. Default False.

    Example:
        >>> from pathlib import Path
        >>> setup_logging(
        ...     level=logging.DEBUG,
        ...     log_file=Path("build/build.log"),
        ...     json_format=True
        ... )
    """
    handlers: list[logging.Handler] = []

    # Choose formatter based on json_format flag
    formatter: logging.Formatter | JSONFormatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    logging.basicConfig(level=level, handlers=handlers, force=True)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance for a module.

    Args:
        name: Logger name, typically __name__ from the calling module

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Starting asset collection")
    """
    return logging.getLogger(name)


def set_trace_id(trace_id: Optional[str] = None) -> str:
    """Set trace_id for current context.

    Args:
        trace_id: Optional trace ID. If not provided, generates a new UUID.

    Returns:
        The trace_id that was set

    Example:
        >>> trace_id = set_trace_id()
        >>> logger.info("Operation started")  # Will include trace_id
    """
    if trace_id is None:
        trace_id = str(uuid4())
    trace_id_var.set(trace_id)
    return trace_id


def get_trace_id() -> str:
    """Get current trace_id from context.

    Returns:
        Current trace_id or empty string if not set
    """
    return trace_id_var.get()
