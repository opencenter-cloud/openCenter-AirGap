#!/bin/bash
set -euo pipefail

# Merge openCenter platform service images with kubespray-offline additional_images.txt
# This script copies the curated openCenter image list to kubespray-offline before download

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Paths
OPENCENTER_IMAGES="${PROJECT_ROOT}/config/opencenter-images.txt"
KUBESPRAY_OFFLINE_DIR="${PROJECT_ROOT}/build/kubespray-offline"
ADDITIONAL_IMAGES="${KUBESPRAY_OFFLINE_DIR}/imagelists/additional_images.txt"

main() {
    log_info "Merging openCenter platform service images with kubespray-offline..."
    
    # Check if openCenter images list exists
    if [ ! -f "${OPENCENTER_IMAGES}" ]; then
        log_error "openCenter images list not found: ${OPENCENTER_IMAGES}"
        log_error "Run: python3 scripts/build/extract_opencenter_images.py"
        exit 1
    fi
    
    # Check if kubespray-offline directory exists
    if [ ! -d "${KUBESPRAY_OFFLINE_DIR}" ]; then
        log_error "kubespray-offline directory not found: ${KUBESPRAY_OFFLINE_DIR}"
        log_error "Clone kubespray-offline first"
        exit 1
    fi
    
    # Create imagelists directory if it doesn't exist
    mkdir -p "${KUBESPRAY_OFFLINE_DIR}/imagelists"
    
    # Backup existing additional_images.txt if it exists
    if [ -f "${ADDITIONAL_IMAGES}" ]; then
        BACKUP="${ADDITIONAL_IMAGES}.backup-$(date +%Y%m%d-%H%M%S)"
        log_info "Backing up existing additional_images.txt to: ${BACKUP}"
        cp "${ADDITIONAL_IMAGES}" "${BACKUP}"
    fi
    
    # Copy openCenter images to additional_images.txt
    log_info "Copying openCenter images to: ${ADDITIONAL_IMAGES}"
    cp "${OPENCENTER_IMAGES}" "${ADDITIONAL_IMAGES}"
    
    # Count images (excluding comments and empty lines)
    IMAGE_COUNT=$(grep -v "^#" "${ADDITIONAL_IMAGES}" | grep -v "^$" | wc -l)
    
    log_info "Merged ${IMAGE_COUNT} openCenter platform service images"
    log_info "kubespray-offline will download these images during asset collection"
    
    # Show summary
    echo ""
    log_info "Image categories:"
    grep "^# [A-Z]" "${ADDITIONAL_IMAGES}" | sed 's/^# */  - /' | sed 's/ (.*//' || true
    echo ""
    
    log_info "Next step: Run kubespray-offline download-all.sh"
}

main "$@"
