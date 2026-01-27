#!/bin/bash
set -euo pipefail

# Inspect Zarf package and generate SBOM

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

# Find the package
DIST_DIR="${PROJECT_ROOT}/dist"
PACKAGE_FILE=$(find "${DIST_DIR}" -name "zarf-package-*.tar.zst" -type f | head -1)

if [ -z "${PACKAGE_FILE}" ]; then
    log_error "No Zarf package found in ${DIST_DIR}"
    exit 1
fi

log_info "Inspecting package: $(basename "${PACKAGE_FILE}")"

# Check if zarf is available
if ! command -v zarf &> /dev/null; then
    log_error "zarf CLI not found in PATH"
    exit 1
fi

# Inspect package definition
log_info "Inspecting package definition..."
if zarf package inspect "${PACKAGE_FILE}" --sbom-out="${DIST_DIR}/sbom"; then
    log_info "✓ Package inspection complete"
    log_info "  SBOM saved to: ${DIST_DIR}/sbom/"
else
    log_warn "Package inspection failed (non-fatal)"
fi

# List package contents
log_info "Package contents:"
zarf package inspect "${PACKAGE_FILE}" || log_warn "Could not list package contents"

# Package info
PACKAGE_SIZE=$(du -h "${PACKAGE_FILE}" | cut -f1)
log_info "Package size: ${PACKAGE_SIZE}"

log_info "Package inspection complete"
