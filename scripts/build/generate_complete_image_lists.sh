#!/bin/bash
# Generate Complete Image Lists
#
# Creates two separate image lists:
# 1. opencenter-images.txt - openCenter platform services (20+ services)
# 2. kubespray-images.txt - Kubespray/Kubernetes core images
#
# This separation allows tracking which images are for platform vs infrastructure.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
GITOPS_BASE="${PROJECT_ROOT}/assets/opencenter-gitops-base"
KUBESPRAY_OFFLINE="${PROJECT_ROOT}/build/kubespray-offline"
OPENCENTER_OUTPUT="${PROJECT_ROOT}/config/opencenter-images.txt"
KUBESPRAY_OUTPUT="${PROJECT_ROOT}/config/kubespray-images.txt"
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

# Check prerequisites
check_prerequisites() {
    log_step "Checking prerequisites..."

    if [ ! -d "$GITOPS_BASE" ]; then
        log_error "opencenter-gitops-base not found at: $GITOPS_BASE"
        log_error "Please clone: git clone https://github.com/rackerlabs/genestack.git assets/opencenter-gitops-base"
        return 1
    fi

    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found"
        return 1
    fi

    log_info "Prerequisites OK"
    return 0
}

# Generate openCenter platform images
generate_opencenter_images() {
    log_step "Generating openCenter platform service images..."

    if [ ! -f "${SCRIPT_DIR}/generate_opencenter_images.py" ]; then
        log_error "Generator script not found: ${SCRIPT_DIR}/generate_opencenter_images.py"
        return 1
    fi

    python3 "${SCRIPT_DIR}/generate_opencenter_images.py" \
        --opencenter-gitops-base "$GITOPS_BASE" \
        --output "$OPENCENTER_OUTPUT" \
        --verbose

    if [ $? -eq 0 ]; then
        log_info "openCenter images: $OPENCENTER_OUTPUT"
        return 0
    else
        log_error "Failed to generate openCenter images"
        return 1
    fi
}

# Extract Kubespray images from kubespray-offline
generate_kubespray_images() {
    log_step "Generating Kubespray/Kubernetes core images..."

    # Create output file
    cat > "$KUBESPRAY_OUTPUT" << 'EOF'
# Kubespray and Kubernetes Core Images
# Generated from kubespray-offline image lists
# These are infrastructure images required for Kubernetes cluster

EOF

    # Check if kubespray-offline exists
    if [ ! -d "$KUBESPRAY_OFFLINE" ]; then
        log_warn "kubespray-offline not found at: $KUBESPRAY_OFFLINE"
        log_warn "Creating placeholder list with common Kubernetes images"

        cat >> "$KUBESPRAY_OUTPUT" << 'EOF'
# Kubernetes Control Plane
registry.k8s.io/kube-apiserver:v1.34.3
registry.k8s.io/kube-controller-manager:v1.34.3
registry.k8s.io/kube-scheduler:v1.34.3
registry.k8s.io/kube-proxy:v1.34.3
registry.k8s.io/pause:3.9
registry.k8s.io/coredns/coredns:v1.11.1
registry.k8s.io/etcd:3.5.10-0

# Calico CNI
docker.io/calico/cni:v3.27.0
docker.io/calico/node:v3.27.0
docker.io/calico/kube-controllers:v3.27.0

# DNS and Networking
registry.k8s.io/dns/k8s-dns-node-cache:1.22.28

# Metrics and Monitoring
registry.k8s.io/metrics-server/metrics-server:v0.7.0

# Ingress
registry.k8s.io/ingress-nginx/controller:v1.9.0
registry.k8s.io/ingress-nginx/kube-webhook-certgen:v20231011-8b53cabe0

# Note: Run kubespray-offline to get complete list
# This is a minimal placeholder list
EOF

        log_warn "Created placeholder kubespray-images.txt"
        log_warn "Run kubespray-offline to generate complete list"
        return 0
    fi

    # Extract from kubespray-offline image lists
    local imagelists_dir="${KUBESPRAY_OFFLINE}/imagelists"

    if [ -d "$imagelists_dir" ]; then
        log_info "Extracting images from kubespray-offline..."

        # Process images.txt (core Kubernetes images)
        if [ -f "${imagelists_dir}/images.txt" ]; then
            echo "# Core Kubernetes Images (from kubespray-offline)" >> "$KUBESPRAY_OUTPUT"
            grep -v "^#" "${imagelists_dir}/images.txt" | grep -v "^$" | sort -u >> "$KUBESPRAY_OUTPUT"
            echo "" >> "$KUBESPRAY_OUTPUT"
        fi

        # Process files.txt if it contains image references
        if [ -f "${imagelists_dir}/files.txt" ]; then
            log_info "Checking files.txt for image references..."
            # files.txt typically contains binaries, not images
        fi

        log_info "Kubespray images: $KUBESPRAY_OUTPUT"
    else
        log_warn "kubespray-offline imagelists not found"
        log_warn "Run: cd build/kubespray-offline && ./download-all.sh"
    fi

    return 0
}

