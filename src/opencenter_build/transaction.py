"""Transaction and rollback support for multi-step operations.

This module provides transaction semantics with automatic rollback on failure.
Critical operations can register rollback actions that execute in reverse order
if an exception occurs.
"""

import logging
from contextlib import contextmanager
from typing import Callable, List, Optional, Generator

logger = logging.getLogger(__name__)


class Transaction:
    """Transaction with rollback support for multi-step operations.

    Rollback actions are executed in reverse order (LIFO) when an exception
    occurs or when explicitly requested. This ensures proper cleanup of
    partially completed operations.

    Example:
        tx = Transaction()
        tx.add_rollback(lambda: os.remove("temp.txt"))
        # ... perform operations ...
        tx.commit()  # Clear rollback actions on success
    """

    def __init__(self) -> None:
        """Initialize empty transaction."""
        self.rollback_actions: List[Callable[[], None]] = []
        self.committed = False

    def add_rollback(self, action: Callable[[], None]) -> None:
        """Add rollback action to be executed on failure.

        Actions are executed in reverse order (LIFO) during rollback.

        Args:
            action: Callable that performs rollback operation. Should not
                   raise exceptions, but if it does, the exception is logged
                   and rollback continues with remaining actions.
        """
        if self.committed:
            logger.warning("Adding rollback action to committed transaction has no effect")
            return

        self.rollback_actions.append(action)
        logger.debug(f"Added rollback action (total: {len(self.rollback_actions)})")

    def commit(self) -> None:
        """Commit transaction and clear rollback actions.

        After commit, no rollback actions will be executed even if an
        exception occurs later.
        """
        action_count = len(self.rollback_actions)
        self.rollback_actions.clear()
        self.committed = True
        logger.debug(f"Transaction committed, cleared {action_count} rollback actions")

    def rollback(self) -> None:
        """Execute all rollback actions in reverse order.

        Rollback actions are executed even if previous actions fail.
        Exceptions during rollback are logged but do not stop execution
        of remaining rollback actions.
        """
        if not self.rollback_actions:
            logger.debug("No rollback actions to execute")
            return

        action_count = len(self.rollback_actions)
        logger.info(f"Rolling back {action_count} actions")

        failed_actions = 0
        for i, action in enumerate(reversed(self.rollback_actions), 1):
            try:
                logger.debug(f"Executing rollback action {i}/{action_count}")
                action()
            except Exception as e:
                failed_actions += 1
                logger.error(f"Rollback action {i}/{action_count} failed: {e}", exc_info=True)

        self.rollback_actions.clear()

        if failed_actions > 0:
            logger.warning(f"Rollback completed with {failed_actions} failed actions")
        else:
            logger.info("Rollback completed successfully")


@contextmanager
def transactional_operation() -> Generator[Transaction, None, None]:
    """Context manager for transactional operations with automatic rollback.

    If an exception occurs within the context, all registered rollback
    actions are executed in reverse order before re-raising the exception.
    If the context completes successfully, rollback actions are cleared.

    Yields:
        Transaction: Transaction object for registering rollback actions

    Example:
        with transactional_operation() as tx:
            # Backup original file
            shutil.copy("config.yaml", "config.yaml.backup")
            tx.add_rollback(lambda: shutil.move("config.yaml.backup", "config.yaml"))

            # Modify file
            update_config("config.yaml")

            # If exception occurs, backup is restored automatically
    """
    tx = Transaction()
    try:
        logger.debug("Starting transactional operation")
        yield tx
        tx.commit()
        logger.debug("Transactional operation completed successfully")
    except Exception as e:
        logger.error(f"Transactional operation failed: {e}", exc_info=True)
        tx.rollback()
        raise
