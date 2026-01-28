"""Centralized logging configuration for openCenter build operations.

This module provides structured logging with consistent formatting across
all build scripts. Logs are written to both console and rotating files.
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    log_to_console: bool = True,
) -> None:
    """Configure logging for build operations.

    Sets up logging handlers with consistent formatting. Supports both
    console output and file logging with automatic rotation.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output. If provided, enables
            rotating file handler with 10MB max size and 5 backups.
        log_to_console: Whether to log to stderr. Default True.

    Example:
        >>> from pathlib import Path
        >>> setup_logging(
        ...     level=logging.DEBUG,
        ...     log_file=Path("build/build.log")
        ... )
    """
    handlers: list[logging.Handler] = []

    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        handlers.append(console_handler)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
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
