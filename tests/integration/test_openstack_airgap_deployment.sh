#!/bin/bash
# tests/integration/test_openstack_airgap_deployment.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Configuration
export OS_AUTH_URL="${OS_AUTH_URL:-}"
export OS_PROJECT_NAME="${OS_PROJECT_NAME:-}"
export OS_USERNAME="${OS_USERNAME:-}"
export OS_PASSWORD="${OS_PASSWORD:-}"
export OS_REGION_NAME="${OS_REGION_NAME:-RegionOne}"
export OS_EXTERNAL_NETWORK="${OS_EXTERNAL_NETWORK:-public}"
export OS_SSH_KEY_NAME="${OS_SSH_KEY_NAME:-airgap-test-key}"
export AIRGAP_TEST_CLEANUP="${AIRGAP_TEST_CLEANUP:-true}"

# Validate prerequisites
if [[ -z "${OS_AUTH_URL}" || -z "${OS_PROJECT_NAME}" || -z "${OS_USERNAME}" || -z "${OS_PASSWORD}" ]]; then
    echo "Error: OpenStack credentials not set"
    echo "Required: OS_AUTH_URL, OS_PROJECT_NAME, OS_USERNAME, OS_PASSWORD"
    exit 1
fi

# Find Zarf package
PACKAGE_PATH="${1:-}"
if [[ -z "${PACKAGE_PATH}" ]]; then
    PACKAGE_PATH=$(find "${PROJECT_ROOT}/dist" -name "zarf-package-*.tar.zst" -type f | head -n1)
fi

if [[ ! -f "${PACKAGE_PATH}" ]]; then
    echo "Error: Zarf package not found"
    exit 1
fi

echo "Using package: ${PACKAGE_PATH}"

# Execute test
python3 "${SCRIPT_DIR}/test_airgap_deployment.py" "${PACKAGE_PATH}"
