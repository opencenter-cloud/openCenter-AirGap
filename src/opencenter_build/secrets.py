"""Secure secrets management with permission validation.

This module provides file-based secrets storage with strict permission
enforcement (0600) to prevent credential exposure in shell history or logs.
"""

from pathlib import Path

from opencenter_build.exceptions import SecretsError


class SecretsManager:
    """Manage secrets with security checks.

    Secrets are stored in individual files within a secrets directory.
    All secret files must have 0600 permissions (owner read/write only).

    Args:
        secrets_dir: Directory containing secret files

    Example:
        >>> secrets = SecretsManager(Path(".secrets"))
        >>> token = secrets.get_secret("github-token")
        >>> secrets.set_secret("api-key", "secret_value")
    """

    def __init__(self, secrets_dir: Path) -> None:
        """Initialize secrets manager.

        Args:
            secrets_dir: Path to directory containing secret files
        """
        self.secrets_dir = secrets_dir

    def _check_permissions(self, file_path: Path) -> None:
        """Verify file has secure permissions (0600).

        Args:
            file_path: Path to secret file

        Raises:
            SecretsError: If permissions are not 0600
        """
        if not file_path.exists():
            raise SecretsError(f"Secret file does not exist: {file_path}")

        stat_info = file_path.stat()
        mode = stat_info.st_mode & 0o777

        if mode != 0o600:
            raise SecretsError(
                f"Insecure permissions on {file_path}: {oct(mode)}\n"
                f"Secret files must be readable/writable by owner only.\n"
                f"Fix with: chmod 600 {file_path}"
            )

    def get_secret(self, secret_name: str) -> str:
        """Read secret from file with validation.

        Args:
            secret_name: Name of the secret file (without path)

        Returns:
            Secret value as string (stripped of whitespace)

        Raises:
            SecretsError: If secret file missing, has wrong permissions, or is empty

        Example:
            >>> secrets = SecretsManager(Path(".secrets"))
            >>> token = secrets.get_secret("github-token")
        """
        secret_file = self.secrets_dir / secret_name

        if not secret_file.exists():
            raise SecretsError(
                f"Secret not found: {secret_file}\n"
                f"Create the secret file:\n"
                f"  echo 'your_secret_value' > {secret_file}\n"
                f"  chmod 600 {secret_file}"
            )

        self._check_permissions(secret_file)

        secret = secret_file.read_text().strip()
        if not secret:
            raise SecretsError(
                f"Secret file is empty: {secret_file}\n"
                f"Add secret value:\n"
                f"  echo 'your_secret_value' > {secret_file}"
            )

        return secret

    def set_secret(self, secret_name: str, value: str) -> None:
        """Write secret to file with secure permissions.

        Creates the secrets directory if it doesn't exist (with 0700 permissions).
        Creates or overwrites the secret file with 0600 permissions.

        Args:
            secret_name: Name of the secret file (without path)
            value: Secret value to write

        Raises:
            SecretsError: If unable to create directory or write file

        Example:
            >>> secrets = SecretsManager(Path(".secrets"))
            >>> secrets.set_secret("github-token", "ghp_xxxxxxxxxxxx")
        """
        try:
            # Create secrets directory with restricted permissions
            self.secrets_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

            # Ensure directory has correct permissions even if it existed
            self.secrets_dir.chmod(0o700)

            secret_file = self.secrets_dir / secret_name

            # Write secret to file
            secret_file.write_text(value)

            # Set secure permissions on file
            secret_file.chmod(0o600)

        except OSError as e:
            raise SecretsError(f"Failed to write secret {secret_name}: {e}") from e

    def secret_exists(self, secret_name: str) -> bool:
        """Check if a secret file exists.

        Args:
            secret_name: Name of the secret file (without path)

        Returns:
            True if secret file exists, False otherwise
        """
        secret_file = self.secrets_dir / secret_name
        return secret_file.exists()

    def delete_secret(self, secret_name: str) -> None:
        """Delete a secret file.

        Args:
            secret_name: Name of the secret file (without path)

        Raises:
            SecretsError: If secret file doesn't exist or cannot be deleted
        """
        secret_file = self.secrets_dir / secret_name

        if not secret_file.exists():
            raise SecretsError(f"Secret not found: {secret_file}")

        try:
            secret_file.unlink()
        except OSError as e:
            raise SecretsError(f"Failed to delete secret {secret_name}: {e}") from e

    def list_secrets(self) -> list[str]:
        """List all secret files in the secrets directory.

        Returns:
            List of secret file names (without paths)
        """
        if not self.secrets_dir.exists():
            return []

        return [f.name for f in self.secrets_dir.iterdir() if f.is_file()]
