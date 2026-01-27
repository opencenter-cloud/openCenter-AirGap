#!/bin/bash
# Update openCenter Platform Service Image List
#
# Scans gitops-base assets and generates the complete image list
# for openCenter platform services (20+ services).
#
# This script should be run whenever gitops-base is updated or
# when preparing a new build.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
GENERATOR="${SCRIPT_DIR}/generate_opencenter_images.py"
GITOPS_BASE="${PROJECT_ROOT}/assets/gitops-base"
OUTPUT_FILE="${PROJECT_ROOT}/config/opencenter-images.txt"
KUBESPRAY_OFFLINE_IMAGES="${PROJECT_ROOT}/build/kubespray-offline/imagelists/additional_images.txt"

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

# Check prerequisites
if [ ! -d "$GITOPS_BASE" ]; then
    log_error "gitops-base not found at: $GITOPS_BASE"
    log_error "Please clone gitops-base to assets/gitops-base"
    exit 1
fi

if [ ! -f "$GENERATOR" ]; then
    log_error "Generator script not found: $GENERATOR"
    exit 1
fi

log_info "Generating openCenter platform service image list..."
echo ""

# Generate image list
if ! python3 "$GENERATOR" --gitops-base "$GITOPS_BASE" --output "$OUTPUT_FILE" --verbose; then
    log_error "Failed to generate image list"
    exit 1
fi

echo ""
log_info "Image list generated: $OUTPUT_FILE"

# Show summary
TOTAL_IMAGES=$(grep -c "^[^#]" "$OUTPUT_FILE" || echo "0")
log_info "Total images: $TOTAL_IMAGES"

# Copy to kubespray-offline if directory exists
if [ -d "$(dirname "$KUBESPRAY_OFFLINE_IMAGES")" ]; then
    log_info "Copying to kubespray-offline additional_images.txt..."
    cp "$OUTPUT_FILE" "$KUBESPRAY_OFFLINE_IMAGES"
    log_info "Updated: $KUBESPRAY_OFFLINE_IMAGES"
else
    log_warn "kubespray-offline directory not found, skipping copy"
    log_warn "Run this script again after kubespray-offline is set up"
fi

echo ""
log_info "Next steps:"
echo "  1. Review the generated image list: $OUTPUT_FILE"
echo "  2. Run build script: python3 scripts/build/build.py --clean"
echo "  3. kubespray-offline will download all images during build"
echo ""
