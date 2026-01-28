"""Unit tests for transaction and rollback functionality."""

import logging
from unittest.mock import Mock, call

import pytest

from opencenter_build.transaction import Transaction, transactional_operation


class TestTransaction:
    """Test Transaction class."""

    def test_add_rollback_action(self):
        """Test adding rollback actions."""
        tx = Transaction()
        action = Mock()

        tx.add_rollback(action)

        assert len(tx.rollback_actions) == 1
        assert tx.rollback_actions[0] == action

    def test_add_multiple_rollback_actions(self):
        """Test adding multiple rollback actions."""
        tx = Transaction()
        action1 = Mock()
        action2 = Mock()
        action3 = Mock()

        tx.add_rollback(action1)
        tx.add_rollback(action2)
        tx.add_rollback(action3)

        assert len(tx.rollback_actions) == 3
        assert tx.rollback_actions == [action1, action2, action3]

    def test_commit_clears_rollback_actions(self):
        """Test that commit clears all rollback actions."""
        tx = Transaction()
        action1 = Mock()
        action2 = Mock()

        tx.add_rollback(action1)
        tx.add_rollback(action2)
        tx.commit()

        assert len(tx.rollback_actions) == 0
        assert tx.committed is True

    def test_rollback_executes_actions_in_reverse_order(self):
        """Test that rollback executes actions in LIFO order."""
        tx = Transaction()
        execution_order = []

        tx.add_rollback(lambda: execution_order.append(1))
        tx.add_rollback(lambda: execution_order.append(2))
        tx.add_rollback(lambda: execution_order.append(3))

        tx.rollback()

        assert execution_order == [3, 2, 1]

    def test_rollback_clears_actions_after_execution(self):
        """Test that rollback clears actions after execution."""
        tx = Transaction()
        action = Mock()

        tx.add_rollback(action)
        tx.rollback()

        assert len(tx.rollback_actions) == 0
        action.assert_called_once()

    def test_rollback_continues_on_action_failure(self):
        """Test that rollback continues even if an action fails."""
        tx = Transaction()
        action1 = Mock()
        action2 = Mock(side_effect=Exception("Rollback failed"))
        action3 = Mock()

        tx.add_rollback(action1)
        tx.add_rollback(action2)
        tx.add_rollback(action3)

        # Should not raise exception
        tx.rollback()

        # All actions should be attempted
        action1.assert_called_once()
        action2.assert_called_once()
        action3.assert_called_once()

    def test_rollback_with_no_actions(self):
        """Test rollback with no registered actions."""
        tx = Transaction()

        # Should not raise exception
        tx.rollback()

        assert len(tx.rollback_actions) == 0

    def test_add_rollback_after_commit_has_no_effect(self):
        """Test that adding rollback after commit has no effect."""
        tx = Transaction()
        action = Mock()

        tx.commit()
        tx.add_rollback(action)

        assert len(tx.rollback_actions) == 0


class TestTransactionalOperation:
    """Test transactional_operation context manager."""

    def test_successful_operation_commits_transaction(self):
        """Test that successful operation commits and clears rollback actions."""
        action = Mock()

        with transactional_operation() as tx:
            tx.add_rollback(action)

        # Action should not be called on success
        action.assert_not_called()

    def test_exception_triggers_rollback(self):
        """Test that exception triggers rollback of all actions."""
        action1 = Mock()
        action2 = Mock()

        with pytest.raises(ValueError):
            with transactional_operation() as tx:
                tx.add_rollback(action1)
                tx.add_rollback(action2)
                raise ValueError("Operation failed")

        # Actions should be called in reverse order
        action1.assert_called_once()
        action2.assert_called_once()

    def test_rollback_executes_in_reverse_order_on_exception(self):
        """Test that rollback executes in LIFO order on exception."""
        execution_order = []

        with pytest.raises(RuntimeError):
            with transactional_operation() as tx:
                tx.add_rollback(lambda: execution_order.append(1))
                tx.add_rollback(lambda: execution_order.append(2))
                tx.add_rollback(lambda: execution_order.append(3))
                raise RuntimeError("Test exception")

        assert execution_order == [3, 2, 1]

    def test_exception_is_reraised_after_rollback(self):
        """Test that original exception is re-raised after rollback."""
        action = Mock()

        with pytest.raises(ValueError, match="Original error"):
            with transactional_operation() as tx:
                tx.add_rollback(action)
                raise ValueError("Original error")

        action.assert_called_once()

    def test_rollback_failure_does_not_suppress_original_exception(self):
        """Test that rollback failure does not suppress original exception."""
        failing_action = Mock(side_effect=Exception("Rollback failed"))

        with pytest.raises(ValueError, match="Original error"):
            with transactional_operation() as tx:
                tx.add_rollback(failing_action)
                raise ValueError("Original error")

        failing_action.assert_called_once()

    def test_multiple_rollback_actions_with_failures(self):
        """Test multiple rollback actions where some fail."""
        action1 = Mock()
        action2 = Mock(side_effect=Exception("Action 2 failed"))
        action3 = Mock()
        action4 = Mock(side_effect=Exception("Action 4 failed"))

        with pytest.raises(RuntimeError):
            with transactional_operation() as tx:
                tx.add_rollback(action1)
                tx.add_rollback(action2)
                tx.add_rollback(action3)
                tx.add_rollback(action4)
                raise RuntimeError("Operation failed")

        # All actions should be attempted despite failures
        action1.assert_called_once()
        action2.assert_called_once()
        action3.assert_called_once()
        action4.assert_called_once()

    def test_nested_transactions_not_supported(self):
        """Test that nested transactions work independently."""
        outer_action = Mock()
        inner_action = Mock()

        with pytest.raises(ValueError):
            with transactional_operation() as outer_tx:
                outer_tx.add_rollback(outer_action)

                with pytest.raises(RuntimeError):
                    with transactional_operation() as inner_tx:
                        inner_tx.add_rollback(inner_action)
                        raise RuntimeError("Inner failure")

                # Inner rollback should have executed
                inner_action.assert_called_once()

                # Outer should not have rolled back yet
                outer_action.assert_not_called()

                raise ValueError("Outer failure")

        # Now outer should have rolled back
        outer_action.assert_called_once()


class TestTransactionLogging:
    """Test transaction logging behavior."""

    def test_rollback_logs_actions(self, caplog):
        """Test that rollback logs action execution."""
        tx = Transaction()
        action = Mock()

        with caplog.at_level(logging.DEBUG):
            tx.add_rollback(action)
            tx.rollback()

        assert "rollback action" in caplog.text.lower()

    def test_rollback_logs_failures(self, caplog):
        """Test that rollback logs action failures."""
        tx = Transaction()
        failing_action = Mock(side_effect=Exception("Test failure"))

        with caplog.at_level(logging.ERROR):
            tx.add_rollback(failing_action)
            tx.rollback()

        assert "rollback action" in caplog.text.lower()
        assert "failed" in caplog.text.lower()

    def test_commit_logs_action_count(self, caplog):
        """Test that commit logs number of cleared actions."""
        tx = Transaction()

        with caplog.at_level(logging.DEBUG):
            tx.add_rollback(Mock())
            tx.add_rollback(Mock())
            tx.commit()

        assert "committed" in caplog.text.lower()
        assert "2" in caplog.text
