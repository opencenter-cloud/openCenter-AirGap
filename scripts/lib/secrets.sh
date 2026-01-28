#!/bin/bash
# Secrets management functions for bash scripts
#
# Provides file-based secrets with permission validation.
# All secret files must have 0600 permissions.

set -euo pipefail

# Get the project root directory
get_project_root() {
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    echo "$(cd "${script_dir}/../.." && pwd)"
}

PROJECT_ROOT="${PROJECT_ROOT:-$(get_project_root)}"
SECRETS_DIR="${SECRETS_DIR:-${PROJECT_ROOT}/.secrets}"

# Check if a secret file exists
#
# Args:
#   $1: Secret name (filename without path)
#
# Returns:
#   0 if secret exists, 1 otherwise
secret_exists() {
    local secret_name="$1"
    local secret_file="${SECRETS_DIR}/${secret_name}"

    [ -f "${secret_file}" ]
}

# Validate secret file permissions
#
# Args:
#   $1: Secret file path
#
# Returns:
#   0 if permissions are 0600, 1 otherwise
check_secret_permissions() {
    local secret_file="$1"

    if [ ! -f "${secret_file}" ]; then
        return 1
    fi

    # Get file permissions (works on Linux and macOS)
    local perms
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        perms=$(stat -f "%A" "${secret_file}")
    else
        # Linux
        perms=$(stat -c "%a" "${secret_file}")
    fi

    [ "${perms}" = "600" ]
}

# Get secret value from file
#
# Args:
#   $1: Secret name (filename without path)
#
# Returns:
#   Secret value (whitespace stripped)
#
# Exits:
#   1 if secret missing, has wrong permissions, or is empty
get_secret() {
    local secret_name="$1"
    local secret_file="${SECRETS_DIR}/${secret_name}"

    # Check if secret file exists
    if [ ! -f "${secret_file}" ]; then
        echo "Error: Secret not found: ${secret_file}" >&2
        echo "" >&2
        echo "Create the secret file:" >&2
        echo "  echo 'your_secret_value' > ${secret_file}" >&2
        echo "  chmod 600 ${secret_file}" >&2
        return 1
    fi

    # Check permissions
    if ! check_secret_permissions "${secret_file}"; then
        local perms
        if [[ "$OSTYPE" == "darwin"* ]]; then
            perms=$(stat -f "%A" "${secret_file}")
        else
            perms=$(stat -c "%a" "${secret_file}")
        fi

        echo "Error: Insecure permissions on ${secret_file}: ${perms}" >&2
        echo "Secret files must be readable/writable by owner only." >&2
        echo "" >&2
        echo "Fix with:" >&2
        echo "  chmod 600 ${secret_file}" >&2
        return 1
    fi

    # Read and validate secret
    local secret_value
    secret_value=$(cat "${secret_file}" | tr -d '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

    if [ -z "${secret_value}" ]; then
        echo "Error: Secret file is empty: ${secret_file}" >&2
        echo "" >&2
        echo "Add secret value:" >&2
        echo "  echo 'your_secret_value' > ${secret_file}" >&2
        return 1
    fi

    echo "${secret_value}"
}

# Set secret value to file
#
# Args:
#   $1: Secret name (filename without path)
#   $2: Secret value
#
# Returns:
#   0 on success, 1 on failure
set_secret() {
    local secret_name="$1"
    local secret_value="$2"
    local secret_file="${SECRETS_DIR}/${secret_name}"

    # Create secrets directory if it doesn't exist
    if [ ! -d "${SECRETS_DIR}" ]; then
        mkdir -p "${SECRETS_DIR}"
        chmod 700 "${SECRETS_DIR}"
    fi

    # Write secret to file
    echo "${secret_value}" > "${secret_file}"

    # Set secure permissions
    chmod 600 "${secret_file}"
}

# List all secrets in the secrets directory
#
# Returns:
#   List of secret filenames (one per line)
list_secrets() {
    if [ ! -d "${SECRETS_DIR}" ]; then
        return 0
    fi

    find "${SECRETS_DIR}" -maxdepth 1 -type f -exec basename {} \;
}

# Delete a secret file
#
# Args:
#   $1: Secret name (filename without path)
#
# Returns:
#   0 on success, 1 if secret doesn't exist
delete_secret() {
    local secret_name="$1"
    local secret_file="${SECRETS_DIR}/${secret_name}"

    if [ ! -f "${secret_file}" ]; then
        echo "Error: Secret not found: ${secret_file}" >&2
        return 1
    fi

    rm -f "${secret_file}"
}

# Check if GITHUB_TOKEN is available (file or env var)
# Prefers file-based secret, falls back to environment variable
#
# Returns:
#   GITHUB_TOKEN value
#
# Exits:
#   1 if token not available
get_github_token() {
    local token=""

    # Try file-based secret first
    if secret_exists "github-token"; then
        token=$(get_secret "github-token")
        if [ -n "${token}" ]; then
            echo "${token}"
            return 0
        fi
    fi

    # Fall back to environment variable (deprecated)
    if [ -n "${GITHUB_TOKEN:-}" ]; then
        echo "Warning: Using GITHUB_TOKEN from environment variable (deprecated)" >&2
        echo "Migrate to file-based secret:" >&2
        echo "  echo \"\$GITHUB_TOKEN\" > .secrets/github-token" >&2
        echo "  chmod 600 .secrets/github-token" >&2
        echo "  unset GITHUB_TOKEN" >&2
        echo "" >&2
        echo "${GITHUB_TOKEN}"
        return 0
    fi

    # No token available
    echo "Error: GitHub token not found" >&2
    echo "" >&2
    echo "Create file-based secret:" >&2
    echo "  echo 'ghp_xxxxxxxxxxxx' > .secrets/github-token" >&2
    echo "  chmod 600 .secrets/github-token" >&2
    echo "" >&2
    echo "Or set environment variable (deprecated):" >&2
    echo "  export GITHUB_TOKEN='ghp_xxxxxxxxxxxx'" >&2
    return 1
}
