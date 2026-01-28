#!/bin/bash
# Generate Complete Image Lists from All Sources
# shellcheck disable=SC2181,SC2155,SC2126
#
# Scans multiple sources for container images:
# 1. kubespray repository (https://github.com/kubernetes-sigs/kubespray)
# 2. kubespray-offline outputs (https://github.com/kubespray-offline/kubespray-offline)
# 3. opencenter-gitops-base (https://github.com/rackerlabs/openCenter-gitops-base)
# 4. genestack (https://github.com/rackerlabs/genestack)
#
# Outputs:
# - config/kubespray-offline-images.txt (from kubespray-offline outputs)
# - config/kubespray-images.txt (from kubespray repo scan)
# - config/opencenter-gitops-base-images.txt (from openCenter-gitops-base scan)
# - config/genestack-images.txt (from genestack scan)
# - config/all-images.txt (combined deduplicated list)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Repository paths
KUBESPRAY_REPO="${PROJECT_ROOT}/assets/kubespray/kubespray-master"
KUBESPRAY_OFFLINE="${PROJECT_ROOT}/build/kubespray-offline"
OPENCENTER_GITOPS_BASE="${PROJECT_ROOT}/assets/opencenter-gitops-base"
GENESTACK="${PROJECT_ROOT}/assets/genestack"
SCAN_OUTPUT="${PROJECT_ROOT}/build/repository-scans"

# Output files
KUBESPRAY_OFFLINE_OUTPUT="${PROJECT_ROOT}/config/kubespray-offline-images.txt"
KUBESPRAY_REPO_OUTPUT="${PROJECT_ROOT}/config/kubespray-images.txt"
OPENCENTER_GITOPS_BASE_OUTPUT="${PROJECT_ROOT}/config/opencenter-gitops-base-images.txt"
GENESTACK_OUTPUT="${PROJECT_ROOT}/config/genestack-images.txt"
COMBINED_OUTPUT="${PROJECT_ROOT}/config/all-images.txt"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $*"
}

check_prerequisites() {
    log_step "Checking prerequisites..."

    if ! command -v python3 &> /dev/null; then
        log_error "python3 not found"
        return 1
    fi

    if ! command -v git &> /dev/null; then
        log_error "git not found"
        return 1
    fi

    log_info "Prerequisites OK"
    return 0
}

clone_repositories() {
    log_step "Cloning missing repositories..."

    # Clone genestack if neither it nor opencenter-gitops-base exists
    if [ ! -d "$OPENCENTER_GITOPS_BASE" ] && [ ! -d "$GENESTACK" ]; then
        log_info "Cloning genestack (primary platform service repository)..."
        git clone --depth 1 https://github.com/rackerlabs/genestack.git "$GENESTACK"
        if [ $? -ne 0 ]; then
            log_error "Failed to clone genestack"
            return 1
        fi
        log_info "Cloned genestack successfully"
    fi

    # Clone kubespray if not exists
    if [ ! -d "$KUBESPRAY_REPO" ]; then
        log_info "Cloning kubespray repository..."
        mkdir -p "$(dirname "$KUBESPRAY_REPO")"
        git clone --depth 1 https://github.com/kubernetes-sigs/kubespray.git "$KUBESPRAY_REPO"
        if [ $? -ne 0 ]; then
            log_warn "Failed to clone kubespray, will skip kubespray scanning"
        else
            log_info "Cloned kubespray successfully"
        fi
    fi

    # Note: kubespray-offline is cloned by collect_kubespray_offline.sh
    if [ ! -d "$KUBESPRAY_OFFLINE" ]; then
        log_info "kubespray-offline will be cloned by collect_kubespray_offline.sh"
    fi

    return 0
}

scan_repositories() {
    log_step "Scanning repositories for images and URLs..."

    python3 "${SCRIPT_DIR}/scan_repository_images.py" \
        --project-root "$PROJECT_ROOT" \
        --output-dir "$SCAN_OUTPUT" \
        --verbose

    if [ $? -ne 0 ]; then
        log_error "Repository scan failed"
        return 1
    fi

    log_info "Repository scan complete"
    return 0
}

