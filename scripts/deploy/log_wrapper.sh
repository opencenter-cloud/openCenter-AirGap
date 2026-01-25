#!/bin/bash
# Wrapper script for logging command output
# Requirements 11.2, 11.3, 11.4: Log Terraform, Ansible, and Zarf output

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source logging module if not already sourced
if ! declare -f log_info > /dev/null 2>&1; then
    # shellcheck disable=SC1091
    source "${SCRIPT_DIR}/logging.sh"
fi

# Usage: log_wrapper.sh "description" command args...
if [ $# -lt 2 ]; then
    echo "Usage: $0 <description> <command> [args...]"
    exit 1
fi

DESCRIPTION="$1"
shift
COMMAND="$*"

# Use log_command from logging module
log_command "${DESCRIPTION}" "${COMMAND}"
