#!/bin/bash
set -euo pipefail

# Collect kubespray-offline assets
# Clones/updates kubespray-offline repo and runs download-all.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Source version configuration
source "${PROJECT_ROOT}/config/versions.env"

# Directories
KUBESPRAY_OFFLINE_DIR="${PROJECT_ROOT}/build/kubespray-offline"
KUBESPRAY_OFFLINE_REPO="${KUBESPRAY_OFFLINE_REPO:-https://github.com/tmurakam/kubespray-offline.git}"
KUBESPRAY_OFFLINE_BRANCH="${KUBESPRAY_OFFLINE_BRANCH:-main}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check if step already completed (idempotency)
check_completion_marker() {
    local marker_file="${PROJECT_ROOT}/build/.completed/collect_kubespray_offline"
    
    if [ -f "${marker_file}" ]; then
        log_info "Step already completed (marker found: ${marker_file})"
        log_info "Skipping kubespray-offline collection"
        log_info "To force re-run, delete: ${marker_file}"
        return 0  # Already completed
    fi
    
    return 1  # Not completed
}

# Create completion marker
create_completion_marker() {
    local marker_dir="${PROJECT_ROOT}/build/.completed"
    local marker_file="${marker_dir}/collect_kubespray_offline"
    
    mkdir -p "${marker_dir}"
    date -Iseconds > "${marker_file}"
    
    log_info "Created completion marker: ${marker_file}"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v git &> /dev/null; then
        log_error "git is not installed"
        exit 1
    fi
    
    log_info "Prerequisites satisfied"
}

# Clone or update kubespray-offline repository
clone_or_update_repo() {
    log_info "Setting up kubespray-offline repository..."
    
    if [ -d "${KUBESPRAY_OFFLINE_DIR}/.git" ]; then
        log_info "Repository already exists, updating..."
        cd "${KUBESPRAY_OFFLINE_DIR}"
        
        # Fetch latest changes
        git fetch origin
        
        # Checkout specified branch
        git checkout "${KUBESPRAY_OFFLINE_BRANCH}"
        
        # Pull latest changes
        git pull origin "${KUBESPRAY_OFFLINE_BRANCH}"
        
        log_info "Repository updated to latest ${KUBESPRAY_OFFLINE_BRANCH}"
    else
        log_info "Cloning kubespray-offline repository..."
        
        # Create parent directory
        mkdir -p "$(dirname "${KUBESPRAY_OFFLINE_DIR}")"
        
        # Clone repository
        git clone -b "${KUBESPRAY_OFFLINE_BRANCH}" \
            "${KUBESPRAY_OFFLINE_REPO}" \
            "${KUBESPRAY_OFFLINE_DIR}"
        
        log_info "Repository cloned successfully"
    fi
    
    cd "${KUBESPRAY_OFFLINE_DIR}"
    COMMIT=$(git rev-parse --short HEAD)
    log_info "kubespray-offline: ${KUBESPRAY_OFFLINE_BRANCH} (${COMMIT})"
}

# Run download-all.sh
run_download_all() {
    log_info "Running kubespray-offline download-all.sh..."
    
    cd "${KUBESPRAY_OFFLINE_DIR}"
    
    if [ ! -f "download-all.sh" ]; then
        log_error "download-all.sh not found in ${KUBESPRAY_OFFLINE_DIR}"
        exit 1
    fi
    
    # Make script executable
    chmod +x download-all.sh
    
    # Run download script
    log_info "Starting asset download (this may take a while)..."
    
    if ./download-all.sh; then
        log_info "download-all.sh completed successfully"
    else
        log_error "download-all.sh failed with exit code $?"
        return 1
    fi
    
    # Verify outputs directory exists
    if [ ! -d "${KUBESPRAY_OFFLINE_DIR}/outputs" ]; then
        log_error "outputs directory not found after download"
        return 1
    fi
    
    log_info "Assets downloaded to: ${KUBESPRAY_OFFLINE_DIR}/outputs"
}

# Generate summary
generate_summary() {
    log_info "=== Collection Summary ==="
    
    if [ -d "${KUBESPRAY_OFFLINE_DIR}/outputs" ]; then
        # Count files
        if [ -d "${KUBESPRAY_OFFLINE_DIR}/outputs/files" ]; then
            FILE_COUNT=$(find "${KUBESPRAY_OFFLINE_DIR}/outputs/files" -type f | wc -l)
            log_info "Kubernetes binaries: ${FILE_COUNT} files"
        fi
        
        # Count images
        if [ -d "${KUBESPRAY_OFFLINE_DIR}/outputs/images" ]; then
            IMAGE_COUNT=$(find "${KUBESPRAY_OFFLINE_DIR}/outputs/images" -name "*.tar.gz" | wc -l)
            log_info "Container images: ${IMAGE_COUNT} tar.gz files"
        fi
        
        # Count debs
        if [ -d "${KUBESPRAY_OFFLINE_DIR}/outputs/debs" ]; then
            DEB_COUNT=$(find "${KUBESPRAY_OFFLINE_DIR}/outputs/debs" -name "*.deb" | wc -l)
            log_info "Debian packages: ${DEB_COUNT} .deb files"
        fi
        
        # Count Python wheels
        if [ -d "${KUBESPRAY_OFFLINE_DIR}/outputs/pypi" ]; then
            WHEEL_COUNT=$(find "${KUBESPRAY_OFFLINE_DIR}/outputs/pypi" -name "*.whl" | wc -l)
            log_info "Python wheels: ${WHEEL_COUNT} .whl files"
        fi
        
        # Total size
        TOTAL_SIZE=$(du -sh "${KUBESPRAY_OFFLINE_DIR}/outputs" 2>/dev/null | cut -f1)
        log_info "Total size: ${TOTAL_SIZE}"
    fi
}

# Generate provenance records for kubespray-offline artifacts
generate_provenance() {
    log_info "Generating provenance records for kubespray-offline artifacts..."

    # Use Python provenance reconstruction module
    if command -v python3 &> /dev/null; then
        python3 -c "
import sys
sys.path.insert(0, '${PROJECT_ROOT}/src')
from opencenter_build.provenance_kubespray import generate_kubespray_provenance
from opencenter_build.config import parse_versions_env
from pathlib import Path

versions_env = parse_versions_env(Path('${PROJECT_ROOT}/config/versions.env'))
output = generate_kubespray_provenance(
    kubespray_offline_dir=Path('${KUBESPRAY_OFFLINE_DIR}'),
    provenance_dir=Path('${PROJECT_ROOT}/build/provenance'),
    versions_env=versions_env,
)
print(f'Provenance written to: {output}')
" && log_info "Provenance generation complete" || log_warn "Provenance generation failed (non-fatal)"
    else
        log_warn "python3 not available, skipping provenance generation"
    fi
}

# Main execution
main() {
    log_info "Starting kubespray-offline collection..."
    
    # Check if already completed
    if check_completion_marker; then
        exit 0
    fi
    
    check_prerequisites
    clone_or_update_repo
    
    if run_download_all; then
        log_info "Asset download completed successfully"
    else
        log_error "Asset download failed"
        return 1
    fi
    
    generate_summary
    generate_provenance
    
    # Create completion marker on success
    create_completion_marker
    
    log_info "kubespray-offline collection complete!"
}

main "$@"