extract_kubespray_offline_images() {
    log_step "Extracting images from kubespray-offline outputs..."

    if [ ! -d "$KUBESPRAY_OFFLINE/outputs" ]; then
        log_warn "kubespray-offline outputs not found, skipping"
        return 0
    fi

    local temp_file=$(mktemp)

    # Extract from image lists in outputs
    find "$KUBESPRAY_OFFLINE/outputs" -name "*.txt" -o -name "images.list" | while read -r file; do
        if grep -qE '^[a-z0-9\.\-]+(/[a-z0-9\.\-]+)*:[a-z0-9\.\-]+$' "$file" 2>/dev/null; then
            cat "$file" >> "$temp_file"
        fi
    done

    # Deduplicate and sort
    if [ -s "$temp_file" ]; then
        cat > "$KUBESPRAY_OFFLINE_OUTPUT" << 'EOF'
# Kubespray-Offline Downloaded Images
# Source: https://github.com/kubespray-offline/kubespray-offline
# Extracted from kubespray-offline outputs directory after running download-all.sh

EOF
        sort -u "$temp_file" >> "$KUBESPRAY_OFFLINE_OUTPUT"
        local count=$(grep -v '^#' "$KUBESPRAY_OFFLINE_OUTPUT" | grep -v '^$' | wc -l)
        log_info "Extracted $count images from kubespray-offline"
    else
        log_warn "No images found in kubespray-offline outputs"
    fi

    rm -f "$temp_file"
    return 0
}

consolidate_kubespray_images() {
    log_step "Consolidating kubespray repository images..."

    local scan_file="${SCAN_OUTPUT}/kubespray-images.txt"

    if [ ! -f "$scan_file" ]; then
        log_warn "Kubespray scan results not found"
        return 0
    fi

    cat > "$KUBESPRAY_REPO_OUTPUT" << 'EOF'
# Kubespray Repository Images
# Source: https://github.com/kubernetes-sigs/kubespray
# Scanned from kubespray repository manifests and configuration files
# These are Kubernetes core and infrastructure images

EOF

    grep -v '^#' "$scan_file" | grep -v '^$' | sort -u >> "$KUBESPRAY_REPO_OUTPUT"

    local count=$(grep -v '^#' "$KUBESPRAY_REPO_OUTPUT" | grep -v '^$' | wc -l)
    log_info "Consolidated $count kubespray images"

    return 0
}

consolidate_opencenter_gitops_base_images() {
    log_step "Consolidating openCenter-gitops-base images..."

    local scan_file="${SCAN_OUTPUT}/opencenter-gitops-base-images.txt"

    if [ ! -f "$scan_file" ]; then
        log_warn "openCenter-gitops-base scan results not found"
        return 0
    fi

    cat > "$OPENCENTER_GITOPS_BASE_OUTPUT" << 'EOF'
# openCenter GitOps Base Images
# Source: https://github.com/rackerlabs/openCenter-gitops-base
# Scanned from openCenter-gitops-base repository
# These are openCenter platform service images

EOF

    grep -v '^#' "$scan_file" | grep -v '^$' | sort -u >> "$OPENCENTER_GITOPS_BASE_OUTPUT"

    local count=$(grep -v '^#' "$OPENCENTER_GITOPS_BASE_OUTPUT" | grep -v '^$' | wc -l)
    log_info "Consolidated $count openCenter-gitops-base images"

    return 0
}

consolidate_genestack_images() {
    log_step "Consolidating genestack images..."

    local scan_file="${SCAN_OUTPUT}/genestack-images.txt"

    if [ ! -f "$scan_file" ]; then
        log_warn "Genestack scan results not found"
        return 0
    fi

    cat > "$GENESTACK_OUTPUT" << 'EOF'
# Genestack Images
# Source: https://github.com/rackerlabs/genestack
# Scanned from genestack repository
# These are platform service images from genestack

EOF

    grep -v '^#' "$scan_file" | grep -v '^$' | sort -u >> "$GENESTACK_OUTPUT"

    local count=$(grep -v '^#' "$GENESTACK_OUTPUT" | grep -v '^$' | wc -l)
    log_info "Consolidated $count genestack images"

    return 0
}

