#!/bin/bash
set -euo pipefail

# Wrapper to run kubespray-offline download-all.sh from correct directory

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
KUBESPRAY_OFFLINE_DIR="${PROJECT_ROOT}/build/kubespray-offline"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Check completion marker
MARKER_FILE="${PROJECT_ROOT}/build/.completed/run_kubespray_offline"
if [ -f "${MARKER_FILE}" ]; then
    log_info "Step already completed (marker: ${MARKER_FILE})"
    log_info "To force re-run, delete: ${MARKER_FILE}"
    exit 0
fi

# Validate directory
if [ ! -d "${KUBESPRAY_OFFLINE_DIR}" ]; then
    log_error "kubespray-offline directory not found: ${KUBESPRAY_OFFLINE_DIR}"
    exit 1
fi

if [ ! -f "${KUBESPRAY_OFFLINE_DIR}/download-all.sh" ]; then
    log_error "download-all.sh not found in ${KUBESPRAY_OFFLINE_DIR}"
    exit 1
fi

# Change to kubespray-offline directory and run
log_info "Running kubespray-offline download-all.sh..."
cd "${KUBESPRAY_OFFLINE_DIR}"

if ./download-all.sh; then
    log_info "download-all.sh completed successfully"
    
    # Create completion marker
    mkdir -p "$(dirname "${MARKER_FILE}")"
    date -Iseconds > "${MARKER_FILE}"
    log_info "Created completion marker: ${MARKER_FILE}"
    
    exit 0
else
    EXIT_CODE=$?
    log_error "download-all.sh failed with exit code ${EXIT_CODE}"
    exit ${EXIT_CODE}
fi
