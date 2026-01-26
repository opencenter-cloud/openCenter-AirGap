#!/bin/bash
# Validate version pinning across all configuration files
# Requirements: 10.10

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "==> Validating version pinning in configuration files"

# Activate Python venv if it exists
if [ -d "${PROJECT_ROOT}/venv" ]; then
    source "${PROJECT_ROOT}/venv/bin/activate"
fi

# Run validator on config directory
python3 "${SCRIPT_DIR}/version_validator.py" \
    --root-dir "${PROJECT_ROOT}/config" \
    --fail-on-violations

echo "==> Version pinning validation complete"