# Generate combined list
generate_combined_list() {
    log_step "Generating combined image list..."

    cat > "$COMBINED_OUTPUT" << 'EOF'
# Complete Image List for openCenter AirGap
# This file combines all images from both Kubespray and openCenter platform
# Generated by: scripts/build/generate_complete_image_lists.sh

EOF

    # Add Kubespray images
    if [ -f "$KUBESPRAY_OUTPUT" ]; then
        echo "# ============================================================================" >> "$COMBINED_OUTPUT"
        echo "# KUBESPRAY AND KUBERNETES CORE IMAGES" >> "$COMBINED_OUTPUT"
        echo "# ============================================================================" >> "$COMBINED_OUTPUT"
        echo "" >> "$COMBINED_OUTPUT"
        cat "$KUBESPRAY_OUTPUT" >> "$COMBINED_OUTPUT"
        echo "" >> "$COMBINED_OUTPUT"
    fi

    # Add openCenter images
    if [ -f "$OPENCENTER_OUTPUT" ]; then
        echo "# ============================================================================" >> "$COMBINED_OUTPUT"
        echo "# OPENCENTER PLATFORM SERVICE IMAGES" >> "$COMBINED_OUTPUT"
        echo "# ============================================================================" >> "$COMBINED_OUTPUT"
        echo "" >> "$COMBINED_OUTPUT"
        cat "$OPENCENTER_OUTPUT" >> "$COMBINED_OUTPUT"
    fi

    log_info "Combined list: $COMBINED_OUTPUT"
}

# Generate statistics
generate_statistics() {
    log_step "Generating statistics..."
    echo ""

    if [ -f "$KUBESPRAY_OUTPUT" ]; then
        local kubespray_count=$(grep -v "^#" "$KUBESPRAY_OUTPUT" | grep -v "^$" | wc -l)
        log_info "Kubespray images: $kubespray_count"
    fi

    if [ -f "$OPENCENTER_OUTPUT" ]; then
        local opencenter_count=$(grep -v "^#" "$OPENCENTER_OUTPUT" | grep -v "^$" | wc -l)
        log_info "openCenter images: $opencenter_count"
    fi

    if [ -f "$COMBINED_OUTPUT" ]; then
        local total_count=$(grep -v "^#" "$COMBINED_OUTPUT" | grep -v "^$" | wc -l)
        log_info "Total images: $total_count"
    fi
}

# Copy to kubespray-offline if needed
copy_to_kubespray_offline() {
    log_step "Copying to kubespray-offline..."

    local additional_images="${KUBESPRAY_OFFLINE}/imagelists/additional_images.txt"

    if [ -d "$(dirname "$additional_images")" ]; then
        if [ -f "$OPENCENTER_OUTPUT" ]; then
            cp "$OPENCENTER_OUTPUT" "$additional_images"
            log_info "Copied to: $additional_images"
        fi
    else
        log_warn "kubespray-offline imagelists directory not found"
        log_warn "Skip copying to additional_images.txt"
    fi
}

# Main
main() {
    echo "=========================================="
    echo "Generate Complete Image Lists"
    echo "=========================================="
    echo ""

    # Check prerequisites
    if ! check_prerequisites; then
        exit 1
    fi

    echo ""

    # Generate openCenter images
    if ! generate_opencenter_images; then
        log_error "Failed to generate openCenter images"
        exit 1
    fi

    echo ""

    # Generate Kubespray images
    if ! generate_kubespray_images; then
        log_error "Failed to generate Kubespray images"
        exit 1
    fi

    echo ""

    # Generate combined list
    generate_combined_list

    echo ""

    # Generate statistics
    generate_statistics

    echo ""

    # Copy to kubespray-offline
    copy_to_kubespray_offline

    echo ""
    echo "=========================================="
    echo "Summary"
    echo "=========================================="
    echo ""
    echo "Generated files:"
    echo "  1. $OPENCENTER_OUTPUT"
    echo "  2. $KUBESPRAY_OUTPUT"
    echo "  3. $COMBINED_OUTPUT"
    echo ""
    echo "Next steps:"
    echo "  1. Review the generated lists"
    echo "  2. Run: python3 scripts/build/build.py --clean"
    echo "  3. kubespray-offline will download all images"
    echo ""

    log_info "Complete!"
}

# Run main
main