generate_combined_list() {
    log_step "Generating combined image list..."

    local temp_file=$(mktemp)

    # Combine all sources
    for file in "$KUBESPRAY_OFFLINE_OUTPUT" "$KUBESPRAY_REPO_OUTPUT" "$OPENCENTER_GITOPS_BASE_OUTPUT" "$GENESTACK_OUTPUT"; do
        if [ -f "$file" ]; then
            grep -v '^#' "$file" | grep -v '^$' >> "$temp_file"
        fi
    done

    # Create combined output
    cat > "$COMBINED_OUTPUT" << 'EOF'
# Complete Image List for openCenter AirGap
# Combined from all sources:
# - kubespray-offline: https://github.com/kubespray-offline/kubespray-offline
# - kubespray: https://github.com/kubernetes-sigs/kubespray
# - openCenter-gitops-base: https://github.com/rackerlabs/openCenter-gitops-base
# - genestack: https://github.com/rackerlabs/genestack
#
# This is the master list for Zarf packaging

EOF

    sort -u "$temp_file" >> "$COMBINED_OUTPUT"

    local total=$(grep -v '^#' "$COMBINED_OUTPUT" | grep -v '^$' | wc -l)
    log_info "Combined list: $total unique images"

    rm -f "$temp_file"
    return 0
}

generate_summary() {
    log_step "Generating summary..."

    echo ""
    echo "=========================================="
    echo "Image List Generation Summary"
    echo "=========================================="
    echo ""

    if [ -f "$KUBESPRAY_OFFLINE_OUTPUT" ]; then
        local count=$(grep -v '^#' "$KUBESPRAY_OFFLINE_OUTPUT" | grep -v '^$' | wc -l)
        echo "kubespray-offline images: $count"
        echo "  File: $KUBESPRAY_OFFLINE_OUTPUT"
    fi

    if [ -f "$KUBESPRAY_REPO_OUTPUT" ]; then
        local count=$(grep -v '^#' "$KUBESPRAY_REPO_OUTPUT" | grep -v '^$' | wc -l)
        echo "kubespray repo images: $count"
        echo "  File: $KUBESPRAY_REPO_OUTPUT"
    fi

    if [ -f "$OPENCENTER_GITOPS_BASE_OUTPUT" ]; then
        local count=$(grep -v '^#' "$OPENCENTER_GITOPS_BASE_OUTPUT" | grep -v '^$' | wc -l)
        echo "openCenter-gitops-base images: $count"
        echo "  File: $OPENCENTER_GITOPS_BASE_OUTPUT"
    fi

    if [ -f "$GENESTACK_OUTPUT" ]; then
        local count=$(grep -v '^#' "$GENESTACK_OUTPUT" | grep -v '^$' | wc -l)
        echo "genestack images: $count"
        echo "  File: $GENESTACK_OUTPUT"
    fi

    if [ -f "$COMBINED_OUTPUT" ]; then
        local count=$(grep -v '^#' "$COMBINED_OUTPUT" | grep -v '^$' | wc -l)
        echo ""
        echo "Total unique images: $count"
        echo "  File: $COMBINED_OUTPUT"
    fi

    echo ""
    echo "Detailed scan results: $SCAN_OUTPUT"
    echo ""
}

main() {
    echo "=========================================="
    echo "Generate Image Lists from All Sources"
    echo "=========================================="
    echo ""

    if ! check_prerequisites; then
        log_error "Prerequisites check failed"
        exit 1
    fi

    echo ""

    if ! clone_repositories; then
        log_error "Failed to clone required repositories"
        exit 1
    fi

    echo ""

    if ! scan_repositories; then
        log_error "Repository scanning failed"
        exit 1
    fi

    echo ""

    extract_kubespray_offline_images

    echo ""

    consolidate_kubespray_images

    echo ""

    consolidate_opencenter_gitops_base_images

    echo ""

    consolidate_genestack_images

    echo ""

    generate_combined_list

    echo ""

    generate_summary

    log_info "Image list generation complete"
    echo ""
    echo "Next steps:"
    echo "  1. Review generated lists in config/"
    echo "  2. Update zarf.yaml with: scripts/build/generate_zarf_images_block.py"
    echo "  3. Build package: python3 scripts/build/build.py"
    echo ""
}

main "$@"
