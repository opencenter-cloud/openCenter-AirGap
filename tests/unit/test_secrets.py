"""Unit tests for secrets management."""

import os
import stat
from pathlib import Path

import pytest

from opencenter_build.exceptions import SecretsError
from opencenter_build.secrets import SecretsManager


@pytest.fixture
def secrets_dir(tmp_path: Path) -> Path:
    """Create temporary secrets directory."""
    secrets_path = tmp_path / ".secrets"
    secrets_path.mkdir(mode=0o700)
    return secrets_path


@pytest.fixture
def secrets_manager(secrets_dir: Path) -> SecretsManager:
    """Create SecretsManager instance."""
    return SecretsManager(secrets_dir)


class TestSecretsManager:
    """Test SecretsManager class."""

    def test_set_secret_creates_file(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that set_secret creates a file."""
        secrets_manager.set_secret("test-secret", "test_value")

        secret_file = secrets_dir / "test-secret"
        assert secret_file.exists()
        assert secret_file.read_text() == "test_value"

    def test_set_secret_enforces_permissions(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that set_secret sets 0600 permissions."""
        secrets_manager.set_secret("test-secret", "test_value")

        secret_file = secrets_dir / "test-secret"
        file_mode = stat.S_IMODE(secret_file.stat().st_mode)
        assert file_mode == 0o600

    def test_set_secret_creates_directory(self, tmp_path: Path) -> None:
        """Test that set_secret creates secrets directory if missing."""
        secrets_dir = tmp_path / ".secrets"
        secrets_manager = SecretsManager(secrets_dir)

        secrets_manager.set_secret("test-secret", "test_value")

        assert secrets_dir.exists()
        dir_mode = stat.S_IMODE(secrets_dir.stat().st_mode)
        assert dir_mode == 0o700

    def test_set_secret_overwrites_existing(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that set_secret overwrites existing secret."""
        secrets_manager.set_secret("test-secret", "old_value")
        secrets_manager.set_secret("test-secret", "new_value")

        secret_file = secrets_dir / "test-secret"
        assert secret_file.read_text() == "new_value"

    def test_get_secret_reads_file(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that get_secret reads secret value."""
        secret_file = secrets_dir / "test-secret"
        secret_file.write_text("test_value")
        secret_file.chmod(0o600)

        value = secrets_manager.get_secret("test-secret")
        assert value == "test_value"

    def test_get_secret_strips_whitespace(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that get_secret strips leading/trailing whitespace."""
        secret_file = secrets_dir / "test-secret"
        secret_file.write_text("  test_value\n")
        secret_file.chmod(0o600)

        value = secrets_manager.get_secret("test-secret")
        assert value == "test_value"

    def test_get_secret_raises_on_missing_file(self, secrets_manager: SecretsManager) -> None:
        """Test that get_secret raises error for missing file."""
        with pytest.raises(SecretsError) as exc_info:
            secrets_manager.get_secret("nonexistent")

        assert "Secret not found" in str(exc_info.value)
        assert "nonexistent" in str(exc_info.value)

    def test_get_secret_raises_on_empty_file(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that get_secret raises error for empty file."""
        secret_file = secrets_dir / "empty-secret"
        secret_file.write_text("")
        secret_file.chmod(0o600)

        with pytest.raises(SecretsError) as exc_info:
            secrets_manager.get_secret("empty-secret")

        assert "empty" in str(exc_info.value).lower()

    def test_get_secret_raises_on_whitespace_only(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that get_secret raises error for whitespace-only file."""
        secret_file = secrets_dir / "whitespace-secret"
        secret_file.write_text("   \n\t  ")
        secret_file.chmod(0o600)

        with pytest.raises(SecretsError) as exc_info:
            secrets_manager.get_secret("whitespace-secret")

        assert "empty" in str(exc_info.value).lower()

    def test_get_secret_raises_on_insecure_permissions(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that get_secret raises error for insecure permissions."""
        secret_file = secrets_dir / "insecure-secret"
        secret_file.write_text("test_value")
        secret_file.chmod(0o644)  # World-readable

        with pytest.raises(SecretsError) as exc_info:
            secrets_manager.get_secret("insecure-secret")

        error_msg = str(exc_info.value)
        assert "Insecure permissions" in error_msg
        assert "0o644" in error_msg
        assert "chmod 600" in error_msg

    def test_get_secret_raises_on_group_readable(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that get_secret raises error for group-readable file."""
        secret_file = secrets_dir / "group-readable"
        secret_file.write_text("test_value")
        secret_file.chmod(0o640)  # Group-readable

        with pytest.raises(SecretsError) as exc_info:
            secrets_manager.get_secret("group-readable")

        assert "Insecure permissions" in str(exc_info.value)

    def test_get_secret_raises_on_world_readable(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that get_secret raises error for world-readable file."""
        secret_file = secrets_dir / "world-readable"
        secret_file.write_text("test_value")
        secret_file.chmod(0o604)  # World-readable

        with pytest.raises(SecretsError) as exc_info:
            secrets_manager.get_secret("world-readable")

        assert "Insecure permissions" in str(exc_info.value)

    def test_secret_exists_returns_true_for_existing(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that secret_exists returns True for existing secret."""
        secret_file = secrets_dir / "existing-secret"
        secret_file.write_text("test_value")

        assert secrets_manager.secret_exists("existing-secret")

    def test_secret_exists_returns_false_for_missing(self, secrets_manager: SecretsManager) -> None:
        """Test that secret_exists returns False for missing secret."""
        assert not secrets_manager.secret_exists("nonexistent")

    def test_delete_secret_removes_file(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that delete_secret removes the file."""
        secret_file = secrets_dir / "to-delete"
        secret_file.write_text("test_value")

        secrets_manager.delete_secret("to-delete")

        assert not secret_file.exists()

    def test_delete_secret_raises_on_missing(self, secrets_manager: SecretsManager) -> None:
        """Test that delete_secret raises error for missing file."""
        with pytest.raises(SecretsError) as exc_info:
            secrets_manager.delete_secret("nonexistent")

        assert "Secret not found" in str(exc_info.value)

    def test_list_secrets_returns_all_files(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that list_secrets returns all secret files."""
        (secrets_dir / "secret1").write_text("value1")
        (secrets_dir / "secret2").write_text("value2")
        (secrets_dir / "secret3").write_text("value3")

        secrets = secrets_manager.list_secrets()

        assert len(secrets) == 3
        assert "secret1" in secrets
        assert "secret2" in secrets
        assert "secret3" in secrets

    def test_list_secrets_returns_empty_for_missing_dir(self, tmp_path: Path) -> None:
        """Test that list_secrets returns empty list for missing directory."""
        secrets_dir = tmp_path / "nonexistent"
        secrets_manager = SecretsManager(secrets_dir)

        secrets = secrets_manager.list_secrets()

        assert secrets == []

    def test_list_secrets_ignores_subdirectories(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that list_secrets ignores subdirectories."""
        (secrets_dir / "secret1").write_text("value1")
        (secrets_dir / "subdir").mkdir()

        secrets = secrets_manager.list_secrets()

        assert len(secrets) == 1
        assert "secret1" in secrets
        assert "subdir" not in secrets


class TestPermissionValidation:
    """Test permission validation edge cases."""

    def test_permission_check_accepts_0600(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that 0600 permissions are accepted."""
        secret_file = secrets_dir / "valid-perms"
        secret_file.write_text("test_value")
        secret_file.chmod(0o600)

        # Should not raise
        value = secrets_manager.get_secret("valid-perms")
        assert value == "test_value"

    def test_permission_check_rejects_0400(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that 0400 (read-only) permissions are rejected."""
        secret_file = secrets_dir / "readonly"
        secret_file.write_text("test_value")
        secret_file.chmod(0o400)

        with pytest.raises(SecretsError) as exc_info:
            secrets_manager.get_secret("readonly")

        assert "Insecure permissions" in str(exc_info.value)

    def test_permission_check_rejects_0700(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that 0700 (executable) permissions are rejected."""
        secret_file = secrets_dir / "executable"
        secret_file.write_text("test_value")
        secret_file.chmod(0o700)

        with pytest.raises(SecretsError) as exc_info:
            secrets_manager.get_secret("executable")

        assert "Insecure permissions" in str(exc_info.value)


class TestErrorMessages:
    """Test error message quality."""

    def test_missing_secret_error_includes_creation_instructions(
        self, secrets_manager: SecretsManager
    ) -> None:
        """Test that missing secret error includes helpful instructions."""
        with pytest.raises(SecretsError) as exc_info:
            secrets_manager.get_secret("missing")

        error_msg = str(exc_info.value)
        assert "echo" in error_msg
        assert "chmod 600" in error_msg

    def test_empty_secret_error_includes_fix_instructions(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that empty secret error includes fix instructions."""
        secret_file = secrets_dir / "empty"
        secret_file.write_text("")
        secret_file.chmod(0o600)

        with pytest.raises(SecretsError) as exc_info:
            secrets_manager.get_secret("empty")

        error_msg = str(exc_info.value)
        assert "echo" in error_msg

    def test_permission_error_includes_chmod_command(
        self, secrets_manager: SecretsManager, secrets_dir: Path
    ) -> None:
        """Test that permission error includes chmod command."""
        secret_file = secrets_dir / "bad-perms"
        secret_file.write_text("test_value")
        secret_file.chmod(0o644)

        with pytest.raises(SecretsError) as exc_info:
            secrets_manager.get_secret("bad-perms")

        error_msg = str(exc_info.value)
        assert "chmod 600" in error_msg
        assert str(secret_file) in error_msg


class TestIntegration:
    """Integration tests for common workflows."""

    def test_full_secret_lifecycle(self, secrets_manager: SecretsManager) -> None:
        """Test complete secret lifecycle: create, read, update, delete."""
        # Create
        secrets_manager.set_secret("lifecycle-test", "initial_value")
        assert secrets_manager.secret_exists("lifecycle-test")

        # Read
        value = secrets_manager.get_secret("lifecycle-test")
        assert value == "initial_value"

        # Update
        secrets_manager.set_secret("lifecycle-test", "updated_value")
        value = secrets_manager.get_secret("lifecycle-test")
        assert value == "updated_value"

        # Delete
        secrets_manager.delete_secret("lifecycle-test")
        assert not secrets_manager.secret_exists("lifecycle-test")

    def test_multiple_secrets(self, secrets_manager: SecretsManager) -> None:
        """Test managing multiple secrets."""
        secrets_manager.set_secret("secret1", "value1")
        secrets_manager.set_secret("secret2", "value2")
        secrets_manager.set_secret("secret3", "value3")

        assert secrets_manager.get_secret("secret1") == "value1"
        assert secrets_manager.get_secret("secret2") == "value2"
        assert secrets_manager.get_secret("secret3") == "value3"

        secrets_list = secrets_manager.list_secrets()
        assert len(secrets_list) == 3
